import { createMessage } from "./protocol.ts";
import { createStreamObserver, errorCategory } from "./stream-observer.ts";

type Row = Record<string, any>;
type StreamFunction = (...args: any[]) => any;

/** Optional observability only; no control over tools, approvals or retry policy. */
export class RequestDiagnostics {
  private send: (event: unknown) => void;
  private log: (message: string) => void;
  private messageId = "";
  private mode = "basic";
  private row: Row | null = null;
  private start = 0;
  private compacting = false;

  constructor(send: (event: unknown) => void, log: (message: string) => void) {
    this.send = send; this.log = log;
  }

  begin(messageId: string, mode: "basic" | "stream") {
    this.messageId = messageId; this.mode = mode; this.row = null; this.compacting = false;
  }

  end() {
    this.safe(() => {
      if (this.row && this.row.complete_ms === undefined) this.finish("failed", "UNCLASSIFIED_ERROR");
    });
    this.messageId = ""; this.row = null; this.compacting = false;
  }

  extension = (pi: any) => {
    pi.on("before_provider_request", () => {
      this.safe(() => {
        if (this.compacting || !this.row || this.row.complete_ms !== undefined) return;
        this.row.request_ms ??= this.elapsed(); this.phase("waiting_response");
      });
      // Deliberately return undefined: keep the exact provider payload.
    });
    pi.on("after_provider_response", (event: { status: number }) => {
      this.safe(() => this.headers(event.status));
    });
  };

  wrap(original: StreamFunction): StreamFunction {
    return (model, context, options) => {
      if (!this.messageId || this.compacting) return original(model, context, options);
      this.safe(() => {
        this.start = performance.now();
        this.row = {
          request_id: crypto.randomUUID(), message_id: this.messageId,
          started_at: new Date().toISOString(), phase_started_at: new Date().toISOString(),
          detail: this.mode === "basic" ? "off" : model.api === "openai-responses" ? "enabled" : "unsupported",
        };
        this.phase("preparing");
      });
      const row = this.row;
      const next = row?.detail === "enabled"
        ? { ...options, fetch: this.observeFetch(options?.fetch ?? globalThis.fetch, row, this.start) }
        : options;
      return original(model, context, next);
    };
  }

  event(event: Row) {
    this.safe(() => {
      // Pi summaries share streamFunction but are consumed outside the agent message lifecycle.
      if (event.type === "compaction_start") { this.compacting = true; return; }
      if (event.type === "compaction_end") { this.compacting = false; return; }
      if (!this.messageId) return;
      if (event.type === "auto_retry_start" || event.type === "auto_retry_end") {
        const payload: Row = { message_id: this.messageId, phase: event.type === "auto_retry_start" ? "start" : "end" };
        for (const [source, target] of [["attempt", "attempt"], ["maxAttempts", "max_attempts"], ["delayMs", "delay_ms"]]) {
          if (Number.isFinite(event[source])) payload[target] = Math.max(0, event[source]);
        }
        if (typeof event.success === "boolean") payload.success = event.success;
        if (event.errorMessage) payload.error_category = errorCategory(event.errorMessage);
        this.send(createMessage(this.messageId, "agent_retry", payload));
        return;
      }
      if (!this.row || this.row.complete_ms !== undefined) return;
      const update = event.assistantMessageEvent;
      if (event.type === "message_update" && update?.type === "text_delta" && String(update.delta ?? "").trim() && this.row.first_text_ms === undefined) {
        this.row.first_text_ms = this.elapsed(); this.phase("receiving");
      } else if (event.type === "message_update" && update?.type === "thinking_delta" && this.row.first_thinking_ms === undefined) {
        this.row.first_thinking_ms = this.elapsed();
        if (this.row.first_text_ms === undefined) this.phase("thinking");
      } else if (event.type === "message_end" && event.message?.role === "assistant") {
        const stop = event.message.stopReason;
        this.finish(stop === "aborted" ? "aborted" : stop === "error" ? "failed" : "completed",
          stop === "aborted" ? "ABORTED" : stop === "error" ? errorCategory(event.message.errorMessage) : undefined);
      }
    });
  }

  private elapsed() { return Math.round((performance.now() - this.start) * 10) / 10; }
  private phase(phase: string) {
    if (!this.row || this.row.phase === phase) return;
    this.row.phase = phase; this.row.phase_started_at = new Date().toISOString();
    this.row.elapsed_ms = this.elapsed();
    this.send(createMessage(this.messageId, "request_diagnostic", structuredClone(this.row)));
  }
  private headers(status: number) {
    if (this.compacting || !this.row || this.row.complete_ms !== undefined) return;
    this.row.headers_ms ??= this.elapsed(); this.row.http_status = status;
    this.phase("waiting_text");
  }
  private finish(phase: string, category?: string) {
    if (!this.row) return;
    this.row.complete_ms = this.elapsed();
    if (category) this.row.error_category = category;
    if (this.row.detail === "enabled" && this.row.raw_eof_ms !== undefined && !this.row.raw_terminal) {
      this.row.raw_missing_terminal = true;
    }
    this.phase(phase);
  }
  private safe(action: () => void) {
    try { action(); }
    catch { this.log("Agent diagnostics unavailable: OBSERVER_ERROR"); }
  }

  private observeFetch(fetcher: typeof fetch, row: Row, start: number): typeof fetch {
    return async (input, init) => {
      const now = () => Math.round((performance.now() - start) * 10) / 10;
      row.http_attempts = (row.http_attempts ?? 0) + 1;
      const response = await fetcher(input, init);
      this.safe(() => { if (this.row === row) this.headers(response.status); });
      if (!response.body) return response;
      const observer = createStreamObserver(row, now);
      const reader = response.body.getReader();
      const body = new ReadableStream<Uint8Array>({
        pull: async (controller) => {
          try {
            const { done, value } = await reader.read();
            if (done) { this.safe(() => observer.end()); controller.close(); reader.releaseLock(); }
            else {
              this.safe(() => { row.first_byte_ms ??= now(); observer.push(value); });
              controller.enqueue(value);
            }
          } catch (error) { controller.error(error); reader.releaseLock(); }
        },
        cancel: async (reason) => { try { await reader.cancel(reason); } finally { reader.releaseLock(); } },
      }, { highWaterMark: 0 });
      const observed = new Response(body, { status: response.status, statusText: response.statusText, headers: response.headers });
      // Preserve metadata used by HTTP SDK errors without exposing it in diagnostics.
      for (const key of ["url", "redirected", "type"] as const) Object.defineProperty(observed, key, { value: response[key] });
      return observed;
    };
  }
}
