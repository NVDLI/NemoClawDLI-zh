#!/usr/bin/env node
// Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

// Build the same-origin browser bundles and their source-derived inventory.
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { pathToFileURL } from "node:url";

const root = path.resolve(path.dirname(new URL(import.meta.url).pathname), "../..");
const workspace = path.join(root, "scripts/browser-vendor");
const modules = path.join(workspace, "node_modules");
const vendor = path.join(root, "web/nemoclaw/vendor");
const lockPath = path.join(workspace, "package-lock.json");
const packagePath = path.join(workspace, "package.json");

if (!fs.existsSync(lockPath) || !fs.existsSync(path.join(modules, "esbuild"))) {
  throw new Error("run npm ci under scripts/browser-vendor before regenerating");
}

const { build } = await import(pathToFileURL(path.join(modules, "esbuild/lib/main.js")));
const lock = JSON.parse(fs.readFileSync(lockPath, "utf8"));
const direct = JSON.parse(fs.readFileSync(packagePath, "utf8")).dependencies;
const codemirrorVersion = direct.codemirror;
const codemirrorBase = `codemirror-${codemirrorVersion}`;
fs.mkdirSync(vendor, { recursive: true });
for (const item of fs.readdirSync(vendor, { withFileTypes: true })) {
  if (item.name === "SKILL.html" || item.name === "licenses") continue;
  fs.rmSync(path.join(vendor, item.name), { recursive: true, force: true });
}
fs.mkdirSync(path.join(vendor, "licenses"), { recursive: true });
for (const item of fs.readdirSync(path.join(vendor, "licenses"), { withFileTypes: true })) {
  if (item.name === "SKILL.html") continue;
  fs.rmSync(path.join(vendor, "licenses", item.name), { recursive: true, force: true });
}

const output = name => path.join(vendor, name);
const buildResult = async (entry, outfile, options = {}) => build({
  entryPoints: [path.join(workspace, entry)],
  outfile: output(outfile),
  bundle: true,
  minify: true,
  platform: "browser",
  target: "es2022",
  legalComments: "external",
  metafile: true,
  ...options,
});

const highlight = await buildResult("highlight-entry.js", "highlight-11.10.0.min.js", { format: "iife" });
const codemirror = await buildResult("codemirror-entry.js", `${codemirrorBase}.min.js`, { format: "iife" });
const langchain = await buildResult("langchain-entry.js", "langchain-1.4.7.esm.min.js", { format: "esm" });
const yaml = await buildResult("js-yaml-entry.js", "js-yaml-5.2.1.esm.min.js", { format: "esm" });

const copies = [
  ["highlight.js/styles/github-dark.min.css", "highlight-github-dark-11.10.0.min.css"],
  ["codemirror/lib/codemirror.css", `${codemirrorBase}.min.css`],
  ["codemirror/theme/monokai.css", `codemirror-monokai-${codemirrorVersion}.min.css`],
  ["marked/lib/marked.esm.js", "marked-14.1.4.esm.js"],
];
for (const [source, target] of copies) {
  fs.copyFileSync(path.join(modules, source), output(target));
}

function packageRoot(input) {
  const parts = input.split("/");
  const indexes = parts.map((part, index) => part === "node_modules" ? index : -1).filter(index => index >= 0);
  const index = indexes.at(-1);
  if (index === undefined) return null;
  const first = indexes[0];
  const count = parts[index + 1]?.startsWith("@") ? 2 : 1;
  return parts.slice(first, index + 1 + count).join("/");
}

function packagesFromMeta(meta) {
  return new Set(Object.keys(meta.inputs).map(packageRoot).filter(Boolean));
}

const packageRoots = new Set([
  "node_modules/highlight.js",
  "node_modules/codemirror",
  "node_modules/marked",
  ...packagesFromMeta(highlight.metafile),
  ...packagesFromMeta(codemirror.metafile),
  ...packagesFromMeta(langchain.metafile),
  ...packagesFromMeta(yaml.metafile),
]);

const purposes = {
  "highlight.js": "Syntax highlighting in course pages and source explorers.",
  "codemirror": "Editable and read-only code cells.",
  "marked": "Markdown rendering for chat output and repository documents.",
  "js-yaml": "Parsing the live OpenShell policy returned to sandbox exercises.",
  "@langchain/openai": "OpenAI-compatible browser model client used by agent exercises.",
  "@langchain/core": "Tool and message primitives used by agent exercises.",
  "@langchain/langgraph": "Agent construction and checkpoint memory used by agent exercises.",
  "zod": "Tool argument schemas used by agent exercises.",
};

