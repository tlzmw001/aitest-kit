// Observes SSE metadata only. Never retains or emits response text or arbitrary error strings.
const TYPES = new Set([
  "response.created", "response.in_progress", "response.queued",
  "response.output_item.added", "response.output_item.done",
  "response.content_part.added", "response.content_part.done",
  "response.output_text.delta", "response.output_text.done",
  "response.reasoning_summary_part.added", "response.reasoning_summary_part.done",
  "response.reasoning_summary_text.delta", "response.reasoning_summary_text.done",
  "response.reasoning_text.delta", "response.reasoning_text.done",
  "response.refusal.delta", "response.refusal.done",
  "response.function_call_arguments.delta", "response.function_call_arguments.done",
  "response.completed", "response.incomplete", "response.failed", "error",
]);
const MAX_FRAME = 1024 * 1024;

export function errorCategory(error: unknown): string {
  const text = String(error instanceof Error ? error.message : error ?? "").toLowerCase();
  if (/before a terminal response|without a stop reason/.test(text)) return "MISSING_TERMINAL_EVENT";
  if (/json|unexpected token/.test(text)) return "JSON_PARSE_ERROR";
  if (/abort/.test(text)) return "ABORTED";
  if (/timeout|timed out/.test(text)) return "TIMEOUT";
  if (/fetch failed|network|socket|terminated|connection|stream error/.test(text)) return "NETWORK_OR_STREAM_ERROR";
  if (/rate.limit|429/.test(text)) return "RATE_LIMIT";
  if (/401|403|unauthorized|authentication|api.key/.test(text)) return "AUTH_ERROR";
  return "UNCLASSIFIED_ERROR";
}

export function createStreamObserver(row: Record<string, any>, now: () => number) {
  const decoder = new TextDecoder();
  let buffer = "", data: string[] = [], eventName = "", frameSize = 0, dropped = false;
  row.raw_event_types ??= {};
  const dispatch = () => {
    const body = data.join("\n"), candidateName = eventName, skip = dropped;
    data = []; eventName = ""; frameSize = 0; dropped = false;
    if (skip || !body) return;
    if (body === "[DONE]") { row.raw_done_marker = true; return; }
    let item;
    try { item = JSON.parse(body); }
    catch { row.raw_invalid_json = (row.raw_invalid_json ?? 0) + 1; return; }
    const candidate = item?.type ?? candidateName;
    const type = TYPES.has(candidate) ? candidate : "other";
    const stamp = now();
    row.first_sse_event_ms ??= stamp;
    const stat = row.raw_event_types[type] ??= { count: 0, first_ms: stamp };
    stat.count++; stat.last_ms = stamp;
    if (type === "response.output_text.delta" && typeof item.delta === "string" && item.delta.trim()) row.raw_first_text_ms ??= stamp;
    if (["response.completed", "response.incomplete", "response.failed"].includes(type)) row.raw_terminal = type;
    if (type === "error" || type === "response.failed") {
      row.raw_error_category = errorCategory(item.error?.message ?? item.response?.error?.message);
    }
  };
  const line = (value: string) => {
    if (!value) { dispatch(); return; }
    if (value.startsWith("event:")) eventName = value.slice(6).trim().slice(0, 128);
    if (value.startsWith("data:") && !dropped) {
      const part = value.slice(5).replace(/^ /, ""); frameSize += part.length;
      if (frameSize > MAX_FRAME) { row.observer_oversized_frame = true; data = []; dropped = true; }
      else data.push(part);
    }
  };
  const drain = (final: boolean) => {
    while (true) {
      const index = buffer.search(/[\r\n]/);
      if (index < 0) break;
      if (!final && buffer[index] === "\r" && index === buffer.length - 1) break;
      const size = buffer[index] === "\r" && buffer[index + 1] === "\n" ? 2 : 1;
      const value = buffer.slice(0, index); buffer = buffer.slice(index + size); line(value);
    }
    if (buffer.length > MAX_FRAME) { buffer = ""; data = []; dropped = true; row.observer_oversized_frame = true; }
  };
  return {
    push(bytes: Uint8Array) {
      // Slice oversized transport chunks too, so the parser never duplicates an unbounded frame.
      for (let offset = 0; offset < bytes.length; offset += 8192) {
        buffer += decoder.decode(bytes.subarray(offset, offset + 8192), { stream: true }); drain(false);
      }
    },
    end() {
      buffer += decoder.decode(); drain(true); row.raw_eof_ms = now();
      if (buffer.length || data.length || dropped) row.raw_incomplete_frame_at_eof = true;
      buffer = ""; data = [];
    },
  };
}
