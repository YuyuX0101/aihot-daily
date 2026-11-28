/* The homepage follows Shanghai time. A dated preview is available by explicit URL. */
(() => {
  const calendar = new Intl.DateTimeFormat('sv-SE', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit'
  });
  const dateLabel = new Intl.DateTimeFormat('zh-CN', {
    timeZone: 'Asia/Shanghai', year: 'numeric', month: 'long', day: 'numeric', weekday: 'long'
  });
  const requested = new URLSearchParams(location.search).get('preview');
  const requestedDate = /^\d{4}-\d{2}-\d{2}$/.test(requested || '') ? new Date(requested + 'T12:00:00+08:00') : null;
  const preview = requestedDate && !Number.isNaN(requestedDate.getTime()) && calendar.format(requestedDate) === requested ? requested : '';
  const pending = {
    daily: '本期暂无 AI 动态。',
    builder: '本期暂无作品记录。',
    deals: '本期暂无优惠记录。'
  };
  let activeDay = '';
  let availableDates = [];
  let coverDay = '';
  let generation = 0;
  const rendered = new Map();
  const cover = document.getElementById('cover-image');
  const defaultCover = cover.src;

  function textElement(tag, value, className = '') {
    const node = document.createElement(tag);
    node.textContent = value;
    if (className) node.className = className;
    return node;
  }

  function showCover(day) {
    if (coverDay === day) return;
    coverDay = day;
    cover.hidden = false;
    cover.onerror = () => {
      cover.onerror = null;
      if (cover.src !== defaultCover) cover.src = defaultCover;
      else cover.hidden = true;
    };
    cover.src = 'assets/covers/' + day + '.webp';
  }

  function present(channel, entries, message, context = '') {
    const signature = JSON.stringify([entries, message, context]);
    if (rendered.get(channel) === signature) return;
    rendered.set(channel, signature);
    const panel = document.getElementById(channel);
    const output = panel.querySelector('.channel-content');
    panel.classList.toggle('unpublished', !entries.length);
    panel.classList.toggle('has-many', entries.length >= 4);
    panel.querySelector('.item-total').textContent = context || (entries.length ? entries.length + ' 条' : '暂无收录');
    output.replaceChildren();
    if (!entries.length) {
      output.append(textElement('p', message, 'empty-message'));
      return;
    }
    for (const entry of entries) {
      const link = document.createElement('a');
      link.className = 'desk-entry';
      link.href = entry.href;
      const copy = document.createElement('div');
      copy.className = 'entry-copy';
      copy.append(textElement('strong', entry.title));
      if (entry.summary) copy.append(textElement('span', entry.summary, 'entry-summary'));
      if (entry.meta) copy.append(textElement('small', entry.meta, 'entry-meta'));
      link.append(copy);
      output.append(link);
    }
  }

  function arrange(results) {
    const counts = Object.fromEntries(results.map(result => [result.key, result.entries.length]));
    const dailyHeavy = counts.daily >= 7 && counts.daily > counts.builder;
    const flow = document.getElementById('today');
    flow.classList.toggle('daily-heavy', dailyHeavy);
    flow.classList.toggle('builder-heavy', !dailyHeavy && counts.builder >= 4);
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
    showCover(day);
    if (day !== activeDay) {
      for (const key of Object.keys(pending)) present(key, [], '正在读取当日内容…');
    }
    activeDay = day;
    const label = document.getElementById('business-day');
    label.dateTime = day;
    label.textContent = dateLabel.format(new Date(day + 'T12:00:00+08:00')) + ' · 北京时间' + (preview ? ' · 指定日期预览' : '');

    const [unified, archive] = await Promise.allSettled([
      get('data/editions_index.json').then(dates => {
        availableDates = dates;
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
    let recentIssue = null;
    const recentDay = availableDates[0] || '';
    const needsRecent = ['builder', 'deals'].some(key => !(channels[key]?.items || []).length);
    if (needsRecent && recentDay && recentDay !== day) {
      try {
        recentIssue = await get('data/editions/' + recentDay + '.json');
      } catch {}
    }
    if (generation !== revision) return;
    const results = [];
    for (const key of Object.keys(pending)) {
      let group = channels[key];
      let entryDay = day;
      let context = '';
      if (key !== 'daily' && !(group?.items || []).length) {
        const recentGroup = recentIssue?.channels?.[key];
        if ((recentGroup?.items || []).length) {
          group = recentGroup;
          entryDay = recentDay;
          context = '最近 ' + recentGroup.items.length + ' 条 · ' + recentDay;
        }
      }
      const entries = (group?.items || []).map(item => {
        let href = 'e/' + entryDay + '.html#' + encodeURIComponent(item.id);
        if (entryDay === day && issue?.previewFeed) {
          const source = /^https:\/\/aihot\.news\/items\/[a-zA-Z0-9_-]+$/.test(item.source_url);
          href = source ? item.source_url : 'https://aihot.news/daily/' + day;
        }
        if (key === 'daily') {
          return {
            title: item.title,
            meta: item.author || 'AIHOT',
            href
          };
        }
        return {
          title: item.title,
          summary: item.summary || item.author_claim || item.notes || '',
          meta: key === 'builder' ? (item.author ? '作者 · ' + item.author : '独立开发者作品') : '优惠详情与适用条件见期次页',
          href
        };
      });
      if (key === 'daily' && !entries.length && archive.value) {
        try {
          const html = await get(day + '.html', 'text');
          if (generation !== revision) return;
          const doc = new DOMParser().parseFromString(html, 'text/html');
          const articles = doc.querySelectorAll('article.item');
          for (const item of articles) {
            const title = item.querySelector('.item-title')?.textContent;
            if (title) entries.push({title, meta: 'AIHOT 转载', href: day + '.html'});
          }
          if (!entries.length) entries.push({title: 'AI 日报 · 历史日报', summary: day, href: day + '.html'});
        } catch {
          if (generation !== revision) return;
          entries.push({title: 'AI 日报 · 历史日报', summary: '预览暂时无法加载。', href: day + '.html'});
        }
      }
      const failed = unified.status === 'rejected' || (key === 'daily' && archive.status === 'rejected');
      results.push({key, entries, context, message: group?.meta?.empty_message ||
        (failed ? '暂时无法读取当日内容，请稍后刷新。' : pending[key])});
    }
    for (const result of results) present(result.key, result.entries, result.message, result.context);
    arrange(results);
  }
  load();
  setInterval(() => { if (!document.hidden) load(); }, 60000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) load(); });
})();
