(() => {
  const select = document.getElementById('id_avatar_preference');
  if (!select || document.getElementById('mascotPicker')) return;
  const group = document.createElement('div');
  group.id = 'mascotPicker'; group.className = 'mascot-picker';
  group.setAttribute('role', 'group'); group.setAttribute('aria-label', '마스코트 선택');
  const buttons = [];
  for (const option of select.options) {
    if (!['ACTIVE','MUSCULAR','SOFT','BALANCED'].includes(option.value)) continue;
    const button = document.createElement('button');
    button.type = 'button'; button.className = 'mascot-choice';
    button.setAttribute('aria-label', option.text + ' 선택');
    const art = document.createElement('span');
    art.className = 'mascot-choice-art'; art.setAttribute('aria-hidden','true');
    const avatar = document.createElement('span');
    avatar.className = 'avatar-roster style-' + option.value.toLowerCase();
    art.append(avatar);
    const name = document.createElement('strong'); name.textContent = option.text;
    const status = document.createElement('small');
    button.append(art,name,status);
    button.addEventListener('click', () => {
      select.value = option.value;
      select.dispatchEvent(new Event('change', {bubbles:true}));
    });
    buttons.push({button,status,value:option.value}); group.append(button);
  }
  if (!buttons.length) return;
  function sync() {
    for (const item of buttons) {
      const active = item.value === select.value;
      item.button.setAttribute('aria-pressed',String(active));
      item.status.textContent = active ? '✓ 선택됨' : '선택하기';
    }
  }
  select.insertAdjacentElement('afterend',group);
  select.closest('.field')?.classList.add('full');
  // Keep the native select as a working fallback when JavaScript is unavailable.
  select.hidden = true;
  const label = select.labels[0];
  if (label) { label.removeAttribute('for'); label.id='mascotPickerLabel';group.setAttribute('aria-labelledby',label.id); }
  select.addEventListener('change',sync); sync();
})();
