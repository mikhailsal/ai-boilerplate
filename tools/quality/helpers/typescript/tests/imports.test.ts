import { join } from "node:path";
import { expect, test } from "vitest";
import { json, linkPackages, project, structureOf } from "./fixtures.ts";

const MAIN = `import { one } from "../lib/util.ts";
import type { Two } from "@lib/types.ts";
export { one as uno } from "../lib/util.ts";
export const local = 1;
export { local as again };
import "./missing.ts";
import ts = require("typescript");
const later = await import("../lib/util.ts");
const loaded = require("../lib/util.ts");
const named = "../lib/util.ts";
const computed = import(named);
const empty = require();
import("vitest");
const spelled = require(\`../lib/util.ts\`);
`;

const FILES = {
  "package.json": json({ type: "module" }),
  "tsconfig.json": json({
    compilerOptions: {
      module: "nodenext",
      allowImportingTsExtensions: true,
      noEmit: true,
      paths: { "@lib/*": ["./lib/*"] },
    },
    include: ["src", "lib"],
  }),
  "lib/util.ts": "export const one = 1;\n",
  "lib/types.ts": "export type Two = 2;\n",
  "src/main.ts": MAIN,
  "outside/main.ts": MAIN,
};

test("every import form is listed with its line and resolved file", () => {
  const root = project(FILES);
  linkPackages(root);
  const report = structureOf(
    join(root, "src/main.ts"),
    join(root, "tsconfig.json"),
  );
  const util = join(root, "lib/util.ts");
  expect(report.imports).toEqual([
    { specifier: "../lib/util.ts", line: 1, resolved: util },
    {
      specifier: "@lib/types.ts",
      line: 2,
      resolved: join(root, "lib/types.ts"),
    },
    { specifier: "../lib/util.ts", line: 3, resolved: util },
    { specifier: "./missing.ts", line: 6, resolved: null },
    { specifier: "typescript", line: 7, resolved: null },
    { specifier: "../lib/util.ts", line: 8, resolved: util },
    { specifier: "../lib/util.ts", line: 9, resolved: util },
    { specifier: "vitest", line: 13, resolved: null },
    { specifier: "../lib/util.ts", line: 14, resolved: util },
  ]);
});

test("a file outside every project uses the root project's options", () => {
  const root = project(FILES);
  const report = structureOf(
    join(root, "outside/main.ts"),
    join(root, "tsconfig.json"),
  );
  expect(report.imports[1]?.resolved).toBe(join(root, "lib/types.ts"));
});

test("without a tsconfig, or with one that cannot be read, no alias resolves", () => {
  const root = project(FILES);
  for (const tsconfig of [null, join(root, "missing.json")]) {
    const report = structureOf(join(root, "src/main.ts"), tsconfig);
    expect(report.imports[1]?.resolved).toBeNull();
  }
});

const SOLUTION = {
  "tsconfig.json": json({ files: [], references: [{ path: "./app" }] }),
  "app/tsconfig.json": json({
    compilerOptions: { paths: { "~/*": ["./src/*"] } },
    include: ["src"],
  }),
  "app/src/a.ts": 'import { b } from "~/b.ts";\n',
  "app/src/b.ts": "export const b = 1;\n",
  "other/c.ts": 'import { b } from "~/b.ts";\n',
};

test("each file uses the options of the project that lists it", () => {
  const root = project(SOLUTION);
  const tsconfig = join(root, "tsconfig.json");
  const listed = structureOf(join(root, "app/src/a.ts"), tsconfig);
  expect(listed.imports[0]?.resolved).toBe(join(root, "app/src/b.ts"));
  const unlisted = structureOf(join(root, "other/c.ts"), tsconfig);
  expect(unlisted.imports[0]?.resolved).toBeNull();
});

const MODES = {
  "package.json": json({ type: "module" }),
  "tsconfig.json": json({
    compilerOptions: { module: "nodenext", allowImportingTsExtensions: true },
    include: ["src"],
  }),
  "src/dep.ts": "export const dep = 1;\n",
  "src/legacy.cts": 'import dep = require("./dep");\n',
  "src/modern.mts": 'import { dep } from "./dep";\n',
};

test("the module format of the file decides how a specifier resolves", () => {
  const root = project(MODES);
  const tsconfig = join(root, "tsconfig.json");
  const legacy = structureOf(join(root, "src/legacy.cts"), tsconfig);
  expect(legacy.imports[0]?.resolved).toBe(join(root, "src/dep.ts"));
  const modern = structureOf(join(root, "src/modern.mts"), tsconfig);
  expect(modern.imports[0]?.resolved).toBeNull();
});
