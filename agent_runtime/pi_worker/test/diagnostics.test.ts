import assert from "node:assert/strict";
import test from "node:test";
import { RequestDiagnostics } from "../src/diagnostics.ts";
import { createStreamObserver } from "../src/stream-observer.ts";
import { completeSummarization } from "../node_modules/@earendil-works/pi-coding-agent/dist/core/compaction/compaction.js";

for (const scenario of ["post-turn", "pre-prompt", "overflow", "aborted", "failed"] as const) {
  test(`compaction ${scenario} does not create a diagnostic request or intercept its fetch`, async () => {
    const events: any[] = [];
    const d = new RequestDiagnostics((event) => events.push(event), () => undefined);
    const handlers: Record<string, Function> = {};
    d.extension({ on: (name: string, handler: Function) => { handlers[name] = handler; } });
    d.begin("message", "stream");
    const model: any = { api: "openai-responses" };
    const message: any = { role: "assistant", content: [{ type: "text", text: "summary" }], stopReason: "stop" };
    const normalCall = () => {
      d.wrap(() => ({}))(model, {}, {});
      d.event({ type: "message_end", message: scenario === "overflow" && events.length === 1
        ? { ...message, stopReason: "error", errorMessage: "context overflow" } : message });
    };
    if (scenario === "post-turn" || scenario === "overflow") normalCall();
    const beforeCompaction = structuredClone(events);
    d.event({ type: "compaction_start", reason: scenario === "overflow" ? "overflow" : "threshold" });
    let receivedOptions: any;
    const fetcher = async () => { throw new Error("no real HTTP requests allowed"); };
    const summary = await completeSummarization(model, {} as any, { fetch: fetcher } as any,
      d.wrap((_model: any, _context: any, options: any) => {
        receivedOptions = options;
        handlers.before_provider_request({ payload: {} });
        handlers.after_provider_response({ status: 200 });
        return { result: async () => message };
      }));
    assert.equal(summary, message);
    assert.equal(receivedOptions.fetch, fetcher, "compaction must retain its original fetch");
    assert.deepEqual(events, beforeCompaction, "maintenance calls must not create or mutate diagnostics");
    d.event({ type: "compaction_end", aborted: scenario === "aborted",
      ...(scenario === "failed" ? { errorMessage: "summary failed" } : {}) });
    if (scenario !== "post-turn") normalCall();
    d.end();
    assert.deepEqual(events.map((event) => event.payload.phase), scenario === "overflow"
      ? ["preparing", "failed", "preparing", "completed"] : ["preparing", "completed"]);
  });
}

test("compaction hooks cannot mutate an unfinished row and a new prompt clears compaction state", () => {
  const events: any[] = [];
  const d = new RequestDiagnostics((event) => events.push(event), () => undefined);
  const handlers: Record<string, Function> = {};
  d.extension({ on: (name: string, handler: Function) => { handlers[name] = handler; } });
  const call = d.wrap(() => ({}));
  d.begin("first", "basic");
  call({}, {}, {});
  const beforeCompaction = structuredClone(events);
  d.event({ type: "compaction_start" });
  handlers.before_provider_request({ payload: {} });
  handlers.after_provider_response({ status: 200 });
  assert.deepEqual(events, beforeCompaction);
  d.end();
  d.begin("second", "basic");
  call({}, {}, {});
  handlers.before_provider_request({ payload: {} });
  d.event({ type: "message_end", message: { role: "assistant", stopReason: "stop" } });
  d.end();
  assert.deepEqual(events.filter((event) => event.payload.message_id === "second").map((event) => event.payload.phase),
    ["preparing", "waiting_response", "completed"]);
});

test("diagnostics observes stages without modifying payload, options or global fetch", async () => {
  const events: any[] = [];
  const d = new RequestDiagnostics((event) => events.push(event), () => undefined);
  const handlers: Record<string, Function> = {};
  d.extension({ on: (name: string, handler: Function) => { handlers[name] = handler; } });
  d.begin("message-1", "basic");
  const options = { signal: new AbortController().signal, temperature: 0.3 };
  const originalFetch = globalThis.fetch;
  const sentinel = {};
  const wrapped = d.wrap((_model: any, _context: any, received: any) => {
    assert.equal(received, options);
    return sentinel;
  });
  assert.equal(wrapped({ api: "openai-responses" }, {}, options), sentinel);
  assert.equal(handlers.before_provider_request({ payload: { secret: "do-not-log" } }), undefined);
  handlers.after_provider_response({ status: 200, headers: { secret: "do-not-log" } });
  d.event({ type: "message_update", assistantMessageEvent: { type: "text_delta", delta: "private text" } });
  for (let i = 0; i < 100; i++) d.event({ type: "message_update", assistantMessageEvent: { type: "text_delta", delta: "private text" } });
  d.event({ type: "message_end", message: { role: "assistant", stopReason: "stop" } });
  assert.deepEqual(events.map((e) => e.payload.phase), ["preparing", "waiting_response", "waiting_text", "receiving", "completed"]);
  assert.equal(new Set(events.map((e) => e.payload.request_id)).size, 1);
  assert.equal(events.at(-1).payload.http_status, 200);
  assert.equal(globalThis.fetch, originalFetch);
  assert.doesNotMatch(JSON.stringify(events), /private text|do-not-log/);
  handlers.before_provider_request({ payload: {} });
  handlers.after_provider_response({ status: 200 });
  assert.equal(events.length, 5, "out-of-band compaction hooks must not mutate a completed call");
});

