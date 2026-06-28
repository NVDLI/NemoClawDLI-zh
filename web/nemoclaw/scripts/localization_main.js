const $ = selector => document.querySelector(selector);
const esc = value => String(value ?? "").replace(/[&<>"']/g, char => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[char]));
const manifestCandidates = ["../languages.json", "../../languages.json", "../../../languages.json", "../../../../languages.json"];
let drift, languages, activeStatus = "all", selected;

async function languageManifest() {
  for (const rel of manifestCandidates) {
    try {
      const url = new URL(rel, location.href);
      const response = await fetch(url, {cache:"no-store"});
      if (!response.ok) continue;
      const data = await response.json();
      if (data?.schema === "nemoclaw-languages/1") return {data, url};
    } catch (_) {}
  }
  return null;
}

function courseRows() {
  return drift.pages.filter(row => row.path.startsWith("web/nemoclaw/") && row.file !== "SKILL.html");
}

function counts() {
  const out = {};
  courseRows().forEach(row => { out[row.status] = (out[row.status] || 0) + 1; });
  return out;
}

function renderFilters() {
  const found = counts();
  const statuses = ["all", "current", "stale", "blocked", "needs-review", "missing"];
  $("#loc-filters").innerHTML = statuses.map(status => {
    const n = status === "all" ? courseRows().length : (found[status] || 0);
    return `<button class="loc-filter${activeStatus===status?' active':''}" data-status="${status}">${status} ${n}</button>`;
  }).join("");
  document.querySelectorAll(".loc-filter").forEach(button => button.addEventListener("click", () => {
    activeStatus = button.dataset.status; renderFilters(); renderPages();
  }));
}

function renderPages() {
  const rows = courseRows().filter(row => activeStatus === "all" || row.status === activeStatus);
  $("#loc-pages").innerHTML = rows.map(row => `<button class="loc-page${selected?.path===row.path?' active':''}" data-path="${esc(row.path)}"><span class="loc-dot ${esc(row.status)}"></span><span><b>${esc(row.file)}</b><small>${esc(row.status)}</small></span></button>`).join("") || '<div class="loc-empty">No pages in this state.</div>';
  document.querySelectorAll(".loc-page").forEach(button => button.addEventListener("click", () => selectPage(button.dataset.path)));
}

function baseFor(code) {
  const entry = languages?.data.languages.find(item => item.code === code);
  return entry ? new URL(entry.url, languages.url) : null;
}

function shortHash(value) { return value ? value.slice(0, 12) : "none"; }

function selectPage(path) {
  selected = drift.pages.find(row => row.path === path);
  if (!selected) return;
  const sourceBase = baseFor(languages?.data.default || "en") || new URL("./", location.href);
  const targetBase = baseFor(drift.url_code) || new URL(`../../i18n/${drift.url_code}/web/nemoclaw/`, location.href);
  $("#loc-source").src = new URL(selected.file, sourceBase);
  $("#loc-target").src = new URL(selected.file, targetBase);
  $("#loc-source-label").textContent = shortHash(selected.source_sha256);
  $("#loc-target-label").textContent = selected.status;
  $("#loc-evidence").innerHTML = `<strong>${esc(selected.file)}</strong><span>source <code>${shortHash(selected.source_sha256)}</code></span><span>reviewed <code>${shortHash(selected.reviewed_source_sha256)}</code></span><span>target <code>${shortHash(selected.target_sha256)}</code></span>`;
  const findings = selected.quality || [];
  $("#loc-findings").innerHTML = `<strong>${esc(selected.status)}</strong>${findings.length ? `<ul>${findings.map(item => `<li><code>${esc(item.code)}</code> ${esc(item.detail)}</li>`).join("")}</ul>` : '<span> · no static language/structure findings</span>'}<div>After reviewing the complete page: <code>python3 scripts/validation/localization_audit.py --locale pt-BR --accept ${esc(selected.path)}</code></div>`;
  renderPages();
}

async function boot() {
  const [driftResponse, lang] = await Promise.all([fetch("assets/localization-pt.json", {cache:"no-store"}), languageManifest()]);
  if (!driftResponse.ok) throw new Error(`drift manifest unavailable (${driftResponse.status})`);
  drift = await driftResponse.json(); languages = lang;
  const c = counts();
  $("#loc-summary").textContent = `${c.current || 0} current · ${c.stale || 0} stale · ${(c.blocked || 0) + (c['needs-review'] || 0) + (c.missing || 0)} pending`;
  renderFilters(); renderPages();
  const first = courseRows().find(row => row.status !== "missing") || courseRows()[0];
  if (first) selectPage(first.path);
}

boot().catch(error => {
  $("#loc-summary").textContent = "Localization data unavailable";
  $("#loc-pages").innerHTML = `<div class="loc-empty">${esc(error.message)}</div>`;
});
