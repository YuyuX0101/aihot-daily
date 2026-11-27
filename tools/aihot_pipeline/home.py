"""Static navigation and today's three-channel layout."""

from datetime import date

from .render import page_shell


def daily_archive(days: list[str], edition_days: list[str]) -> str:
    cards = []
    destinations = {day: f"../e/{day}.html#daily" for day in edition_days}
    destinations.update({day: f"../{day}.html" for day in days})
    for day in sorted(destinations, reverse=True):
        weekday = "一二三四五六日"[date.fromisoformat(day).weekday()]
        cards.append(
            f'<a class="archive-day" href="{destinations[day]}"><time datetime="{day}">{day}</time>'
            f'<span>周{weekday}</span></a>'
        )
    return page_shell(title="历史日报 · AI HOT", kicker="日报归档", heading="历史日报",
                      lead=f"共 {len(cards)} 期，按发布日期排列。",
                      body='<div class="archive-grid">' + "".join(cards) + '</div>', active_nav="daily")


def build_home() -> str:
    sections = []
    for key, title, archive, label in (
        ("daily", "AI HOT 日报", "daily/index.html", "历史日报"),
        ("builder", "Builder 一手作品", "builder/index.html", "作品档案"),
        ("deals", "AI 羊毛雷达", "deals/index.html", "历史优惠"),
    ):
        sections.append(f"""
<section id="{key}" class="desk-card desk-{key}" tabindex="-1" aria-labelledby="{key}-title">
  <div class="desk-body"><header class="desk-heading"><h2 id="{key}-title">{title}</h2><small class="item-total"></small></header>
  <div class="channel-content" aria-live="polite"><p>正在读取当日内容…</p></div>
  <div class="desk-controls"><a class="action soft" href="{archive}">{label}</a>
  <div class="pager" hidden><button type="button" aria-label="{title}上一页">上一页</button><small></small><button type="button" aria-label="{title}下一页">下一页</button></div></div>
  </div></section>""")
    body = """
<section class="cover"><div class="cover-copy">
<time id="business-day" class="issue-date">北京时间</time>
<h1><span id="day-heading">今日</span><em> AI </em>手记</h1>
<p>AI 动态、开发者作品与优惠</p>
</div></section>
<nav class="quick-nav" aria-label="跳至今日栏目"><a href="#daily">日报</a><a href="#builder">Builder 作品</a><a href="#deals">羊毛雷达</a></nav>
<div id="today" class="desk-grid" aria-label="今日统一期次">""" + "".join(sections) + """</div>
<noscript>请启用 JavaScript 查看北京时间当天的内容，或使用各栏目归档入口。</noscript>
<script src="assets/today.js?v=3" defer></script>"""
    return page_shell(title="AI HOT 日报", kicker="", heading="", lead="", body=body,
                      active_nav="home", css_href="assets/editorial.css", home_href="index.html")
