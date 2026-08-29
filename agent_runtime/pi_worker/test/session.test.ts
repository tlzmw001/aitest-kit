import assert from "node:assert/strict";
import { mkdtemp, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";

import { mapSessionEvent, PiSessionController } from "../src/session.ts";


test("session event mapper normalizes text and tool lifecycle events", () => {
  assert.deepEqual(
    mapSessionEvent({ type: "message_update", assistantMessageEvent: { type: "text_delta", delta: "hello" } }),
    { type: "text_delta", payload: { delta: "hello" } },
  );
  assert.deepEqual(
    mapSessionEvent({ type: "tool_execution_start", toolCallId: "t-1", toolName: "bash", args: { command: "git status" } }),
    {
      type: "tool_call_requested",
      payload: { tool_call_id: "t-1", tool_name: "bash", input: { command: "git status" } },
    },
  );
  assert.deepEqual(
    mapSessionEvent({ type: "tool_execution_end", toolCallId: "t-1", toolName: "bash", result: {}, isError: false }),
    {
      type: "tool_call_finished",
      payload: { tool_call_id: "t-1", tool_name: "bash", is_error: false, result: {} },
    },
  );
  assert.deepEqual(mapSessionEvent({ type: "agent_settled" }), {
    type: "agent_finished",
    payload: { status: "succeeded" },
  });
  assert.deepEqual(mapSessionEvent({ type: "agent_settled" }, "failed"), {
    type: "agent_finished",
    payload: { status: "failed" },
  });
});


test("session event mapper does not copy tool output or credential content", () => {
  const mapped = mapSessionEvent({
    type: "tool_execution_end",
    toolCallId: "t-secret",
    toolName: "read",
    result: { content: "Bearer private-token" },
    isError: false,
  });

  assert.doesNotMatch(JSON.stringify(mapped), /private-token/);
});


test("write tool events preserve diff input and bound oversized content", () => {
  const mapped = mapSessionEvent({
    type: "tool_execution_start",
    toolCallId: "t-write",
    toolName: "write",
    args: { path: "suite.md", content: `prefix-${"x".repeat(80 * 1024)}-suffix` },
  });
  const rendered = JSON.stringify(mapped);

  assert.match(rendered, /"original_bytes":/);
  assert.match(rendered, /"truncated":true/);
  assert.ok(Buffer.byteLength(JSON.stringify(mapped?.payload.input), "utf8") <= 64 * 1024);
});


test("write and edit tool events preserve bounded text needed by diff", () => {
  assert.deepEqual(
    mapSessionEvent({
      type: "tool_execution_start",
      toolCallId: "t-write-small",
      toolName: "write",
      args: { path: "suite.md", content: "new suite" },
    }),
    {
      type: "tool_call_requested",
      payload: {
        tool_call_id: "t-write-small",
        tool_name: "write",
        input: { path: "suite.md", content: "new suite" },
      },
    },
  );
  assert.deepEqual(
    mapSessionEvent({
      type: "tool_execution_start",
      toolCallId: "t-edit",
      toolName: "edit",
      args: { path: "suite.md", oldText: "old", newText: "new" },
    })?.payload.input,
    { path: "suite.md", old_text: "old", new_text: "new" },
  );
});


test("session event mapper emits bounded tool progress and results", () => {
  const update = mapSessionEvent({
    type: "tool_execution_update",
    toolCallId: "t-stream",
    toolName: "bash",
    partialResult: { output: "x".repeat(80 * 1024) },
  });
  const finished = mapSessionEvent({
    type: "tool_execution_end",
    toolCallId: "t-stream",
    toolName: "bash",
    result: { output: "done" },
    isError: false,
  });

  assert.equal(update?.type, "tool_call_updated");
  assert.equal((update?.payload.partial_result as Record<string, unknown>).truncated, true);
  assert.ok(Buffer.byteLength(JSON.stringify(update?.payload.partial_result), "utf8") <= 64 * 1024);
  assert.deepEqual(finished?.payload.result, { output: "done" });
});


test("real permission extension loads the approval and full-trust profiles", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "aitest-pi-session-test-"));
  process.env.AITEST_PI_TEST_KEY = "not-a-real-key";
  try {
    const approval = await PiSessionController.create({
      cwd,
      model: {
        provider: "anthropic",
        name: "claude-sonnet-4-5",
        api_key_env: "AITEST_PI_TEST_KEY",
      },
      permission_mode: "approval",
      skill_paths: [],
    }, () => undefined, () => undefined);
    const approvalService = getPublishedPermissionService(approval.sessionId);
    assert.ok(approvalService);
    assert.equal(approvalService.getToolPermission("read"), "allow");
    assert.equal(approvalService.getToolPermission("write"), "ask");
    assert.equal(approvalService.getToolPermission("bash"), "ask");
    assert.equal(approvalService.checkPermission("path", join(cwd, ".env")).state, "deny");
    assert.equal(approvalService.checkPermission("external_directory", join(tmpdir(), "outside.txt")).state, "ask");
    await approval.dispose();

    const fullTrust = await PiSessionController.create({
      cwd,
      model: {
        provider: "anthropic",
        name: "claude-sonnet-4-5",
        api_key_env: "AITEST_PI_TEST_KEY",
      },
      permission_mode: "full_trust",
      skill_paths: [],
    }, () => undefined, () => undefined);
    const fullTrustService = getPublishedPermissionService(fullTrust.sessionId);
    assert.ok(fullTrustService);
    assert.equal(fullTrustService.getToolPermission("write"), "allow");
    assert.equal(fullTrustService.getToolPermission("bash"), "allow");
    assert.equal(fullTrustService.checkPermission("path", join(cwd, ".env")).state, "allow");
    await fullTrust.dispose();
  } finally {
    delete process.env.AITEST_PI_TEST_KEY;
    await rm(cwd, { recursive: true, force: true });
  }
});


