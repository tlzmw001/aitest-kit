import assert from "node:assert/strict";
import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { createGrepTool } from "@earendil-works/pi-coding-agent";
import { PiSessionController } from "../src/session.ts";

test("native recursive grep must cross the real approval gate before reading hidden files", async () => {
  const cwd = await mkdtemp(join(tmpdir(), "aitest-grep-gate-"));
  process.env.AITEST_SEARCH_TEST_KEY = "not-a-real-key";
  let controller: PiSessionController | undefined;
  let prompts = 0;
  let decision: "deny" | "allow_once" = "deny";
  try {
    await writeFile(join(cwd, ".env"), "AUDIT_MARKER=synthetic-test-value\n");
    await writeFile(join(cwd, ".gitignore"), ".env\n");
    controller = await PiSessionController.create({
      cwd, permission_mode: "approval", skill_paths: [],
      model: { provider: "anthropic", name: "claude-sonnet-4-5", api_key_env: "AITEST_SEARCH_TEST_KEY" },
    }, (message: any) => {
      if (message.type !== "permission_requested") return;
      prompts += 1;
      queueMicrotask(() => controller!.resolvePermission(message.payload.request_id, decision));
    }, () => undefined);
    const runner = (controller as any).session.extensionRunner;
    const input = { path: cwd, glob: ".env", pattern: "AUDIT_MARKER" };
    async function executeSearch(id: string): Promise<string> {
      const result = await runner.emitToolCall({ type: "tool_call", toolName: "grep", toolCallId: id, input });
      if (result?.block) return "blocked";
      return JSON.stringify(await createGrepTool(cwd).execute(id, input));
    }
    assert.equal(await executeSearch("denied-search"), "blocked");
    assert.equal(prompts, 1);
    const read = await runner.emitToolCall({ type: "tool_call", toolName: "read", toolCallId: "read-env", input: { path: join(cwd, ".env") } });
    assert.equal(read?.block, true);
    decision = "allow_once";
    assert.match(await executeSearch("approved-search"), /AUDIT_MARKER/);
    assert.equal(prompts, 2);
  } finally {
    await controller?.dispose();
    delete process.env.AITEST_SEARCH_TEST_KEY;
    await rm(cwd, { recursive: true, force: true });
  }
});
