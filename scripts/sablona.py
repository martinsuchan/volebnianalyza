"""Společná šablona statického webu: hlavička s vyhledáváním, drobečková navigace, záložky územní jednotky,
relativní odkazy podle hloubky stránky, styly a skripty. Web musí fungovat i otevřený z disku (file://),
proto se data pro vyhledávání načítají jako <script>, ne přes fetch()."""
import json, os, posixpath, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svg import E
from common import ROOT

OUT = os.path.join(ROOT, 'report')
GEN = '11. 10. 2026'
AUTHOR_URL = 'https://www.facebook.com/martinsuchan85'
NAV = [('index.html', 'Přehled', 'home'), ('kv/index.html', 'Komunální volby 2026', 'kv'), ('senat/index.html', 'Senát 2026', 'senat'),
       ('nalezy.html', 'Všechny nálezy', 'nalezy'), ('metodika.html', 'Metodika', 'metodika'), ('data.html', 'Data', 'data')]


def link(frm, to):
    """Relativní odkaz ze stránky `frm` na `to` (obě cesty relativně ke kořeni webu, případně s #kotvou)."""
    path, _, frag = to.partition('#')
    r = posixpath.relpath(path, posixpath.dirname(frm) or '.') if path else posixpath.basename(frm)
    return r + (f'#{frag}' if frag else '')


def page(path, title, body, desc='', section=None, crumbs=None, tabs=None):
    """path: cesta stránky v report/ (např. 'kv/praha/nalezy.html'); crumbs: [(popisek, cesta|None)];
    tabs: [(cesta, popisek)] – záložky územní jednotky (aktuální se zvýrazní)."""
    root = '../' * path.count('/')
    nav = ''.join(f'<a href="{link(path, h)}"{" aria-current=page" if s == section else ""}>{E(t)}</a>' for h, t, s in NAV)
    cr = ''
    if crumbs:
        parts = [f'<a href="{link(path, h)}">{E(t)}</a>' if h else f'<span aria-current="page">{E(t)}</span>' for t, h in crumbs]
        cr = f'<nav class="crumbs" aria-label="Drobečková navigace">{" › ".join(parts)}</nav>'
    tb = ''
    if tabs:
        tb = '<nav class="tabs" aria-label="Sekce">' + ''.join(
            f'<a href="{link(path, h)}"{" aria-current=page" if h == path else ""}>{E(t)}</a>' for h, t in tabs) + '</nav>'
    doc = f'''<!doctype html><html lang="cs"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{E(title)} – Forenzní audit voleb 2026</title><meta name="description" content="{E(desc)}"><meta name="root" content="{root}">
<link rel="icon" href="{root}assets/favicon.svg" type="image/svg+xml"><link rel="icon" href="{root}assets/favicon-32.png" sizes="32x32" type="image/png"><link rel="apple-touch-icon" href="{root}assets/favicon-180.png">
<link rel="stylesheet" href="{root}assets/style.css"></head><body>
<header class="top"><div class="wrap"><a class="brand" href="{root}index.html">Forenzní audit voleb 2026</a><nav class="main">{nav}</nav>
<form class="search" role="search" onsubmit="return false"><label class="vh" for="q-top">Hledat obec, MČ nebo senátní obvod</label>
<input id="q-top" type="search" list="hledat-list" data-search placeholder="Hledat obec, MČ, obvod…" autocomplete="off"></form></div></header>
<datalist id="hledat-list"></datalist>
<main class="wrap">{cr}{tb}{body}</main>
<footer class="wrap foot">Autor: <a href="{AUTHOR_URL}">Martin Suchan</a>. Nezávislá analýza veřejných otevřených dat ČSÚ (stav k 11. 10. 2026),
vytvořená s pomocí AI modelu Claude Opus 5.5; může obsahovat chyby. Statistické nálezy nejsou důkazem úmyslného jednání; označují místa,
kde je vhodné ověřit originální zápisy okrskových komisí. Závazné jsou jen výsledky vyhlášené Státní volební komisí. Vygenerováno {GEN}.</footer>
<div id="tip" role="tooltip" hidden></div><script src="{root}assets/hledat.js"></script><script src="{root}assets/app.js"></script></body></html>'''
    full = os.path.join(OUT, *path.split('/'))
    os.makedirs(os.path.dirname(full), exist_ok=True)
    open(full, 'w', encoding='utf-8').write(doc)


