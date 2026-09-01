import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import {
  createAgentSession,
  createEventBus,
  DefaultResourceLoader,
  ModelRuntime,
  SessionManager,
  SettingsManager,
} from "@earendil-works/pi-coding-agent";

import { ApprovalBridge, type PermissionDecision, type PermissionMode, writePermissionConfig } from "./permissions.ts";
import { createMessage, redact } from "./protocol.ts";


const AGENT_TOOL_NAMES = ["read", "write", "edit", "grep", "find", "ls", "bash"] as const;
const MAX_EVENT_VALUE_BYTES = 64 * 1024;
type AgentToolName = typeof AGENT_TOOL_NAMES[number];

export interface InitializePayload {
  cwd: string;
  model: {
    provider: string;
    name: string;
    protocol?: "auto" | "openai_responses" | "openai_chat_completions" | "anthropic_messages";
    api_key_env: string;
    base_url?: string | null;
    base_url_env?: string | null;
  };
  skill_paths?: string[];
  tools?: AgentToolName[];
  permission_mode: PermissionMode;
  approval_timeout_ms?: number;
}

interface NormalizedEvent {
  type: string;
  payload: Record<string, unknown>;
}

type EventSink = (message: unknown) => void;


export function mapSessionEvent(
  event: Record<string, any>,
  settledStatus: "succeeded" | "failed" | "aborted" = "succeeded",
): NormalizedEvent | null {
  if (event.type === "message_update" && event.assistantMessageEvent?.type === "text_delta") {
    return { type: "text_delta", payload: { delta: String(event.assistantMessageEvent.delta ?? "") } };
  }
  if (event.type === "tool_execution_start") {
    return {
      type: "tool_call_requested",
      payload: {
        tool_call_id: String(event.toolCallId),
        tool_name: String(event.toolName),
        input: summarizeToolInput(String(event.toolName), event.args),
      },
    };
  }
  if (event.type === "tool_execution_update") {
    return {
      type: "tool_call_updated",
      payload: {
        tool_call_id: String(event.toolCallId),
        tool_name: String(event.toolName),
        partial_result: boundedEventValue(event.partialResult),
      },
    };
  }
  if (event.type === "tool_execution_end") {
    return {
      type: "tool_call_finished",
      payload: {
        tool_call_id: String(event.toolCallId),
        tool_name: String(event.toolName),
        is_error: Boolean(event.isError),
        result: boundedEventValue(event.result),
      },
    };
  }
  if (event.type === "agent_settled") {
    return { type: "agent_finished", payload: { status: settledStatus } };
  }
  return null;
}

export class PiSessionController {
  private agentDir: string;
  private session: any;
  private bridge: ApprovalBridge;
  private send: EventSink;
  private previousAgentDirEnv: string | undefined;
  private unsubscribe: (() => void) | undefined;
  private activeMessageId: string | null = null;
  private sessionAnnounced = false;
  private finishStatus: "succeeded" | "failed" | "aborted" = "succeeded";

  private constructor(
    agentDir: string,
    session: any,
    bridge: ApprovalBridge,
    send: EventSink,
    previousAgentDirEnv: string | undefined,
  ) {
    this.agentDir = agentDir;
    this.session = session;
    this.bridge = bridge;
    this.send = send;
    this.previousAgentDirEnv = previousAgentDirEnv;
  }

