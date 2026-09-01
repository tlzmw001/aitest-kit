export const PROTOCOL_VERSION = 1;

const COMMAND_TYPES = new Set([
  "initialize",
  "prompt",
  "permission_decision",
  "abort",
  "shutdown",
]);

const SENSITIVE_KEYS = new Set([
  "api_key",
  "apikey",
  "authorization",
  "cookie",
  "password",
  "secret",
  "token",
]);
const SECRET_VALUES = new Set<string>();

export interface ProtocolMessage {
  protocol_version: number;
  id: string;
  type: string;
  payload: Record<string, unknown>;
}

export class ProtocolFailure extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message);
    this.name = "ProtocolFailure";
    this.code = code;
  }
}

export function parseCommand(line: string): ProtocolMessage {
  let value: unknown;
  try {
    value = JSON.parse(line);
  } catch {
    throw new ProtocolFailure("INVALID_JSON", "input line is not valid JSON");
  }
  if (!isRecord(value)) {
    throw new ProtocolFailure("INVALID_ENVELOPE", "protocol message must be a JSON object");
  }
  if (value.protocol_version !== PROTOCOL_VERSION) {
    throw new ProtocolFailure(
      "UNSUPPORTED_PROTOCOL_VERSION",
      `unsupported protocol version: ${String(value.protocol_version)}`,
    );
  }
  if (typeof value.id !== "string" || value.id.length === 0) {
    throw new ProtocolFailure("INVALID_ENVELOPE", "message id must be a non-empty string");
  }
  if (typeof value.type !== "string" || value.type.length === 0) {
    throw new ProtocolFailure("INVALID_ENVELOPE", "message type must be a non-empty string");
  }
  if (!COMMAND_TYPES.has(value.type)) {
    throw new ProtocolFailure("UNKNOWN_MESSAGE_TYPE", `unknown message type: ${value.type}`);
  }
  if (!isRecord(value.payload)) {
    throw new ProtocolFailure("INVALID_ENVELOPE", "message payload must be a JSON object");
  }
  return value as unknown as ProtocolMessage;
}

export function createMessage(
  id: string,
  type: string,
  payload: Record<string, unknown> = {},
): ProtocolMessage {
  return { protocol_version: PROTOCOL_VERSION, id, type, payload };
}

export function serializeMessage(message: ProtocolMessage): string {
  return JSON.stringify(redact(message));
}

export function registerSecret(value: string | undefined): void {
  if (value && value.length >= 4) SECRET_VALUES.add(value);
}

export function redact(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map((item) => redact(item));
  }
  if (isRecord(value)) {
    const result: Record<string, unknown> = {};
    for (const [key, child] of Object.entries(value)) {
      const normalized = key.toLowerCase().replaceAll("-", "_");
      result[key] = SENSITIVE_KEYS.has(normalized) ? "[REDACTED]" : redact(child);
    }
    return result;
  }
  if (typeof value === "string") {
    let rendered = value;
    for (const secret of SECRET_VALUES) {
      rendered = rendered.replaceAll(secret, "[REDACTED]");
    }
    return rendered
      .replace(/\bBearer\s+[^\s"']+/gi, "[REDACTED]")
      .replace(/\bsk-[A-Za-z0-9_-]{8,}/g, "[REDACTED]");
  }
  return value;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