test("chat completions protocol registers a dynamic provider and creates a real session", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "aitest-pi-chat-provider-test-"));
  process.env.AITEST_PI_TEST_KEY = "not-a-real-key";
  process.env.AITEST_PI_TEST_BASE_URL = "https://gateway.example.test/v1";
  try {
    const controller = await PiSessionController.create({
      cwd,
      model: {
        protocol: "openai_chat_completions",
        provider: "openai",
        name: "gpt-5.5",
        api_key_env: "AITEST_PI_TEST_KEY",
        base_url_env: "AITEST_PI_TEST_BASE_URL",
      },
      permission_mode: "approval",
      skill_paths: [],
    }, () => undefined, () => undefined);

    assert.equal((controller as any).session.model.provider, "aitest-openai-chat");
    assert.equal((controller as any).session.model.api, "openai-completions");
    await controller.dispose();
  } finally {
    delete process.env.AITEST_PI_TEST_KEY;
    delete process.env.AITEST_PI_TEST_BASE_URL;
    await rm(cwd, { recursive: true, force: true });
  }
});


test("an explicit empty tool list creates a tool-free connection-test session", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "aitest-pi-no-tools-test-"));
  process.env.AITEST_PI_TEST_KEY = "not-a-real-key";
  try {
    const controller = await PiSessionController.create({
      cwd,
      model: {
        provider: "anthropic",
        name: "claude-sonnet-4-5",
        api_key_env: "AITEST_PI_TEST_KEY",
      },
      permission_mode: "approval",
      skill_paths: [],
      tools: [],
    }, () => undefined, () => undefined);

    assert.deepEqual((controller as any).session._initialActiveToolNames, []);
    assert.deepEqual([...(controller as any).session._allowedToolNames], []);
    await controller.dispose();
  } finally {
    delete process.env.AITEST_PI_TEST_KEY;
    await rm(cwd, { recursive: true, force: true });
  }
});


function getPublishedPermissionService(sessionId: string): any {
  const services = (globalThis as any)[Symbol.for("@gotgenes/pi-permission-system:session-services")];
  return services?.get?.(sessionId);
}