def fig(title, sub, chart, leg='', tbl='', note=''):
    return (f'<figure class="card"><figcaption><h3>{E(title)}</h3><p class="sub">{E(sub)}</p></figcaption>{leg}<div class="cw">{chart}</div>'
            f'{f"<p class=note>{note}</p>" if note else ""}{tbl}</figure>')


JLAB = {5: 'Jistá', 4: 'Velmi vysoká', 3: 'Vysoká', 2: 'Střední', 1: 'Nízká'}


def badge_j(j):
    cls = {5: 'b-crit', 4: 'b-crit', 3: 'b-ser', 2: 'b-warn', 1: 'b-low'}[j]
    return f'<span class="badge {cls}"><span class="ico" aria-hidden="true">{"●" * min(j, 5)}</span>{JLAB[j]}</span>'


DOPAD_CLS = {'Mění mandáty': 'b-crit', 'Může změnit mandáty': 'b-ser', 'Mění zvolené': 'b-ser', 'Těsný výsledek': 'b-warn', 'Bez vlivu': 'b-low'}
DOPAD_RANK = {'Mění mandáty': 4, 'Může změnit mandáty': 3, 'Mění zvolené': 3, 'Těsný výsledek': 2, 'Bez vlivu': 1}


def badge_d(k):
    cls = DOPAD_CLS.get(k, 'b-low')
    ico = {'b-crit': '▲', 'b-ser': '△', 'b-warn': '!', 'b-low': '–'}[cls]
    return f'<span class="badge {cls}"><span class="ico" aria-hidden="true">{ico}</span>{E(k)}</span>'


def filters(table_id, selects, text=True):
    """Ovládací prvky filtru nad tabulkou; selects: [(klíč data-*, popisek, [(hodnota, text)])]."""
    s = f'<div class="filters" data-filter-for="{table_id}">'
    for key, lab, opts in selects:
        s += (f'<label>{E(lab)}<select data-key="{key}"><option value="">vše</option>'
              + ''.join(f'<option value="{E(str(v))}">{E(t)}</option>' for v, t in opts) + '</select></label>')
    if text:
        s += f'<label>Hledat v tabulce<input type="search" placeholder="např. Praha 10"></label>'
    return s + '<span class="count" aria-live="polite"></span></div>'


