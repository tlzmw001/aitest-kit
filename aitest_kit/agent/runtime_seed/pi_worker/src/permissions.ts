import { mkdir, writeFile } from "node:fs/promises";
import { join } from "node:path";

import { createMessage, redact } from "./protocol.ts";


export type PermissionMode = "approval" | "full_trust";
export type PermissionDecision = "allow_once" | "allow_session" | "deny";

interface PermissionConfig {
  debugLog: boolean;
  permissionReviewLog: boolean;
  yoloMode: boolean;
  doublePressToConfirm: boolean;
  authorizerChain: string[];
  permission: Record<string, unknown>;
}

interface PermissionPrompt {
  requestId?: unknown;
  source?: unknown;
  surface?: unknown;
  value?: unknown;
  agentName?: unknown;
  request?: unknown;
  forwarding?: unknown;
}

interface PendingApproval {
  requestId: string;
  options: string[];
  resolve: (selected: string | undefined) => void;
  timer: ReturnType<typeof setTimeout>;
}

type EventSink = (message: unknown) => void;


export function createPermissionConfig(mode: PermissionMode): PermissionConfig {
  if (mode === "full_trust") {
    return {
      debugLog: false,
      permissionReviewLog: true,
      yoloMode: false,
      doublePressToConfirm: false,
      authorizerChain: [],
      permission: {
        "*": "allow",
        path: "allow",
        external_directory: "allow",
      },
    };
  }
  return {
    debugLog: false,
    permissionReviewLog: true,
    yoloMode: false,
    doublePressToConfirm: false,
    authorizerChain: [],
    permission: {
      "*": "ask",
      read: "allow",
      // Native grep authorizes the root, not each recursively searched file.
      grep: "ask",
      find: "allow",
      ls: "allow",
      write: "ask",
      edit: "ask",
      bash: "ask",
      skill: "allow",
      external_directory: "ask",
      path: {
        "*": "allow",
        ".env": "deny",
        "*.env": "deny",
        "*.env.*": "deny",
        "**/.env": "deny",
        "**/.env.*": "deny",
        "*.pem": "deny",
        "*.key": "deny",
      },
    },
  };
}

export async function writePermissionConfig(agentDir: string, mode: PermissionMode): Promise<void> {
  const configDir = join(agentDir, "extensions", "pi-permission-system");
  await mkdir(configDir, { recursive: true, mode: 0o700 });
  await writeFile(
    join(configDir, "config.json"),
    `${JSON.stringify(createPermissionConfig(mode), null, 2)}\n`,
    { encoding: "utf8", mode: 0o600 },
  );
}

export class ApprovalBridge {
  private promptQueue: PermissionPrompt[] = [];
  private pending = new Map<string, PendingApproval>();
  private send: EventSink;
  private timeoutMs: number;

  constructor(send: EventSink, timeoutMs = 300_000) {
    this.send = send;
    this.timeoutMs = timeoutMs;
  }

  observePrompt(raw: unknown): void {
    if (typeof raw === "object" && raw !== null) {
      this.promptQueue.push(raw as PermissionPrompt);
    }
  }

  async select(title: string, options: string[]): Promise<string | undefined> {
    const prompt = this.promptQueue.shift() ?? {};
    const requestId = typeof prompt.requestId === "string"
      ? prompt.requestId
      : `permission-${crypto.randomUUID()}`;
    const request = isRecord(prompt.request) ? prompt.request : {};
    const surface = stringOrNull(prompt.surface) ?? stringOrNull(request.surface);
    const value = stringOrNull(prompt.value) ?? stringOrNull(request.value);
    const toolName = stringOrNull(request.toolName)
      ?? stringOrNull(request.invokedToolName)
      ?? (surface && ["read", "write", "edit", "grep", "find", "ls", "bash"].includes(surface) ? surface : null);
    const command = surface === "bash" ? value : null;
    this.send(createMessage(requestId, "permission_requested", redact({
      request_id: requestId,
      source: stringOrNull(prompt.source),
      tool_name: toolName,
      surface,
      target: surface === "bash" ? null : value,
      command,
      summary: safeSummary(title),
      agent_name: stringOrNull(prompt.agentName),
      forwarding: prompt.forwarding ?? null,
    }) as Record<string, unknown>));

    return new Promise((resolve) => {
      const timer = setTimeout(() => {
        this.pending.delete(requestId);
        resolve(denyOption(options));
      }, this.timeoutMs);
      this.pending.set(requestId, { requestId, options: [...options], resolve, timer });
    });
  }

  resolve(requestId: string, decision: PermissionDecision): boolean {
    const pending = this.pending.get(requestId);
    if (!pending) return false;
    this.pending.delete(requestId);
    clearTimeout(pending.timer);
    let selected = denyOption(pending.options);
    if (decision === "allow_once") selected = pending.options[0];
    if (decision === "allow_session") selected = pending.options[1] ?? pending.options[0];
    pending.resolve(selected);
    return true;
  }

  denyAll(): void {
    for (const pending of this.pending.values()) {
      clearTimeout(pending.timer);
      pending.resolve(denyOption(pending.options));
    }
    this.pending.clear();
  }

  createUiContext(log: (message: string) => void): Record<string, unknown> {
    return {
      select: (title: string, options: string[]) => this.select(title, options),
      confirm: async () => false,
      input: async () => undefined,
      notify: (message: string) => log(message),
      onTerminalInput: () => () => undefined,
      setStatus: () => undefined,
      setWorkingMessage: () => undefined,
      setWorkingVisible: () => undefined,
      setWorkingIndicator: () => undefined,
      setHiddenThinkingLabel: () => undefined,
      setWidget: () => undefined,
      setFooter: () => undefined,
      setHeader: () => undefined,
      setTitle: () => undefined,
      custom: async () => { throw new Error("custom TUI is unavailable in RPC mode"); },
      pasteToEditor: () => undefined,
      setEditorText: () => undefined,
      getEditorText: () => "",
      editor: async () => undefined,
      addAutocompleteProvider: () => undefined,
      setEditorComponent: () => undefined,
      getToolsExpanded: () => false,
      setToolsExpanded: () => undefined,
    };
  }
}

function denyOption(options: string[]): string | undefined {
  return options.find((option) => /^No\b/i.test(option)) ?? options.at(-1);
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function safeSummary(value: string): string {
  const safe = String(redact(value));
  return safe.length > 2000 ? `${safe.slice(0, 2000)}…` : safe;
}
