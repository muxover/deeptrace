"use strict";

const path = require("path");
const fs = require("fs");
const inspector = require("inspector");
const { pathToFileURL, fileURLToPath } = require("url");

function parseArgs(argv) {
  const opts = { root: null, output: null, top: 30, target: null, targetArgs: [], help: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--root") opts.root = argv[++i];
    else if (a === "--output") opts.output = argv[++i];
    else if (a === "--top") opts.top = parseInt(argv[++i], 10);
    else if (a === "--help" || a === "-h") opts.help = true;
    else { opts.target = a; opts.targetArgs = argv.slice(i + 1); break; }
  }
  return opts;
}

function usage() {
  return [
    "usage: node trace-node.js [--root DIR] [--output FILE] [--top N] <entry.js|.ts> [args...]",
    "",
    "Runs a Node or TypeScript entry point under the V8 sampling profiler and prints",
    "the project-scoped call tree, hot functions, and any uncaught error.",
  ].join("\n");
}

function enableTypeScript(target) {
  if (!/\.(ts|tsx|mts|cts)$/.test(target)) return true;
  try {
    require.resolve("tsx");
  } catch (e) {
    console.error("error: TypeScript entry detected but the 'tsx' loader is not installed.");
    console.error("install: npm i -D tsx   (or compile to JS first, then trace the output)");
    return false;
  }
  try {
    const { register } = require("node:module");
    register("tsx/esm", pathToFileURL("./"));
    require("tsx/cjs");
  } catch (e) {
    console.error(`error: could not enable the tsx loader: ${e.message}`);
    console.error("note: tsx registration needs Node 20.6+; on older Node, compile to JS first.");
    return false;
  }
  return true;
}

function toLocalPath(url) {
  if (!url) return null;
  if (url.startsWith("file://")) {
    try { return fileURLToPath(url); } catch (e) { return null; }
  }
  if (url.startsWith("node:") || url.startsWith("internal/")) return null;
  return url;
}

function report(profile, root, opts, failure) {
  const byId = new Map(profile.nodes.map((n) => [n.id, n]));
  const inScope = new Map();

  const resolve = (cf) => {
    const local = toLocalPath(cf.url);
    if (!local) return null;
    const abs = path.resolve(local);
    if (!abs.startsWith(root)) return null;
    return path.relative(root, abs);
  };

  const lines = [];
  const seen = new Set();
  const walk = (id, depth) => {
    if (seen.has(id)) return;
    seen.add(id);
    const node = byId.get(id);
    if (!node) return;
    const rel = resolve(node.callFrame);
    let nextDepth = depth;
    if (rel !== null) {
      const name = node.callFrame.functionName || "(anonymous)";
      const line = (node.callFrame.lineNumber || 0) + 1;
      lines.push("  ".repeat(depth) + `-> ${rel}:${line} ${name} [${node.hitCount} samples]`);
      inScope.set(id, { rel, name, line, hits: node.hitCount });
      nextDepth = depth + 1;
    }
    for (const child of node.children || []) walk(child, nextDepth);
  };
  walk(profile.nodes[0].id, 0);

  const out = ["EXECUTION TRACE (sampled)", "=".repeat(24), ""];
  out.push(lines.length ? lines.join("\n") : "(no in-scope frames sampled; the run may be too short)");
  out.push("");
  out.push("HOT FUNCTIONS (by self samples)");
  const hot = [...inScope.values()].filter((f) => f.hits > 0).sort((a, b) => b.hits - a.hits);
  if (hot.length) {
    for (const f of hot.slice(0, opts.top)) out.push(`  ${String(f.hits).padStart(5)}  ${f.name}  ${f.rel}:${f.line}`);
  } else {
    out.push("  (no samples landed in project code)");
  }
  if (failure) {
    out.push("");
    out.push(`UNCAUGHT: ${failure.stack || failure}`);
  }

  const text = out.join("\n");
  if (opts.output) {
    fs.writeFileSync(opts.output, text + "\n");
    console.log(`trace written to ${opts.output}`);
  } else {
    console.log(text);
  }
}

async function main() {
  const opts = parseArgs(process.argv.slice(2));
  if (opts.help || !opts.target) {
    console.log(usage());
    return opts.target ? 0 : 2;
  }

  const target = path.resolve(opts.target);
  if (!fs.existsSync(target)) {
    console.error(`error: ${opts.target} not found`);
    return 2;
  }
  const root = opts.root ? path.resolve(opts.root) : path.dirname(target);

  if (!enableTypeScript(target)) return 2;

  const session = new inspector.Session();
  session.connect();
  const post = (method, params) =>
    new Promise((resolve, reject) =>
      session.post(method, params || {}, (err, res) => (err ? reject(err) : resolve(res)))
    );

  let finished = false;
  const finish = async (failure) => {
    if (finished) return;
    finished = true;
    const { profile } = await post("Profiler.stop");
    session.disconnect();
    report(profile, root, opts, failure);
  };

  await post("Profiler.enable");
  await post("Profiler.setSamplingInterval", { interval: 50 });
  await post("Profiler.start");

  process.argv = [process.argv[0], target, ...opts.targetArgs];
  process.on("beforeExit", () => { finish(null); });
  process.on("uncaughtException", (err) => { finish(err).then(() => process.exit(1)); });

  try {
    require(target);
  } catch (err) {
    if (err && err.code === "ERR_REQUIRE_ESM") {
      await import(pathToFileURL(target).href).catch((e) => finish(e));
    } else {
      await finish(err);
    }
  }
}

main().then((code) => { if (code) process.exit(code); });
