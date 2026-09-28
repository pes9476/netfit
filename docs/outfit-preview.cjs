// Local-only visual QA. Serves only this page and public fitness static assets.
const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../fitness/static/fitness');
const html = `<!doctype html><html lang="ko"><meta charset="utf-8"><title>NETFIT 착용 확인</title>
<link rel="stylesheet" href="/static/fitness/css/netfit-outfits.css">
<style>body{margin:24px;background:#080f1b;color:#eef5ff;font:16px system-ui}button{padding:10px;margin:4px;background:#172637;color:white;border:1px solid #3c5868;border-radius:8px;cursor:pointer}.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:16px}.card{border:1px solid #254354;border-radius:20px;padding:20px;background:radial-gradient(at 50% 35%,#192b47,#0b1422);text-align:center}.netfit-fitting{--fitting-size:260px;margin:20px auto}.small .netfit-fitting{--fitting-size:180px}h1{font-size:22px}output{display:block;margin:12px}label{margin:12px}@media(max-width:900px){.grid{grid-template-columns:repeat(2,1fr)}}</style>
<h1>네 캐릭터 · 실제 피팅룸 렌더러</h1><p>계정·구매·점수에는 영향을 주지 않는 로컬 미리보기입니다.</p>
<nav id="presets"></nav><output id="selection"></output><label><input id="size" type="checkbox">실제 피팅룸 크기</label><label><input id="motion" type="checkbox">움직임 확인</label><div class="grid" id="grid"></div>
<script src="/static/fitness/js/netfit-outfits.js"></script><script>
const grid=document.getElementById('grid');
for(const [style,name] of [['active','백호'],['muscular','포동'],['soft','토리'],['balanced','아콩']]){const card=document.createElement('section');card.className='card';card.innerHTML='<h2>'+name+'</h2><div class="netfit-fitting" data-paused="true" data-style="'+style+'"></div>';grid.append(card)}
function show(codes){document.getElementById('selection').textContent=codes.map(c=>NetfitOutfits.labels[c]).join(' + ')||'기본';document.querySelectorAll('.netfit-fitting').forEach(el=>NetfitOutfits.render(el,codes))}
for(const [name,codes] of [['기본',[]],['얼굴 3종',['BAND','GLASS','HEADSET']],['밴드·마스크·목걸이',['BAND','MASK','MEDAL']],['운동복·벨트·글러브',['SPORT','BELT','GLOVES']],['날개·망토·검',['WING','CLOAK','SWORD']],...NetfitOutfits.codes.map(c=>[NetfitOutfits.labels[c],[c]])]){const b=document.createElement('button');b.textContent=name;b.onclick=()=>show(codes);document.getElementById('presets').append(b)}
document.getElementById('size').onchange=e=>grid.classList.toggle('small',e.target.checked);
document.getElementById('motion').onchange=e=>document.querySelectorAll('.netfit-fitting').forEach(el=>el.dataset.paused=String(!e.target.checked));
show(['BAND','GLASS','HEADSET']);</script></html>`;
http.createServer((req,res)=>{
  const pathname = new URL(req.url,'http://localhost').pathname;
  if(pathname==='/'){res.setHeader('Content-Type','text/html; charset=utf-8');res.end(html);return;}
  if(!pathname.startsWith('/static/fitness/')){res.writeHead(404).end();return;}
  const file=path.resolve(root,decodeURIComponent(pathname.slice('/static/fitness/'.length)));
  if(!file.startsWith(root+path.sep)||!['.png','.css','.js'].includes(path.extname(file))){res.writeHead(404).end();return;}
  fs.readFile(file,(err,data)=>{if(err){res.writeHead(404).end();return;}res.setHeader('Cache-Control','no-store');res.setHeader('Content-Type',({'.png':'image/png','.css':'text/css','.js':'text/javascript'})[path.extname(file)]);res.end(data);});
}).listen(8765,'127.0.0.1',()=>console.log('Outfit QA: http://127.0.0.1:8765'));
