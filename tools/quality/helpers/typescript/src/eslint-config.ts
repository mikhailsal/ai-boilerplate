// The `eslint-config` command: whether ESLint configures each file, and
// whether that configuration lints it with type information.

import type { ESLint } from "eslint";
import { loadEslint } from "./load.ts";
import { absolutePath, field, pathList, type JsonObject } from "./protocol.ts";

export interface FileConfig {
  readonly file: string;
  readonly configured: boolean;
  readonly ignored: boolean;
  readonly typed: boolean;
  readonly parser: string | null;
}

export interface EslintConfigResponse {
  readonly files: readonly FileConfig[];
}

async function inspect(eslint: ESLint, file: string): Promise<FileConfig> {
  const config: unknown = await eslint.calculateConfigForFile(file);
  const language = field(config, "languageOptions");
  const options = field(language, "parserOptions");
  const name = field(field(field(language, "parser"), "meta"), "name");
  const typed =
    Boolean(field(options, "projectService")) ||
    Boolean(field(options, "project"));
  return {
    file,
    configured: config !== undefined,
    ignored: await eslint.isPathIgnored(file),
    typed,
    parser: typeof name === "string" ? name : null,
  };
}

export async function runEslintConfig(
  request: JsonObject,
): Promise<EslintConfigResponse> {
  const ESLintClass = await loadEslint(absolutePath(request, "eslint"));
  const eslint = new ESLintClass({ cwd: absolutePath(request, "cwd") });
  const files: FileConfig[] = [];
  for (const file of pathList(request, "files")) {
    files.push(await inspect(eslint, file));
  }
  return { files };
}
