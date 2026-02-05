import datetime as dt
import email.utils
import re
from xml.sax.saxutils import escape

import requests
from bs4 import BeautifulSoup

SV_URL = "https://supremeventures.com/latest-results/"
JI_TODAY_URL = "https://www.jamaicaindex.com/lottery/jamaica-lotto-results-for-today"

OUT_FILE = "rss.xml"
FEED_TITLE = "Supreme Ventures – Latest Results (Unofficial RSS)"
FEED_LINK = SV_URL
FEED_DESC = "Auto-generated RSS feed from public results pages (for convenience only)."

GAMES = [
    "Cash Pot", "Hot Pick", "Pick 2", "Pick 3", "Pick 4",
    "Lucky 5", "Top Draw", "Dollaz", "Lotto", "Super Lotto", "Money Time"
]

def try_parse_sv_basic(html: str):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    items = []
    for g in GAMES:
        m = re.search(rf"{re.escape(g)}\s*[·:\-]\s*([A-Z0-9\s]+)", text, re.IGNORECASE)
        if m:
            val = " ".join(m.group(1).split())[:80]
            items.append((g, f"{g}: {val}", SV_URL))
    return items if items else None

def parse_jamaicaindex_today(html: str):
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    big = "\n".join(lines)

    raw_blocks = re.split(r"\n-\s*#", "\n" + big)
    blocks = []
    for b in raw_blocks:
        b = b.strip()
        if not b:
            continue
        if not re.match(r"^\d+", b):
            continue
        blocks.append("#" + b)

    items = []
    for b in blocks:
        m_no = re.search(r"#(\d+)", b)
        draw_no = m_no.group(1) if m_no else "unknown"

        game = None
        for g in GAMES:
            if re.search(rf"\b{re.escape(g)}\b", b, re.IGNORECASE):
                game = g
                break
        if not game:
            continue

        draw_time = None
        m_time = re.search(r"\b(EARLYBIRD|MORNING|MIDDAY|MIDAFTERNOON|DRIVETIME|EVENING)\b", b, re.IGNORECASE)
        if m_time:
            draw_time = m_time.group(1).upper()

        cleaned = re.sub(r"\s+", " ", b).strip()
        cleaned = cleaned[:220]

        title_parts = [game]
        if draw_time:
            title_parts.append(draw_time)
        title_parts.append(f"#{draw_no}")
        title = " – ".join(title_parts)

        items.append((title, cleaned, JI_TODAY_URL))

    return items[:40]

def build_rss(items):
    now = dt.datetime.utcnow()
    pubdate = email.utils.format_datetime(now)

    rss_items = []
    for title, desc, link in items:
        guid = escape(f"{title}|{desc[:80]}|{link}")
        rss_items.append(f"""\
<item>
  <title>{escape(title)}</title>
  <link>{escape(link)}</link>
  <guid isPermaLink="false">{guid}</guid>
  <pubDate>{pubdate}</pubDate>
  <description>{escape(desc)}</description>
</item>""")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
<channel>
  <title>{escape(FEED_TITLE)}</title>
  <link>{escape(FEED_LINK)}</link>
  <description>{escape(FEED_DESC)}</description>
  <lastBuildDate>{pubdate}</lastBuildDate>
  {''.join(rss_items)}
</channel>
</rss>
"""

def main():
    headers = {"User-Agent": "Mozilla/5.0 (GitHub Actions RSS generator)"}

    # Try SV (bonus)
    sv_items = None
    try:
        r = requests.get(SV_URL, headers=headers, timeout=30)
        r.raise_for_status()
        sv_items = try_parse_sv_basic(r.text)
    except Exception:
        sv_items = None

    # Main feed from JamaicaIndex today page
    r = requests.get(JI_TODAY_URL, headers=headers, timeout=30)
    r.raise_for_status()
    ji_items = parse_jamaicaindex_today(r.text)

    final_items = []
    if sv_items:
        for g, desc, link in sv_items[:15]:
            final_items.append((f"{g} – (SV summary)", desc, link))
    final_items.extend(ji_items)

    if not final_items:
        raise RuntimeError("No results parsed.")

    rss = build_rss(final_items)

    with open(OUT_FILE, "w", encoding="utf-8") as f:
        f.write(rss)

if __name__ == "__main__":
    main()
