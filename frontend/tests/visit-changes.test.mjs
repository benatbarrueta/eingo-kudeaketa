import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import ts from "typescript";
const code = ts.transpileModule(readFileSync(new URL("../src/lib/visitChanges.ts", import.meta.url), "utf8"), { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText;
const { visitChanges, visitKey, readVisit, saveVisit } = await import("data:text/javascript;base64," + Buffer.from(code).toString("base64"));
const row = (town, hour = "18:00") => ({ kind: "event", date: "2027-02-17", values: ["OTSAILAK 17", town, hour, "private"] });
const table = rows => ({ title: "Calendar", columns: ["DATA", "HERRIA", "ORDUA", "WAWA"], rows });
test("no changes after identical reload or row reordering", () => {
  assert.deepEqual(visitChanges(table([row("A"), row("B")]), table([row("B"), row("A")])), []);
});
test("additions, deletions and field edits since previous visit", () => {
  const changes = visitChanges(table([row("A"), row("B")]), table([row("A", "20:00"), row("C")]));
  assert.deepEqual(changes.map(c => c.kind).sort(), ["added", "removed", "updated"]);
  assert.deepEqual(changes.find(c => c.kind === "updated").fields, [{ name: "ORDUA", before: "18:00", after: "20:00" }]);
});
test("ambiguous events are not attributed to arbitrary edits", () => {
  assert.equal(visitChanges(table([row("A"), row("A", "19:00")]), table([row("A", "21:00"), row("A", "22:00")])).some(c => c.kind === "updated"), false);
});
test("separate sources, malformed storage and unavailable storage", () => {
  assert.notEqual(visitKey({ source: "sheets", year: 2027, documentUrl: "a" }), visitKey({ source: "sheets", year: 2027, documentUrl: "b" }));
  globalThis.localStorage = { getItem: () => '{"rows":[{}],"columns":[]}', setItem: () => { throw Error(); } };
  assert.equal(readVisit("key"), undefined);
  assert.equal(saveVisit("key", table([])), false);
});
