#!/usr/bin/env python3
"""Generate the hosted stakeholder deck from its shared slide manifest."""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path

for _path in (Path(__file__).resolve(), *Path(__file__).resolve().parents):
    if (_path / "scripts" / "_bootstrap.py").exists():
        sys.path.insert(0, str(_path / "scripts"))
        break
from _bootstrap import find_repo_root

ROOT = find_repo_root(Path(__file__).resolve())
MANIFEST = ROOT / "docs" / "repository-overview.slides.json"
OUTPUT = ROOT / "docs" / "repository-overview.html"


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def text_block(slide: dict) -> str:
    lead = slide.get("lead")
    return f'<p class="lead">{esc(lead)}</p>' if lead else ""


def asset_src(value: str) -> str:
    """Resolve a repository-relative slide asset from docs/repository-overview.html."""
    return "../" + value.lstrip("/")


def points(items: list[str]) -> str:
    return '<ul class="talking-points">' + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul>"


def visual(slide: dict) -> str:
    spec = slide.get("visual") or {}
    layout = slide["layout"]
    if layout == "sequence":
        rows = "".join(
            f'<div class="sequence-step"><b>{esc(item["label"])}</b><span>{esc(item["detail"])}</span></div>'
            for item in spec["items"]
        )
        return f'<div class="sequence"><div class="sequence-steps">{rows}</div><p>{esc(spec["outcome"])}</p></div>'
    if layout == "screenshot":
        return (
            '<div class="screenshot-layout">'
            f'<figure><img src="{esc(asset_src(spec["asset"]))}" alt="{esc(spec["alt"])}">'
            f'<figcaption>{esc(spec["caption"])}</figcaption></figure>'
            f'{points(spec["points"])}</div>'
        )
    if layout == "comparison":
        images = "".join(
            f'<img src="{esc(asset_src(item["asset"]))}" alt="{esc(item["alt"])}">'
            for item in spec["images"]
        )
        rows = "".join(
            f'<div class="comparison-row"><strong>{esc(item["label"])}</strong><span>{esc(item["detail"])}</span></div>'
            for item in spec["items"]
        )
        return f'<div class="comparison"><div class="comparison-images">{images}</div><div class="comparison-rows">{rows}</div></div>'
    if layout == "gates":
        rows = "".join(
            f'<div class="gate"><b>{index:02d}</b><span><strong>{esc(item["label"])}</strong>'
            f'<small>{esc(item["detail"])}</small></span></div>'
            for index, item in enumerate(spec["steps"], 1)
        )
        return f'<div class="gates">{rows}</div>'
    if layout == "tree":
        rows = "".join(
            f'<div class="tree-row"><code>{esc(item["label"])}</code><span>{esc(item["detail"])}</span></div>'
            for item in spec["items"]
        )
        return f'<div class="tree"><div class="tree-root">{esc(spec["root"])}</div>{rows}</div>'
    if layout == "layers":
        rows = "".join(
            f'<div class="layer-row"><b>{index}</b><strong>{esc(item["label"])}</strong><span>{esc(item["detail"])}</span></div>'
            for index, item in enumerate(spec["items"], 1)
        )
        return f'<div class="layers">{rows}</div>'
    if layout == "lanes":
        rows = "".join(
            f'<div class="lane"><strong>{esc(item["label"])}</strong><span>{esc(item["detail"])}</span>'
            f'<b class="lane-status">{esc(item["status"])}</b></div>'
            for item in spec["lanes"]
        )
        return f'<div class="lanes">{rows}</div>'
    if layout == "review":
        rows = "".join(
            f'<div class="review-row"><strong>{esc(item["label"])}</strong><code>{esc(item["path"])}</code><span>{esc(item["detail"])}</span></div>'
            for item in spec["items"]
        )
        return f'<div class="review-rows">{rows}</div>'
    return ""


def slide_markup(slide: dict, number: int, total: int, deck_title: str) -> str:
    layout = slide["layout"]
    if layout == "title":
        return f'''<section class="slide title-slide" data-slide-id="{esc(slide["id"])}" data-claim-scope="{esc(slide["claim_scope"])}" aria-label="Slide {number}: {esc(slide["title"])}">
  <div class="title-brand">{esc(slide["kicker"])}</div><div class="title-rule"></div>
  <h1>{esc(slide["title"])}</h1><p class="title-lead">{esc(slide["lead"])}</p>
  <div class="title-footer">{esc(slide["footer"])}</div>
</section>'''
    if layout == "section":
        return f'''<section class="slide section-slide" data-slide-id="{esc(slide["id"])}" data-claim-scope="{esc(slide["claim_scope"])}" aria-label="Slide {number}: {esc(slide["title"])}">
  <div class="section-number">{esc(slide["kicker"])}</div><h2>{esc(slide["title"])}</h2>
  <div class="section-rule"></div>{text_block(slide)}
</section>'''
    return f'''<section class="slide content-slide layout-{esc(layout)}" data-slide-id="{esc(slide["id"])}" data-claim-scope="{esc(slide["claim_scope"])}" aria-label="Slide {number}: {esc(slide["title"])}">
  <div class="brand">NVIDIA Deep Learning Institute</div><div class="brand-rule"></div>
  <header><div class="kicker">{esc(slide["kicker"])}</div><h2>{esc(slide["title"])}</h2>{text_block(slide)}</header>
  <div class="visual">{visual(slide)}</div>
  <footer><span>{esc(deck_title)}</span><span>{number} / {total}</span></footer>
</section>'''


