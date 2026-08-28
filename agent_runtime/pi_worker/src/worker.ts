import { createInterface } from "node:readline";

import { type PermissionDecision } from "./permissions.ts";
import { createMessage, isRecord, parseCommand, ProtocolFailure, redact, registerSecret, serializeMessage } from "./protocol.ts";
import { type InitializePayload, PiSessionController } from "./session.ts";


let controller: PiSessionController | null = null;
let initialized = false;
let shuttingDown = false;

const originalError = console.error.bind(console);
for (const method of ["log", "info", "debug"] as const) {
  console[method] = (...args: unknown[]) => originalError(...args.map((arg) => redact(arg)));
}
console.warn = (...args: unknown[]) => originalError(...args.map((arg) => redact(arg)));

function emit(message: unknown): void {
  process.stdout.write(`${serializeMessage(message as any)}\n`);
}

function log(message: string): void {
  originalError(String(redact(message)));
}

async function handleLine(line: string): Promise<void> {
  let command;
  try {
    command = parseCommand(line);
  } catch (error) {
    const failure = error instanceof ProtocolFailure
      ? error
      : new ProtocolFailure("INVALID_COMMAND", error instanceof Error ? error.message : String(error));
    emit(createMessage("unattributed", "error", { code: failure.code, message: failure.message }));
    return;
  }

  try {
    if (command.type === "initialize") {
      if (initialized) throw new ProtocolFailure("ALREADY_INITIALIZED", "worker is already initialized");
      const model = isRecord(command.payload.model) ? command.payload.model : {};
      if (typeof model.api_key_env === "string") {
        registerSecret(process.env[model.api_key_env]);
      }
      controller = await PiSessionController.create(command.payload as unknown as InitializePayload, emit, log);
      initialized = true;
      emit(createMessage(command.id, "ready", {
        runtime: "pi",
        protocol_version: 1,
        session_id: controller.sessionId,
      }));
      return;
    }
    if (!controller || !initialized) {
      throw new ProtocolFailure("NOT_INITIALIZED", "initialize must be sent first");
    }
    if (command.type === "prompt") {
      const text = command.payload.text;
      if (typeof text !== "string" || text.length === 0) {
        throw new ProtocolFailure("INVALID_PROMPT", "prompt.text must be a non-empty string");
      }
      void controller.prompt(command.id, text).catch((error) => emitError(command.id, "PROMPT_FAILED", error));
      return;
    }
    if (command.type === "permission_decision") {
      const requestId = command.payload.request_id;
      const decision = command.payload.decision;
      if (
        typeof requestId !== "string"
        || !["allow_once", "allow_session", "deny"].includes(String(decision))
      ) {
        throw new ProtocolFailure("INVALID_PERMISSION_DECISION", "permission decision payload is invalid");
      }
      if (!controller.resolvePermission(requestId, decision as PermissionDecision)) {
        throw new ProtocolFailure("UNKNOWN_PERMISSION_REQUEST", `permission request is not pending: ${requestId}`);
      }
      return;
    }
    if (command.type === "abort") {
      await controller.abort();
      emit(createMessage(command.id, "aborted"));
      return;
    }
    if (command.type === "shutdown") {
      shuttingDown = true;
      await controller.abort();
      await controller.dispose();
      controller = null;
      emit(createMessage(command.id, "shutdown_complete"));
      reader.close();
      process.stdin.pause();
      setImmediate(() => process.exit(0));
      return;
    }
  } catch (error) {
    const code = error instanceof ProtocolFailure ? error.code : "COMMAND_FAILED";
    emitError(command.id, code, error);
  }
}

function emitError(id: string, code: string, error: unknown): void {
  const message = error instanceof Error ? error.message : String(error);
  emit(createMessage(id, "error", { code, message: String(redact(message)) }));
}

const reader = createInterface({ input: process.stdin, crlfDelay: Infinity });
reader.on("line", (line) => {
  if (!shuttingDown) void handleLine(line);
});
reader.on("close", () => {
  if (controller) {
    void controller.dispose().finally(() => {
      controller = null;
    });
  }
});

process.on("SIGTERM", () => {
  shuttingDown = true;
  if (controller) {
    void controller.abort().finally(() => controller?.dispose()).finally(() => process.exit(143));
  } else {
    process.exit(143);
  }
});

process.on("uncaughtException", (error) => {
  emitError("unattributed", "UNCAUGHT_EXCEPTION", error);
  process.exitCode = 1;
});

process.on("unhandledRejection", (error) => {
  emitError("unattributed", "UNHANDLED_REJECTION", error);
  process.exitCode = 1;
});