function packageName(packageRootPath) {
  const parts = packageRootPath.split("node_modules/").at(-1).split("/");
  return parts[0].startsWith("@") ? `${parts[0]}/${parts[1]}` : parts[0];
}

function licenseSource(packageRootPath, name) {
  const base = path.join(workspace, packageRootPath);
  for (const candidate of fs.readdirSync(base)) {
    if (/^licen[cs]e(?:\.|$)/i.test(candidate)) return path.join(base, candidate);
  }
  const override = path.join(workspace, "license-overrides", `${name.replaceAll("/", "__")}.txt`);
  if (fs.existsSync(override)) return override;
  throw new Error(`missing license text for bundled package ${name}`);
}

const packages = [...packageRoots].map(packageRootPath => {
  const locked = lock.packages[packageRootPath];
  if (!locked?.version || !locked?.license) throw new Error(`incomplete lock metadata for ${packageRootPath}`);
  const name = packageName(packageRootPath);
  const filename = `${name.replaceAll("/", "__")}--${locked.version}.txt`;
  fs.copyFileSync(licenseSource(packageRootPath, name), path.join(vendor, "licenses", filename));
  const packageJson = JSON.parse(fs.readFileSync(path.join(workspace, packageRootPath, "package.json"), "utf8"));
  return {
    name,
    version: locked.version,
    license: locked.license,
    direct: Object.hasOwn(direct, name),
    purpose: purposes[name] || "Transitive code included by the browser agent bundle.",
    package_url: `https://www.npmjs.com/package/${name}`,
    homepage: packageJson.homepage || packageJson.repository?.url || packageJson.repository || null,
    license_file: `licenses/${filename}`,
  };
}).sort((a, b) => a.name.localeCompare(b.name) || a.version.localeCompare(b.version));

const assetPackages = {
  "highlight-11.10.0.min.js": ["highlight.js"],
  "highlight-github-dark-11.10.0.min.css": ["highlight.js"],
  [`${codemirrorBase}.min.js`]: ["codemirror"],
  [`${codemirrorBase}.min.css`]: ["codemirror"],
  [`codemirror-monokai-${codemirrorVersion}.min.css`]: ["codemirror"],
  "marked-14.1.4.esm.js": ["marked"],
  "js-yaml-5.2.1.esm.min.js": [...packagesFromMeta(yaml.metafile)].map(packageName).sort(),
  "langchain-1.4.7.esm.min.js": [...packagesFromMeta(langchain.metafile)].map(packageName).sort(),
};

const assetProvenance = {
  "highlight-11.10.0.min.js": {
    distribution_form: "transformed-bundle",
    modified_from_upstream: true,
    transformation: "Selected modules are bundled and minified with esbuild for browser delivery.",
    source_files: ["scripts/browser-vendor/highlight-entry.js"],
  },
  [`${codemirrorBase}.min.js`]: {
    distribution_form: "transformed-bundle",
    modified_from_upstream: true,
    transformation: "Selected modules are bundled and minified with esbuild for browser delivery.",
    source_files: ["scripts/browser-vendor/codemirror-entry.js"],
  },
  "langchain-1.4.7.esm.min.js": {
    distribution_form: "transformed-bundle",
    modified_from_upstream: true,
    transformation: "Selected modules are bundled and minified with esbuild for browser ESM delivery.",
    source_files: ["scripts/browser-vendor/langchain-entry.js"],
  },
  "js-yaml-5.2.1.esm.min.js": {
    distribution_form: "transformed-bundle",
    modified_from_upstream: true,
    transformation: "Selected modules are bundled and minified with esbuild for browser ESM delivery.",
    source_files: ["scripts/browser-vendor/js-yaml-entry.js"],
  },
  "highlight-github-dark-11.10.0.min.css": {
    distribution_form: "upstream-file-copy",
    modified_from_upstream: false,
    transformation: "Copied byte-for-byte from the pinned npm package; only the destination filename is selected here.",
    source_files: ["scripts/browser-vendor/node_modules/highlight.js/styles/github-dark.min.css"],
  },
  [`${codemirrorBase}.min.css`]: {
    distribution_form: "upstream-file-copy",
    modified_from_upstream: false,
    transformation: "Copied byte-for-byte from the pinned npm package; only the destination filename is selected here.",
    source_files: ["scripts/browser-vendor/node_modules/codemirror/lib/codemirror.css"],
  },
  [`codemirror-monokai-${codemirrorVersion}.min.css`]: {
    distribution_form: "upstream-file-copy",
    modified_from_upstream: false,
    transformation: "Copied byte-for-byte from the pinned npm package; only the destination filename is selected here.",
    source_files: ["scripts/browser-vendor/node_modules/codemirror/theme/monokai.css"],
  },
  "marked-14.1.4.esm.js": {
    distribution_form: "upstream-file-copy",
    modified_from_upstream: false,
    transformation: "Copied byte-for-byte from the pinned npm package; only the destination filename is selected here.",
    source_files: ["scripts/browser-vendor/node_modules/marked/lib/marked.esm.js"],
  },
};