def render(manifest: dict) -> str:
    slides = manifest["slides"]
    slide_html = "\n".join(
        slide_markup(slide, index, len(slides), manifest["title"])
        for index, slide in enumerate(slides, 1)
    )
    notes = json.dumps([slide.get("notes", "") for slide in slides]).replace("</", "<\\/")
    pptx_link = (
        ' · <a href="repository-overview.pptx" style="color:#76b900">PPTX</a>'
        if (ROOT / "docs" / "repository-overview.pptx").is_file()
        else ""
    )
    return f'''<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(manifest["title"])} · repository overview</title>
<style>
:root{{--green:#76b900;--green-dark:#4a7a00;--ink:#1a1a1a;--gray:#5e5e5e;--faint:#6b6b6b;--line:#d4d4d4;--soft:#f3f6ee;--canvas:#fff;--outer:#202020;--blue:#0071c5;--purple:#7c3aed;--rust:#c2410c;--teal:#0d9488;--sans:Arial,"Helvetica Neue",Helvetica,sans-serif;--mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;color-scheme:light}}
:root[data-theme="dark"]{{--green:#aee23a;--green-dark:#aee23a;--ink:#f2f2f2;--gray:#c4c4c4;--faint:#a7a7a7;--line:#3a3a3a;--soft:#1e1e1e;--canvas:#121212;--outer:#080808;color-scheme:dark}}
*{{box-sizing:border-box;margin:0;padding:0}}html,body{{height:100%;background:var(--outer);font-family:var(--sans)}}
.deck{{height:100vh;display:flex;align-items:center;justify-content:center}}.stage{{position:relative;width:min(100vw,calc(100vh*16/9));height:min(100vh,calc(100vw*9/16));background:var(--canvas);overflow:hidden;container-type:size;box-shadow:0 0 60px #0008}}
.slide{{position:absolute;inset:0;display:none;flex-direction:column;padding:5.5cqh 6.2cqw 4.5cqh;background:var(--canvas);color:var(--ink)}}.slide.on{{display:flex;animation:enter .32s ease-out}}@keyframes enter{{from{{opacity:0;transform:translateY(1cqh)}}}}
.brand{{position:absolute;top:4.6cqh;left:6.2cqw;font-size:1.75cqh;font-weight:800;letter-spacing:.08em;color:var(--ink)}}.brand-rule{{position:absolute;top:8.2cqh;left:6.2cqw;right:6.2cqw;height:3px;background:linear-gradient(90deg,var(--green) 0 15%,#e6e6e6 15%)}}
header{{margin-top:7.4cqh}}.kicker{{font-size:2.1cqh;font-weight:800;letter-spacing:.13em;text-transform:uppercase;color:var(--green-dark)}}h2{{font-size:5cqh;line-height:1.08;margin-top:.4cqh;white-space:nowrap;color:var(--ink)}}.lead{{font-size:2.45cqh;line-height:1.35;color:var(--gray);margin-top:1.15cqh;max-width:92%}}
.visual{{flex:1;min-height:0;margin-top:2.4cqh;display:flex;align-items:center;justify-content:center}}footer{{position:absolute;bottom:3.1cqh;left:6.2cqw;right:6.2cqw;display:flex;justify-content:space-between;font-size:1.7cqh;color:var(--faint)}}
.title-slide{{justify-content:center}}.title-brand{{position:absolute;top:7cqh;left:6.2cqw;font-size:2.25cqh;font-weight:800;letter-spacing:.09em}}.title-rule{{width:15cqw;height:.8cqh;background:var(--green);border-radius:4px;margin-bottom:2.5cqh}}h1{{font-size:6.2cqh;line-height:1.02;max-width:100%;white-space:nowrap;color:var(--ink)}}.title-lead{{font-size:3.15cqh;color:var(--green-dark);font-weight:700;margin-top:1.8cqh;max-width:76%}}.title-footer{{position:absolute;bottom:6cqh;left:6.2cqw;color:var(--faint);font-size:1.9cqh;letter-spacing:.08em}}
.section-slide{{justify-content:center;background:linear-gradient(180deg,#fff,#f3f6ee)}}.section-number{{font-size:11cqh;font-weight:900;color:var(--green);line-height:.85}}.section-slide h2{{font-size:7.2cqh;max-width:78%;margin-top:1cqh}}.section-rule{{width:11cqw;height:.75cqh;background:var(--green);margin:2.1cqh 0 1.6cqh;border-radius:4px}}.section-slide .lead{{max-width:74%;font-size:3cqh}}
.sequence{{width:94%;display:grid;gap:2.2cqh}}.sequence-steps{{display:grid;grid-template-columns:repeat(3,1fr);gap:1.6cqw}}.sequence-step{{position:relative;border-top:5px solid var(--green);padding:2.1cqh 1.5cqw;background:var(--soft);min-height:28cqh}}.sequence-step:not(:last-child)::after{{content:"→";position:absolute;right:-1.35cqw;top:10.5cqh;color:var(--green-dark);font-size:3.2cqh;z-index:2}}.sequence-step b{{font-size:2.45cqh;display:block}}.sequence-step span{{display:block;font-size:1.9cqh;color:var(--gray);margin-top:1cqh;line-height:1.35}}.sequence>p{{font-size:2.15cqh;font-weight:700;color:var(--green-dark);text-align:center}}
.screenshot-layout{{width:100%;display:grid;grid-template-columns:minmax(0,1.85fr) minmax(22cqw,1fr);gap:2.2cqw;align-items:center}}.screenshot-layout figure{{min-width:0}}.screenshot-layout img{{display:block;width:100%;max-height:39cqh;object-fit:contain;object-position:center;background:#0d0d0d;border:1px solid #404040;box-shadow:0 1.2cqh 2.8cqh #0002}}.screenshot-layout figcaption{{font-size:1.45cqh;color:var(--faint);margin-top:.8cqh;line-height:1.35}}.talking-points{{display:grid;gap:1.35cqh;list-style:none}}.talking-points li{{font-size:1.9cqh;line-height:1.35;color:var(--gray);padding:0 0 1.25cqh 1.5cqw;border-bottom:1px solid var(--line);position:relative}}.talking-points li::before{{content:"";position:absolute;left:0;top:.6cqh;width:.7cqh;height:.7cqh;background:var(--green)}}
.comparison{{width:100%;display:grid;grid-template-columns:minmax(0,1.35fr) minmax(28cqw,1fr);gap:2.2cqw;align-items:center}}.comparison-images{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:.7cqw;background:#0d0d0d;border:1px solid #404040;padding:.7cqw}}.comparison-images img{{display:block;width:100%;height:30cqh;object-fit:contain}}.comparison-rows{{border-left:4px solid var(--green);padding-left:1.8cqw}}.comparison-row{{display:grid;gap:.55cqh;padding:1.15cqh 0;border-bottom:1px solid var(--line)}}.comparison-row strong{{font-size:2.1cqh}}.comparison-row span{{font-size:1.75cqh;line-height:1.32;color:var(--gray)}}
.gates{{width:100%;min-height:36cqh;display:grid;grid-template-columns:repeat(5,1fr);gap:1.3cqw}}.gate{{position:relative;padding:1.6cqh 1.2cqw;border-top:5px solid var(--green);background:#fff;border-bottom:1px solid var(--line)}}.gate:not(:last-child)::after{{content:"→";position:absolute;right:-1.15cqw;top:9cqh;font-size:3cqh;color:var(--faint);z-index:2}}.gate>b{{font-size:4.5cqh;color:#d9e8c7}}.gate strong{{display:block;font-size:2.3cqh}}.gate small{{display:block;font-size:1.75cqh;line-height:1.28;color:var(--gray);margin-top:.8cqh}}
.tree{{width:76%;min-height:34cqh;display:grid;grid-template-rows:auto repeat(4,1fr);font-family:var(--mono);border-left:5px solid var(--green);padding-left:3cqw}}.tree-root{{font-size:3.2cqh;font-weight:800;margin-bottom:1.3cqh}}.tree-row{{display:grid;grid-template-columns:19cqw 1fr;align-items:center;border-top:1px solid var(--line);padding:1.25cqh 0}}.tree-row code{{font-size:2.35cqh;color:var(--green-dark);font-weight:800}}.tree-row span{{font-family:var(--sans);font-size:2.05cqh;color:var(--gray)}}
.layers{{width:94%;min-height:34cqh;display:grid;grid-template-rows:repeat(4,1fr);gap:1.05cqh}}.layer-row{{display:grid;grid-template-columns:5cqw 18cqw 1fr;align-items:center;padding:1.3cqh 1.5cqw;border-bottom:1px solid var(--line)}}.layer-row b{{font-size:3.5cqh;color:#d7e7c5}}.layer-row strong{{font-size:2.25cqh}}.layer-row span{{font-size:1.9cqh;line-height:1.3;color:var(--gray)}}
.lanes{{width:94%;min-height:34cqh;display:grid;grid-template-rows:repeat(3,1fr);gap:1.4cqh}}.lane{{display:grid;grid-template-columns:23cqw 1fr 18cqw;align-items:center;padding:1.8cqh 2cqw;border-left:6px solid var(--green);background:var(--soft)}}.lane:nth-child(2){{border-color:var(--blue)}}.lane:nth-child(3){{border-color:var(--rust)}}.lane strong{{font-size:2.5cqh}}.lane span{{font-size:2.05cqh;color:var(--gray)}}.lane-status{{text-align:right;font-size:1.9cqh;color:var(--green-dark)}}.lane:nth-child(3) .lane-status{{color:var(--rust)}}
.review-rows{{width:96%;min-height:34cqh;display:grid;grid-template-rows:repeat(4,1fr);border-left:5px solid var(--green);padding-left:2.2cqw}}.review-row{{display:grid;grid-template-columns:15cqw 26cqw 1fr;align-items:center;border-bottom:1px solid var(--line);padding:1.3cqh 0;gap:1cqw}}.review-row strong{{font-size:2.25cqh}}.review-row code{{font-size:1.7cqh;color:var(--green-dark);font-weight:700}}.review-row span{{font-size:1.85cqh;line-height:1.3;color:var(--gray)}}
.controls{{position:fixed;right:12px;bottom:12px;color:#b8b8b8;font-size:12px;z-index:6}}.progress{{position:fixed;left:0;bottom:0;height:3px;background:var(--green);z-index:6}}.notes{{display:none;position:fixed;left:0;right:0;bottom:0;max-height:34vh;overflow:auto;background:#121412f2;color:#f3f6ee;border-top:3px solid var(--green);padding:14px 26px;font:15px/1.5 var(--sans);z-index:8}}body.notes-on .notes{{display:block}}.notes b{{color:var(--green);margin-right:.6em}}
:root[data-theme="dark"] .section-slide{{background:linear-gradient(180deg,var(--canvas),var(--soft))}}:root[data-theme="dark"] .gate{{background:var(--canvas)}}
@media print{{html,body{{background:#fff;height:auto}}.deck,.stage{{display:block;width:100%;height:auto;box-shadow:none}}.slide{{display:flex!important;position:relative;width:100vw;height:56.25vw;page-break-after:always}}.controls,.progress,.notes{{display:none!important}}}}
</style></head><body>
<div class="deck"><main class="stage" id="stage">{slide_html}</main></div>
<div class="controls">← → / space · F fullscreen · N notes{pptx_link}</div><div class="progress" id="progress"></div><aside class="notes" id="notes"></aside>
<script type="application/json" id="speaker-notes">{notes}</script>
<script>
(()=>{{const slides=[...document.querySelectorAll('.slide')],notes=JSON.parse(document.getElementById('speaker-notes').textContent),panel=document.getElementById('notes'),bar=document.getElementById('progress');let i=Math.max(0,Math.min(slides.length-1,(parseInt(location.hash.slice(1),10)||1)-1));
function render(){{slides.forEach((s,n)=>s.classList.toggle('on',n===i));bar.style.width=((i+1)/slides.length*100)+'%';panel.innerHTML='<b>'+(i+1)+' / '+slides.length+'</b>'+notes[i];history.replaceState(null,'','#'+(i+1));}}
function go(n){{i=Math.max(0,Math.min(slides.length-1,n));render()}}addEventListener('keydown',e=>{{if(['ArrowRight',' ','PageDown'].includes(e.key)){{go(i+1);e.preventDefault()}}else if(['ArrowLeft','PageUp'].includes(e.key))go(i-1);else if(e.key==='Home')go(0);else if(e.key==='End')go(slides.length-1);else if(e.key.toLowerCase()==='f')document.documentElement.requestFullscreen?.();else if(e.key.toLowerCase()==='n')document.body.classList.toggle('notes-on')}});addEventListener('hashchange',()=>{{const n=parseInt(location.hash.slice(1),10);if(Number.isFinite(n))go(n-1)}});render();}})();
</script></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--out", type=Path, default=OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    generated = render(json.loads(args.manifest.read_text(encoding="utf-8")))
    if args.check:
        if not args.out.is_file() or args.out.read_text(encoding="utf-8") != generated:
            print(f"stakeholder HTML deck is stale: run {Path(__file__).relative_to(ROOT)}", file=sys.stderr)
            return 1
        print("stakeholder HTML deck: current")
        return 0
    args.out.write_text(generated, encoding="utf-8")
    print(f"wrote {args.out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
