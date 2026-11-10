"""Standalone offline HTML report, in English or French. Contents are always rendered as text."""

import base64
import hashlib
import html
import json
from pathlib import Path

from .i18n import UI


CSS = r"""
:root{color-scheme:light;--ink:#152e26;--muted:#53675f;--paper:#f5f7f3;--white:#fff;--line:#d9e2da;--green:#155f43;--green-bg:#e3f2e7;--amber:#854509;--amber-bg:#fff1d8;--red:#9b3426;--red-bg:#fce9e3;--accent:#d8ee9b;--radius:18px}
*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.55 'Segoe UI',system-ui,sans-serif}button,input{font:inherit}button,a,input,summary{-webkit-tap-highlight-color:transparent}button,summary{cursor:pointer}button:focus-visible,a:focus-visible,input:focus-visible,summary:focus-visible{outline:3px solid #236cac;outline-offset:4px}a{color:inherit}button{transition:background .16s ease,transform .16s ease}button:active{transform:translateY(1px)}.skip{position:absolute;left:20px;top:-80px;background:white;padding:12px;z-index:5}.skip:focus{top:10px}
.shell{max-width:1420px;margin:auto;padding:0 44px}header{border-bottom:1px solid var(--line);background:var(--paper)}.topbar{min-height:90px;display:flex;justify-content:space-between;align-items:center;gap:24px}.brand{display:flex;align-items:center;gap:12px;font-size:23px;font-weight:700;letter-spacing:-.8px;text-decoration:none}.brand svg{width:36px;height:36px}.topnav{display:flex;gap:26px;align-items:center;font-size:14px}.topnav a{text-decoration:none;padding:12px 0}.topnav a:hover{text-decoration:underline}.pill{display:inline-flex;align-items:center;gap:8px;border:1px solid var(--line);border-radius:999px;padding:7px 12px;font-size:12px;font-weight:650;letter-spacing:.2px;white-space:nowrap}.dot{width:7px;height:7px;border-radius:50%;background:var(--green)}
.hero{display:grid;grid-template-columns:1.45fr 1fr;gap:60px;align-items:center;padding:55px 0 44px}.eyebrow{text-transform:uppercase;letter-spacing:2px;font-size:12px;font-weight:700;color:var(--green);margin:0 0 16px}h1{font-size:clamp(36px,4.5vw,64px);line-height:1.06;letter-spacing:-2.8px;max-width:800px;margin:0 0 24px;font-weight:650}h1 span{color:var(--green)}.intro{max-width:630px;font-size:17px;color:var(--muted);margin:0}.hero-note{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:22px 0 0;font-size:13px;color:var(--muted)}.hero-note .pill{background:white}.loop-card{border-radius:24px;background:#183c30;color:white;padding:28px;box-shadow:0 15px 35px #162e260d}.loop-label{font-size:12px;letter-spacing:2px;text-transform:uppercase;color:#c7decf}.flow{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:26px 0 24px}.flow-node{display:flex;flex-direction:column;align-items:center;gap:10px;font-size:12px;flex:1;text-align:center}.flow-node b{display:grid;place-items:center;width:49px;height:49px;border:1px solid #5c7d6a;border-radius:16px;font:22px/1 ui-monospace,monospace;color:var(--accent)}.flow-node:last-child b{background:var(--accent);color:#193c30;border-color:var(--accent)}.connector{height:1px;flex:.3;background:#769b83;margin-top:-28px}.loop-card p{font-size:14px;color:#d4e3da;margin:0;border-top:1px solid #426150;padding-top:18px}
.metrics{display:grid;grid-template-columns:1fr 1fr 1fr;border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;background:white;margin-bottom:44px}.metric{padding:20px 26px;border-right:1px solid var(--line);display:flex;align-items:center;gap:18px}.metric:last-child{border:0}.metric strong{font-size:32px;font-weight:600;letter-spacing:-1px}.metric span{display:block;font-size:13px;color:var(--muted)}.metric b{display:block;font-size:14px;font-weight:600}.section-heading{display:flex;justify-content:space-between;align-items:end;gap:20px;margin:0 0 20px}h2{font-size:25px;letter-spacing:-.7px;line-height:1.25;margin:0}h3{font-size:17px;letter-spacing:-.2px;margin:0 0 14px}.section-heading p{color:var(--muted);font-size:13px;margin:6px 0 0}.section-index{font:13px ui-monospace,monospace;color:var(--muted)}
.explorer{display:grid;grid-template-columns:270px minmax(0,1fr);gap:24px;align-items:start}.scenarios{display:grid;gap:8px}.scenario{display:flex;align-items:flex-start;gap:13px;background:transparent;border:1px solid transparent;border-radius:12px;padding:14px;width:100%;text-align:left;color:var(--ink);min-height:73px}.scenario:hover{background:#e9eee7}.scenario[aria-pressed=true]{background:white;border-color:#94b7a1;box-shadow:0 3px 10px #142d2605}.scenario .number{font:12px ui-monospace,monospace;color:var(--muted);padding-top:4px}.scenario .name{font-size:14px;font-weight:650;display:block}.scenario .subtitle{font-size:12px;color:var(--muted);display:block;margin-top:3px}.scenario[aria-pressed=true] .number{color:var(--green)}.scenario .mini-dot{margin-left:auto;margin-top:7px;width:7px;height:7px;flex-shrink:0;border-radius:100%;background:var(--green)}.scenario .mini-dot.stale{background:var(--red)}.scenario .mini-dot.limit{background:var(--amber)}
.panel{background:var(--white);border:1px solid var(--line);border-radius:var(--radius);overflow:hidden;min-width:0}.verdict{padding:28px 30px 24px;border-bottom:1px solid var(--line);position:relative}.verdict:before{content:'';position:absolute;inset:0 auto 0 0;width:4px;background:var(--green)}.verdict.stale:before{background:var(--red)}.verdict.limit:before{background:var(--amber)}.verdict-head{display:flex;align-items:center;justify-content:space-between;gap:14px;margin-bottom:16px}.badge{display:inline-flex;align-items:center;gap:7px;background:var(--green-bg);color:var(--green);border-radius:7px;font-size:12px;font-weight:700;padding:5px 9px}.badge.stale{background:var(--red-bg);color:var(--red)}.badge.limit{background:var(--amber-bg);color:var(--amber)}.frozen{font-size:12px;color:var(--muted)}.verdict h3{font-size:27px;line-height:1.22;letter-spacing:-.7px;margin:0 0 12px}.verdict p{margin:0;color:var(--muted);font-size:15px;max-width:750px}.assessment{padding:25px 30px}.reason-list{padding:0;list-style:none;display:grid;gap:10px;margin:0 0 26px}.reason-list li{display:flex;gap:10px;font-size:14px}.reason-list li:before{content:'•';color:var(--green);font-weight:700}.dep-list{display:grid;gap:0;border:1px solid var(--line);border-radius:12px;overflow:hidden}.dep-row{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:16px;padding:15px 18px;border-bottom:1px solid var(--line);align-items:center}.dep-row:last-child{border:0}.dep-name{font-size:14px;font-weight:650}.dep-meta{color:var(--muted);font-size:12px;margin-top:4px}.dep-state{font-size:12px;white-space:nowrap}.helper{color:var(--muted);font-size:12px;margin:17px 0 0}.panel-section{border-top:1px solid var(--line);padding:25px 30px}.context-tools{display:flex;justify-content:space-between;gap:24px;align-items:center;margin-bottom:18px}.context-tools h3{margin:0}.search label{display:block;font-size:12px;font-weight:600;margin-bottom:5px}.search input{width:230px;max-width:100%;border:1px solid #b8c9bc;border-radius:8px;padding:10px 12px;min-height:44px;background:#fbfcfa;color:var(--ink)}.context-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.object-card{padding:18px;border:1px solid var(--line);border-radius:12px;background:#fbfcfa;min-width:0}.object-card .kind{font-size:11px;letter-spacing:1px;text-transform:uppercase;color:var(--muted)}.object-card h4{font-size:15px;line-height:1.35;margin:8px 0}.object-card p{font-size:13px;color:var(--muted);margin:0}.object-card .revision{font-size:11px;color:var(--muted);margin-top:14px;font-family:ui-monospace,monospace}.artifact{grid-column:1/-1;border:1px solid var(--line);border-radius:12px;padding:16px 18px;background:white;min-width:0}.artifact summary{font-size:14px;font-weight:650;min-height:28px}.artifact .file-meta{font-size:12px;color:var(--muted);margin-top:5px;overflow-wrap:anywhere}pre{font:13px/1.65 ui-monospace,Consolas,monospace;white-space:pre-wrap;overflow-wrap:anywhere;background:#172e26;color:#e0efe6;border-radius:8px;padding:18px;margin:16px 0 0;max-height:350px;overflow:auto}.empty{font-size:14px;color:var(--muted);padding:16px}.technical summary{min-height:34px;font-size:13px;font-weight:600}.trace{display:grid;grid-template-columns:160px minmax(0,1fr);gap:10px;margin-top:12px;font-size:12px}.trace dt{color:var(--muted)}.trace dd{margin:0;overflow-wrap:anywhere;font-family:ui-monospace,Consolas,monospace}
.scope{display:grid;grid-template-columns:1fr 1fr;gap:40px;padding:45px 0 40px;margin-top:40px;border-top:1px solid var(--line)}.scope p,.scope li{font-size:14px;color:var(--muted)}.scope ul{padding-left:18px;margin:15px 0}.scope-code{background:white;border:1px solid var(--line);border-radius:12px;padding:16px;font:13px/1.7 ui-monospace,monospace;overflow-wrap:anywhere}.scope .small{font-size:12px;margin:10px 0 0}footer{border-top:1px solid var(--line);padding:22px 0 30px;display:flex;justify-content:space-between;gap:20px;font-size:12px;color:var(--muted)}.noscript{background:white;border:1px solid var(--line);padding:24px;border-radius:12px}
.comparison{margin-bottom:24px}.comparison-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.comparison pre{margin:6px 0 0;font-size:12px}.comparison h3{font-size:14px}@media(max-width:760px){.comparison-grid{grid-template-columns:1fr}}
@media(min-width:1500px){.shell{padding:0 60px}}@media(max-width:1050px){.shell{padding:0 28px}.hero{gap:28px}.explorer{grid-template-columns:230px minmax(0,1fr)}.metric{padding:18px;gap:12px}.context-tools{align-items:start;flex-direction:column;gap:12px}.search,.search input{width:100%}}
@media(max-width:760px){.shell{padding:0 20px}.topbar{min-height:76px}.topnav>a{display:none}.topnav{gap:10px}.brand{font-size:21px}.hero{grid-template-columns:1fr;padding:34px 0 28px;gap:26px}h1{letter-spacing:-1.6px;font-size:42px}.intro{font-size:16px}.loop-card{padding:22px}.flow{margin:18px 0}.hero-note{margin-top:18px}.metrics{margin-bottom:32px}.metric{padding:15px 12px;display:block}.metric strong{font-size:27px}.metric b{font-size:12px}.metric span{font-size:11px}.explorer{grid-template-columns:1fr}.scenarios{grid-template-columns:repeat(2,minmax(0,1fr));gap:6px}.scenario{padding:10px;gap:8px;min-height:85px;background:#edf1eb;border-color:var(--line)}.scenario .name{font-size:13px}.scenario .subtitle{font-size:11px}.scenario .number{font-size:10px}.scenario .mini-dot{display:none}.verdict{padding:24px 20px}.verdict h3{font-size:24px}.assessment,.panel-section{padding:22px 20px}.context-grid{grid-template-columns:1fr}.verdict-head{flex-wrap:wrap}.dep-row{padding:12px;gap:8px}.dep-name{font-size:13px}.dep-state{white-space:normal;text-align:right;font-size:11px}.scope{grid-template-columns:1fr;gap:20px;margin-top:28px;padding:30px 0}.trace{grid-template-columns:1fr;gap:4px}.trace dd{margin-bottom:9px}.section-index{display:none}footer{display:block}footer span{display:block;margin-bottom:6px}}
@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}button{transition:none}}@media(forced-colors:active){.scenario[aria-pressed=true]{outline:3px solid Highlight;outline-offset:-3px}.scenario[aria-pressed=true] .name{text-decoration:underline}}@media print{.scenarios,.search,.topnav{display:none}.hero{padding:20px 0}.explorer{display:block}.shell{padding:0}.panel,.loop-card{box-shadow:none}.scope-code{display:none}body{background:white}.scope{break-inside:avoid}}
"""

