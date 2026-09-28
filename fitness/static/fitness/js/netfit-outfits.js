/* Fitted atlas renderer. Source artwork is never independently resized/recentred.
 * Every path below is measured in the same 627 x 627 character cell.
 * Keep patches tight: a face item must not repaint the forehead or necklace.
 */
(function (root) {
  'use strict';
  const NS = 'http://www.w3.org/2000/svg';
  const CELL = 627;
  const NAMES = {active: '백호', slim: '백호', muscular: '포동', soft: '토리', balanced: '아콩'};
  const INDEX = {active: 0, slim: 0, muscular: 1, soft: 2, balanced: 3};
  const LABELS = {BAND:'헤어밴드', GLASS:'선글라스', HEADSET:'헤드셋', MASK:'마스크',
    BELT:'챔피언 벨트', MEDAL:'목걸이', GLOVES:'글러브', CAP:'모자', SPORT:'운동복',
    CROWN:'왕관', CLOAK:'망토', WING:'날개', SWORD:'빔세이버', DRAGON:'미니 드래곤',
    AURA:'오라', VICTORY:'트로피'};
  const rect = (x,y,w,h) => `M${x} ${y}h${w}v${h}h-${w}Z`;
  const poly = points => `M${points}Z`;
  // Order in each row: 백호, 포동, 토리, 아콩. Paths include contact shadows.
  const PATCH = {
    BAND: [poly('174 239L184 178L245 116L338 84L417 89L459 116L466 174L446 147L352 144L269 174L219 210'),
      poly('155 205L161 151L210 114L296 103L383 121L439 168L453 213L432 190L352 160L268 151L200 173'),
      poly('173 180L181 132L234 100L330 88L420 102L471 144L480 184L447 170L365 145L284 142L211 163'),
      poly('141 197L153 150L192 115L269 91L353 105L425 143L464 195L465 216L426 190L360 167L284 158L206 172')],
    GLASS: [poly('200 208L292 185L373 165L466 162L473 211L449 242L398 250L359 231L339 251L293 261L246 252L222 231L201 229'),
      poly('155 185L212 177L276 182L310 180L380 177L454 184L451 208L431 215L414 246L367 257L326 241L306 219L290 228L271 249L225 258L190 244L175 215L154 211'),
      poly('173 167L225 149L293 151L337 161L364 154L424 148L481 167L478 185L459 196L450 215L412 228L374 220L341 191L323 193L305 216L265 227L220 216L203 188L175 187'),
      poly('142 172L197 167L259 174L302 177L332 172L398 166L468 176L466 198L446 202L434 232L393 249L354 242L320 215L302 212L279 239L244 249L200 238L176 202L144 199')],
    MASK: [poly('193 206L213 229L254 250L298 252L345 230L388 232L418 247L447 230L460 206L462 259L443 303L405 326L323 332L252 316L218 290L216 244L194 224'),
      poly('154 203L177 235L199 253L234 254L270 239L302 257L335 257L367 241L408 253L434 236L453 204L453 265L432 310L390 333L310 347L231 340L186 313L158 265'),
      poly('156 185L184 187L228 207L274 212L310 207L341 221L371 211L410 207L456 193L493 178L503 194L472 214L458 240L459 279L483 299L429 317L346 329L261 320L208 303L226 280L228 247L217 223L158 200'),
      poly('141 199L166 229L197 240L233 239L272 257L303 263L338 251L363 240L403 241L433 225L466 198L466 258L447 299L411 325L345 342L278 342L216 325L177 300L148 260')],
    MEDAL: [poly('282 316L316 321L341 356L365 317L391 317L366 366L368 385L372 408L352 428L323 425L306 405L309 383L317 371'),
      poly('226 328L255 334L306 383L341 337L368 329L327 392L335 411L332 433L312 449L287 446L270 429L273 405L285 391'),
      poly('252 329L284 336L337 380L382 338L419 329L364 386L367 408L358 434L335 447L310 440L298 418L302 396L312 383'),
      poly('226 322L257 331L303 370L342 332L375 322L326 379L336 400L331 426L310 442L286 440L270 422L270 398L282 382')],
    BELT: [poly('268 389L312 397L359 395L400 417L403 448L381 475L340 482L298 458L257 439'),
      poly('169 442L206 450L247 445L278 433L315 432L349 443L389 449L438 441L441 492L399 510L359 518L339 530L305 539L271 532L248 517L201 509L168 496'),
      poly('132 359L167 374L217 383L264 376L287 362L322 351L353 353L384 367L404 380L451 383L489 373L520 359L523 414L491 434L427 448L389 462L366 477L330 483L296 476L267 461L215 449L158 433L132 416'),
      poly('174 388L197 402L241 407L272 397L310 392L342 398L367 409L407 405L440 390L446 429L425 449L381 462L351 483L319 496L282 491L254 476L221 465L186 449L167 430')],
    GLOVES: [rect(173,345,95,122)+rect(335,314,121,107),
      rect(75,325,104,128)+rect(425,407,107,128),
      poly('42 208L126 201L142 247L169 289L111 332L48 299')+poly('521 204L577 202L616 246L605 283L552 332L500 292'),
      rect(36,303,124,119)+rect(453,300,144,126)],
    HEADSET: [poly('134 164L197 149L231 197L231 273L216 298L163 302L137 267')+poly('447 138L488 143L507 193L501 251L480 281L418 306L402 290L463 267L462 213')+poly('177 154L199 97L264 50L346 39L419 60L460 107L476 150L452 158L434 109L389 78L340 64L278 74L232 106L209 155'),
      poly('114 153L166 150L188 181L183 253L161 279L126 275L112 249')+poly('428 143L469 151L492 195L492 252L465 287L413 317L365 318L362 300L411 285L452 259L432 224')+poly('150 158L169 108L220 66L275 57L341 62L409 96L446 146L426 167L398 120L346 96L291 87L237 101L198 133L178 172'),
      poly('117 145L180 139L205 159L198 212L176 247L144 257L118 233')+poly('460 139L502 144L535 185L540 237L517 262L475 288L426 291L421 273L474 259L501 231L474 211')+poly('152 155L191 101L253 61L331 51L406 65L463 103L503 160L475 170L446 124L395 95L328 79L261 88L211 117L181 165'),
      poly('103 160L154 152L177 181L174 235L158 276L125 286L104 270')+poly('435 157L481 158L507 190L511 248L488 277L441 298L379 301L371 286L425 272L468 251L445 226')+poly('125 167L155 102L206 62L271 43L291 39L287 68L236 80L190 112L165 171')+poly('317 45L369 56L418 84L466 141L480 173L451 178L427 136L391 104L342 83L318 80')],
    CLOAK: [poly('229 309L290 312L357 320L407 310L421 348L354 351L281 336L225 354'),
      poly('173 317L222 329L300 344L369 330L407 316L447 355L454 382L396 353L308 374L224 358L160 374'),
      poly('152 294L230 323L332 330L422 324L504 296L495 326L417 353L334 360L237 350L167 325'),
      poly('158 298L220 316L302 331L389 313L437 298L467 324L402 334L321 362L292 361L216 335L151 323')],
    CAP: [rect(105,10,402,188), rect(135,5,344,185), rect(146,9,358,165), rect(125,0,362,185)],
    CROWN: [rect(140,0,350,170), rect(155,0,315,157), rect(180,0,304,154), rect(170,0,278,170)],
    SWORD: [poly('0 256L163 256L267 383L267 472L163 474L143 429L0 375'),
      poly('479 73L627 73L627 470L427 470L420 390L383 344L409 326L462 344'),
      poly('0 0L113 0L153 166L174 230L180 322L90 344L0 225'),
      poly('489 47L627 47L627 435L451 435L448 318L475 259')],
    DRAGON: [rect(0,170,205,235), rect(425,90,202,267), rect(0,39,200,215), rect(442,129,185,224)],
    VICTORY: [rect(403,324,224,272), rect(430,391,197,235), rect(474,350,153,255), rect(441,380,186,220)]
  };
  let serial = 0;
  function svgNode(tag, attrs = {}) {
    const node = document.createElementNS(NS, tag);
    for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
    return node;
  }
  function asset(code) {
    if (!code) return 'netfit-mascots.png';
    if (['CAP','SPORT','CROWN'].includes(code)) return `netfit-mascots-${code.toLowerCase()}.png`;
    return `netfit-fitted-${code.toLowerCase()}-v3.png`;
  }
  function render(target, codes = []) {
    const equipped = [...new Set(codes)].filter(code => Object.hasOwn(LABELS, code));
    const style = Object.hasOwn(INDEX, target.dataset.style) ? target.dataset.style : 'balanced';
    const index = INDEX[style];
    const x = -(index % 2) * CELL, y = -Math.floor(index / 2) * CELL;
    const prefix = `fitted-${++serial}`;
    const baseUrl = target.dataset.assetRoot || '/static/fitness/img/';
    const svg = svgNode('svg', {viewBox: '0 0 627 627', role: 'img', 'aria-label':
      `${NAMES[style]} · ${equipped.length ? equipped.map(code => LABELS[code]).join(', ') : '기본 모습'}`});
    const defs = svgNode('defs');
    svg.append(defs);
    const title = svgNode('title');
    title.textContent = svg.getAttribute('aria-label');
    svg.append(title);
    const atlas = code => svgNode('image', {href: baseUrl + asset(code), x, y, width:1254, height:1254});
    const clip = (name, path) => {
      const id = `${prefix}-${name}`;
      const node = svgNode('clipPath', {id, clipPathUnits:'userSpaceOnUse'});
      node.append(svgNode('path', {d:path})); defs.append(node);
      return `url(#${id})`;
    };
    const layer = (code, path, attrs = {}) => {
      const group = svgNode('g', {'data-item':code || 'BASE', ...attrs});
      if (path) group.setAttribute('clip-path', clip(`${code}-${defs.childNodes.length}`, path));
      group.append(atlas(code)); svg.append(group); return group;
    };
    // Erase the opaque body from back atlases. Otherwise one full sprite would
    // hide another back item, or show an unequipped hand under the saber.
    const blackId = `${prefix}-black`;
    const filter = svgNode('filter', {id:blackId, 'color-interpolation-filters':'sRGB'});
    // Cover anti-aliased silhouette edges too; otherwise back sheets leave a
    // faint duplicate outline around hands when the saber changes the pose.
    filter.append(svgNode('feMorphology', {operator:'dilate', radius:3}));
    filter.append(svgNode('feColorMatrix', {type:'matrix', values:'0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0'}));
    defs.append(filter);
    const backId = `${prefix}-outside-body`;
    const backMask = svgNode('mask', {id:backId, maskUnits:'userSpaceOnUse', x:0,y:0,width:CELL,height:CELL, style:'mask-type:luminance'});
    backMask.append(svgNode('rect', {width:CELL,height:CELL,fill:'white'}));
    const silhouette = atlas(''); silhouette.setAttribute('filter', `url(#${blackId})`);
    backMask.append(silhouette); defs.append(backMask);
    for (const code of ['AURA','CLOAK','WING','DRAGON','VICTORY']) {
      if (equipped.includes(code)) layer(code, ['DRAGON','VICTORY'].includes(code) ? PATCH[code][index] : null, {mask:`url(#${backId})`});
    }
    // Replace the saber hand rather than drawing a second hand on top of it.
    const bodyId = `${prefix}-body`;
    const bodyMask = svgNode('mask', {id:bodyId, maskUnits:'userSpaceOnUse', x:0,y:0,width:CELL,height:CELL, style:'mask-type:luminance'});
    bodyMask.append(svgNode('rect', {width:CELL,height:CELL,fill:'white'}));
    if (equipped.includes('SWORD')) bodyMask.append(svgNode('path', {d:PATCH.SWORD[index],fill:'black'}));
    defs.append(bodyMask);
    layer(equipped.includes('SPORT') ? 'SPORT' : '', null, {mask:`url(#${bodyId})`});
    // Fixed physical depth, independent of the order in which items were equipped.
    for (const code of ['SWORD','CLOAK','BELT','MEDAL','BAND','CAP','CROWN','MASK','GLASS','HEADSET','GLOVES']) {
      if (equipped.includes(code)) layer(code, PATCH[code][index]);
    }
    target.replaceChildren(svg);
    target.dataset.equipped = equipped.join(',');
    return svg;
  }
  const api = {render, codes:Object.keys(LABELS), labels:LABELS, asset, patches:PATCH};
  root.NetfitOutfits = api;
  if (typeof module !== 'undefined') module.exports = api;
  if (typeof document !== 'undefined') {
    const init = () => document.querySelectorAll('[data-netfit-fitting]').forEach(el => render(el, (el.dataset.equipped || '').split(',')));
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
    else init();
  }
})(typeof window !== 'undefined' ? window : globalThis);