  static async create(payload: InitializePayload, send: EventSink, log: (message: string) => void): Promise<PiSessionController> {
    validateInitializePayload(payload);
    const agentDir = await mkdtemp(join(tmpdir(), "aitest-pi-agent-"));
    const previousAgentDirEnv = process.env.PI_CODING_AGENT_DIR;
    process.env.PI_CODING_AGENT_DIR = agentDir;
    try {
      await writePermissionConfig(agentDir, payload.permission_mode);
      const eventBus = createEventBus();
      const bridge = new ApprovalBridge(send, payload.approval_timeout_ms ?? 300_000);
      eventBus.on("permissions:ui_prompt", (event) => bridge.observePrompt(event));
      eventBus.on("permissions:decision", (event) => {
        const value = isRecord(event) ? event : {};
        const requestId = typeof value.requestId === "string" ? value.requestId : crypto.randomUUID();
        send(createMessage(requestId, "permission_resolved", redact({
          request_id: value.requestId,
          surface: value.surface,
          target: value.value,
          decision: value.result,
          resolution: value.resolution,
          matched_pattern: value.matchedPattern,
        }) as Record<string, unknown>));
      });

      const permissionExtensionPath = permissionSystemExtensionPath();
      const settingsManager = SettingsManager.inMemory(
        {
          defaultProjectTrust: "never",
          retry: { enabled: true, maxRetries: 2 },
        },
        { projectTrusted: false },
      );
      const resourceLoader = new DefaultResourceLoader({
        cwd: payload.cwd,
        agentDir,
        settingsManager,
        eventBus,
        additionalExtensionPaths: [permissionExtensionPath],
        additionalSkillPaths: payload.skill_paths ?? [],
        noExtensions: true,
        noSkills: true,
        noPromptTemplates: true,
        noThemes: true,
      });
      await resourceLoader.reload();
      const extensionErrors = resourceLoader.getExtensions().errors;
      if (extensionErrors.length > 0) {
        throw new Error(`permission extension failed to load: ${extensionErrors.map((item: any) => item.error).join("; ")}`);
      }
      const modelRuntime = await ModelRuntime.create({
        authPath: join(agentDir, "auth.json"),
        modelsPath: null,
        refreshOnCreate: false,
      });
      const apiKey = process.env[payload.model.api_key_env];
      if (!apiKey) {
        throw new Error(`required API key environment variable is not set: ${payload.model.api_key_env}`);
      }
      const baseUrl = resolveBaseUrl(payload.model);
      const model = await configureRuntimeModel(modelRuntime, payload.model, apiKey, baseUrl);
      if (!model) {
        throw new Error(`unknown Pi model: ${payload.model.provider}/${payload.model.name}`);
      }
      const { session } = await createAgentSession({
        cwd: payload.cwd,
        agentDir,
        model,
        modelRuntime,
        resourceLoader,
        sessionManager: SessionManager.inMemory(payload.cwd),
        settingsManager,
        tools: payload.tools ?? [...AGENT_TOOL_NAMES],
      });
      await session.bindExtensions({
        uiContext: bridge.createUiContext(log) as any,
        mode: "rpc",
      });
      const controller = new PiSessionController(agentDir, session, bridge, send, previousAgentDirEnv);
      controller.unsubscribe = session.subscribe((event: Record<string, unknown>) => controller.handleSessionEvent(event));
      return controller;
    } catch (error) {
      restoreAgentDirEnvironment(previousAgentDirEnv);
      await rm(agentDir, { recursive: true, force: true });
      throw error;
    }
  }

  get sessionId(): string {
    return String(this.session.sessionId);
  }

  async prompt(messageId: string, text: string): Promise<void> {
    if (this.activeMessageId !== null) {
      throw new Error("an Agent prompt is already running");
    }
    this.activeMessageId = messageId;
    this.finishStatus = "succeeded";
    if (!this.sessionAnnounced) {
      this.send(createMessage(messageId, "session_started", { session_id: this.sessionId }));
      this.sessionAnnounced = true;
    }
    try {
      await this.session.prompt(text);
    } finally {
      this.activeMessageId = null;
    }
  }

  resolvePermission(requestId: string, decision: PermissionDecision): boolean {
    return this.bridge.resolve(requestId, decision);
  }

  async abort(): Promise<void> {
    this.bridge.denyAll();
    await this.session.abort();
  }

  async dispose(): Promise<void> {
    this.bridge.denyAll();
    this.unsubscribe?.();
    await this.session.extensionRunner.emit({ type: "session_shutdown", reason: "quit" });
    this.session.dispose();
    restoreAgentDirEnvironment(this.previousAgentDirEnv);
    await rm(this.agentDir, { recursive: true, force: true });
  }