JS = r"""
const report=JSON.parse(document.getElementById('report-data').textContent);
const T=report.ui;const lang=report.lang||'en';
const cases=report.scenarios;
const $=id=>document.getElementById(id);
const make=(tag,cls,text)=>{const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;};
const fmt=(s,o)=>s.replace(/\{(\w+)\}/g,(_,k)=>o[k]??'');
let selected=cases[0];
function context(){
  const query=$('filter').value.trim().toLocaleLowerCase(lang);
  const container=$('context');container.replaceChildren();
  for(const item of selected.objects){
    if(query&&!JSON.stringify([item.title,item.object_id,item.document.content]).toLocaleLowerCase(lang).includes(query))continue;
    const card=make('article','object-card');card.append(make('div','kind',T.kinds[item.document.kind]||item.document.kind),make('h4','',item.title),make('p','',item.document.content),make('div','revision',fmt(T.revision,{id:item.object_id,rev:item.revision})));container.append(card);
  }
  for(const file of selected.artifacts){
    if(query&&!(file.path+' '+file.artifact_id).toLocaleLowerCase(lang).includes(query))continue;
    const box=make('details','artifact');box.append(make('summary','',fmt(T.view,{path:file.path})),make('div','file-meta',fmt(T.file_meta,{size:file.size,sha:file.sha256.slice(0,16)})),make('pre','',file.preview));
    if(file.truncated)box.append(make('p','helper',T.truncated));
    container.append(box);
  }
  if(!container.childElementCount)container.append(make('p','empty',T.no_match));
}
const nameOf=(item,id)=>item.objects.find(o=>o.object_id===id)?.title||item.artifacts.find(f=>f.artifact_id===id)?.path||id;
function show(item){
  selected=item;
  for(const button of $('scenarios').children)button.setAttribute('aria-pressed',String(button.dataset.id===item.id));
  const v=item.validation;const contextOnly=v.purpose==='CONTEXT_INSPECTION_NOT_AUTHORIZATION';
  const state=item.limit?'limit':v.eligible===false||v.stability==='UNSTABLE'?'stale':'';
  $('verdict').className='verdict '+state;
  $('badge').className='badge '+state;
  $('badge').textContent=item.limit?T.b_limit:v.stability==='UNSTABLE'?T.b_unstable:v.eligible===null?T.b_kept:v.eligible?T.b_same:T.b_review;
  $('headline').textContent=item.limit?T.h_limit:v.stability==='UNSTABLE'?T.h_unstable:contextOnly?(v.eligible?T.h_ctx_same:T.h_ctx_changed):v.eligible===null?T.h_kept:v.eligible?T.h_ok:T.h_stale;
  $('explanation').textContent=item.explanation;
  $('case-count').textContent=String(cases.indexOf(item)+1).padStart(2,'0')+' / '+String(cases.length).padStart(2,'0');
  const reasons=$('reasons');reasons.replaceChildren();
  const messages=item.limit?T.r_limit:v.issues.length?v.issues.map(issue=>(T.issues[issue.code]||issue.message)+(issue.reference_id?' ('+nameOf(item,issue.reference_id)+')':'')):v.eligible===null?T.r_kept:T.r_ok;
  for(const message of [...new Set(messages)])reasons.append(make('li','',message));
  const changes=$('changes');changes.replaceChildren();
  for(const change of item.changes||[]){
    const box=make('section','comparison');box.append(make('h3','',change.name));
    const grid=make('div','comparison-grid');
    for(const [label,text] of [[T.before,change.before],[T.after,change.after]]){const col=make('div');col.append(make('b','dep-meta',label),make('pre','',text));grid.append(col);}
    box.append(grid);changes.append(box);
  }
  const deps=$('dependencies');deps.replaceChildren();
  for(const dep of v.dependencies){
    const row=make('div','dep-row');const name=nameOf(item,dep.reference_id);
    // Path-derived file identifiers add nothing for a reader; object IDs stay visible.
    const ref=name===dep.reference_id||dep.reference_id.startsWith('file:')?'':dep.reference_id+' · ';
    const left=make('div');left.append(make('div','dep-name',name),make('div','dep-meta',ref+dep.origins.map(x=>T.sources[x]||x).join(' + ')));
    if(dep.state==='CHANGED')left.append(make('div','dep-meta',dep.current_revision&&dep.expected_revision!==dep.current_revision?fmt(T.rev_change,{a:dep.expected_revision,b:dep.current_revision}):fmt(T.hash_change,{a:(dep.expected_sha256||T.absent).slice(0,10),b:(dep.current_sha256||T.absent).slice(0,10)})));
    row.append(left,make('span','badge dep-state '+(dep.state==='CURRENT'?'':'stale'),T.states[dep.state]||dep.state));deps.append(row);
  }
  if(!v.dependencies.length)deps.append(make('p','empty',T.no_deps));
  const m=item.snapshot.manifest;
  $('trace').replaceChildren();
  for(const [label,value] of [[T.t_snapshot,m.snapshot_id],[T.t_project,m.project_id],[T.t_cut,String(m.cut_event_seq)],[T.t_events,String(item.event_count)],[T.t_capture,m.stability==='STABLE'?T.t_stable:T.t_unstable],[T.t_date,m.created_at],[T.t_mode,item.mode],[T.t_action,T.t_none]])$('trace').append(make('dt','',label),make('dd','',value));
  context();
}
for(const [index,item] of cases.entries()){
  const button=make('button','scenario');button.type='button';button.dataset.id=item.id;button.setAttribute('aria-pressed','false');
  const text=make('span');text.append(make('span','name',item.title),make('span','subtitle',item.subtitle));
  button.append(make('span','number',String(index+1).padStart(2,'0')),text,make('span','mini-dot '+(item.limit?'limit':item.validation.eligible===false?'stale':'')));
  button.addEventListener('click',()=>{show(item);history.replaceState(null,'','#'+encodeURIComponent(item.id));});$('scenarios').append(button);
}
$('filter').addEventListener('input',context);
let initial=cases[0];try{initial=cases.find(c=>c.id===decodeURIComponent(location.hash.slice(1)))||initial;}catch{}
show(initial);
"""

