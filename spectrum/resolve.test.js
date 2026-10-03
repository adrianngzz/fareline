import assert from "node:assert/strict";
import test from "node:test";
import { loadMap, resolveRider } from "./resolve.js";

test("maps an iMessage sender id onto a rider", () => {
  const map = loadMap('{"+15551212":"Adrian","alex@phone":"Alex"}');
  assert.equal(resolveRider({ id: "+15551212" }, map), "Adrian");
  assert.equal(resolveRider({ id: "ALEX@phone" }, map), "Alex");
});

test("unknown senders stay unmapped", () => {
  assert.equal(resolveRider({ id: "+1999" }, { "+1555": "Sam" }), null);
  assert.equal(resolveRider(undefined, {}), null);
});

test("rejects a map that is not an object", () => {
  assert.throws(() => loadMap("[]"), /JSON object/);
});