const sourceRoots = [path.join(root, "web"), path.join(root, "i18n")];
const sourceFiles = [];
function walk(directory) {
  if (!fs.existsSync(directory)) return;
  for (const item of fs.readdirSync(directory, { withFileTypes: true })) {
    const full = path.join(directory, item.name);
    const rel = path.relative(root, full).replaceAll(path.sep, "/");
    if (item.isDirectory()) {
      if (!rel.includes("/vendor") && !rel.includes("/standalone") && !rel.includes("/mats")) walk(full);
    } else if (/\.(?:html|js|mjs|css)$/.test(item.name)) {
      sourceFiles.push([rel, fs.readFileSync(full, "utf8")]);
    }
  }
}
sourceRoots.forEach(walk);

const assets = Object.keys(assetPackages).sort().map(file => {
  const bytes = fs.readFileSync(output(file));
  const references = [];
  for (const [source, text] of sourceFiles) {
    text.split(/\r?\n/).forEach((line, index) => {
      if (line.includes(file)) references.push({ source, line: index + 1 });
    });
  }
  references.sort((a, b) => a.source.localeCompare(b.source) || a.line - b.line);
  return {
    file,
    ...assetProvenance[file],
    media_type: file.endsWith(".css") ? "text/css" : "text/javascript",
    bytes: bytes.length,
    sha256: crypto.createHash("sha256").update(bytes).digest("hex"),
    packages: assetPackages[file],
    references,
  };
});

const legalNotices = fs.readdirSync(vendor).filter(file => file.endsWith(".LEGAL.txt")).sort().map(file => {
  const bytes = fs.readFileSync(output(file));
  return {
    file,
    bytes: bytes.length,
    sha256: crypto.createHash("sha256").update(bytes).digest("hex"),
  };
});

function purl(name, version) {
  if (name.startsWith("@")) {
    const [scope, packageName] = name.split("/");
    return `pkg:npm/${encodeURIComponent(scope)}/${packageName}@${version}`;
  }
  return `pkg:npm/${name}@${version}`;
}

const sbomPath = output("browser-sbom.cdx.json");
const sbom = {
  bomFormat: "CycloneDX",
  specVersion: "1.6",
  version: 1,
  metadata: {
    component: {
      type: "application",
      name: "nemoclaw-student-browser-runtime",
      version: "source",
      "bom-ref": "nemoclaw-student-browser-runtime",
    },
  },
  components: packages.map(item => ({
    type: "library",
    name: item.name,
    version: item.version,
    purl: purl(item.name, item.version),
    "bom-ref": purl(item.name, item.version),
    licenses: [{ license: { id: item.license } }],
    properties: [{ name: "nemoclaw:relationship", value: item.direct ? "direct" : "transitive" }],
  })),
};
fs.writeFileSync(sbomPath, JSON.stringify(sbom, null, 2) + "\n");
const sbomBytes = fs.readFileSync(sbomPath);

const manifest = {
  schema: "nemoclaw-browser-dependencies/1",
  delivery: "same-origin-vendored",
  generated_from: [
    "scripts/browser-vendor/package.json",
    "scripts/browser-vendor/package-lock.json",
    "scripts/browser-vendor/highlight-entry.js",
    "scripts/browser-vendor/codemirror-entry.js",
    "scripts/browser-vendor/js-yaml-entry.js",
    "scripts/browser-vendor/langchain-entry.js",
    "web/ and i18n/ runtime references",
  ],
  lock_sha256: crypto.createHash("sha256").update(fs.readFileSync(lockPath)).digest("hex"),
  packages,
  assets,
  legal_notices: legalNotices,
  sbom: {
    file: "browser-sbom.cdx.json",
    bytes: sbomBytes.length,
    sha256: crypto.createHash("sha256").update(sbomBytes).digest("hex"),
    component_count: packages.length,
  },
};
fs.writeFileSync(output("browser-dependencies.json"), JSON.stringify(manifest, null, 2) + "\n");
console.log(`browser vendor: ${packages.length} packages, ${assets.length} assets -> web/nemoclaw/vendor/`);
