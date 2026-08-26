/** Enforces the plain-English file and named-function documentation contract for web code. */

import assert from "node:assert/strict";
import { readdir, readFile } from "node:fs/promises";
import path from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const webRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const scriptExtensions = new Set([".js", ".mjs", ".ts", ".tsx"]);
const documentedExtensions = new Set([...scriptExtensions, ".css", ".html"]);
const ignoredDirectories = new Set(["coverage", "dist", "node_modules"]);
const nonDeclarationCalls = new Set([
  "afterEach",
  "beforeEach",
  "catch",
  "describe",
  "filter",
  "for",
  "forEach",
  "if",
  "it",
  "map",
  "reduce",
  "requestAnimationFrame",
  "setInterval",
  "setTimeout",
  "sort",
  "switch",
  "test",
  "useCallback",
  "useEffect",
  "useMemo",
  "while",
]);

/** Recursively finds human-authored web source while excluding generated dependencies. */
async function sourceFiles(directory) {
  const entries = await readdir(directory, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    if (entry.isDirectory()) {
      if (!ignoredDirectories.has(entry.name)) {
        files.push(...(await sourceFiles(path.join(directory, entry.name))));
      }
    } else if (documentedExtensions.has(path.extname(entry.name))) {
      files.push(path.join(directory, entry.name));
    }
  }
  return files.sort();
}

/** Masks strings and comments while preserving offsets and line breaks for source scans. */
function maskNonCode(source) {
  const masked = [...source];
  let mode = "code";
  let escaped = false;
  for (let index = 0; index < source.length; index += 1) {
    const current = source[index];
    const next = source[index + 1];
    if (mode === "code") {
      if (current === "/" && next === "/") {
        masked[index] = " ";
        masked[index + 1] = " ";
        mode = "line-comment";
        index += 1;
      } else if (current === "/" && next === "*") {
        masked[index] = " ";
        masked[index + 1] = " ";
        mode = "block-comment";
        index += 1;
      } else if (current === '"' || current === "'" || current === "`") {
        masked[index] = " ";
        mode = current;
        escaped = false;
      }
    } else if (mode === "line-comment") {
      if (current === "\n") mode = "code";
      else masked[index] = " ";
    } else if (mode === "block-comment") {
      masked[index] = current === "\n" ? "\n" : " ";
      if (current === "*" && next === "/") {
        masked[index + 1] = " ";
        mode = "code";
        index += 1;
      }
    } else {
      masked[index] = current === "\n" ? "\n" : " ";
      if (escaped) escaped = false;
      else if (current === "\\") escaped = true;
      else if (current === mode) mode = "code";
    }
  }
  return masked.join("");
}

/** Returns the one-based line number for a source offset in a failure message. */
function lineNumber(source, offset) {
  return source.slice(0, offset).split("\n").length;
}

/** Requires a comment to contain enough ordinary words to explain behavior. */
function isPlainEnglish(comment) {
  return (comment.match(/[A-Za-z][A-Za-z'-]*/gu) ?? []).length >= 3;
}

/** Checks that the immediately preceding non-whitespace text is a JSDoc block. */
function hasLeadingDocumentation(source, offset) {
  const prefix = source
    .slice(0, offset)
    .trimEnd()
    .replace(/\b(?:async|get|return|set)$/u, "")
    .trimEnd();
  if (!prefix.endsWith("*/")) return false;
  const opening = prefix.lastIndexOf("/**");
  const ordinaryOpening = prefix.lastIndexOf("/*");
  return (
    opening >= 0 &&
    opening === ordinaryOpening &&
    isPlainEnglish(prefix.slice(opening + 3, -2))
  );
}

/** Allows required format directives, then checks the format's explanatory header syntax. */
function hasFileHeader(source, extension) {
  const lines = source.replace(/^\uFEFF/u, "").split("\n");
  while (lines[0]?.trim() === "") lines.shift();
  if (extension === ".html" && lines[0]?.trim().toLowerCase() === "<!doctype html>") {
    lines.shift();
    while (lines[0]?.trim() === "") lines.shift();
    const header = lines.join("\n").trimStart().match(/^<!--([\s\S]*?)-->/u);
    return Boolean(header && isPlainEnglish(header[1]));
  }
  if (extension === ".css") {
    const header = lines.join("\n").trimStart().match(/^\/\*([\s\S]*?)\*\//u);
    return Boolean(header && isPlainEnglish(header[1]));
  }
  while (lines[0]?.trim().startsWith("/// <reference")) {
    lines.shift();
    while (lines[0]?.trim() === "") lines.shift();
  }
  const header = lines.join("\n").trimStart().match(/^\/\*\*([\s\S]*?)\*\//u);
  return Boolean(header && isPlainEnglish(header[1]));
}

/** Finds named declarations while excluding anonymous callbacks and routine API calls. */
function namedDeclarations(source) {
  const masked = maskNonCode(source);
  const declarations = [];

  /** Adds one declaration once even when two conservative patterns recognize it. */
  function record(name, offset) {
    if (!declarations.some((item) => item.offset === offset)) {
      declarations.push({ name, offset });
    }
  }

  const functions = /\b(?:export\s+(?:default\s+)?)?(?:async\s+)?function\s+([A-Za-z_$][\w$]*)\s*\(/gu;
  for (const match of masked.matchAll(functions)) record(match[1], match.index);

  const arrows = /\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:useCallback\s*\(\s*)?(?:async\s*)?(?:\([^;]*?\)|[A-Za-z_$][\w$]*)\s*(?::\s*[^=\n]+)?=>/gsu;
  for (const match of masked.matchAll(arrows)) record(match[1], match.index);

  const methods = /^[ \t]+(?:(?:async|get|set)\s+)?([A-Za-z_$][\w$]*)\s*\([^;\n]*\)\s*(?::[^\n{]+)?\{/gmu;
  for (const match of masked.matchAll(methods)) {
    if (!nonDeclarationCalls.has(match[1])) record(match[1], match.index);
  }

  const inlineMethods = /[{,;][ \t]*(?:(?:async|get|set)\s+)?([A-Za-z_$][\w$]*)\s*\([^;\n]*\)\s*(?::[^\n{]+)?\{/gmu;
  for (const match of masked.matchAll(inlineMethods)) {
    if (!nonDeclarationCalls.has(match[1])) {
      record(match[1], match.index + match[0].indexOf(match[1]));
    }
  }
  return declarations.sort((left, right) => left.offset - right.offset);
}

test("every web source file and named function has leading plain-English documentation", async () => {
  const failures = [];
  for (const file of await sourceFiles(webRoot)) {
    const source = await readFile(file, "utf8");
    const relative = path.relative(webRoot, file);
    const extension = path.extname(file);
    if (!hasFileHeader(source, extension)) {
      failures.push(`${relative}: missing file header`);
    }
    const declarations = scriptExtensions.has(extension)
      ? namedDeclarations(source)
      : [];
    for (const declaration of declarations) {
      if (!hasLeadingDocumentation(source, declaration.offset)) {
        failures.push(
          `${relative}:${lineNumber(source, declaration.offset)} ${declaration.name} lacks leading JSDoc`,
        );
      }
    }
  }
  assert.deepEqual(failures, []);
});
