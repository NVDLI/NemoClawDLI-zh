// _figures.js holds the inline figure builders that used to live in _shared.js.
//
// course-specific figure generators kept out of the shared diagram engine. ganttBarsSVG (02c)
// renders a concurrency-vs-serial Gantt chart as an SVG string. The general engine (diagramSVG
// / mountDiagram) stays in _shared.js; this is for one-off, per-section figures.

export function ganttBarsSVG(workers, wallSeconds, title = "Concurrency vs serial time") {
  /* @doc <code>helpers.ganttBarsSVG(workers, wallSeconds, title)</code> ::
       Returns a Gantt-style concurrency chart as an SVG string (the string form of
       <code>helpers.viz.ganttBars</code>), for rendering in a live artifact with
       <code>view.html(...)</code>. <code>workers</code>: array of <code>{label, dt}</code>
       (seconds); compares the per-worker bars and their serial sum against the real
       <code>wallSeconds</code>.
  */
  const W = 560, BAR_H = 26, GAP = 8, PAD_L = 130, PAD_T = 52, PAD_B = 44, PAD_R = 60;
  const maxBarW = W - PAD_L - PAD_R;
  const serialTotal = workers.reduce((s, w) => s + (w.dt || 0), 0);
  const scale = dt => Math.round((dt / Math.max(serialTotal, 0.001)) * maxBarW);
  const H = PAD_T + (workers.length + 2) * (BAR_H + GAP) + PAD_B;
  const esc = t => String(t || "").replace(/[<>&]/g, c => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c]));
  let body = "";
  workers.forEach((w, i) => {
    const y = PAD_T + i * (BAR_H + GAP);
    const bw = scale(w.dt || 0);
    body += `<text x="${PAD_L - 6}" y="${y + BAR_H / 2 + 4}" text-anchor="end" font-size="11" font-family="ui-monospace,monospace" fill="#b0b0b0">${esc(w.label || `worker ${i + 1}`)}</text>`;
    body += `<rect x="${PAD_L}" y="${y}" width="${maxBarW}" height="${BAR_H}" rx="3" fill="#161616"/>`;
    body += `<rect x="${PAD_L}" y="${y}" width="${bw}" height="${BAR_H}" rx="3" fill="#3b82f6" opacity="0.75"/>`;
    body += `<text x="${PAD_L + bw + 5}" y="${y + BAR_H / 2 + 4}" font-size="11" font-family="ui-monospace,monospace" fill="#7eb8ff">${(w.dt || 0).toFixed(2)}s</text>`;
  });
  const serY = PAD_T + workers.length * (BAR_H + GAP) + GAP;
  body += `<text x="${PAD_L - 6}" y="${serY + BAR_H / 2 + 4}" text-anchor="end" font-size="11" font-family="ui-monospace,monospace" fill="#d49c2c" font-weight="700">serial total</text>`;
  body += `<rect x="${PAD_L}" y="${serY}" width="${maxBarW}" height="${BAR_H}" rx="3" fill="#161616"/>`;
  body += `<rect x="${PAD_L}" y="${serY}" width="${maxBarW}" height="${BAR_H}" rx="3" fill="#d49c2c" opacity="0.35"/>`;
  body += `<text x="${PAD_L + maxBarW + 5}" y="${serY + BAR_H / 2 + 4}" font-size="11" font-family="ui-monospace,monospace" fill="#e8c87a">${serialTotal.toFixed(2)}s</text>`;
  const wallY = serY + BAR_H + GAP;
  const wallW = scale(wallSeconds);
  body += `<text x="${PAD_L - 6}" y="${wallY + BAR_H / 2 + 4}" text-anchor="end" font-size="11" font-family="ui-monospace,monospace" fill="#76b900" font-weight="700">wall time</text>`;
  body += `<rect x="${PAD_L}" y="${wallY}" width="${maxBarW}" height="${BAR_H}" rx="3" fill="#161616"/>`;
  body += `<rect x="${PAD_L}" y="${wallY}" width="${wallW}" height="${BAR_H}" rx="3" fill="#76b900" opacity="0.75"/>`;
  body += `<text x="${PAD_L + wallW + 5}" y="${wallY + BAR_H / 2 + 4}" font-size="11" font-family="ui-monospace,monospace" fill="#aee23a">${wallSeconds.toFixed(2)}s</text>`;
  const speedup = serialTotal / Math.max(wallSeconds, 0.001);
  return `<svg viewBox="0 0 ${W} ${H}" xmlns="http://www.w3.org/2000/svg" style="max-width:100%;background:#0d0d0d;border:1px solid #2a2a2a;border-radius:6px">
    <text x="${W / 2}" y="22" text-anchor="middle" font-size="12" font-family="ui-monospace,monospace" fill="#aee23a" font-weight="700">${esc(title)}</text>
    <text x="${W / 2}" y="38" text-anchor="middle" font-size="10" font-family="ui-monospace,monospace" fill="#6a6a6a">parallel speedup: ${speedup.toFixed(2)}x  (serial ${serialTotal.toFixed(2)}s / wall ${wallSeconds.toFixed(2)}s)</text>
    ${body}</svg>`;
}