LOGO = '<svg viewBox="0 0 40 40" fill="none" aria-hidden="true"><rect width="40" height="40" rx="12" fill="#183c30"/><path d="M12 23V16a7 7 0 0 1 14 0v2M28 17v7a7 7 0 0 1-14 0v-2" stroke="#d8ee9b" stroke-width="2.2"/><path d="m23 15 3 3 3-3M11 25l3-3 3 3" stroke="#d8ee9b" stroke-width="2.2"/></svg>'


def render(data: dict) -> str:
    lang = data.get("lang") if data.get("lang") in UI else "en"
    t = UI[lang]
    cases = data["scenarios"]
    count = len(cases)
    file_count = len(cases[0]["artifacts"])
    object_count = len(cases[0]["objects"])
    synthetic = data["kind"] == "demo"
    context_only = any(item["validation"].get("purpose") == "CONTEXT_INSPECTION_NOT_AUTHORIZATION" for item in cases)
    payload = json.dumps({**data, "lang": lang, "ui": t}, ensure_ascii=False, separators=(",", ":"))
    payload = payload.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    script_hash = base64.b64encode(hashlib.sha256(JS.encode("utf-8")).digest()).decode("ascii")
    fallback = "".join(f"<p><strong>{html.escape(item['title'])}</strong> — {html.escape(item['explanation'])}</p>" for item in cases)
    scope = "".join(f"<li>{html.escape(item)}</li>" for item in data["limits"])
    pick = lambda demo, other: t[demo] if synthetic else t[other]
    command = "principalloop demo" if synthetic else ("principalloop codex report" if context_only else "principalloop snapshot list")
    return f'''<!doctype html>
<html lang="{lang}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'sha256-{script_hash}'; style-src 'unsafe-inline'; img-src data:; connect-src 'none'; base-uri 'none'; form-action 'none'">
<meta name="description" content="{html.escape(data['subtitle'])}">
<title>PrincipalLoop — {html.escape(data['title'])}</title><style>{CSS}</style></head>
<body><a class="skip" href="#explorer">{t['skip']}</a>
<header><div class="shell topbar"><a class="brand" href="#top" aria-label="{t['brand']}">{LOGO}PrincipalLoop</a>
<nav class="topnav" aria-label="{t['nav']}"><a href="#explorer">{t['explore']}</a><a href="#scope">{t['limits_link']}</a><span class="pill"><span class="dot"></span> {pick('observation', 'readonly')}</span></nav></div></header>
<main class="shell" id="top"><section class="hero" aria-labelledby="hero-title"><div><p class="eyebrow">{t['eyebrow']}</p><h1 id="hero-title">{t['h1a']}<br><span>{t['h1b']}</span></h1><p class="intro">{t['intro_context'] if context_only else t['intro_default']}</p><div class="hero-note"><span class="pill">{t['tag_context'] if context_only else t['tag_default']}</span><span>{pick('synthetic', 'private')}</span></div></div>
<aside class="loop-card" aria-label="{t['steps']}"><div class="loop-label">{t['chain']}</div><div class="flow"><div class="flow-node"><b>01</b><span>{t['step1']}</span></div><span class="connector" aria-hidden="true"></span><div class="flow-node"><b>02</b><span>{t['step2_context'] if context_only else t['step2_default']}</span></div><span class="connector" aria-hidden="true"></span><div class="flow-node"><b>03</b><span>{t['step3']}</span></div></div><p>{t['chain_note']}</p></aside></section>
<section class="metrics" aria-label="{t['metrics']}"><div class="metric"><strong>{count:02}</strong><div><b>{pick('m_cases', 'm_snapshot')}</b><span>{pick('m_cases_note', 'm_snapshot_note')}</span></div></div><div class="metric"><strong>{object_count:02}</strong><div><b>{t['m_objects']}</b><span>{t['m_objects_note']}</span></div></div><div class="metric"><strong>{file_count:02}</strong><div><b>{t['m_file'] if file_count == 1 else t['m_files']}</b><span>{t['m_files_note']}</span></div></div></section>
<section id="explorer" aria-labelledby="explorer-title"><div class="section-heading"><div><p class="eyebrow">{pick('eyebrow_demo', 'eyebrow_snapshot')}</p><h2 id="explorer-title">{pick('h2_demo', 'h2_snapshot')}</h2><p>{html.escape(data['subtitle'])}</p></div><span class="section-index" id="case-count"></span></div>
<noscript><div class="noscript"><h3>{t['noscript']}</h3>{fallback}<p>{t['noscript_note']}</p></div></noscript>
<div class="explorer"><aside class="scenarios" id="scenarios" aria-label="{t['choose']}"></aside><article class="panel"><section class="verdict" id="verdict"><div class="verdict-head"><span class="badge" id="badge">{t['badge_default']}</span><span class="frozen">{t['frozen']}</span></div><h3 id="headline" aria-live="polite"></h3><p id="explanation"></p></section>
<section class="assessment"><h3>{t['why']}</h3><ul class="reason-list" id="reasons"></ul><div id="changes"></div><h3>{t['deps']}</h3><div class="dep-list" id="dependencies"></div><p class="helper">{t['helper']}</p></section>
<section class="panel-section"><div class="context-tools"><h3>{t['inside']}</h3><div class="search"><label for="filter">{t['filter']}</label><input id="filter" type="search" placeholder="{t['placeholder']}" autocomplete="off"></div></div><div class="context-grid" id="context"></div></section>
<section class="panel-section"><details class="technical"><summary>{t['trace_title']}</summary><dl class="trace" id="trace"></dl></details></section></article></div></section>
<section class="scope" id="scope" aria-labelledby="scope-title"><div><p class="eyebrow">{t['promise']}</p><h2 id="scope-title">{t['scope_h2']}</h2><ul>{scope}</ul></div><div><h3>{pick('replay', 'find')}</h3><p>{pick('replay_note', 'find_note')}</p><div class="scope-code">{command}</div><p class="small">{t['status_note']}</p></div></section>
</main><footer class="shell"><span>{t['footer']}</span><span>{t['footer_right']}</span></footer>
<script type="application/json" id="report-data">{payload}</script><script>{JS}</script></body></html>'''


def write_report(data: dict, path: Path) -> Path:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    # No silent replacement of an existing report or symlink target.
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(render(data))
    return path
