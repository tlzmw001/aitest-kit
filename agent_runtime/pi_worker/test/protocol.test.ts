import assert from "node:assert/strict";
import test from "node:test";

import { ProtocolFailure, createMessage, parseCommand, registerSecret, serializeMessage } from "../src/protocol.ts";


test("protocol parses a supported command envelope", () => {
  const command = parseCommand(JSON.stringify({
    protocol_version: 1,
    id: "m-1",
    type: "initialize",
    payload: { cwd: "/tmp/workspace" },
  }));

  assert.equal(command.type, "initialize");
  assert.equal(command.payload.cwd, "/tmp/workspace");
});


test("protocol rejects unknown versions and message types", () => {
  assert.throws(
    () => parseCommand(JSON.stringify({ protocol_version: 2, id: "m", type: "initialize", payload: {} })),
    (error: unknown) => error instanceof ProtocolFailure && error.code === "UNSUPPORTED_PROTOCOL_VERSION",
  );
  assert.throws(
    () => parseCommand(JSON.stringify({ protocol_version: 1, id: "m", type: "surprise", payload: {} })),
    (error: unknown) => error instanceof ProtocolFailure && error.code === "UNKNOWN_MESSAGE_TYPE",
  );
});


test("protocol serialization redacts credential-shaped fields", () => {
  registerSecret("arbitrary-provider-credential");
  const rendered = serializeMessage(createMessage("m-2", "error", {
    api_key: "sk-secret-value",
    authorization: "Bearer private-token",
    nested: { password: "hidden", safe: "visible", message: "failed with arbitrary-provider-credential" },
  }));

  assert.doesNotMatch(rendered, /sk-secret-value|private-token|hidden|arbitrary-provider-credential/);
  assert.match(rendered, /visible/);
});
