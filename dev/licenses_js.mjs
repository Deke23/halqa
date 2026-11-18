// Print a Markdown table of the direct npm dependencies in frontend/package.json,
// read from the installed copies in frontend/node_modules. No dependencies.

import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const frontend = resolve(here, "..", "frontend");
const MISSING = "unknown";

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return null;
  }
}

function clean(value) {
  if (value === undefined || value === null || value === "") return MISSING;
  return String(value).replace(/\s+/g, " ").trim().replace(/\|/g, "\\|") || MISSING;
}

function licenceOf(pkg) {
  if (typeof pkg.license === "string") return pkg.license;
  if (pkg.license && typeof pkg.license === "object" && pkg.license.type) return pkg.license.type;
  if (Array.isArray(pkg.licenses)) {
    const types = pkg.licenses.map((l) => (typeof l === "string" ? l : l && l.type)).filter(Boolean);
    if (types.length) return types.join(" OR ");
  }
  return null;
}

function urlOf(pkg) {
  if (typeof pkg.homepage === "string" && pkg.homepage) return pkg.homepage;
  const repo = pkg.repository;
  if (typeof repo === "string" && repo) return repo;
  if (repo && typeof repo === "object" && repo.url) return repo.url;
  return null;
}

const manifest = readJson(join(frontend, "package.json"));
if (!manifest) {
  console.error(`Cannot read ${join(frontend, "package.json")}`);
  process.exit(1);
}

const entries = [
  ...Object.keys(manifest.dependencies ?? {}).map((name) => [name, "runtime"]),
  ...Object.keys(manifest.devDependencies ?? {}).map((name) => [name, "dev"]),
];

console.log("| Package | Version | Licence | Type | URL |");
console.log("| --- | --- | --- | --- | --- |");
for (const [name, type] of entries) {
  const pkg = readJson(join(frontend, "node_modules", ...name.split("/"), "package.json")) ?? {};
  console.log(
    `| ${clean(name)} | ${clean(pkg.version)} | ${clean(licenceOf(pkg))} | ${type} | ${clean(urlOf(pkg))} |`,
  );
}
