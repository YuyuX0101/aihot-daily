#!/usr/bin/env python3
"""Generate AI HOT daily HTML from API data."""

import json, sys, os

def generate_daily(date_str):
    repo_dir = "/mnt/e/hermes-agent-data/.hermes/aihot-daily-repo"
    
    # Read API data from stdin or file
    if os.path.exists("/tmp/daily.json"):
        with open("/tmp/daily.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)
    
    if "error" in data:
        print(f"Error: {data['error']}")
        return False
    
    # Read template
    with open(f"{repo_dir}/daily-template.html", "r", encoding="utf-8") as f:
        template = f.read()
    
    # Prepare content
    lead_title = data.get("lead", {}).get("title", "") if data.get("lead") else ""
    lead_para = data.get("lead", {}).get("leadParagraph", "") if data.get("lead") else ""
    lead_text = lead_para if lead_para else lead_title
    
    sections_html = ""
    item_counter = 1
    
    for section in data.get("sections", []):
        label = section.get("label", "")
        items = section.get("items", [])
        if not items:
            continue
        
        # Pure text section header, no icons
        sections_html += f"""
    <div class="section">
      <div class="section-header">
        <span class="section-title">{label}</span>
        <span class="section-count">{len(items)} 条</span>
      </div>
"""
        for item in items:
            title = item.get("title", "")
            summary = item.get("summary", "")
            source = item.get("sourceName", "")
            url = item.get("sourceUrl", "")
            
            link_html = f'<a href="{url}" class="item-link" target="_blank">阅读原文 →</a>' if url else ""
            
            sections_html += f"""
      <div class="item">
        <div class="item-header">
          <div class="item-num">{item_counter}</div>
          <div class="item-title">{title}</div>
        </div>
        <div class="item-source">{source}</div>
        <div class="item-summary">{summary}</div>
        {link_html}
      </div>
"""
            item_counter += 1
        
        sections_html += "    </div>\n"
    
    # Flashes (no icon)
    flashes_html = ""
    if data.get("flashes"):
        flashes_html = '<div class="section">\n'
        flashes_html += '      <div class="section-header"><span class="section-title">快讯</span></div>\n'
        flashes_html += '      <div class="flashes">\n'
        for flash in data.get("flashes", []):
            f_title = flash.get("title", "")
            f_source = flash.get("sourceName", "")
            flashes_html += f'        <div class="flash"><span class="flash-dot"></span><span class="flash-text">{f_title}</span><span class="flash-source">{f_source}</span></div>\n'
        flashes_html += '      </div>\n    </div>\n'
    
    # Replace template
    html = template.replace("{{DATE}}", date_str)
    html = html.replace("{{LEAD}}", lead_text)
    html = html.replace("{{ITEM_COUNT}}", str(item_counter - 1))
    html = html.replace("{{SECTIONS}}", sections_html)
    html = html.replace("{{FLASHES}}", flashes_html)
    
    # Save
    output_path = f"{repo_dir}/{date_str}.html"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"Generated: {output_path}")
    print(f"Total items: {item_counter - 1}")
    return True

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 generate_daily.py YYYY-MM-DD")
        sys.exit(1)
    
    date_str = sys.argv[1]
    success = generate_daily(date_str)
    sys.exit(0 if success else 1)
