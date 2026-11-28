(() => {
  const picker = document.querySelector('[data-date-picker]');
  if (picker) {
    if (picker.dataset.urlTemplate) {
      picker.addEventListener('change', () => {
        location.href = picker.dataset.urlTemplate.replace('{date}', encodeURIComponent(picker.value));
      });
    } else {
      const panels = Array.from(document.querySelectorAll('[data-date-panel]'));
      const show = (day, updateUrl) => {
        for (const panel of panels) panel.hidden = panel.dataset.datePanel !== day;
        for (const label of document.querySelectorAll('[data-current-date]')) label.textContent = day;
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
  const caption = document.createElement('span');
  caption.textContent = '日期';
  const select = document.createElement('select');
  select.setAttribute('aria-label', '选择日报日期');
  const currentOption = document.createElement('option');
  currentOption.value = current;
  currentOption.textContent = current;
  select.append(currentOption);
  select.addEventListener('change', () => { location.href = select.value + '.html'; });
  label.append(caption, select);
  legacyDate.replaceWith(label);

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
  }).catch(() => {});
})();
