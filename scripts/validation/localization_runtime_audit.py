#!/usr/bin/env python3
"""Browser-check the language menu and same-branch Localization Studio."""
from __future__ import annotations

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_IMAGE = "nemoclaw/lab-runtime-test:local"

RUNTIME = r"""
const http=require('http'),fs=require('fs'),path=require('path');
const {chromium}=require('playwright-core');
const root=process.env.SITE_ROOT,shots=process.env.SHOTS,port=4197;
const mime={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.json':'application/json; charset=utf-8','.svg':'image/svg+xml','.ico':'image/x-icon'};
const server=http.createServer((req,res)=>{let p=path.resolve(root,decodeURIComponent(req.url.split('?')[0]).replace(/^\/+/,''));if(!p.startsWith(path.resolve(root))){res.writeHead(403);return res.end();}if(fs.existsSync(p)&&fs.statSync(p).isDirectory())p=path.join(p,'index.html');fs.readFile(p,(e,d)=>{if(e){res.writeHead(404);return res.end('not found');}res.writeHead(200,{'content-type':mime[path.extname(p)]||'application/octet-stream'});res.end(d);});});
function ok(value,message){if(!value)throw new Error(message)}
async function open(page,url){const errors=[];page.removeAllListeners('console');page.removeAllListeners('pageerror');page.removeAllListeners('response');page.on('console',m=>{if(m.type()==='error')errors.push(`console: ${m.text()}`)});page.on('pageerror',e=>errors.push(`pageerror: ${e.message}`));page.on('response',r=>{if(r.status()>=400)errors.push(`HTTP ${r.status()}: ${r.url()}`)});await page.goto(`http://127.0.0.1:${port}${url}`,{waitUntil:'domcontentloaded'});await page.waitForTimeout(500);ok(!errors.length,`${url} browser errors: ${errors.join('; ')}`)}
(async()=>{await new Promise(r=>server.listen(port,'127.0.0.1',r));const browser=await chromium.launch({headless:true});const page=await browser.newPage({viewport:{width:1280,height:900}});
await open(page,'/nemoclaw/01a-loop.html');await page.waitForSelector('.language-menu-button');await page.click('.language-menu-button');let links=await page.$$eval('.language-menu-popover a',xs=>xs.map(x=>({text:x.textContent.trim(),href:x.href,current:x.getAttribute('aria-current')})));ok(links.some(x=>x.text.includes('Português')&&x.href.endsWith('/pt/nemoclaw/01a-loop.html')),'English 01a lacks same-page Portuguese target');ok(await page.$$eval('.language-menu-popover a',xs=>xs.every(x=>{const r=x.getBoundingClientRect();return r.top>=0&&r.bottom<=innerHeight&&r.left>=0&&r.right<=innerWidth})),'English language-menu entries are clipped');
await page.screenshot({path:path.join(shots,'english-01a-language-menu.png'),fullPage:false});
await open(page,'/nemoclaw/01b-react.html');await page.waitForSelector('.language-menu-button');await page.click('.language-menu-button');links=await page.$$eval('.language-menu-popover a',xs=>xs.map(x=>({text:x.textContent.trim(),href:x.href})));ok(links.some(x=>x.text.includes('Português')&&x.href.endsWith('/pt/nemoclaw/01b-react.html')),'English 01b lacks same-page Portuguese target');
await open(page,'/pt/nemoclaw/01a-loop.html');await page.waitForSelector('.language-menu-button');ok(await page.getAttribute('html','lang')==='pt-BR','Portuguese page lang is not pt-BR');await page.waitForSelector('.key-panel');ok((await page.textContent('.key-panel')).includes('Chave da API NVIDIA'),'Portuguese key panel retains English copy');let next=await page.$eval('.foot-nav .next',x=>({href:x.href,fallback:x.dataset.languageFallback}));ok(next.href.endsWith('/pt/nemoclaw/01b-react.html')&&!next.fallback,'Portuguese 01a does not continue to translated 01b');await page.click('.language-menu-button');links=await page.$$eval('.language-menu-popover a',xs=>xs.map(x=>({text:x.textContent.trim(),href:x.href})));ok(links.some(x=>x.text.startsWith('English')&&x.href.endsWith('/nemoclaw/01a-loop.html')),'Portuguese 01a lacks same-page English target');await page.screenshot({path:path.join(shots,'portuguese-01a-language-menu.png'),fullPage:false});
await open(page,'/pt/nemoclaw/02c-deep.html');await page.waitForSelector('.language-menu-button');next=await page.$eval('.foot-nav .next',x=>({href:x.href,fallback:x.dataset.languageFallback}));ok(next.href.endsWith('/nemoclaw/03a-kickstart.html')&&next.fallback==='en','Portuguese 02c does not mark the Module 3 English fallback');
const translatedPages=[['01b-react.html','O ciclo ReAct'],['01c-tools.html','Ferramentas em Escala'],['02a-routing.html','O fluxo de trabalho do agente'],['02b-rag.html','O Agente de Índice'],['02c-deep.html','Agente Profundo']];for(const [file,heading] of translatedPages){await open(page,`/pt/nemoclaw/${file}`);ok(await page.getAttribute('html','lang')==='pt-BR',`${file} lang is not pt-BR`);const title=(await page.textContent('h1')).replace(/\s+/g,' ').trim();ok(title===heading,`${file} heading mismatch: ${title}`);const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);ok(overflow<=2,`${file} overflows by ${overflow}px`);const englishControls=await page.$$eval('.cf-btn-run,.rc-run,.chatui-send,.cf-btn-reset,.rc-reset',xs=>xs.map(x=>x.textContent.trim()).filter(x=>/\b(?:Run|Reset|Send)\b/.test(x)));ok(!englishControls.length,`${file} retains English controls: ${englishControls.join(', ')}`)}ok((await page.textContent('.cf-jm-current-title')).trim()==='Agentes profundos','Portuguese journey map retains English current title');ok((await page.textContent('.cf-jm-mod-label')).trim()==='Seção 2','Portuguese journey map retains English section label');ok((await page.textContent('#key-status')).trim()==='Sem chave de API','Portuguese key status retains English copy');const englishJourney=await page.$$eval('#journey-map text,.cf-jm-nav-title,.cf-jm-current-title',xs=>xs.map(x=>x.textContent.trim()).filter(x=>['The Agent','The ReAct Loop','Tools at Scale','The Index Agent','Deep Agents','Connect NemoClaw','Always-On','Modern CLIs','Going Further'].includes(x)));ok(!englishJourney.length,`Portuguese journey map retains: ${englishJourney.join(', ')}`);await page.screenshot({path:path.join(shots,'portuguese-02c-course-page.png'),fullPage:false});
await open(page,'/nemoclaw/03a-kickstart.html');await page.waitForSelector('.language-menu-button');await page.click('.language-menu-button');links=await page.$$eval('.language-menu-popover a',xs=>xs.map(x=>({text:x.textContent.trim(),href:x.href})));ok(links.some(x=>x.text.includes('Português')&&x.href.endsWith('/pt/nemoclaw/index.html')),'untranslated English 03a does not route Portuguese to locale home');
await open(page,'/nemoclaw/localization.html');await page.waitForSelector('.loc-page');const summary=await page.textContent('#loc-summary');ok(/current/.test(summary),'Localization Studio summary missing current count');const rows=await page.$$eval('.loc-page',xs=>xs.map(x=>x.textContent));ok(rows.some(x=>x.includes('01a-loop.html'))&&rows.some(x=>x.includes('02c-deep.html')),'Localization Studio omits translated Module 1-2 pages');ok(await page.isVisible('#loc-source')&&await page.isVisible('#loc-target'),'comparison frames are not visible');await page.screenshot({path:path.join(shots,'localization-studio-desktop.png'),fullPage:false});
await page.setViewportSize({width:390,height:844});await open(page,'/pt/nemoclaw/index.html');await page.waitForSelector('.language-menu-button');const badges=await page.$$eval('.language-fallback-badge',xs=>xs.map(x=>x.textContent.trim()));const translatedBadges=await page.$$eval('.module-card:nth-child(-n+2) .language-fallback-badge',xs=>xs.length);const pendingBadges=await page.$$eval('.module-card:nth-child(n+3) .language-fallback-badge',xs=>xs.length);ok(translatedBadges===0,'translated Modules 1-2 still show English fallback badges');ok(pendingBadges>=8&&badges.every(x=>x==='EN'),'pending Modules 3-4 do not visibly mark English fallback links');const disclosure=await page.textContent('.howto');ok(disclosure.includes('prévia parcial')&&disclosure.includes('Módulos 1 e 2'),'Portuguese landing page does not disclose coverage through Module 2');const overflow=await page.evaluate(()=>document.documentElement.scrollWidth-document.documentElement.clientWidth);ok(overflow<=2,`Portuguese mobile page overflows by ${overflow}px`);await page.locator('.howto').screenshot({path:path.join(shots,'portuguese-partial-coverage.png')});await page.locator('.module-grid').screenshot({path:path.join(shots,'portuguese-fallback-badges.png')});await page.click('.language-menu-button');await page.screenshot({path:path.join(shots,'portuguese-home-mobile-language-menu.png'),fullPage:false});
await browser.close();server.close();console.log(JSON.stringify({ok:true,summary,shots:fs.readdirSync(shots)},null,2));})().catch(e=>{try{server.close()}catch(_){};console.error(e.stack||String(e));process.exit(1)});
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--site-root", default="/tmp/pt-localization-pages")
    parser.add_argument("--screenshots", default="/tmp/pt-localization-screenshots")
    parser.add_argument("--engine", default=os.environ.get("CONTAINER_ENGINE", "podman"))
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    args = parser.parse_args()
    site = Path(args.site_root).resolve()
    shots = Path(args.screenshots).resolve()
    shots.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False) as handle:
        handle.write(RUNTIME)
        script = Path(handle.name)
    cmd = [args.engine, "run", "--rm", "--entrypoint", "node"]
    if args.engine.endswith("podman"):
        cmd.append("--userns=keep-id")
    cmd += ["-e", "NODE_PATH=/opt/nemoclaw-runtime/node_modules", "-e", "SITE_ROOT=/site",
            "-e", "SHOTS=/shots", "-v", f"{site}:/site:ro", "-v", f"{shots}:/shots",
            "-v", f"{script}:/tmp/localization-runtime.js:ro", args.image, "/tmp/localization-runtime.js"]
    try:
        run = subprocess.run(cmd, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    finally:
        script.unlink(missing_ok=True)
    print(run.stdout.rstrip())
    print("localization runtime audit: " + ("OK" if run.returncode == 0 else "FAIL"))
    return run.returncode


if __name__ == "__main__":
    raise SystemExit(main())
