"use strict";
/*
 * engine.js: the SINGLE link-graph engine for the task1 bundle.
 *
 * One implementation, two runtimes:
 *   - BROWSER: scripts/link_graph.html loads this and computes the graph live from the
 *     JupyterLab contents API (the viewer is what humans + agents actually read).
 *   - NODE:    `node scripts/engine.js --check | --self-test | --graph PATH | --embed`
 *     runs the exact same code headless for CI (pre-push, the DGX watcher). The dli
 *     volume is bind-mounted to the host tree, so the lab container's node sees the same
 *     files being pushed; the CI wrapper resolves `node` on PATH, else `docker exec` lab.
 *
 * It REPLACES the python link_projection.py graph engine. There is no second engine to
 * drift from: resolution, crawl, graph, reachability, the foyer contract, and the
 * self-test all live here. v12-compatible (no optional chaining / nullish coalescing),
 * since the lab container ships node v12.
 *
 * Models how a WRITTEN link projects through the deploy "compiler": nginx routes +
 * redirects, Jupyter extra_static_paths, the dli bind, docker-compose topology, down to a
 * physical repo-relative file or a service. Paths are repo-relative throughout (rooted at
 * task1), which is what the browser already works in.
 */
(function (root, factory) {
  if (typeof module !== "undefined" && module.exports) module.exports = factory();
  else root.LinkEngine = factory();
})(typeof self !== "undefined" ? self : this, function () {

  // ── constants ──────────────────────────────────────────────────────────────
  var DLI = "/sandbox/dli";
  var PAGE_EXT = [".md", ".ipynb", ".html", ".htm"];
  var ASSET_EXT = [".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", ".css", ".js",
    ".mjs", ".woff", ".woff2", ".ttf", ".mp4", ".webm", ".json", ".pdf"];
  // The crawl boundary: which directories are NOT a source of navigable pages. This is by KIND,
  // not by which course a path belongs to (the page extension and reachability decide everything
  // about content; this only keeps non-source bytes out of the candidate set):
  //   - dependency / build / cache dirs that recur in any repo (node_modules, __pycache__, the
  //     dot-prefixed tool caches, dist/build/venv);
  //   - generated output this bundle writes and gitignores (export, standalone, grounding_cache,
  //     docs/validation), all regenerated, never authored, surfaced live through the gate report;
  //   - service seed data (skills-seed: the openclaw agent's own SKILL.md skill definitions),
  //     which the service loads at runtime and is not part of the course's navigable graph.
  // It is deliberately NOT a list of "these course dirs are assets"; that assumption is gone.
  var SKIP_DIR = setOf(["__pycache__", ".ipynb_checkpoints", ".pytest_cache", ".jupyter",
    "node_modules", ".figtools", "export", "standalone", "dist", "build", "venv", ".venv",
    "skills-seed", "grounding_cache", "validation", ".git", ".cache",
    "i18n"]);   // staged translation content (a copy of web/), not part of the source graph

  // mats are the curated reference layer, now COURSE-SCOPED under web/nemoclaw/mats/ (no longer
  // a top-level peer). They are recognized by the "mats" path SEGMENT anywhere in the path, not
  // by a top-level dir. MAT_REL is the canonical repo-relative location of the packets.
  var MAT_REL = "web/nemoclaw/mats";
  function isMatPath(r) { return r.split("/").indexOf("mats") >= 0; }

  var SHIP_PREFIXES = ["web/nemoclaw/", "web/index", "web/courses",
    "cpu/services/", "docs/", "scripts/"];
  var SHIP_HUBS = setOf(["SKILL.html", "web/SKILL.html", "cpu/SKILL.html"]);

  // Release contract: the courses the release foyer (web/index.html) may surface.
  var RELEASED = ["nemoclaw"];

  // mats now live UNDER web/ (already a crawl root that recurses), so "mats" is no longer a
  // separate top-level crawl root or shared TOPDIR. It is still shared infra, detected by segment.
  var SHARED_SUBDIRS = setOf(["mats", "repos", "services"]);
  var SHARED_TOPDIRS = setOf(["repos", "scripts", "docs"]);
  var CRAWL_TOP = ["web", "cpu", "docs", "scripts"];

  var TEMPLATE_MARK = ["{{", "}}", "<?", "?>", "<%", "%>", "${", "&lt;", "&gt;", "&#"];

  var NOISE_HOST = setOf(["localhost", "127.0.0.1", "0.0.0.0", "example.com", "bring-up.sh", "skill.md",
    "cdnjs.cloudflare.com", "cdn.jsdelivr.net", "unpkg.com",
    "fonts.googleapis.com", "fonts.gstatic.com", "dli-lms.s3.amazonaws.com"]);

  function setOf(a) { var s = {}; for (var i = 0; i < a.length; i++) s[a[i]] = 1; return s; }
  function has(s, k) { return Object.prototype.hasOwnProperty.call(s, k); }

  // ── small pure helpers ───────────────────────────────────────────────────────
  function lc(s) { return (s || "").toLowerCase(); }
  function baseName(p) { var a = p.split("/"); return a[a.length - 1]; }
  function extOf(fn) { var i = fn.lastIndexOf("."); return i < 0 ? "" : fn.slice(i); }
  function startsWithAny(s, arr) { for (var i = 0; i < arr.length; i++) if (s.indexOf(arr[i]) === 0) return true; return false; }
  function endsWithAny(s, arr) { for (var i = 0; i < arr.length; i++) { var x = arr[i]; if (s.length >= x.length && s.slice(-x.length) === x) return true; } return false; }

  function junkFile(fn) {
    return fn.indexOf("._") === 0 || (fn.length >= 15 && fn.slice(-15) === ".nbconvert.ipynb") || fn.indexOf("-checkpoint.") >= 0;
  }
  function isTemplateLink(t) { for (var i = 0; i < TEMPLATE_MARK.length; i++) if (t.indexOf(TEMPLATE_MARK[i]) >= 0) return true; return false; }
  function isAsset(p) { return ASSET_EXT.indexOf(lc(extOf(baseName(p.split("#")[0].split("?")[0])))) >= 0; }

  function courseOf(p) {
    var parts = p.split("/").filter(function (x) { return x; });
    if (parts.length < 2) return "_shared";
    if (parts[parts.length - 1] === "SKILL.html" && parts.length <= 2) return "_shared";
    if (parts[0] === "docs") return "_shared";
    // mats are the shared reference layer wherever they sit (now under web/nemoclaw/mats/),
    // so a mats path classifies as _shared, not as the enclosing course.
    if (isMatPath(p)) return "_shared";
    if (parts[0] === "web" || parts[0] === "cpu") {
      if (has(SHARED_SUBDIRS, parts[1])) return "_shared";
      if (parts.length === 2 && parts[1].indexOf(".") >= 0) {
        return "_shared";   // a file directly under web/ (index.html picker, courses.html, SKILL.html)
      }
      return parts[1];
    }
    if (parts[0] === "workspace") return "_shared";
    if (has(SHARED_TOPDIRS, parts[0])) return "_shared";
    return parts[0];
  }

  function shipRelevant(rel) {
    rel = rel.split("\\").join("/");
    var base = lc(baseName(rel));
    if (base.indexOf("example") === 0 || base.indexOf("template") === 0 || base.indexOf("sample") === 0) return false;
    if (rel.indexOf("/") < 0) return true;
    if (has(SHIP_HUBS, rel)) return true;
    return startsWithAny(rel, SHIP_PREFIXES);
  }

  function navSource(rel) {
    var parts = rel.split("/").filter(function (x) { return x; });
    var base = lc(parts.length ? parts[parts.length - 1] : "");
    // bundle-root files (README.md, SKILL.html, AGENT_QUICKSTART.md, ...) are bundle-level
    // indexes: they may reference any course. The isolation rule is course<->course.
    if (parts.length === 1) return true;
    if (["skill.html", "courses.html", "index.html"].indexOf(base) >= 0) return true;
    if (parts.indexOf("mats") >= 0) return true;
    return false;
  }

  // Structural only: a page is a graph node unless some path segment is "private" (leading
  // underscore: _shared, _tools, a leading-underscore file). No list of which dir names are
  // "assets" or "relevant" (that overfits to whatever courses happened to exist); the page
  // extension already decides page-vs-asset, and reachability decides connectedness.
  function graphNavigable(rel) {
    var parts = rel.split("/");
    for (var i = 0; i < parts.length; i++) if (parts[i].charAt(0) === "_") return false;
    return true;
  }

  function clamp(baseDir, tgt) {
    var parts = baseDir.split("/").filter(function (x) { return x; });
    var segs = tgt.split("/");
    for (var i = 0; i < segs.length; i++) {
      var seg = segs[i];
      if (seg === "" || seg === ".") continue;
      if (seg === "..") { if (parts.length) parts.pop(); }
      else parts.push(seg);
    }
    return parts.join("/");
  }

  function normUrl(u) {
    u = u.replace(/^\s+|\s+$/g, "").replace(/[.,;:!]+$/, "").split("#")[0];
    var m = /^(https?:\/\/)([^/]+)(.*)$/.exec(u);
    if (m) return m[1].toLowerCase() + m[2].toLowerCase() + m[3].replace(/\/+$/, "");
    return u.toLowerCase();
  }
  function isCitation(u) {
    var m = /^https?:\/\/([^/:]+)/.exec(u);
    if (!m) return false;
    var host = m[1].toLowerCase();
    if (has(NOISE_HOST, host) || host.indexOf("w3.org") >= 0 || /^\d+\.\d+\.\d+\.\d+$/.test(host)) return false;
    return host.indexOf(".") >= 0;
  }

  // A materials index (the *_materials.json / *materials_index.json / *glossary_index.json a page
  // fetches) is the manifest of the reference packets that page surfaces. A page that loads one is,
  // in effect, citing every source URL the index lists, so we fold those URLs into the page's
  // citation set. Citation-sharing then connects each listed packet (every mat carries its own
  // source URL) to the page that surfaces it. This is the materials mechanism's real structure,
  // not a "mats/ is special" path assumption: a packet no index names stays an honest stray.
  function collectUrls(node, out) {
    if (node == null) return;
    if (typeof node === "string") { if (/^https?:\/\//.test(node)) out.push(node); return; }
    if (typeof node === "object") { for (var k in node) if (has(node, k)) collectUrls(node[k], out); }
  }
  function indexCitations(proj, rel, raw) {
    if (raw == null) return [];
    var reIdx = /([\w./-]*(?:materials_index|glossary_index|_materials)\.json)/g;
    var refs = findAll(reIdx, raw), urls = [], seenF = {};
    for (var i = 0; i < refs.length; i++) {
      var p = refs[i]; if (has(seenF, p)) continue; seenF[p] = 1;
      var r = proj.resolve(p, rel);
      if (!(r.kind === "static_file" && r.exists && r.physical)) continue;
      var js = proj.io.read(r.physical); if (js == null) continue;
      var data; try { data = JSON.parse(js); } catch (e) { continue; }
      collectUrls(data, urls);
    }
    return urls;
  }

  // ── link extraction / non-content stripping ────────────────────────────────
  function findAll(re, s) { var out = [], m; re.lastIndex = 0; while ((m = re.exec(s))) { out.push(m[1]); if (m.index === re.lastIndex) re.lastIndex++; } return out; }
  function reHref() { return /(?:href|src)\s*=\s*["']([^"']+)["']/ig; }
  function reMd() { return /!?\[[^\]]*\]\(\s*<?([^)\s>]+)/g; }
  function reUrl() { return /(https?:\/\/[^\s)"'<>\]\[(]+)/g; }

  function stripNoncontent(text, suffix) {
    if (suffix === ".html" || suffix === ".htm") {
      text = text.replace(/(<script\b[^>]*>)[\s\S]*?(<\/script>)/ig, "$1$2");
      text = text.replace(/(<style\b[^>]*>)[\s\S]*?(<\/style>)/ig, "$1$2");
      text = text.replace(/<!--[\s\S]*?-->/g, " ");
    } else {
      text = text.replace(/```[\s\S]*?```/g, " ");
      text = text.replace(/`[^`\n]*`/g, " ");
    }
    return text;
  }

  function readForLinks(io, rel) {
    if (lc(extOf(rel)) === ".ipynb") {
      var raw = io.read(rel);
      if (raw == null) return ["", ".md"];
      var nb; try { nb = JSON.parse(raw); } catch (e) { return ["", ".md"]; }
      var md = [], cells = (nb && nb.cells) || [];
      for (var i = 0; i < cells.length; i++) {
        if (cells[i].cell_type === "markdown") {
          var s = cells[i].source;
          md.push(s && s.join ? s.join("") : (s || ""));
        }
      }
      return [md.join("\n\n"), ".md"];
    }
    var t = io.read(rel);
    return [t == null ? "" : t, lc(extOf(rel))];
  }

  function iterPages(io) { return io.walk(); }

  // ── config parsing ───────────────────────────────────────────────────────────
  function parseEntrypoint(io) {
    var out = { static_roots: [], root_dir: DLI, base_url: "/lab", default_url: "/lab/static/index.html" };
    var txt = io.read("workspace/entrypoint.sh");
    if (txt == null) return out;
    var m = /extra_static_paths\s*=\s*'(\[[^']*\])'/.exec(txt);
    if (m) { try { out.static_roots = JSON.parse(m[1]); } catch (e) { } }
    var b = /base_url\s*=\s*"([^"]+)"/.exec(txt); if (b) out.base_url = b[1];
    var d = /default_url\s*=\s*'([^']+)'/.exec(txt); if (d) out.default_url = d[1];
    return out;
  }

  function parseCompose(io) {
    var files = ["docker-compose.yml", "docker-compose.override.yml"];
    var services = {}, aliases = {}, dliDevice = null;
    function mergeService(name, ondemand, al) {
      if (!has(services, name)) services[name] = { ondemand: false, aliases: [] };
      if (ondemand) services[name].ondemand = true;
      if (al) for (var i = 0; i < al.length; i++) if (services[name].aliases.indexOf(al[i]) < 0) services[name].aliases.push(al[i]);
    }
    for (var fi = 0; fi < files.length; fi++) {
      var txt = io.read(files[fi]); if (txt == null) continue;
      var lines = txt.split("\n"), inServices = false, cur = null;
      for (var li = 0; li < lines.length; li++) {
        var ln = lines[li];
        if (/^services:\s*$/.test(ln)) { inServices = true; continue; }
        if (inServices && /^\S/.test(ln)) inServices = false;
        if (!inServices) { if (ln.indexOf("device:") >= 0 && ln.indexOf("${PWD}") >= 0) dliDevice = "${PWD}"; continue; }
        var m = /^  ([a-zA-Z0-9_-]+):\s*$/.exec(ln);
        if (m) { cur = m[1]; mergeService(cur, false, null); }
        else if (cur && /^\s+profiles:/.test(ln)) mergeService(cur, true, null);
        else if (cur && /^\s+-\s*openshell\s*$/.test(ln)) { mergeService(cur, false, ["openshell"]); aliases["openshell"] = cur; }
      }
    }
    if (dliDevice === "${PWD}" || dliDevice == null) dliDevice = "";   // repo root
    return { services: services, aliases: aliases, dli_device: dliDevice };
  }

  function parseUpstreams(txt) {
    var out = {}, m, re = /upstream\s+([\w-]+)\s*\{([^}]*)\}/g;
    while ((m = re.exec(txt))) { var sv = /server\s+([\w.\-]+):(\d+)/.exec(m[2]); if (sv) out[m[1]] = [sv[1], parseInt(sv[2], 10)]; }
    return out;
  }
  function splitLocationBlocks(txt) {
    var out = [], i = 0, n = txt.length;
    while (true) {
      var re = /location\s+([^\{]+?)\s*\{/g; re.lastIndex = i;
      var m = re.exec(txt); if (!m) return out;
      var header = m[1].replace(/^\s+|\s+$/g, ""); var start = m.index + m[0].length;
      var depth = 1, j = start;
      while (j < n && depth) { var c = txt[j]; if (c === "{") depth++; else if (c === "}") depth--; j++; }
      out.push([header, txt.slice(start, j - 1)]); i = j;
    }
  }
  function NginxRule(header, body, upstreams) {
    if (header.indexOf("= ") === 0) { this.match = "exact"; this.pattern = header.slice(2).replace(/^\s+|\s+$/g, ""); }
    else if (header.indexOf("~* ") === 0 || header.indexOf("~ ") === 0) { this.match = "regex"; this.pattern = header.split(" ").slice(1).join(" ").replace(/^\s+|\s+$/g, ""); }
    else if (header.indexOf("@") === 0) { this.match = "named"; this.pattern = header; }
    else { this.match = "prefix"; this.pattern = header.replace(/^\s+|\s+$/g, ""); }
    this.kind = "static"; this.redirect = null; this.rewrite = null; this.upstream = null;
    var rt = /return\s+30[12]\s+(\S+?);/.exec(body);
    if (rt) { this.kind = "redirect"; this.redirect = rt[1]; }
    var rw = /rewrite\s+(\S+)\s+(\S+)\s+break;/.exec(body);
    if (rw) this.rewrite = [rw[1], rw[2]];
    var pp = /proxy_pass\s+(\S+?);/.exec(body);
    if (pp) {
      var target = pp[1], host = null, port = null;
      var vm = /^\$(\w+)/.exec(target);
      if (vm) { var sm = new RegExp("set\\s+\\$" + vm[1] + "\\s+https?://([\\w.\\-]+):(\\d+)").exec(body); if (sm) { host = sm[1]; port = parseInt(sm[2], 10); } }
      else { var lm = /^https?:\/\/([\w.\-]+):?(\d+)?/.exec(target); if (lm) { host = lm[1]; port = lm[2] ? parseInt(lm[2], 10) : null; } }
      if (host && has(upstreams, host)) { var up = upstreams[host]; host = up[0]; port = up[1]; }
      if (host) { this.kind = "proxy"; this.upstream = [host, port]; }
    }
    if (/return\s+404/.test(body) && this.match === "regex") this.kind = "guard404";
  }
  function parseNginx(io) {
    var txt = io.read("nginx.conf"); if (txt == null) return { rules: [], upstreams: {} };
    var ups = parseUpstreams(txt), blocks = splitLocationBlocks(txt), rules = [];
    for (var i = 0; i < blocks.length; i++) rules.push(new NginxRule(blocks[i][0], blocks[i][1], ups));
    return { rules: rules, upstreams: ups };
  }

  // ── resolution ───────────────────────────────────────────────────────────────
  function Resolution(o) {
    this.kind = o.kind; this.physical = o.physical != null ? o.physical : null; this.exists = !!o.exists;
    this.service = o.service != null ? o.service : null; this.ondemand = o.ondemand != null ? o.ondemand : null;
    this.course = o.course != null ? o.course : null; this.reason = o.reason || ""; this.chain = o.chain || [];
  }

  function Projection(io) {
    this.io = io;
    this.ep = parseEntrypoint(io);
    this.compose = parseCompose(io);
    this.nginx = parseNginx(io);
    var roots = [];
    for (var i = 0; i < this.ep.static_roots.length; i++) { var c = this.c2h(this.ep.static_roots[i]); if (c != null) roots.push(c); }
    this.staticRoots = roots.length ? roots : [""];
  }
  Projection.prototype.c2h = function (cpath) {
    if (cpath === DLI) return "";
    if (cpath.indexOf(DLI + "/") === 0) return cpath.slice(DLI.length + 1);
    return null;
  };
  Projection.prototype.exists = function (rel) {
    if (this.io.exists(rel)) return true;
    if (rel.length >= 6 && rel.slice(-6) === ".ipynb" && this.io.exists(rel.slice(0, -6) + ".md")) return true;
    if (rel.length >= 3 && rel.slice(-3) === ".md" && this.io.exists(rel.slice(0, -3) + ".ipynb")) return true;
    return false;
  };
  Projection.prototype.serviceFor = function (host) {
    var svcs = this.compose.services;
    if (has(svcs, host)) return [host, svcs[host].ondemand];
    var real = this.compose.aliases[host];
    if (real && has(svcs, real)) return [real, svcs[real].ondemand];
    return [host, null];
  };
  Projection.prototype.staticRest = function (rest) {
    rest = rest.replace(/^\/+/, "");
    var cand = [];
    for (var i = 0; i < this.staticRoots.length; i++) {
      var root = this.staticRoots[i]; if (root == null) continue;
      var h = root ? root + "/" + rest : rest; cand.push(h);
      if (this.exists(h)) return new Resolution({ kind: "static_file", physical: h, exists: true, course: courseOf(h), reason: "extra_static_paths hit", chain: ["/lab/static", "extra_static_paths"] });
    }
    var first = cand.length ? cand[0] : rest;
    return new Resolution({ kind: "static_file", physical: first, exists: false, course: courseOf(first), reason: "no extra_static_paths root serves it", chain: ["/lab/static", "extra_static_paths"] });
  };
  Projection.prototype.treeRest = function (rest) {
    rest = rest.replace(/^\/+/, "").replace(/\/+$/, "");
    return new Resolution({ kind: "lab_tree", physical: rest, exists: this.io.exists(rest), course: courseOf(rest), reason: "JupyterLab file tree", chain: ["/lab/tree"] });
  };
  Projection.prototype.matchNginx = function (path) {
    var rules = this.nginx.rules, i;
    for (i = 0; i < rules.length; i++) if (rules[i].match === "exact" && rules[i].pattern === path) return rules[i];
    for (i = 0; i < rules.length; i++) if (rules[i].match === "regex") { try { if (new RegExp(rules[i].pattern, "i").test(path)) return rules[i]; } catch (e) { } }
    var best = null;
    for (i = 0; i < rules.length; i++) { var r = rules[i]; if (r.match === "prefix" && path.indexOf(r.pattern) === 0) { if (best === null || r.pattern.length > best.pattern.length) best = r; } }
    return best;
  };
  Projection.prototype.dispatchLab = function (path, chain) {
    var m = /^\/lab\/static\/(.+)$/.exec(path);
    if (m) { var r = this.staticRest(m[1]); r.chain = chain.concat(r.chain); return r; }
    m = /^\/lab\/(?:lab\/)?tree\/(.+)$/.exec(path);
    if (m) { var r2 = this.treeRest(m[1]); r2.chain = chain.concat(r2.chain); return r2; }
    return new Resolution({ kind: "runtime", physical: null, exists: true, reason: "JupyterLab runtime route", course: "_shared", chain: chain });
  };
  Projection.prototype.resolve = function (href, fromRepo, depth) {
    fromRepo = fromRepo || ""; depth = depth || 0;
    var t = (href || "").split("#")[0].split("?")[0].replace(/^\s+|\s+$/g, "");
    if (!t) return new Resolution({ kind: "empty", exists: true, reason: "anchor/empty" });
    if (/^(https?:|mailto:|tel:|data:|\/\/)/.test(t)) return new Resolution({ kind: "external", exists: true, reason: "external", course: "_shared" });
    if (depth > 6) return new Resolution({ kind: "unresolved", exists: false, reason: "redirect loop" });
    if (t.charAt(0) !== "/") {
      var baseDir = fromRepo.split("/").slice(0, -1).join("/");
      var rel = clamp(baseDir, t);
      return new Resolution({ kind: "static_file", physical: rel, exists: this.exists(rel), course: courseOf(rel), reason: "relative", chain: [fromRepo] });
    }
    var rule = this.matchNginx(t);
    if (rule === null) return this.dispatchLab(t, ["(no nginx match)"]);
    if (rule.kind === "guard404") return new Resolution({ kind: "guarded", physical: null, exists: false, reason: "nginx secret-guard 404", chain: [rule.pattern] });
    if (rule.kind === "redirect") {
      var tgt = rule.redirect.split("$is_args$args").join("").split("$args").join("");
      var r = this.resolve(tgt, fromRepo, depth + 1);
      r.chain = ["302 " + rule.pattern + " -> " + tgt].concat(r.chain || []);
      if ((r.kind === "static_file" || r.kind === "lab_tree") && !r.exists) r.reason = "dead redirect: " + tgt + " -> " + r.reason;
      return r;
    }
    if (rule.kind === "proxy") {
      var host = rule.upstream[0], port = rule.upstream[1];
      if (host === "lab") return this.dispatchLab(t, ["proxy " + rule.pattern + " -> lab:" + port]);
      var sf = this.serviceFor(host);
      return new Resolution({ kind: "service", physical: host + ":" + port, exists: has(this.compose.services, sf[0]), service: sf[0], ondemand: sf[1], course: "_shared", reason: sf[1] ? "on-demand service (profile)" : "service", chain: ["proxy " + rule.pattern + " -> " + host + ":" + port] });
    }
    return this.dispatchLab(t, [rule.match + " " + rule.pattern]);
  };

  // ── graph snapshot (viewer DATA + offline embed) ──────────────────────────────
  function isMat(r) { return isMatPath(r); }
  function isCross(a, b) { return a !== b && a !== "_shared" && b !== "_shared"; }

  function graphJson(proj) {
    var io = proj.io;
    var pages = [], all = iterPages(io), i, m;
    for (i = 0; i < all.length; i++) { var e = lc(extOf(all[i])); if (e === ".html" || e === ".htm" || e === ".md" || e === ".ipynb") pages.push(all[i]); }
    var pset = setOf(pages);
    var nodes = {}, edges = [], dead = [], ext = {};
    for (i = 0; i < pages.length; i++) {
      var rel = pages[i];
      var skill = baseName(rel) === "SKILL.html";
      var mat = isMat(rel);
      nodes[rel] = { id: rel, course: courseOf(rel), skill: skill, nav: graphNavigable(rel) && !mat, mat: mat, "in": 0, out: 0 };
      var rl = readForLinks(io, rel), raw = rl[0], suf = rl[1];
      var txt = stripNoncontent(raw, suf);
      var hs = (suf === ".html" || suf === ".htm") ? findAll(reHref(), raw) : findAll(reHref(), txt);
      hs = hs.concat(findAll(reMd(), txt));
      var seenH = {};
      for (var k = 0; k < hs.length; k++) {
        m = hs[k]; if (has(seenH, m)) continue; seenH[m] = 1;
        if (m.indexOf("http") === 0) { var u = normUrl(m); if (isCitation(u)) { if (!ext[rel]) ext[rel] = {}; ext[rel][u] = 1; } continue; }
        if (isTemplateLink(m) || /^(\/\/|#|mailto:|data:|tel:)/.test(m)) continue;
        var r = proj.resolve(m, rel);
        if (r.kind !== "static_file" && r.kind !== "lab_tree") continue;
        var tr = r.physical;
        if (tr && !has(pset, tr)) {
          var alt = (tr.slice(-6) === ".ipynb") ? tr.slice(0, -6) + ".md" : (tr.slice(-3) === ".md" ? tr.slice(0, -3) + ".ipynb" : null);
          tr = (alt && has(pset, alt)) ? alt : tr;
        }
        if (!tr || !has(pset, tr)) {
          // dead ONLY for a missing NAVIGABLE content page. A target under a skipped/build dir
          // (standalone/, node_modules, ...) or a private path (leading-underscore segment) is
          // outside the graph by the same structural rule graphNavigable uses, so node (fs) and
          // the browser (crawl pageset) agree to SKIP it rather than flag it dead.
          if (r.kind === "static_file" && !r.exists && /\.(html?|md|ipynb)$/.test(r.physical || "") && graphNavigable(r.physical)) dead.push({ from: rel, to: r.physical || m });
          continue;
        }
        if (tr === rel) continue;
        if (isMat(tr) && !mat) { dead.push({ from: rel, to: tr, note: "links a mats/ packet directly; link the underlying URL instead" }); continue; }
        edges.push({ f: rel, t: tr, x: isCross(courseOf(rel), courseOf(tr)), s: skill });
      }
      var iu = indexCitations(proj, rel, raw);
      for (var z = 0; z < iu.length; z++) { var cz = normUrl(iu[z]); if (isCitation(cz)) { if (!ext[rel]) ext[rel] = {}; ext[rel][cz] = 1; } }
    }
    // shared-citation edges: a mat joins only by sharing an external URL with content
    var url2mat = {}, url2content = {};
    for (var rel2 in ext) { if (!has(ext, rel2)) continue; var tgt = isMat(rel2) ? url2mat : url2content; for (var u2 in ext[rel2]) { if (!tgt[u2]) tgt[u2] = {}; tgt[u2][rel2] = 1; } }
    for (var u3 in url2mat) { if (!has(url2content, u3)) continue; for (var c in url2content[u3]) for (var mt in url2mat[u3]) edges.push({ f: c, t: mt, shared: true, via: u3, s: false }); }
    // dedupe
    var seen = {}, E2 = [];
    for (i = 0; i < edges.length; i++) { var key = edges[i].f + ">" + edges[i].t; if (!has(seen, key)) { seen[key] = 1; E2.push(edges[i]); } }
    for (i = 0; i < E2.length; i++) { if (nodes[E2[i].f]) nodes[E2[i].f].out++; if (nodes[E2[i].t]) nodes[E2[i].t]["in"]++; }
    var nlist = []; for (var id in nodes) nlist.push(nodes[id]);
    var iso = nlist.filter(function (n) { return n["in"] === 0 && n.out === 0; });
    var cross = []; for (i = 0; i < E2.length; i++) if (E2[i].x) cross.push({ from: E2[i].f, to: E2[i].t });
    var c2s = [];
    for (i = 0; i < E2.length; i++) { var ed = E2[i]; if (!ed.s && nodes[ed.t] && nodes[ed.t].skill && ed.f.split("/").length !== 2) c2s.push({ from: ed.f, to: ed.t }); }
    var issues = {
      dead: dead, cross_course: cross, child_to_skill: c2s,
      isolated: iso.filter(function (n) { return n.nav; }).map(function (n) { return n.id; }),
      isolated_assets: iso.filter(function (n) { return !n.nav; }).map(function (n) { return n.id; }), cycles: []
    };
    var summary = {
      pages: nlist.length, internal_links: E2.length, dead: dead.length,
      cross_course_violations: cross.length, child_to_skill: c2s.length,
      isolated: issues.isolated.length, clean: !(dead.length || cross.length || issues.isolated.length)
    };
    return { base: "(static snapshot from engine.js)", summary: summary, by_course: {}, issues: issues, nodes: nlist, edges: E2 };
  }

  // ── reachability / strays ──────────────────────────────────────────────────
  function reachability(proj) {
    var io = proj.io, i;
    var pages = [], all = iterPages(io);
    for (i = 0; i < all.length; i++) { var e = lc(extOf(all[i])); if (e === ".html" || e === ".htm" || e === ".md" || e === ".ipynb") pages.push(all[i]); }
    var pset = setOf(pages);
    var adjO = {}, adjI = {}, ext = {};
    for (i = 0; i < pages.length; i++) { adjO[pages[i]] = {}; adjI[pages[i]] = {}; }
    for (i = 0; i < pages.length; i++) {
      var rel = pages[i], rl = readForLinks(io, rel), raw = rl[0], suf = rl[1];
      var txt = stripNoncontent(raw, suf);
      var hs = (suf === ".html" || suf === ".htm") ? findAll(reHref(), raw) : findAll(reHref(), txt);
      hs = hs.concat(findAll(reMd(), txt));
      var seenH = {};
      for (var k = 0; k < hs.length; k++) {
        var m = hs[k]; if (has(seenH, m)) continue; seenH[m] = 1;
        if (m.indexOf("http") === 0) { var cu = normUrl(m); if (isCitation(cu)) { if (!ext[rel]) ext[rel] = {}; ext[rel][cu] = 1; } continue; }
        var t = m.split("#")[0].split("?")[0].replace(/^\s+|\s+$/g, "");
        if (!t || /^(\/\/|#|mailto:|data:|tel:)/.test(t) || isTemplateLink(m)) continue;
        var r = proj.resolve(m, rel);
        if ((r.kind !== "static_file" && r.kind !== "lab_tree") || !r.exists || !r.physical) continue;
        var tr = r.physical;
        if (tr && !has(pset, tr)) { var alt = (tr.slice(-6) === ".ipynb") ? tr.slice(0, -6) + ".md" : (tr.slice(-3) === ".md" ? tr.slice(0, -3) + ".ipynb" : null); tr = (alt && has(pset, alt)) ? alt : tr; }
        if (tr && has(pset, tr) && tr !== rel) { adjO[rel][tr] = 1; adjI[tr][rel] = 1; }
      }
      var iu = indexCitations(proj, rel, raw);
      for (var z = 0; z < iu.length; z++) { var cz = normUrl(iu[z]); if (isCitation(cz)) { if (!ext[rel]) ext[rel] = {}; ext[rel][cz] = 1; } }
    }
    // A reference packet (mats/) is never linked; its real structural tie to the course is the
    // external citation URL it shares with a page that cites the same source. Treat that shared
    // citation as a (bidirectional) connection, exactly as the graph view draws it, so a packet
    // inherits reachability from the content it documents. This replaces any "these directories
    // are expected to be detached" assumption: a page is reachable iff it is actually connected,
    // by a link or by a citation it genuinely shares.
    var url2mat = {}, url2content = {};
    for (var rel2 in ext) { if (!has(ext, rel2)) continue; var tgt = isMat(rel2) ? url2mat : url2content; for (var u2 in ext[rel2]) { if (!tgt[u2]) tgt[u2] = {}; tgt[u2][rel2] = 1; } }
    for (var u3 in url2mat) { if (!has(url2content, u3)) continue; for (var cc in url2content[u3]) for (var mt in url2mat[u3]) { adjO[cc][mt] = 1; adjI[mt][cc] = 1; adjO[mt][cc] = 1; adjI[cc][mt] = 1; } }
    var skills = pages.filter(function (p) { return baseName(p) === "SKILL.html"; });
    var reach = setOf(skills), st = skills.slice();
    while (st.length) { var u = st.pop(); for (var v in adjO[u]) if (!has(reach, v)) { reach[v] = 1; st.push(v); } }
    // weakly-connected components
    var adjU = {}; for (i = 0; i < pages.length; i++) adjU[pages[i]] = {};
    for (var a in adjO) for (var b in adjO[a]) { adjU[a][b] = 1; adjU[b][a] = 1; }
    var comp = {}, cmem = [];
    for (i = 0; i < pages.length; i++) {
      var p = pages[i]; if (has(comp, p)) continue;
      var c = cmem.length; cmem.push([]); comp[p] = c; var stk = [p];
      while (stk.length) { var x = stk.pop(); cmem[c].push(x); for (var y in adjU[x]) if (!has(comp, y)) { comp[y] = c; stk.push(y); } }
    }
    var hasSkill = cmem.map(function (mem) { for (var j = 0; j < mem.length; j++) if (baseName(mem[j]) === "SKILL.html") return true; return false; });
    var strays = [];
    for (i = 0; i < pages.length; i++) {
      var pg = pages[i]; if (has(reach, pg)) continue;
      var reason = !hasSkill[comp[pg]] ? "detached cluster (no SKILL hub)" : (objEmpty(adjI[pg]) ? "no inbound link" : "only sideways/upward; no SKILL path");
      strays.push({ page: pg, course: courseOf(pg), reason: reason, cluster: cmem[comp[pg]].length });
    }
    // Every surviving stray is real: it is connected by neither a link nor a shared citation.
    // There is no "expected to be detached" class; expected_strays stays 0 for report compatibility.
    return { pages: pages.length, reachable: objLen(reach), strays: strays, real_strays: strays.length, expected_strays: 0 };
  }
  function objEmpty(o) { for (var k in o) if (has(o, k)) return false; return true; }
  function objLen(o) { var n = 0; for (var k in o) if (has(o, k)) n++; return n; }

  // ── link check (CI failures / leaks / cross / mat-links) ──────────────────────
  function check(proj) {
    var io = proj.io, report = { failures: [], asset_leaks: [], cross_course: [], mat_links: [], stats: {} };
    var pages = 0, links = 0, all = iterPages(io), i;
    for (i = 0; i < all.length; i++) {
      var rel = all[i]; pages++;
      var srcCourse = courseOf(rel), ship = shipRelevant(rel);
      var rl = readForLinks(io, rel), raw = rl[0], suf = rl[1];
      var txt = stripNoncontent(raw, suf);
      var raws = {}, hh = findAll(reHref(), txt).concat(findAll(reMd(), txt));
      for (var z = 0; z < hh.length; z++) raws[hh[z]] = 1;
      for (var rawk in raws) {
        if (!has(raws, rawk)) continue;
        var t = rawk.split("#")[0].split("?")[0].replace(/^\s+|\s+$/g, "");
        if (!t || /^(https?:|mailto:|tel:|data:|\/\/)/.test(t)) continue;
        if (isTemplateLink(rawk)) continue;
        links++;
        var r = proj.resolve(rawk, rel);
        var asset = isAsset(t);
        if ((r.kind === "static_file" || r.kind === "lab_tree") && !r.exists)
          report.failures.push({ page: rel, link: rawk, resolved: r.physical, ship: ship, reason: r.reason, chain: r.chain, kind: r.kind });
        if (r.kind === "service" && r.exists === false)
          report.failures.push({ page: rel, link: rawk, service: r.service, ship: ship, reason: "service not declared in compose", chain: r.chain });
        if (r.kind === "static_file" && r.physical && /\/mats\/[^?]*\.(md|html?)$/.test(r.physical) && !navSource(rel) && ("/" + rel).indexOf("/mats/") < 0)
          report.mat_links.push({ page: rel, link: rawk, resolved: r.physical, ship: ship });
        var tgt = r.course;
        if (tgt && tgt !== "_shared" && tgt !== null && tgt !== srcCourse && (r.kind === "static_file" || r.kind === "lab_tree") && !navSource(rel)) {
          var rec = { page: rel, src_course: srcCourse, link: rawk, ship: ship, tgt_course: tgt, resolved: r.physical, exists: r.exists };
          if (asset) { rec.isolate = "copy/move asset into " + srcCourse + "/ or promote to the course mats/"; report.asset_leaks.push(rec); }
          else report.cross_course.push(rec);
        }
      }
    }
    function blk(key) { var n = 0; for (var j = 0; j < report[key].length; j++) if (report[key][j].ship) n++; return n; }
    report.stats = {
      pages: pages, links: links, failures: report.failures.length, asset_leaks: report.asset_leaks.length,
      cross_course: report.cross_course.length, mat_links: report.mat_links.length,
      blocking_failures: blk("failures"), blocking_asset_leaks: blk("asset_leaks"),
      blocking_cross_course: blk("cross_course"), blocking_mat_links: blk("mat_links")
    };
    return report;
  }

  // ── release-foyer contract ─────────────────────────────────────────────────
  function foyerReleaseCheck(proj) {
    var io = proj.io;
    var out = { ok: false, released: RELEASED.slice(), exists: io.exists("web/index.html"), declared: null, declared_ok: false, entries_ok: true, surfaced_courses: [], violations: [] };
    var raw = io.read("web/index.html");
    if (raw == null) { out.violations.push({ kind: "missing", detail: "web/index.html not found" }); return out; }
    var noComments = raw.replace(/<!--[\s\S]*?-->/g, " ");
    var m = /<script[^>]*id=["']foyer-release["'][^>]*>([\s\S]*?)<\/script>/i.exec(noComments);
    if (!m) out.violations.push({ kind: "no_meta", detail: "no <script id=foyer-release> contract block in the foyer" });
    else {
      try {
        var meta = JSON.parse(m[1]);
        out.declared = meta.released || null;
        out.declared_ok = JSON.stringify(meta.released || []) === JSON.stringify(RELEASED);
        if (!out.declared_ok) out.violations.push({ kind: "declared_mismatch", detail: "foyer declares " + JSON.stringify(meta.released) + ", enforced " + JSON.stringify(RELEASED) });
        var entries = meta.entries || {};
        for (var cid in entries) {
          if (!has(entries, cid)) continue;
          var r = proj.resolve(entries[cid], "web/index.html");
          if (!((r.kind === "static_file" || r.kind === "lab_tree") && r.exists)) { out.entries_ok = false; out.violations.push({ kind: "dead_entry", detail: cid + " entry " + entries[cid] + " -> " + r.reason }); }
        }
      } catch (e) { out.violations.push({ kind: "bad_meta", detail: "foyer-release JSON: " + e.message }); }
    }
    var txt = stripNoncontent(raw, ".html");
    var surfaced = {}, hh = findAll(reHref(), txt);
    for (var i = 0; i < hh.length; i++) {
      var href = hh[i], t = href.split("#")[0].split("?")[0].replace(/^\s+|\s+$/g, "");
      if (!t || /^(http|\/\/|mailto:|data:|tel:)/.test(t) || isTemplateLink(href)) continue;
      var rr = proj.resolve(href, "web/index.html");
      if (rr.kind !== "static_file" && rr.kind !== "lab_tree") continue;
      var cc = rr.course;
      if (cc && cc !== "_shared" && cc !== null) { if (!surfaced[cc]) surfaced[cc] = []; surfaced[cc].push(href); }
    }
    out.surfaced_courses = Object.keys(surfaced).sort();
    for (var c2 = 0; c2 < out.surfaced_courses.length; c2++) {
      var c = out.surfaced_courses[c2];
      if (RELEASED.indexOf(c) < 0) out.violations.push({ kind: "unreleased_course", detail: "foyer surfaces unreleased course '" + c + "' via " + surfaced[c][0] });
    }
    out.ok = out.violations.length === 0;
    return out;
  }

  // ── per-page drift audit (every .html auto-verifies against the same engine) ──
  // Detects, for EACH .html in the tree: stale tokens (course code + deprecated paths that
  // should never appear in the content root), missing local assets (img/css/js it loads),
  // and contract drift (skill-meta children that no longer resolve; a foyer-release block
  // that disagrees with RELEASED). This is the tree-wide "is this page up to date" check; it
  // runs in CI (--audit) and the in-page self-tests call the same rules in the browser.
  // Only patterns that are UNAMBIGUOUSLY stale anywhere in the content root. SKILL.md stays
  // off this list because agent-skills legitimately use it; flagging it would be a false
  // positive, and a noisy detector is worse than none.
  var STALE_TOKENS = [
    { re: /s-fx-43-v1/, why: "course code is an above-task1 wrapper detail; never name it in the content root",
      // the DLI-LMS navigator addresses the course's hosted assets by their dli-lms S3 path, which
      // carries the course code; there it is the functional deployment URL, not a leaked detail.
      exceptFile: /(^|\/)edx_navigator_quick\.html$/ },
    { re: /archived_courses\//, why: "archived_courses is removed" },
    { re: /\bscaffold\//, why: "scaffold was removed; task1 is canonical" },
    { re: /workspace\/build_agents\//, why: "pre-migration path for a course no longer in this release; flag any regression that reintroduces it" }
  ];
  var AUDIT_ASSET_EXT = [".css", ".js", ".mjs", ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico"];

  function pageAudit(proj) {
    var io = proj.io, out = [], all = iterPages(io), i;
    for (i = 0; i < all.length; i++) {
      var rel = all[i];
      if (lc(extOf(rel)) !== ".html" && lc(extOf(rel)) !== ".htm") continue;
      // never audit the generated viewer or build/vendored trees for staleness noise
      var parts = rel.split("/");
      if (rel.indexOf("/standalone/") >= 0 || parts.indexOf("repos") >= 0) continue;
      var raw = io.read(rel); if (raw == null) continue;
      var findings = [];
      // 1) stale tokens (skip mats: vendored reference snapshots are not ours to rewrite)
      if (!isMatPath(rel)) {
        var noScript = raw.replace(/<script[\s\S]*?<\/script>/ig, " ");   // tokens in real content, not JS rules
        for (var s = 0; s < STALE_TOKENS.length; s++) {
          if (STALE_TOKENS[s].exceptFile && STALE_TOKENS[s].exceptFile.test(rel)) continue;
          if (STALE_TOKENS[s].re.test(noScript)) findings.push({ kind: "stale", token: String(STALE_TOKENS[s].re), detail: STALE_TOKENS[s].why });
        }
      }
      // 2) missing local assets it loads (href/src to a css/js/image that does not resolve)
      var hrefs = findAll(reHref(), raw), seenA = {};
      for (var h = 0; h < hrefs.length; h++) {
        var m = hrefs[h], t = m.split("#")[0].split("?")[0];
        if (!t || has(seenA, m) || /^(https?:|\/\/|data:|mailto:|tel:|#)/.test(m) || isTemplateLink(m)) continue;
        if (AUDIT_ASSET_EXT.indexOf(lc(extOf(t))) < 0) continue;
        seenA[m] = 1;
        var r = proj.resolve(m, rel);
        if ((r.kind === "static_file" || r.kind === "lab_tree") && !r.exists) findings.push({ kind: "missing_asset", asset: m, detail: "resolves to nothing" });
      }
      // 3) contract drift: skill-meta children resolve; foyer-release matches RELEASED
      var sm = /<script[^>]*id=["']skill-meta["'][^>]*>([\s\S]*?)<\/script>/i.exec(raw);
      if (sm) {
        try {
          var meta = JSON.parse(sm[1]);
          // hubs use node_type; typed contracts (e.g. service-index) declare `schema` instead.
          if (!meta.schema && !meta.node_type) findings.push({ kind: "contract", detail: "skill-meta has neither node_type nor schema" });
          var kids = meta.children || [];
          for (var k = 0; k < kids.length; k++) {
            var kp = kids[k].path; if (!kp) continue;
            var rr = proj.resolve("/lab/static/" + kp, rel);
            var ok = (rr.kind === "static_file" || rr.kind === "lab_tree") && rr.exists;
            if (!ok) { var r2 = proj.resolve(kp, rel); ok = (r2.kind === "static_file" || r2.kind === "lab_tree") && r2.exists; }
            if (!ok) findings.push({ kind: "contract", detail: "skill-meta child does not resolve: " + kp });
          }
        } catch (e) { findings.push({ kind: "contract", detail: "skill-meta is not valid JSON: " + e.message }); }
      }
      var fr = /<script[^>]*id=["']foyer-release["'][^>]*>([\s\S]*?)<\/script>/i.exec(raw.replace(/<!--[\s\S]*?-->/g, " "));
      if (fr) {
        try {
          var fm = JSON.parse(fr[1]);
          if (JSON.stringify(fm.released || []) !== JSON.stringify(RELEASED)) findings.push({ kind: "contract", detail: "foyer-release 'released' drifted from RELEASED" });
        } catch (e2) { findings.push({ kind: "contract", detail: "foyer-release is not valid JSON: " + e2.message }); }
      }
      if (findings.length) out.push({ page: rel, findings: findings });
    }
    var pages = 0;
    for (i = 0; i < all.length; i++) { var e3 = lc(extOf(all[i])); if (e3 === ".html" || e3 === ".htm") pages++; }
    return { pages: pages, pages_with_findings: out.length, findings: out };
  }

  // ── self-test: pin the engine to known projection facts (repo-relative) ───────
  function selfTest(proj) {
    var checks = [];
    function expect(name, cond, got) { checks.push([name, !!cond, got || ""]); }
    var r;
    r = proj.resolve("/lab/static/SKILL.html");
    expect("/lab/static/SKILL.html -> root task hub (exists)", r.kind === "static_file" && r.exists && r.physical === "SKILL.html", r.physical);
    r = proj.resolve("/lab/static/index.html");
    expect("/lab/static/index.html -> web/index.html (exists)", r.exists && r.physical === "web/index.html", r.physical);
    r = proj.resolve("/lab/svc/llm/v1/models");
    expect("/lab/svc/llm/* -> service llm_client (always-on)", r.kind === "service" && r.service === "llm_client" && r.ondemand === false, JSON.stringify(r));
    r = proj.resolve("/securing-agents");
    expect("/securing-agents -> released course nemoclaw/index.html (exists)", r.kind === "static_file" && r.exists && r.course === "nemoclaw", r.reason + " " + r.physical);
    r = proj.resolve("/");
    expect("/ -> 302 foyer (exists)", r.exists && r.physical === "web/index.html", r.physical);
    r = proj.resolve("01b-loop.html", "web/nemoclaw/01a-loop.html");
    expect("relative link resolves within course", r.course === "nemoclaw", r.course);
    var fr = foyerReleaseCheck(proj);
    expect("release foyer surfaces only RELEASED courses (contract honored)", fr.ok, "surfaced=" + JSON.stringify(fr.surfaced_courses) + " violations=" + JSON.stringify(fr.violations.map(function (v) { return v.kind; })));
    var npass = 0; for (var i = 0; i < checks.length; i++) if (checks[i][1]) npass++;
    return { checks: checks, npass: npass };
  }

  // ── node IO adapter + CLI ──────────────────────────────────────────────────
  function nodeIO(task1) {
    var fs = require("fs"), path = require("path");
    function abs(rel) { return rel ? path.join(task1, rel) : task1; }
    function read(rel) { try { return fs.readFileSync(abs(rel), "utf8"); } catch (e) { return null; } }
    function exists(rel) { try { return fs.existsSync(abs(rel)); } catch (e) { return false; } }
    function listDir(rel) { try { return fs.readdirSync(abs(rel), { withFileTypes: true }); } catch (e) { return []; } }
    function walk() {
      var out = [], seen = {};
      function rec(dirRel) {
        var ents = listDir(dirRel);
        ents.sort(function (a, b) { return a.name < b.name ? -1 : (a.name > b.name ? 1 : 0); });
        for (var i = 0; i < ents.length; i++) {
          var nm = ents[i].name, rel = dirRel ? dirRel + "/" + nm : nm;
          if (ents[i].isDirectory()) { if (has(SKIP_DIR, nm)) continue; rec(rel); }
          else { if (junkFile(nm)) continue; if (PAGE_EXT.indexOf(lc(extOf(nm))) >= 0 && !has(seen, rel)) { seen[rel] = 1; out.push(rel); } }
        }
      }
      for (var i = 0; i < CRAWL_TOP.length; i++) if (exists(CRAWL_TOP[i])) rec(CRAWL_TOP[i]);
      var rootEnts = listDir(""); rootEnts.sort(function (a, b) { return a.name < b.name ? -1 : (a.name > b.name ? 1 : 0); });
      for (var j = 0; j < rootEnts.length; j++) { var e = rootEnts[j]; if (!e.isDirectory() && !junkFile(e.name) && PAGE_EXT.indexOf(lc(extOf(e.name))) >= 0 && !has(seen, e.name)) { seen[e.name] = 1; out.push(e.name); } }
      return out;
    }
    return { root: task1, read: read, exists: exists, walk: walk };
  }

  function embedSnapshot(proj, htmlRel) {
    var io = proj.io, html = io.read(htmlRel);
    if (html == null) return false;
    var data = "let DATA = " + JSON.stringify(graphJson(proj)) + ";\n";
    var lines = html.split("\n"), done = false;
    for (var i = 0; i < lines.length; i++) {
      if (lines[i].indexOf("let DATA = ") === 0) { lines[i] = data.replace(/\n$/, ""); done = true; break; }
    }
    if (!done) return false;
    require("fs").writeFileSync(require("path").join(io.root, htmlRel), lines.join("\n"));
    return true;
  }

  function runCLI(argv) {
    var fs = require("fs"), path = require("path");
    var task1 = path.resolve(__dirname, "../..");
    var io = nodeIO(task1), proj = new Projection(io);
    function arg(name) { var i = argv.indexOf(name); return i >= 0 && i + 1 < argv.length ? argv[i + 1] : null; }
    var rc = 0;
    if (argv.indexOf("--self-test") >= 0) {
      var st = selfTest(proj);
      for (var i = 0; i < st.checks.length; i++) { var c = st.checks[i]; process.stdout.write("  " + (c[1] ? "✓" : "✗") + " " + c[0] + (c[1] ? "" : "   [" + c[2] + "]") + "\n"); }
      process.stdout.write("engine self-test: " + st.npass + "/" + st.checks.length + " pass\n");
      if (st.npass !== st.checks.length) rc = 1;
    }
    if (argv.indexOf("--graph") >= 0) { var p = arg("--graph"); fs.writeFileSync(p, JSON.stringify(graphJson(proj), null, 2)); process.stdout.write("viewer DATA snapshot -> " + p + "\n"); }
    if (argv.indexOf("--embed") >= 0) { var ok = embedSnapshot(proj, "scripts/link_graph.html"); process.stdout.write("link_graph.html embedded snapshot " + (ok ? "refreshed" : "NOT updated (DATA line not found)") + "\n"); }
    if (argv.indexOf("--resolve") >= 0) { var rr = proj.resolve(arg("--resolve"), arg("--from") || ""); process.stdout.write(JSON.stringify(rr, null, 2) + "\n"); }
    if (argv.indexOf("--reach") >= 0) { process.stdout.write(JSON.stringify(reachability(proj)) + "\n"); }
    if (argv.indexOf("--check-json") >= 0) { process.stdout.write(JSON.stringify(check(proj)) + "\n"); }
    if (argv.indexOf("--foyer-json") >= 0) { process.stdout.write(JSON.stringify(foyerReleaseCheck(proj)) + "\n"); }
    if (argv.indexOf("--graph-json") >= 0) { process.stdout.write(JSON.stringify(graphJson(proj)) + "\n"); }
    if (argv.indexOf("--audit-json") >= 0) { process.stdout.write(JSON.stringify(pageAudit(proj)) + "\n"); }
    if (argv.indexOf("--audit") >= 0) {
      var au = pageAudit(proj);
      process.stdout.write("  · page audit: " + au.pages + " .html, " + au.pages_with_findings + " with drift\n");
      for (var ai = 0; ai < au.findings.length; ai++) {
        var pf = au.findings[ai];
        for (var fj = 0; fj < pf.findings.length; fj++) process.stdout.write("    " + pf.page + " [" + pf.findings[fj].kind + "] " + (pf.findings[fj].detail || pf.findings[fj].asset || pf.findings[fj].token) + "\n");
      }
      if (au.pages_with_findings) rc = 1;
    }
    if (argv.indexOf("--check") >= 0) {
      var rep = check(proj), s = rep.stats, scope = arg("--scope") || "ship";
      process.stdout.write("  · crawl: " + s.pages + " pages, " + s.links + " links\n");
      process.stdout.write("  · failures-to-get : " + s.failures + " (blocking " + s.blocking_failures + ")\n");
      process.stdout.write("  · asset leaks     : " + s.asset_leaks + " (blocking " + s.blocking_asset_leaks + ")\n");
      process.stdout.write("  · cross-course    : " + s.cross_course + " (blocking " + s.blocking_cross_course + ")\n");
      process.stdout.write("  · direct mat links: " + s.mat_links + " (blocking " + s.blocking_mat_links + ")\n");
      var report = arg("--report"); if (report) fs.writeFileSync(report, JSON.stringify(rep, null, 2));
      var block = (scope === "all") ? (s.failures + s.asset_leaks + s.cross_course) : (s.blocking_failures + s.blocking_asset_leaks + s.blocking_cross_course);
      if (block) rc = 1;
    }
    // set exitCode (do NOT process.exit) so large stdout writes (e.g. --graph-json) fully
    // drain to the pipe before node exits; process.exit() truncates at the pipe buffer.
    process.exitCode = rc;
  }

  var api = {
    DLI: DLI, RELEASED: RELEASED, Projection: Projection, Resolution: Resolution,
    courseOf: courseOf, shipRelevant: shipRelevant, navSource: navSource,
    graphNavigable: graphNavigable, normUrl: normUrl, isCitation: isCitation,
    parseEntrypoint: parseEntrypoint, parseCompose: parseCompose, parseNginx: parseNginx,
    graphJson: graphJson, reachability: reachability, check: check, foyerReleaseCheck: foyerReleaseCheck,
    pageAudit: pageAudit, selfTest: selfTest, embedSnapshot: embedSnapshot, nodeIO: nodeIO, iterPages: iterPages, readForLinks: readForLinks
  };

  if (typeof require !== "undefined" && typeof module !== "undefined" && require.main === module) {
    runCLI(process.argv.slice(2));
  }
  return api;
});