  private handleSessionEvent(event: Record<string, unknown>): void {
    if (event.type === "agent_end") {
      this.finishStatus = deriveFinishStatus(event);
      return;
    }
    const mapped = mapSessionEvent(event, this.finishStatus);
    if (!mapped || this.activeMessageId === null) return;
    this.send(createMessage(this.activeMessageId, mapped.type, mapped.payload));
  }
}

export async function runtimeSelfTest(): Promise<{ runtime: "pi"; status: "ok" }> {
  const agentDir = await mkdtemp(join(tmpdir(), "aitest-pi-self-test-"));
  const previousAgentDirEnv = process.env.PI_CODING_AGENT_DIR;
  process.env.PI_CODING_AGENT_DIR = agentDir;
  try {
    await writePermissionConfig(agentDir, "approval");
    const settingsManager = SettingsManager.inMemory(
      { defaultProjectTrust: "never" },
      { projectTrusted: false },
    );
    const resourceLoader = new DefaultResourceLoader({
      cwd: agentDir,
      agentDir,
      settingsManager,
      eventBus: createEventBus(),
      additionalExtensionPaths: [permissionSystemExtensionPath()],
      noExtensions: true,
      noSkills: true,
      noPromptTemplates: true,
      noThemes: true,
    });
    await resourceLoader.reload();
    const extensionErrors = resourceLoader.getExtensions().errors;
    if (extensionErrors.length > 0) {
      throw new Error(`permission extension failed to load: ${extensionErrors.map((item: any) => item.error).join("; ")}`);
    }
    return { runtime: "pi", status: "ok" };
  } finally {
    restoreAgentDirEnvironment(previousAgentDirEnv);
    await rm(agentDir, { recursive: true, force: true });
  }
}

function permissionSystemExtensionPath(): string {
  const serviceUrl = import.meta.resolve("@gotgenes/pi-permission-system");
  const servicePath = fileURLToPath(serviceUrl);
  return join(dirname(servicePath), "index.ts");
}

function validateInitializePayload(payload: InitializePayload): void {
  if (!payload || typeof payload.cwd !== "string" || payload.cwd.length === 0) {
    throw new Error("initialize.cwd must be a non-empty string");
  }
  if (!payload.model || typeof payload.model.provider !== "string" || typeof payload.model.name !== "string") {
    throw new Error("initialize.model provider and name are required");
  }
  if (typeof payload.model.api_key_env !== "string" || !/^[A-Za-z_][A-Za-z0-9_]*$/.test(payload.model.api_key_env)) {
    throw new Error("initialize.model.api_key_env must be an environment variable name");
  }
  if (
    payload.model.base_url_env
    && !/^[A-Za-z_][A-Za-z0-9_]*$/.test(payload.model.base_url_env)
  ) {
    throw new Error("initialize.model.base_url_env must be an environment variable name");
  }
  if (
    payload.model.protocol
    && !["auto", "openai_responses", "openai_chat_completions", "anthropic_messages"].includes(payload.model.protocol)
  ) {
    throw new Error("initialize.model.protocol is unsupported");
  }
  if (
    payload.tools !== undefined
    && (
      !Array.isArray(payload.tools)
      || payload.tools.some((tool) => !AGENT_TOOL_NAMES.includes(tool))
    )
  ) {
    throw new Error("initialize.tools contains an unsupported tool");
  }
  if (payload.permission_mode !== "approval" && payload.permission_mode !== "full_trust") {
    throw new Error("initialize.permission_mode must be approval or full_trust");
  }
}

function resolveBaseUrl(model: InitializePayload["model"]): string | undefined {
  if (typeof model.base_url === "string" && model.base_url.length > 0) return model.base_url;
  if (!model.base_url_env) return undefined;
  const value = process.env[model.base_url_env];
  if (!value) {
    throw new Error(`required base URL environment variable is not set: ${model.base_url_env}`);
  }
  return value;
}

