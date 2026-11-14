import { test, after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createServer } from "vite";

const storage = new Map();
globalThis.localStorage = {
  getItem: key => storage.get(key) ?? null,
  setItem: (key, value) => storage.set(key, value),
};
globalThis.document = { documentElement: { lang: "" }, title: "" };
const server = await createServer({ server: { middlewareMode: true }, appType: "custom" });
after(() => server.close());
const { default: i18n, t, languageStorageKey } = await server.ssrLoadModule("/src/lib/labels.ts");
const { createElement } = await import("react");
const { renderToStaticMarkup } = await import("react-dom/server");
const { EventsPage } = await server.ssrLoadModule("/src/pages/EventsPage.tsx");
const { VisitChanges } = await server.ssrLoadModule("/src/components/VisitChanges.tsx");
const { ConflictChoices } = await server.ssrLoadModule("/src/components/SyncConflict.tsx");
const render = element => renderToStaticMarkup(element);

test("both catalogs cover the same labels and calendar", () => {
  const read = code => JSON.parse(readFileSync(new URL(`../src/lib/locales/${code}.json`, import.meta.url)));
  const eu = read("eu"), es = read("es");
  assert.deepEqual(Object.keys(eu).sort(), Object.keys(es).sort());
  for (const catalog of [eu, es]) {
    assert.equal(catalog.months.length, 12);
    assert.equal(catalog.weekdays.length, 7);
    assert.ok(Object.values(catalog).every(value => Array.isArray(value) || value.trim().length > 0));
  }
});

test("language switches translate months and field labels without changing data", async () => {
  assert.equal(i18n.language, "eu");
  await i18n.changeLanguage("es");
  assert.equal(storage.get(languageStorageKey), "es");
  assert.equal(document.documentElement.lang, "es");
  assert.equal(document.title, "Gestión EINGO");
  assert.equal(t.disconnected, "Sin conexión");
  const table = { title: "Calendar", columns: ["DATA", "HERRIA", "ORDUA"], rows: [] };
  const events = [{ id: 1, date: "2027-02-17", values: ["OTSAILAK 17", "Bilbo", "18:00"] }];
  const before = JSON.stringify({ table, events });
  const html = render(createElement(EventsPage, { events, table }));
  assert.match(html, /Febrero/);
  assert.match(html, /HORA/);
  assert.match(html, /Bilbo/);
  assert.equal(JSON.stringify({ table, events }), before);
  const changes = [{ kind: "updated", town: "Bilbo", date: "2027-02-17", fields: [{ name: "ORDUA", before: "18:00", after: "19:00" }] }];
  assert.match(render(createElement(VisitChanges, { changes })), /HORA/);
  await i18n.changeLanguage("eu");
  assert.equal(document.documentElement.lang, "eu");
  assert.equal(t.disconnected, "Konexiorik ez");
});

test("blocked local storage does not prevent switching languages", async () => {
  const previous = globalThis.localStorage;
  globalThis.localStorage = { getItem() { throw Error("blocked"); }, setItem() { throw Error("blocked"); } };
  try {
    await i18n.changeLanguage("es");
    assert.equal(document.documentElement.lang, "es");
    } finally {
    globalThis.localStorage = previous;
    await i18n.changeLanguage("eu");
  }
});

test("conflict choices show the field and both values with no automatic selection", async () => {
  const preview = { token: "example", canResolve: true, reason: null, fields: [
    { key: "event:ORDUA", date: "2027-01-07", town: "Test town", column: "ORDUA", options: [
      { source: "sheets", value: "18:00" }, { source: "docs", value: "19:00" },
    ] },
  ] };
  await i18n.changeLanguage("es");
  try {
    const html = render(createElement(ConflictChoices, { preview, choices: {}, busy: false, onChoose() {} }));
    assert.match(html, /Test town/);
    assert.match(html, /HORA/);
    assert.match(html, /Google Sheets/);
    assert.match(html, /Google Docs/);
    assert.match(html, /18:00/);
    assert.match(html, /19:00/);
    assert.equal((html.match(/type="radio"/g) ?? []).length, 2);
    assert.doesNotMatch(html, /checked/);
    const selected = render(createElement(ConflictChoices, { preview, choices: { "event:ORDUA": "docs" }, busy: true, onChoose() {} }));
    assert.match(selected, /disabled/);
    assert.equal((selected.match(/checked/g) ?? []).length, 1);
  } finally { await i18n.changeLanguage("eu"); }
});
