const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
class Element {
  constructor(tag) { this.tag=tag; this.attrs={}; this.childNodes=[]; this.dataset={}; }
  setAttribute(k,v) { this.attrs[k]=String(v); }
  getAttribute(k) { return this.attrs[k]; }
  append(...nodes) { this.childNodes.push(...nodes); }
  replaceChildren(...nodes) { this.childNodes=nodes; }
}
global.document={readyState:'loading',addEventListener(){},createElementNS:(_,tag)=>new Element(tag)};
const renderer=require('./static/fitness/js/netfit-outfits.js');
const walk = el => [el,...el.childNodes.flatMap(walk)];
test('all 16 items have assets and render for all four characters',()=>{
  assert.equal(renderer.codes.length,16);
  for(const style of ['active','muscular','soft','balanced']) for(const code of renderer.codes){
    assert.ok(fs.existsSync(path.join(__dirname,'static/fitness/img',renderer.asset(code))));
    const target=new Element('div'); target.dataset.style=style;
    const svg=renderer.render(target,[code]);
    assert.ok(walk(svg).some(node=>node.attrs['data-item']===code));
    for(const image of walk(svg).filter(n=>n.tag==='image')) {
      assert.equal(image.attrs.width,'1254'); assert.equal(image.attrs.height,'1254');
    }
  }
});
test('layer order is independent of equip order; removal leaves no stale items',()=>{
  const target=new Element('div');target.dataset.style='soft';
  const layers=svg=>svg.childNodes.filter(n=>n.tag==='g').map(n=>n.attrs['data-item']);
  assert.deepEqual(layers(renderer.render(target,['HEADSET','BAND','GLASS'])),['BASE','BAND','GLASS','HEADSET']);
  assert.deepEqual(layers(renderer.render(target,['GLASS','HEADSET','BAND'])),['BASE','BAND','GLASS','HEADSET']);
  assert.deepEqual(layers(renderer.render(target,[])),['BASE']);
  assert.equal(target.childNodes.length,1);
  assert.equal(target.dataset.equipped,'');
});
test('multiple characters use unique SVG IDs and unknown items are ignored',()=>{
  const ids=[];
  for(const style of ['active','muscular','soft','balanced']) {
    const target=new Element('div'); target.dataset.style=style;
    const svg=renderer.render(target,[...renderer.codes,'UNKNOWN','GLASS']);
    ids.push(...walk(svg).map(n=>n.attrs.id).filter(Boolean));
    assert.equal(target.dataset.equipped.split(',').length,16);
  }
  assert.equal(ids.length,new Set(ids).size);
});