test("oversized SSE frame cannot retain text or poison the next event", () => {
  const row: any = {};
  const observer = createStreamObserver(row, () => 1);
  observer.push(new TextEncoder().encode('data: ' + 'x'.repeat(1024 * 1024 + 100)));
  observer.push(new TextEncoder().encode('\n\ndata: {"type":"response.completed"}\n\n'));
  observer.end();
  assert.equal(row.observer_oversized_frame, true);
  assert.equal(row.raw_terminal, "response.completed");
  assert.ok(JSON.stringify(row).length < 1024);
});

test("network read failure remains the original error, diagnostic observer cannot swallow it", async () => {
  const events: any[] = [];
  const d = new RequestDiagnostics((event) => events.push(event), () => undefined);
  d.begin("m", "stream");
  const failure = new Error("network private error");
  const response = await d.wrap((_m: any, _c: any, options: any) => options.fetch("unused"))(
    { api: "openai-responses" }, {}, { fetch: async () => new Response(new ReadableStream({ pull(c) { c.error(failure); } })) },
  );
  await assert.rejects(response.body.getReader().read(), (error) => error === failure);
  d.event({ type: "message_end", message: { role: "assistant", stopReason: "error", errorMessage: failure.message } });
  assert.equal(events.at(-1).payload.error_category, "NETWORK_OR_STREAM_ERROR");
  assert.doesNotMatch(JSON.stringify(events), /private error/);
});

test("detailed fetch preserves bytes, signal, cancellation and does not eagerly drain", async () => {
  const events: any[] = [];
  const d = new RequestDiagnostics((event) => events.push(event), () => undefined);
  d.begin("m", "stream");
  const signal = new AbortController().signal;
  const bytes = new TextEncoder().encode('data: {"type":"response.output_text.delta","delta":"secret"}\n\ndata: {"type":"response.completed"}\n\n');
  let pulls = 0, cancelled: unknown;
  const upstream = new ReadableStream({ pull(c) { pulls++; c.enqueue(bytes); }, cancel(reason) { cancelled = reason; } }, { highWaterMark: 0 });
  const fetcher = async (_url: any, init: any) => {
    assert.equal(init.signal, signal);
    return new Response(upstream, { headers: { "content-type": "text/event-stream" } });
  };
  const response = await d.wrap((_m: any, _c: any, options: any) => options.fetch("unused", { signal }))(
    { api: "openai-responses" }, {}, { fetch: fetcher },
  );
  assert.equal(pulls, 0);
  const reader = response.body.getReader();
  assert.deepEqual((await reader.read()).value, bytes);
  await reader.cancel("user abort");
  assert.equal(cancelled, "user abort");
  d.event({ type: "message_end", message: { role: "assistant", stopReason: "aborted" } });
  const row = events.at(-1).payload;
  assert.equal(row.phase, "aborted");
  assert.equal(row.raw_terminal, "response.completed");
  assert.equal(row.raw_event_types['response.output_text.delta'].count, 1);
  assert.doesNotMatch(JSON.stringify(events), /secret/);
});

test("stream observer accepts every byte boundary, bounds unknown types and flags incomplete EOF", () => {
  const row: any = {};
  const observer = createStreamObserver(row, () => 42);
  const bytes = new TextEncoder().encode('data: {"type":"response.output_text.delta","delta":"你好 secret"}\r\n\r\ndata: {"type":"private-type-secret"}\n\ndata: nope\n\ndata: partial');
  for (const byte of bytes) observer.push(new Uint8Array([byte]));
  observer.end();
  assert.equal(row.raw_first_text_ms, 42);
  assert.equal(row.raw_event_types.other.count, 1);
  assert.equal(row.raw_invalid_json, 1);
  assert.equal(row.raw_incomplete_frame_at_eof, true);
  assert.doesNotMatch(JSON.stringify(row), /secret|你好|partial/);
});

test("retry events are safe and separate calls have separate ids, unsupported detail is explicit", () => {
  const events: any[] = [];
  const d = new RequestDiagnostics((event) => events.push(event), () => undefined);
  d.begin("m", "stream");
  const call = d.wrap(() => ({}));
  call({ api: "anthropic-messages" }, {}, {});
  d.event({ type: "message_end", message: { role: "assistant", stopReason: "error", errorMessage: "network secret" } });
  d.event({ type: "auto_retry_start", attempt: 1, maxAttempts: 2, delayMs: 2000, errorMessage: "secret" });
  call({ api: "anthropic-messages" }, {}, {});
  d.event({ type: "auto_retry_end", success: true, attempt: 1 });
  assert.equal(new Set(events.filter((e) => e.type === "request_diagnostic").map((e) => e.payload.request_id)).size, 2);
  assert.equal(events[0].payload.detail, "unsupported");
  assert.equal(events.find((e) => e.type === "agent_retry").payload.delay_ms, 2000);
  assert.doesNotMatch(JSON.stringify(events), /secret/);
});
