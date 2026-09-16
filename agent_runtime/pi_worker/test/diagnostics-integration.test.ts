import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { createServer, type ServerResponse } from "node:http";
import { once } from "node:events";
import test from "node:test";
import { PiSessionController } from "../src/session.ts";

function fixture(kind: "success" | "failed" | "truncated") {
  const message = { id: "msg_fixture", type: "message", role: "assistant", status: "completed", content: [{ type: "output_text", text: "fixture-private-text", annotations: [] }] };
  const events: any[] = [
    { type: "response.created", response: { id: "resp_fixture", status: "in_progress" } },
    { type: "response.output_item.added", output_index: 0, item: { ...message, content: [] } },
    { type: "response.output_text.delta", output_index: 0, content_index: 0, delta: "fixture-private-text" },
    { type: "response.output_item.done", output_index: 0, item: message },
    { type: "response.completed", response: { id: "resp_fixture", status: "completed", output: [message], usage: { input_tokens: 1, output_tokens: 1, total_tokens: 2 } } },
  ];
  if (kind === "failed") events.splice(1, events.length - 1, { type: "response.failed", response: { status: "failed", error: { code: "server_error", message: "server error fixture-private-error" } } });
  if (kind === "truncated") events.pop();
  return events.map((event) => `data: ${JSON.stringify(event)}\n\n`).join("");
}

async function setup(handler: (response: ServerResponse, count: number) => void, mode: "approval" | "full_trust" = "approval") {
  const cwd = await mkdtemp(join(tmpdir(), "aitest-diagnostic-sdk-"));
  const events: any[] = [], requests: any[] = [];
  const server = createServer(async (request, response) => {
    let body = "";
    for await (const chunk of request) body += chunk;
    requests.push(JSON.parse(body));
    handler(response, requests.length);
  });
  server.listen(0, "127.0.0.1");
  await once(server, "listening");
  const address = server.address();
  assert.ok(address && typeof address !== "string");
  process.env.AITEST_DIAGNOSTIC_FIXTURE_KEY = "not-a-real-key";
  const controller = await PiSessionController.create({
    cwd, permission_mode: mode, tools: [], skill_paths: [],
    model: { provider: "openai", name: "gpt-5.5", protocol: "openai_responses", base_url: `http://127.0.0.1:${address.port}`, api_key_env: "AITEST_DIAGNOSTIC_FIXTURE_KEY" },
  }, (event) => events.push(event), (message) => { throw new Error(message); });
  return { controller, events, requests, async close() {
    await controller.dispose();
    server.closeAllConnections();
    await new Promise<void>((resolve, reject) => server.close((error) => error ? reject(error) : resolve()));
    delete process.env.AITEST_DIAGNOSTIC_FIXTURE_KEY;
    await rm(cwd, { recursive: true, force: true });
  } };
}

for (const mode of ["approval", "full_trust"] as const) {
  test(`official SDK hooks + per-request fetch are wired, payload unchanged in ${mode}`, async () => {
    const run = await setup((response) => { response.writeHead(200, { "Content-Type": "text/event-stream" }); response.end(fixture("success")); }, mode);
    try {
      await run.controller.prompt("basic", "hello");
      await run.controller.prompt("detailed", "hello", "stream");
      const basic = run.events.filter((e) => e.type === "request_diagnostic" && e.id === "basic");
      const detail = run.events.filter((e) => e.type === "request_diagnostic" && e.id === "detailed");
      assert.deepEqual(basic.map((e) => e.payload.phase), ["preparing", "waiting_response", "waiting_text", "receiving", "completed"]);
      const row = detail.at(-1).payload;
      assert.equal(row.raw_terminal, "response.completed");
      assert.equal(row.http_attempts, 1);
      assert.ok(row.raw_first_text_ms <= row.first_text_ms);
      assert.equal(row.http_status, 200);
      assert.equal(run.events.filter((e) => e.type === "agent_finished").at(-1).payload.status, "succeeded");
      assert.doesNotMatch(JSON.stringify([...basic, ...detail]), /fixture-private|not-a-real-key/);
      assert.equal(run.requests[0].model, run.requests[1].model);
      assert.deepEqual(run.requests[0].tools, run.requests[1].tools);
      assert.equal(run.requests[0].stream, true);
    } finally { await run.close(); }
  });
}

test("official SDK retry remains enabled and is visible with per-call ids", async () => {
  const run = await setup((response, count) => {
    response.writeHead(200, { "Content-Type": "text/event-stream" });
    response.end(fixture(count === 1 ? "failed" : "success"));
  });
  try {
    await run.controller.prompt("retry", "hello", "stream");
    assert.equal(run.requests.length, 2);
    const retries = run.events.filter((e) => e.type === "agent_retry");
    assert.equal(retries[0].payload.phase, "start");
    assert.equal(retries.at(-1).payload.success, true);
    const completed = run.events.filter((e) => e.type === "request_diagnostic" && e.payload.complete_ms !== undefined);
    assert.equal(completed.length, 2);
    assert.notEqual(completed[0].payload.request_id, completed[1].payload.request_id);
    assert.equal(completed[0].payload.raw_terminal, "response.failed");
    assert.equal(completed[1].payload.phase, "completed");
    assert.doesNotMatch(JSON.stringify([...retries, ...completed]), /fixture-private/);
  } finally { await run.close(); }
});

test("truncated stream is classified without hiding SDK failure", async () => {
  const run = await setup((response) => {
    response.writeHead(200, { "Content-Type": "text/event-stream" }); response.end(fixture("truncated"));
  });
  try {
    await run.controller.prompt("truncated", "hello", "stream");
    const row = run.events.filter((e) => e.type === "request_diagnostic").at(-1).payload;
    assert.equal(row.phase, "failed");
    assert.equal(row.error_category, "MISSING_TERMINAL_EVENT");
    assert.equal(row.raw_missing_terminal, true);
    assert.equal(run.events.filter((e) => e.type === "agent_finished").at(-1).payload.status, "failed");
  } finally { await run.close(); }
});

test("waiting headers is observable before delayed body and user abort still settles", async () => {
  let signalHeaders!: () => void;
  const headersSeen = new Promise<void>((resolve) => { signalHeaders = resolve; });
  const run = await setup((response) => {
    response.writeHead(200, { "Content-Type": "text/event-stream" }); response.flushHeaders();
  });
  const internal = (run.controller as any).session;
  internal.subscribe((event: any) => { if (event.type === "message_update") signalHeaders(); });
  // Observe the output event without timing sleeps.
  const send = (run.controller as any).diagnostics.send;
  (run.controller as any).diagnostics.send = (event: any) => { send(event); if (event.payload.phase === "waiting_text") signalHeaders(); };
  try {
    const running = run.controller.prompt("abort", "hello", "stream");
    await headersSeen;
    assert.equal(run.events.some((e) => e.type === "text_delta"), false);
    await run.controller.abort(); await running;
    assert.equal(run.events.filter((e) => e.type === "request_diagnostic").at(-1).payload.phase, "aborted");
  } finally { await run.close(); }
});