async function configureRuntimeModel(
  modelRuntime: ModelRuntime,
  requested: InitializePayload["model"],
  apiKey: string,
  baseUrl: string | undefined,
): Promise<any> {
  const protocol = requested.protocol && requested.protocol !== "auto" ? requested.protocol : undefined;
  if (protocol === "openai_chat_completions") {
    const source = modelRuntime.getModel("openai", requested.name);
    if (!source) return undefined;
    const provider = "aitest-openai-chat";
    modelRuntime.registerProvider(provider, {
      name: "AITest OpenAI Chat Completions",
      baseUrl: baseUrl ?? source.baseUrl,
      api: "openai-completions",
      authHeader: true,
      models: [{
        id: source.id,
        name: source.name,
        reasoning: source.reasoning,
        thinkingLevelMap: source.thinkingLevelMap,
        input: source.input,
        cost: source.cost,
        contextWindow: source.contextWindow,
        maxTokens: source.maxTokens,
      }],
    });
    await modelRuntime.setRuntimeApiKey(provider, apiKey);
    return modelRuntime.getModel(provider, requested.name);
  }

  const provider = protocol === "openai_responses"
    ? "openai"
    : protocol === "anthropic_messages"
      ? "anthropic"
      : requested.provider;
  if (baseUrl) modelRuntime.registerProvider(provider, { baseUrl });
  await modelRuntime.setRuntimeApiKey(provider, apiKey);
  return modelRuntime.getModel(provider, requested.name);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function summarizeToolInput(toolName: string, raw: unknown): Record<string, unknown> {
  if (!isRecord(raw)) return {};
  if (toolName === "bash") {
    return redact(compactRecord({ command: raw.command, timeout: raw.timeout })) as Record<string, unknown>;
  }
  if (toolName === "write") {
    return boundedEventRecord(compactRecord({
      path: raw.path,
      content: raw.content,
    }));
  }
  if (toolName === "edit") {
    return boundedEventRecord(compactRecord({
      path: raw.path,
      old_text: raw.oldText,
      new_text: raw.newText,
      edit_count: Array.isArray(raw.edits) ? raw.edits.length : undefined,
    }));
  }
  if (["read", "grep", "find", "ls"].includes(toolName)) {
    return redact(compactRecord({
      path: raw.path,
      pattern: raw.pattern,
      glob: raw.glob,
      offset: raw.offset,
      limit: raw.limit,
    })) as Record<string, unknown>;
  }
  return boundedEventRecord(raw);
}

function compactRecord(value: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(Object.entries(value).filter(([, child]) => child !== undefined));
}

function boundedEventRecord(value: Record<string, unknown>): Record<string, unknown> {
  const bounded = boundedEventValue(value);
  return isRecord(bounded) ? bounded : { value: bounded };
}

function boundedEventValue(value: unknown): unknown {
  const safe = redact(value);
  const serialized = safe === undefined ? "null" : JSON.stringify(safe);
  const bytes = Buffer.byteLength(serialized, "utf8");
  if (bytes <= MAX_EVENT_VALUE_BYTES) return safe ?? null;
  return {
    preview: truncateUtf8(serialized, MAX_EVENT_VALUE_BYTES - 160),
    truncated: true,
    original_bytes: bytes,
  };
}

function truncateUtf8(value: string, maxBytes: number): string {
  const source = Buffer.from(value, "utf8");
  if (source.byteLength <= maxBytes) return value;
  return source.subarray(0, maxBytes).toString("utf8").replace(/\uFFFD$/u, "");
}

function restoreAgentDirEnvironment(previous: string | undefined): void {
  if (previous === undefined) {
    delete process.env.PI_CODING_AGENT_DIR;
  } else {
    process.env.PI_CODING_AGENT_DIR = previous;
  }
}

function deriveFinishStatus(event: Record<string, unknown>): "succeeded" | "failed" | "aborted" {
  if (!Array.isArray(event.messages)) return "succeeded";
  const assistant = [...event.messages]
    .reverse()
    .find((message) => isRecord(message) && message.role === "assistant");
  if (!isRecord(assistant)) return "succeeded";
  if (assistant.stopReason === "aborted") return "aborted";
  if (assistant.stopReason === "error") return "failed";
  return "succeeded";
}
