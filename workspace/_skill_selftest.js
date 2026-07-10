// Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
// SPDX-License-Identifier: Apache-2.0

/* Shared SKILL.html self-test harness.
 *
 * Served at /lab/static/_skill_selftest.js (workspace root is a jupyter static
 * path). A SKILL.html mounts it with:
 *
 *   <div id="selftest"></div>
 *   <script src="/lab/static/_skill_selftest.js"></script>
 *   <script>SkillSelfTest.run("#selftest", [
 *     { name: "thing works", run: async ({f, A}) => {
 *         const r = await f("/lab/svc/.../endpoint"); A(r.ok, "HTTP " + r.status);
 *         return { detail: "HTTP " + r.status }; } },
 *   ]);</script>
 *
 * Each test's `run` is async and receives helpers {f, A, execSandbox}. It may:
 *   - return {detail} or nothing  -> pass
 *   - return {skip: "reason"}      -> skipped (use for on-demand services)
 *   - throw                        -> fail (the message is shown)
 *
 * The tester runs network checks only inside /lab/static/. Outside the lab it
 * renders a stable lab-only state and performs no requests. Prose and skill-meta
 * stay inline in each SKILL.html, so the file remains a portable dual-reader contract.
 */
(function () {
  if (!document.getElementById("skill-selftest-css")) {
    var css = document.createElement("style");
    css.id = "skill-selftest-css";
    css.textContent = [
      ".selftest{border:1px solid var(--bd,#2a2a2a);border-radius:8px;background:var(--e1,#161616);padding:14px 18px;margin:2em 0}",
      ".selftest h2{border:0;margin:0;display:flex;align-items:center;gap:10px;font-size:1.05rem;color:#fff}",
      ".st-badge{font-family:ui-monospace,monospace;font-size:.72rem;padding:2px 9px;border-radius:999px;background:var(--e2,#1e1e1e);border:1px solid var(--bd,#2a2a2a);color:var(--td,#b0b0b0)}",
      ".st-badge.st-b-ok{color:var(--gs,#aee23a);border-color:var(--gd,#4a7a00);background:rgba(118,185,0,.12)}",
      ".st-badge.st-b-fail{color:#ff9a9a;border-color:#a33;background:rgba(200,40,40,.12)}",
      ".st-run{margin-left:auto;background:var(--e2,#1e1e1e);border:1px solid var(--bd,#2a2a2a);color:var(--td,#b0b0b0);border-radius:6px;padding:4px 12px;font-size:.8rem;font-family:ui-monospace,monospace;cursor:pointer}",
      ".st-run:hover{border-color:var(--g,#76b900);color:var(--gs,#aee23a)}.st-run:disabled{opacity:.55;cursor:not-allowed}",
      ".st-note{font-size:.85rem;color:var(--td,#b0b0b0);margin:.5em 0 .8em}",
      ".st-list{list-style:none;margin:0;padding:0;font-size:.86rem}",
      ".st-item{display:flex;align-items:baseline;gap:10px;padding:5px 0;border-bottom:1px solid var(--e2,#1e1e1e)}",
      ".st-item:last-child{border-bottom:0}",
      ".st-dot{flex:none;width:9px;height:9px;border-radius:50%;background:var(--td,#b0b0b0);margin-top:5px}",
      ".st-pass .st-dot{background:var(--g,#76b900)}.st-fail .st-dot{background:#e05656}.st-skip .st-dot{background:var(--tf,#8a8a8a)}",
      ".st-name{color:var(--tx,#f2f2f2)}",
      ".st-detail{color:var(--tf,#8a8a8a);font-family:ui-monospace,monospace;font-size:.78rem;margin-left:auto;text-align:right;padding-left:12px}",
      ".st-fail .st-detail{color:#ff9a9a}"
    ].join("\n");
    document.head.appendChild(css);
  }

  var A = function (c, m) { if (!c) throw new Error(m || "assertion failed"); };
  var f = function (url, opts) { return fetch(url, Object.assign({ credentials: "include" }, opts || {})); };
  var SBX = { "Authorization": "Bearer dli-openclaw-token", "Content-Type": "application/json" };
  var execSandbox = function (argv) {
    return f("/lab/svc/sandbox-admin/admin/sandbox/exec", { method: "POST", headers: SBX, body: JSON.stringify({ argv: argv }) });
  };
  var helpers = { A: A, f: f, execSandbox: execSandbox };

  async function run(mountSel, tests) {
    var mount = typeof mountSel === "string" ? document.querySelector(mountSel) : mountSel;
    if (!mount) return;
    mount.classList.add("selftest");
    var inLab = /^\/lab\/static(?:\/|$)/.test(location.pathname);
    mount.innerHTML =
      '<h2>Self-tests <span class="st-badge">' + (inLab ? 'running…' : 'lab only') + '</span>' +
      '<button class="st-run" type="button">Re-run</button></h2>' +
      '<p class="st-note">Min-code checks that this directory\'s declared interfaces actually work. ' +
      (inLab ? 'They are running against the live lab services with the current session.' :
      'Open this page through /lab/static/ to authorize and run the service calls.') +
      '</p><ol class="st-list"></ol>';
    var list = mount.querySelector(".st-list");
    var badge = mount.querySelector(".st-badge");
    var btn = mount.querySelector(".st-run");

    async function go() {
      list.innerHTML = ""; badge.textContent = "running…"; badge.className = "st-badge";
      var pass = 0, fail = 0, skip = 0;
      for (var i = 0; i < tests.length; i++) {
        var t = tests[i];
        var li = document.createElement("li"); li.className = "st-item st-pending";
        li.innerHTML = '<span class="st-dot"></span><span class="st-name"></span><span class="st-detail">…</span>';
        li.querySelector(".st-name").textContent = t.name; list.appendChild(li);
        try {
          var r = await t.run(helpers);
          if (r && r.skip) { skip++; li.className = "st-item st-skip"; li.querySelector(".st-detail").textContent = "skip: " + r.skip; }
          else { pass++; li.className = "st-item st-pass"; li.querySelector(".st-detail").textContent = (r && r.detail) || "ok"; }
        } catch (e) { fail++; li.className = "st-item st-fail"; li.querySelector(".st-detail").textContent = (e && e.message) || String(e); }
      }
      badge.textContent = pass + " passed · " + fail + " failed · " + skip + " skipped";
      badge.className = "st-badge " + (fail ? "st-b-fail" : "st-b-ok");
    }
    btn.disabled = !inLab;
    if (inLab) {
      btn.addEventListener("click", go);
      go();
    }
  }

  window.SkillSelfTest = { run: run, helpers: helpers };
})();
