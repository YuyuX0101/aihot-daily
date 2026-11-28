(() => {
  let selectCount = 0;

  function enhanceSelect(select) {
    if (!select || select.dataset.enhanced) return;
    select.dataset.enhanced = 'true';
    const shell = document.createElement('div');
    shell.className = 'select-shell';
    select.before(shell);
    shell.append(select);
    select.hidden = true;
    select.tabIndex = -1;
    select.setAttribute('aria-hidden', 'true');

    const trigger = document.createElement('button');
    trigger.type = 'button';
    trigger.className = 'select-trigger';
    trigger.setAttribute('aria-haspopup', 'true');
    trigger.setAttribute('aria-expanded', 'false');
    const value = document.createElement('span');
    value.className = 'select-value';
    trigger.append(value);
    const menu = document.createElement('div');
    menu.className = 'select-menu';
    menu.hidden = true;
    menu.setAttribute('role', 'group');
    menu.setAttribute('aria-label', '日期选项');
    menu.id = 'select-menu-' + (++selectCount);
    trigger.setAttribute('aria-controls', menu.id);
    shell.append(trigger, menu);

    const close = () => {
      menu.hidden = true;
      trigger.setAttribute('aria-expanded', 'false');
    };
    const sync = () => {
      const selected = select.options[select.selectedIndex];
      value.textContent = selected ? selected.textContent : '';
      for (const option of menu.children) {
        option.setAttribute('aria-pressed', String(option.dataset.value === select.value));
      }
    };
    const refresh = () => {
      menu.replaceChildren();
      for (const item of Array.from(select.options)) {
        const option = document.createElement('button');
        option.type = 'button';
        option.dataset.value = item.value;
        option.textContent = item.textContent;
        option.setAttribute('aria-pressed', 'false');
        option.addEventListener('click', () => {
          select.value = item.value;
          sync();
          select.dispatchEvent(new Event('change', {bubbles: true}));
          close();
          trigger.focus();
        });
        menu.append(option);
      }
      sync();
    };
    const open = () => {
      menu.hidden = false;
      trigger.setAttribute('aria-expanded', 'true');
      menu.querySelector('[aria-pressed="true"]')?.focus();
    };
    trigger.addEventListener('click', () => {
      if (menu.hidden) open();
      else close();
    });
    trigger.addEventListener('keydown', event => {
      if (event.key === 'ArrowDown') {
        event.preventDefault();
        open();
      }
    });
    document.addEventListener('click', event => {
      if (!shell.contains(event.target)) close();
    });
    document.addEventListener('keydown', event => {
      if (event.key === 'Escape' && !menu.hidden) {
        close();
        trigger.focus();
      }
    });
    select._refresh = refresh;
    select._sync = sync;
    refresh();
  }

  const picker = document.querySelector('[data-date-picker]');
  if (picker) {
    enhanceSelect(picker);
    if (picker.dataset.urlTemplate) {
      picker.addEventListener('change', () => {
        location.href = picker.dataset.urlTemplate.replace('{date}', encodeURIComponent(picker.value));
      });
    } else {
      const panels = Array.from(document.querySelectorAll('[data-date-panel]'));
      const show = (day, updateUrl) => {
        for (const panel of panels) panel.hidden = panel.dataset.datePanel !== day;
        for (const label of document.querySelectorAll('[data-current-date]')) label.textContent = day;
        picker._sync?.();
        if (updateUrl) {
          const url = new URL(location.href);
          url.searchParams.set('date', day);
          history.replaceState(null, '', url);
        }
      };
      const requested = new URLSearchParams(location.search).get('date');
      if (panels.some(panel => panel.dataset.datePanel === requested)) picker.value = requested;
      show(picker.value, false);
      picker.addEventListener('change', () => show(picker.value, true));
    }
  }

  const legacyDate = document.querySelector('.hero-date');
  if (!legacyDate) return;
  const current = legacyDate.textContent.trim();
  if (!/^\d{4}-\d{2}-\d{2}$/.test(current)) return;
  const brand = document.querySelector('.nav-brand');
  if (brand) brand.textContent = 'AI 日报';
  const heading = document.querySelector('.hero h1');
  if (heading) heading.textContent = 'AI 日报';

  const label = document.createElement('label');
  label.className = 'date-picker legacy-date-picker';
  const select = document.createElement('select');
  select.setAttribute('aria-label', '选择日报日期');
  const currentOption = document.createElement('option');
  currentOption.value = current;
  currentOption.textContent = current;
  select.append(currentOption);
  select.addEventListener('change', () => { location.href = select.value + '.html'; });
  label.append(select);
  legacyDate.replaceWith(label);
  enhanceSelect(select);

  fetch('days.json', {cache: 'no-store'}).then(response => {
    if (!response.ok) throw new Error('Date index unavailable');
    return response.json();
  }).then(days => {
    for (const day of days) {
      if (day === current || !/^\d{4}-\d{2}-\d{2}$/.test(day)) continue;
      const option = document.createElement('option');
      option.value = day;
      option.textContent = day;
      select.append(option);
    }
    select._refresh?.();
  }).catch(() => {});
})();