CSS = r'''
:root{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;
--border:rgba(11,11,11,.10);--series-1:#2a78d6;--series-2:#eb6834;--series-3:#1baf7a;--good:#0ca30c;--warning:#fab219;--serious:#ec835a;--critical:#d03b3b;
--div-pos:#2a78d6;--div-neg:#e34948;--neutral:#e1e0d9;--map-base:#e6e5df;--accent-bg:#eef4fc}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;
--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);--series-1:#3987e5;--series-2:#d95926;--series-3:#199e70;--div-pos:#3987e5;--div-neg:#e66767;--neutral:#383835;--map-base:#2c2c2a;--accent-bg:#16263a}}
:root[data-theme="dark"]{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;--border:rgba(255,255,255,.10);
--series-1:#3987e5;--series-2:#d95926;--series-3:#199e70;--div-pos:#3987e5;--div-neg:#e66767;--neutral:#383835;--map-base:#2c2c2a;--accent-bg:#16263a}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--page);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
.wrap{max-width:1120px;margin:0 auto;padding:0 16px}
a{color:var(--series-1)}
.vh{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
header.top{background:var(--surface);border-bottom:1px solid var(--border);position:sticky;top:0;z-index:5}
header.top .wrap{display:flex;flex-wrap:wrap;gap:6px 18px;align-items:center;padding-top:9px;padding-bottom:9px}
.brand{font-weight:650;color:var(--ink);text-decoration:none}
nav.main{display:flex;flex-wrap:wrap;gap:4px 14px}nav.main a{color:var(--ink2);text-decoration:none;font-size:14px;padding:2px 0;border-bottom:2px solid transparent}
nav.main a[aria-current]{color:var(--ink);border-bottom-color:var(--series-1)}
.search{margin-left:auto}.search input,.searchbig input{font:inherit;font-size:14px;padding:6px 10px;border:1px solid var(--border);border-radius:8px;background:var(--page);color:var(--ink);width:230px}
.searchbig{margin:14px 0}.searchbig input{width:100%;max-width:560px;font-size:17px;padding:10px 14px}
@media (max-width:760px){.search{margin-left:0;width:100%}.search input{width:100%}}
.crumbs{font-size:13px;color:var(--ink2);margin:16px 0 0}.crumbs a{color:var(--ink2)}
.tabs{display:flex;gap:2px;border-bottom:1px solid var(--border);margin:12px 0 0;overflow-x:auto}
.tabs a{padding:8px 12px;text-decoration:none;color:var(--ink2);border-bottom:2px solid transparent;white-space:nowrap;font-size:14.5px}
.tabs a[aria-current]{color:var(--ink);border-bottom-color:var(--series-1);font-weight:600}
h1{font-size:28px;line-height:1.2;margin:22px 0 6px}h2{font-size:21px;margin:34px 0 10px}h3{font-size:16px;margin:0}
.lead{font-size:17px;color:var(--ink2);max-width:860px}
.verdict{background:var(--accent-bg);border:1px solid var(--border);border-left:4px solid var(--series-1);border-radius:10px;padding:16px 18px;margin:18px 0}
.verdict p{margin:.35em 0}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:16px 0}
.tile{background:var(--surface);border:1px solid var(--border);border-radius:10px;padding:12px 14px}
.tile .l{color:var(--ink2);font-size:13px}.tile .v{font-size:26px;font-weight:650;margin-top:2px}.tile .s{color:var(--muted);font-size:12.5px}
.hubs{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:14px;margin:16px 0}
.hub{display:block;background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px;color:var(--ink);text-decoration:none}
.hub:hover,.hub:focus{border-color:var(--series-1)}.hub h3{color:var(--series-1);font-size:17px}.hub p{margin:6px 0 0;color:var(--ink2)}
.card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:16px;margin:16px 0}
.card figcaption{margin-bottom:6px}.sub{color:var(--ink2);margin:2px 0 0;font-size:13.5px}
.cw{width:100%;overflow-x:auto}.chart{width:100%;height:auto;display:block;min-width:620px}.chart.sm{min-width:300px}.two .cw,.two>div{min-width:0}
.chart .grid{stroke:var(--grid);stroke-width:1}.chart .axis{stroke:var(--axis);stroke-width:1}
.chart .tick{fill:var(--muted);font-size:11px;font-variant-numeric:tabular-nums}.chart .lab{fill:var(--ink2);font-size:12px}
.chart .val{fill:var(--ink2);font-size:11px;font-variant-numeric:tabular-nums}
.chart .hit{fill:transparent}.chart .mk:hover path,.chart .mk:focus path,.chart .mk:hover rect:not(.hit){opacity:.78}
.chart .col:hover,.chart .col:focus{fill:var(--grid);fill-opacity:.5}
.chart .hl{stroke:var(--critical);stroke-width:1.5;stroke-dasharray:none}.chart .expmark{stroke:var(--ink);stroke-width:2;stroke-linecap:round}
.chart :focus{outline:none}
.legend{display:flex;flex-wrap:wrap;gap:4px 16px;color:var(--ink2);font-size:13px;margin:6px 0}.lg{display:inline-flex;align-items:center;gap:6px}
.note{color:var(--ink2);font-size:13px;margin:8px 0 0}
details.tableview{margin-top:8px}details.tableview summary{cursor:pointer;color:var(--ink2);font-size:13px}
.tw{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:13.5px;margin:6px 0}
th,td{text-align:left;padding:7px 8px;border-bottom:1px solid var(--grid);vertical-align:top}th{color:var(--ink2);font-weight:600;font-size:12.5px}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums}td.id{white-space:nowrap}
table.sortable th:not([data-nosort]){cursor:pointer;user-select:none}table.sortable th:not([data-nosort]):hover{color:var(--ink)}
table.sortable th[aria-sort=ascending]::after{content:" ▲";font-size:10px}table.sortable th[aria-sort=descending]::after{content:" ▼";font-size:10px}
tr:target td{background:var(--accent-bg)}
.filters{display:flex;flex-wrap:wrap;gap:8px 12px;align-items:flex-end;margin:4px 0 8px}
.filters label{display:flex;flex-direction:column;gap:3px;font-size:12.5px;color:var(--ink2)}
.filters select,.filters input{font:inherit;font-size:14px;padding:5px 8px;border:1px solid var(--border);border-radius:8px;background:var(--page);color:var(--ink)}
.count{color:var(--muted);font-size:13px;margin-left:auto}
.badge{display:inline-flex;align-items:center;gap:5px;border-radius:999px;padding:2px 9px 2px 7px;font-size:12px;font-weight:600;white-space:nowrap;border:1px solid var(--border)}
.badge .ico{font-size:9px;letter-spacing:-1px}
.b-crit .ico{color:var(--critical)}.b-ser .ico{color:var(--serious)}.b-warn .ico{color:var(--warning)}.b-low .ico{color:var(--muted)}
.b-crit{background:color-mix(in srgb,var(--critical) 12%,transparent)}.b-ser{background:color-mix(in srgb,var(--serious) 12%,transparent)}
.b-warn{background:color-mix(in srgb,var(--warning) 14%,transparent)}
.st{display:inline-block;border-radius:999px;padding:1px 9px;font-size:12px;font-weight:600;border:1px solid var(--border);white-space:nowrap}
.st-done{background:color-mix(in srgb,var(--good) 13%,transparent)}.st-plan{color:var(--muted)}
.find{border-left:4px solid var(--grid)}.find.p1{border-left-color:var(--critical)}.find.p2{border-left-color:var(--serious)}.find.p3{border-left-color:var(--warning)}
.find dl{display:grid;grid-template-columns:150px 1fr;gap:4px 14px;margin:10px 0 0}.find dt{color:var(--ink2);font-size:13px}.find dd{margin:0}
@media (max-width:640px){.find dl{grid-template-columns:1fr}.find dt{margin-top:6px}h1{font-size:23px}}
.two{display:grid;grid-template-columns:1fr 1fr;gap:16px}@media (max-width:760px){.two{grid-template-columns:1fr}}
.foot{color:var(--muted);font-size:12.5px;padding-top:24px;padding-bottom:40px}
#tip{position:fixed;z-index:20;pointer-events:none;background:var(--surface);color:var(--ink);border:1px solid var(--border);border-radius:8px;
padding:6px 9px;font-size:12.5px;max-width:320px;box-shadow:0 4px 18px rgba(0,0,0,.18)}
.map path{stroke:var(--surface);stroke-width:.35}.map path.f{stroke:var(--ink);stroke-width:.6}
ol.steps li,ul.l li{margin:5px 0}code{font-size:13px;background:var(--grid);padding:1px 5px;border-radius:4px}
.json{font-size:12px;color:var(--ink2)}.kicker{color:var(--ink2);font-size:13px;text-transform:uppercase;letter-spacing:.04em;margin-top:24px}
'''

