/* Only display publications belonging to the current Shanghai business day. */
(() => {
  const calendar = new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit'
  });
  const dateLabel = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: 'long', day: 'numeric', weekday: 'long'
  });
  const pending = {
    daily: '今天的日报尚未收录。',
    builder: '今天的作品尚未收录。',
    deals: '今天的优惠尚未收录。'
  };
  let activeDay = '';
  let generation = 0;
  const rendered = new Map();

  function textElement(tag, value) {
    const node = document.createElement(tag);
    node.textContent = value;
    return node;
  }

  function present(channel, entries, message) {
    const signature = JSON.stringify([entries, message]);
    if (rendered.get(channel) === signature) return;
    rendered.set(channel, signature);
    const panel = document.getElementById(channel);
    const output = panel.querySelector('.channel-content');
    const pager = panel.querySelector('.pager');
    const [prev, next] = pager.querySelectorAll('button');
    let index = 0;
    function show() {
      output.replaceChildren();
      pager.hidden = entries.length < 2;
      if (!entries.length) {
        output.append(textElement('p', message));
        return;
      }
      const entry = entries[index];
      const link = document.createElement('a');
      link.className = 'desk-entry';
      link.href = entry.href;
      const title = textElement('strong', entry.title);
      const summary = textElement('span', entry.summary);
      link.append(title, summary, textElement('small', entry.action));
      output.append(link);
      pager.querySelector('small').textContent = (index + 1) + ' / ' + entries.length;
    }
    prev.onclick = () => { index = (index + entries.length - 1) % entries.length; show(); };
    next.onclick = () => { index = (index + 1) % entries.length; show(); };
    show();
  }

  async function get(path, type = 'json') {
    const response = await fetch(path, {cache: 'no-store'});
    if (!response.ok) throw new Error('Publication unavailable');
    return type === 'json' ? response.json() : response.text();
  }

  async function load() {
    const now = new Date();
    const day = calendar.format(now);
    const revision = ++generation;
    if (day !== activeDay) {
      for (const key of Object.keys(pending)) present(key, [], '正在读取当日内容…');
    }
    activeDay = day;
    const label = document.getElementById('business-day');
    label.dateTime = day;
    label.textContent = dateLabel.format(now) + ' · 北京时间';

    const [unified, archive] = await Promise.allSettled([
      get('data/editions_index.json').then(dates =>
        dates.includes(day) ? get('data/editions/' + day + '.json') : null),
      get('days.json').then(days => days.includes(day))
    ]);
    if (generation !== revision) return;
    const issue = unified.value;
    const channels = issue && issue.edition_date === day ? issue.channels : {};
    for (const key of Object.keys(pending)) {
      const group = channels[key];
      const entries = (group?.items || []).map(item => ({
        title: item.title,
        summary: key === 'daily' ? 'AIHOT 转载 · ' + (item.author || '上游来源') + ' · 未独立核验' :
          item.author_claim || item.summary || item.notes || '',
        action: key === 'builder' ? '看作品与简介 ↗' : '阅读全文 ↗',
        href: 'e/' + day + '.html#' + encodeURIComponent(item.id)
      }));
      if (key === 'daily' && !entries.length && archive.value) {
        try {
          const html = await get(day + '.html', 'text');
          if (generation !== revision) return;
          const doc = new DOMParser().parseFromString(html, 'text/html');
          const articles = doc.querySelectorAll('article.item');
          for (const item of articles) {
            const title = item.querySelector('.item-title')?.textContent;
            if (title) entries.push({title, summary: 'AIHOT 转载 · 未独立核验',
              action: '打开当日日报 ↗', href: day + '.html'});
          }
          if (!entries.length) entries.push({title: '今日 AI HOT 日报', summary: day,
            action: '打开当日日报 ↗', href: day + '.html'});
        } catch {
          if (generation !== revision) return;
          entries.push({title: '今日 AI HOT 日报', summary: '预览暂时无法加载。',
            action: '打开当日日报 ↗', href: day + '.html'});
        }
      }
      const failed = unified.status === 'rejected' || (key === 'daily' && archive.status === 'rejected');
      present(key, entries, group?.meta?.empty_message ||
        (failed ? '暂时无法读取当日内容，请稍后刷新。' : pending[key]));
    }
  }
  load();
  setInterval(() => { if (!document.hidden) load(); }, 60000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
})();
