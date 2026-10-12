(function(){var t=document.getElementById('tip');
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
th.addEventListener('click',s);th.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();s();}});});});})();