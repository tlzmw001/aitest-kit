import assert from "node:assert/strict";
import test from "node:test";

import { ApprovalBridge, createPermissionConfig } from "../src/permissions.ts";


test("approval profile allows workspace discovery, asks for mutation, and denies sensitive paths", () => {
  const config = createPermissionConfig("approval");

  assert.equal(config.yoloMode, false);
  assert.equal(config.permission.read, "allow");
  assert.equal(config.permission.grep, "allow");
  assert.equal(config.permission.write, "ask");
  assert.equal(config.permission.edit, "ask");
  assert.equal(config.permission.bash, "ask");
  assert.equal(config.permission.external_directory, "ask");
  assert.equal((config.permission.path as Record<string, string>)["*.env"], "deny");
});

test("full trust is an explicit allow-all profile rather than yolo mode", () => {
  const config = createPermissionConfig("full_trust");

  assert.equal(config.yoloMode, false);
  assert.equal(config.permission["*"], "allow");
  assert.equal(config.permission.path, "allow");
  assert.equal(config.permission.external_directory, "allow");
});


test("approval bridge maps one-shot and session decisions to official UI options", async () => {
  const requested: unknown[] = [];
  const bridge = new ApprovalBridge((message) => requested.push(message), 1000);
  bridge.observePrompt({
    requestId: "permission-1",
    source: "tool_call",
    surface: "write",
    value: "suite.md",
    agentName: null,
    request: { surface: "write" },
    forwarding: null,
  });
  const selection = bridge.select("Permission\nwrite suite.md", ["Yes", "Yes, for this session", "No"]);

  assert.equal(requested.length, 1);
  bridge.resolve("permission-1", "allow_session");
  assert.equal(await selection, "Yes, for this session");
});


test("approval bridge fails closed when the UI does not answer", async () => {
  const bridge = new ApprovalBridge(() => undefined, 10);
  bridge.observePrompt({
    requestId: "permission-timeout",
    source: "tool_call",
    surface: "bash",
    value: "git status",
    agentName: null,
    request: { surface: "bash" },
    forwarding: null,
  });

  const selected = await bridge.select("Permission", ["Yes", "Yes, for this session", "No"]);

  assert.equal(selected, "No");
});


test("approval bridge redacts sensitive prompt details before JSONL", async () => {
  const requested: Array<Record<string, unknown>> = [];
  const bridge = new ApprovalBridge((message) => requested.push(message as Record<string, unknown>), 1000);
  bridge.observePrompt({
    requestId: "permission-secret",
    source: "tool_call",
    surface: "bash",
    value: "curl -H 'Authorization: Bearer private-token' example.test",
    agentName: null,
    request: { surface: "bash" },
    forwarding: null,
  });
  const selection = bridge.select("Authorization: Bearer private-token", ["Yes", "No"]);
  bridge.resolve("permission-secret", "deny");
  await selection;

  assert.doesNotMatch(JSON.stringify(requested), /private-token/);
});
