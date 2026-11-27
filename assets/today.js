/* The homepage follows Shanghai time. A dated preview is available by explicit URL. */
(() => {
  const calendar = new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit'
  });
  const dateLabel = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: 'long', day: 'numeric', weekday: 'long'
  });
  const requested = new URLSearchParams(location.search).get('preview');
  const preview = /^\d{4}-\d{2}-\d{2}$/.test(requested || '') &&
    calendar.format(new Date(requested + 'T12:00:00+08:00').getTime() || 0) === requested ? requested : '';
  const pending = {
    daily: '本期暂无日报记录。',
    builder: '本期暂无作品记录。',
    deals: '本期暂无优惠记录。'
  };
  let activeDay = '';
  let generation = 0;
  const rendered = new Map();

  function textElement(tag, value) {
    const node = document.createElement(tag);
    node.textContent = value;
    return node;
  }

  function present(channel, entries, message, featured = false) {
    const signature = JSON.stringify([entries, message, featured]);
    if (rendered.get(channel) === signature) return;
    rendered.set(channel, signature);
    const panel = document.getElementById(channel);
    const output = panel.querySelector('.channel-content');
    const pager = panel.querySelector('.pager');
    const [prev, next] = pager.querySelectorAll('button');
    const pageSize = featured ? 3 : 1;
    const pages = Math.ceil(entries.length / pageSize);
    panel.classList.toggle('featured', featured);
    panel.classList.toggle('unpublished', !entries.length);
    panel.querySelector('.item-total').textContent = entries.length ? entries.length + ' 条' : '';
    let page = 0;
    function show() {
      output.replaceChildren();
      pager.hidden = pages < 2;
      if (!entries.length) {
        output.append(textElement('p', message));
        return;
      }
      for (const entry of entries.slice(page * pageSize, (page + 1) * pageSize)) {
        const link = document.createElement('a');
        link.className = 'desk-entry';
        link.href = entry.href;
        link.append(textElement('strong', entry.title), textElement('span', entry.summary));
        output.append(link);
      }
      prev.disabled = page === 0;
      next.disabled = page === pages - 1;
      pager.querySelector('small').textContent = (page + 1) + ' / ' + pages;
    }
    prev.onclick = () => { if (page > 0) { page--; show(); } };
    next.onclick = () => { if (page + 1 < pages) { page++; show(); } };
    show();
  }

  async function get(path, type = 'json') {
    const response = await fetch(path, {cache: 'no-store'});
    if (!response.ok) throw new Error('Publication unavailable');
    return type === 'json' ? response.json() : response.text();
  }

  async function load() {
    const now = new Date();
    const day = preview || calendar.format(now);
    const revision = ++generation;
    if (day !== activeDay) {
      for (const key of Object.keys(pending)) present(key, [], '正在读取当日内容…');
    }
    activeDay = day;
    const label = document.getElementById('business-day');
    label.dateTime = day;
    label.textContent = dateLabel.format(new Date(day + 'T12:00:00+08:00')) + ' · 北京时间' + (preview ? ' · 指定日期预览' : '');
    document.getElementById('day-heading').textContent = preview ? '本期' : '今日';

    const [unified, archive] = await Promise.allSettled([
      get('data/editions_index.json').then(dates => {
        if (dates.includes(day)) return get('data/editions/' + day + '.json');
        if (!preview) return null;
        return get('data/previews/' + day + '-daily.json').then(feed => {
          if (feed.edition_date !== day || feed.channel !== 'daily') throw new Error('Preview date mismatch');
          return {edition_date: day, channels: {daily: feed}, previewFeed: true};
        });
      }),
      get('days.json').then(days => days.includes(day))
    ]);
    if (generation !== revision) return;
    const issue = unified.value;
    const channels = issue && issue.edition_date === day ? issue.channels : {};
    const results = [];
    for (const key of Object.keys(pending)) {
      const group = channels[key];
      const entries = (group?.items || []).map(item => {
        let href = 'e/' + day + '.html#' + encodeURIComponent(item.id);
        if (issue.previewFeed) {
          const source = /^https:\/\/aihot\.news\/items\/[a-zA-Z0-9_-]+$/.test(item.source_url);
          href = source ? item.source_url : 'https://aihot.news/daily/' + day;
        }
        const summary = key === 'daily'
          ? 'AIHOT 转载 · ' + (item.author || '上游来源') + ' · 未独立核验'
          : item.author_claim || item.summary || item.notes || '';
        return {title: item.title, summary, href};
      });
      if (key === 'daily' && !entries.length && archive.value) {
        try {
          const html = await get(day + '.html', 'text');
          if (generation !== revision) return;
          const doc = new DOMParser().parseFromString(html, 'text/html');
          const articles = doc.querySelectorAll('article.item');
          for (const item of articles) {
            const title = item.querySelector('.item-title')?.textContent;
            if (title) entries.push({title, summary: 'AIHOT 转载 · 未独立核验',
              href: day + '.html'});
          }
          if (!entries.length) entries.push({title: 'AI HOT 日报', summary: day,
            href: day + '.html'});
        } catch {
          if (generation !== revision) return;
          entries.push({title: 'AI HOT 日报', summary: '预览暂时无法加载。',
            href: day + '.html'});
        }
      }
      const failed = unified.status === 'rejected' || (key === 'daily' && archive.status === 'rejected');
      results.push({key, entries, message: group?.meta?.empty_message ||
        (failed ? '暂时无法读取当日内容，请稍后刷新。' : pending[key])});
    }
    const lead = results.reduce((best, result) => result.entries.length > best.entries.length ? result : best);
    for (const result of results) present(result.key, result.entries, result.message, result === lead);
  }
  load();
  setInterval(() => { if (!document.hidden) load(); }, 60000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
})();
