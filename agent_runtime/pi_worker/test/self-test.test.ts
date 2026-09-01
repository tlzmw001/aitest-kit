import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";


const workerRoot = dirname(dirname(fileURLToPath(import.meta.url)));

test("worker self-test validates the installed runtime without starting JSONL mode", () => {
  const completed = spawnSync(
    process.execPath,
    ["--experimental-strip-types", join(workerRoot, "src", "worker.ts"), "--self-test"],
    {
      cwd: workerRoot,
      encoding: "utf-8",
      timeout: 15_000,
    },
  );

  assert.equal(completed.status, 0, completed.stderr);
  assert.deepEqual(JSON.parse(completed.stdout.trim()), {
    runtime: "pi",
    status: "ok",
  });
});