JS = r'''(function(){var t=document.getElementById('tip');
function show(e,el){var s=el.getAttribute('data-tip');if(!s)return;t.textContent=s;t.hidden=false;var r=el.getBoundingClientRect();
var x=(e&&e.clientX!=null&&e.type!=='focus')?e.clientX:r.left+r.width/2,y=(e&&e.clientY!=null&&e.type!=='focus')?e.clientY:r.top;
var w=t.offsetWidth,h=t.offsetHeight;var L=Math.min(Math.max(8,x+12),innerWidth-w-8),T=y-h-12;if(T<8)T=y+16;t.style.left=L+'px';t.style.top=T+'px';}
function hide(){t.hidden=true;}
document.addEventListener('pointermove',function(e){var el=e.target.closest&&e.target.closest('[data-tip]');if(el)show(e,el);else hide();});
document.addEventListener('focusin',function(e){var el=e.target.closest&&e.target.closest('[data-tip]');if(el)show(e,el);});
document.addEventListener('focusout',hide);document.addEventListener('pointerleave',hide);})();
(function(){var m=document.querySelector('meta[name=root]'),root=m?m.content:'',data=window.HLEDAT||[],dl=document.getElementById('hledat-list');
if(dl)data.forEach(function(d){var o=document.createElement('option');o.value=d[0];dl.appendChild(o);});
function find(v){v=v.trim().toLowerCase();if(!v)return null;var i,d;for(i=0;i<data.length;i++)if(data[i][0].toLowerCase()===v)return data[i];
for(i=0;i<data.length;i++)if(data[i][0].toLowerCase().indexOf(v)===0)return data[i];for(i=0;i<data.length;i++)if(data[i][0].toLowerCase().indexOf(v)>=0)return data[i];return null;}
document.querySelectorAll('input[data-search]').forEach(function(inp){function go(){var d=find(inp.value);if(d)location.href=root+d[1];}
inp.addEventListener('change',function(){var v=inp.value.trim().toLowerCase();for(var i=0;i<data.length;i++)if(data[i][0].toLowerCase()===v){go();return;}});
inp.addEventListener('keydown',function(e){if(e.key==='Enter'){e.preventDefault();go();}});});})();
(function(){document.querySelectorAll('[data-filter-for]').forEach(function(box){var tb=document.getElementById(box.getAttribute('data-filter-for'));if(!tb)return;
var rows=[].slice.call(tb.tBodies[0].rows),cnt=box.querySelector('.count'),q=box.querySelector('input[type=search]');
function apply(){var f={};box.querySelectorAll('select[data-key]').forEach(function(s){if(s.value)f[s.getAttribute('data-key')]=s.value;});
var s=q?q.value.trim().toLowerCase():'',n=0;rows.forEach(function(r){var ok=true;for(var k in f){var v=r.getAttribute('data-'+k)||'';
if(k==='jistota'||k==='dopad'){if(+v<+f[k])ok=false;}else if(v!==f[k])ok=false;}if(ok&&s&&r.textContent.toLowerCase().indexOf(s)<0)ok=false;r.hidden=!ok;if(ok)n++;});
if(cnt)cnt.textContent='Zobrazeno '+n+' z '+rows.length;}
box.addEventListener('input',apply);box.addEventListener('change',apply);apply();});})();
(function(){document.querySelectorAll('table.sortable').forEach(function(t){var ths=t.tHead.rows[0].cells;[].forEach.call(ths,function(th,i){if(th.hasAttribute('data-nosort'))return;
th.tabIndex=0;function s(){var asc=th.getAttribute('aria-sort')!=='ascending';[].forEach.call(ths,function(h){h.removeAttribute('aria-sort');});
th.setAttribute('aria-sort',asc?'ascending':'descending');var b=t.tBodies[0],rs=[].slice.call(b.rows);
rs.sort(function(a,c){var x=a.cells[i],y=c.cells[i],vx=x.getAttribute('data-v'),vy=y.getAttribute('data-v');if(vx===null)vx=x.textContent.trim();if(vy===null)vy=y.textContent.trim();
var nx=parseFloat(vx),ny=parseFloat(vy),r=(!isNaN(nx)&&!isNaN(ny))?nx-ny:vx.localeCompare(vy,'cs');return asc?r:-r;});rs.forEach(function(r){b.appendChild(r);});}
th.addEventListener('click',s);th.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();s();}});});});})();'''


def write_assets(search_entries):
    """search_entries: [(popisek, cesta od kořene webu)]."""
    os.makedirs(os.path.join(OUT, 'assets'), exist_ok=True)
    open(os.path.join(OUT, 'assets/style.css'), 'w', encoding='utf-8').write(CSS)
    open(os.path.join(OUT, 'assets/app.js'), 'w', encoding='utf-8').write(JS)
    open(os.path.join(OUT, 'assets/hledat.js'), 'w', encoding='utf-8').write(
        'window.HLEDAT=' + json.dumps([list(e) for e in search_entries], ensure_ascii=False, separators=(',', ':')) + ';')
