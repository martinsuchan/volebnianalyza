(function(){var t=document.getElementById('tip');
function show(e,el){var s=el.getAttribute('data-tip');if(!s)return;t.textContent=s;t.hidden=false;var r=el.getBoundingClientRect();
var x=(e&&e.clientX!=null&&e.type!=='focus')?e.clientX:r.left+r.width/2,y=(e&&e.clientY!=null&&e.type!=='focus')?e.clientY:r.top;
var w=t.offsetWidth,h=t.offsetHeight;var L=Math.min(Math.max(8,x+12),innerWidth-w-8),T=y-h-12;if(T<8)T=y+16;t.style.left=L+'px';t.style.top=T+'px';}
function hide(){t.hidden=true;}
document.addEventListener('pointermove',function(e){var el=e.target.closest&&e.target.closest('[data-tip]');if(el)show(e,el);else hide();});
document.addEventListener('focusin',function(e){var el=e.target.closest&&e.target.closest('[data-tip]');if(el)show(e,el);});
document.addEventListener('focusout',hide);document.addEventListener('pointerleave',hide);})();
(function(){var m=document.querySelector('meta[name=root]'),root=m?m.content:'',data=null,idx=[],pend=[],MAX=8;
/* vlastní našeptávač místo <datalist>: ve WebView (např. prohlížeč Facebooku na Androidu) se datalist rozbalí přes klávesnici celý;
   rejstřík všech obcí (assets/hledat.js) se načte až při prvním použití vyhledávání */
function norm(v){return v.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase();}
function need(cb){if(data){cb();return;}pend.push(cb);if(pend.length>1)return;var s=document.createElement('script');s.src=root+'assets/hledat.js';
s.onload=function(){data=window.HLEDAT||[];idx=data.map(function(d){return norm(d[0]);});var p=pend;pend=[];p.forEach(function(f){f();});};document.head.appendChild(s);}
function search(v){v=norm(v.trim());if(v.length<2)return[];var a=[],b=[],c=[],i,t,p;
for(i=0;i<data.length;i++){t=idx[i];p=t.indexOf(v);if(p<0)continue;if(p===0)a.push(data[i]);else if(/[\s(–-]/.test(t.charAt(p-1)))b.push(data[i]);else c.push(data[i]);if(a.length>=MAX)break;}
return a.concat(b,c).slice(0,MAX);}
var n=0;document.querySelectorAll('input[data-search]').forEach(function(inp){
var box=document.createElement('ul'),id='sugg-'+(++n),hits=[],act=-1;box.className='sugg';box.id=id;box.setAttribute('role','listbox');box.hidden=true;
inp.parentNode.appendChild(box);inp.setAttribute('role','combobox');inp.setAttribute('aria-autocomplete','list');inp.setAttribute('aria-controls',id);inp.setAttribute('aria-expanded','false');
function close(){box.hidden=true;act=-1;inp.setAttribute('aria-expanded','false');inp.removeAttribute('aria-activedescendant');}
function mark(){[].forEach.call(box.children,function(li,k){li.classList.toggle('on',k===act);li.setAttribute('aria-selected',k===act?'true':'false');});
if(act>=0){inp.setAttribute('aria-activedescendant',id+'-'+act);box.children[act].scrollIntoView({block:'nearest'});}else inp.removeAttribute('aria-activedescendant');}
function fit(){var r=inp.getBoundingClientRect(),vv=window.visualViewport,h=vv?vv.height+vv.offsetTop:window.innerHeight;box.style.maxHeight=Math.max(120,h-r.bottom-12)+'px';}
function render(){if(!data){need(render);return;}hits=search(inp.value);act=-1;box.innerHTML='';
if(!hits.length){if(inp.value.trim().length>=2){var e=document.createElement('li');e.className='empty';e.textContent='Nic nenalezeno';box.appendChild(e);box.hidden=false;fit();}else close();return;}
hits.forEach(function(d,k){var li=document.createElement('li'),a=document.createElement('a');li.id=id+'-'+k;li.setAttribute('role','option');a.href=root+d[1];a.textContent=d[0];a.tabIndex=-1;li.appendChild(a);box.appendChild(li);});
box.hidden=false;inp.setAttribute('aria-expanded','true');fit();}
inp.addEventListener('input',render);inp.addEventListener('focus',function(){need(function(){});if(inp.value.trim().length>=2)render();});
inp.addEventListener('keydown',function(e){if(e.key==='ArrowDown'&&hits.length){e.preventDefault();act=(act+1)%hits.length;mark();}
else if(e.key==='ArrowUp'&&hits.length){e.preventDefault();act=act<=0?hits.length-1:act-1;mark();}
else if(e.key==='Enter'){e.preventDefault();var d=hits[act>=0?act:0];if(d)location.href=root+d[1];}else if(e.key==='Escape')close();});
box.addEventListener('mousedown',function(e){e.preventDefault();});
inp.addEventListener('blur',function(){setTimeout(close,150);});
if(window.visualViewport)window.visualViewport.addEventListener('resize',function(){if(!box.hidden)fit();});});})();
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