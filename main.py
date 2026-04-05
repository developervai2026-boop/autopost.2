"""
Multi-Source News → Claude AI Edit → Facebook Auto Post
========================================================
Sources:
  ① Al Jazeera   ② CNN   ③ BBC   ④ Washington Post
  ⑤ TRT World    ⑥ The Jerusalem Post

Railway Deploy Version:
  - Credentials environment variable থেকে নেয় (hardcode নয়)
  - output_images/ Railway-র /tmp ফোল্ডারে সেভ হয়
  - Crash হলে auto-restart হয়

Requirements:
    pip install requests beautifulsoup4 anthropic pillow schedule lxml
"""

import requests
import anthropic
import schedule
import time
import os
import io
import json
import re
import random
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from datetime import datetime

# ============================================================
#  CONFIG — Railway Environment Variables থেকে নেয়
#  Railway Dashboard → Variables-এ এগুলো set করুন
# ============================================================

ANTHROPIC_API_KEY    = os.environ.get("ANTHROPIC_API_KEY", "")
FB_PAGE_ACCESS_TOKEN = os.environ.get("FB_PAGE_ACCESS_TOKEN", "")
FB_PAGE_ID           = os.environ.get("FB_PAGE_ID", "")

POST_INTERVAL_MINUTES = int(os.environ.get("POST_INTERVAL_MINUTES", "60"))
MAX_POSTS_PER_RUN     = int(os.environ.get("MAX_POSTS_PER_RUN", "6"))
MAX_PER_SOURCE        = int(os.environ.get("MAX_PER_SOURCE", "2"))

# Railway-তে /tmp ফোল্ডার writable
IMAGE_OUTPUT_DIR = "/tmp/output_images"
POSTED_URLS_FILE = "/tmp/posted_urls.json"

IMAGE_WIDTH        = 1200
IMAGE_HEIGHT       = 630
FONT_SIZE_HEADLINE = 50
FONT_SIZE_SOURCE   = 26

# ============================================================
#  Startup — credentials check
# ============================================================

def check_credentials():
    missing = []
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")
    if not FB_PAGE_ACCESS_TOKEN:
        missing.append("FB_PAGE_ACCESS_TOKEN")
    if not FB_PAGE_ID:
        missing.append("FB_PAGE_ID")

    if missing:
        print("❌ নিচের Environment Variables set করা নেই:")
        for m in missing:
            print(f"   → {m}")
        print("\nRailway Dashboard → আপনার project → Variables-এ set করুন।")
        raise SystemExit(1)

    print("✅ সব credentials পাওয়া গেছে।")

# ============================================================
#  NEWS SOURCES
# ============================================================

NEWS_SOURCES = [
    {
        "name":       "Al Jazeera",
        "short":      "AL JAZEERA",
        "rss":        "https://www.aljazeera.com/xml/rss/all.xml",
        "color":      (190, 28,  44),
        "text_color": (255, 255, 255),
        "hashtags":   "#AlJazeera #আন্তর্জাতিক_সংবাদ",
    },
    {
        "name":       "CNN",
        "short":      "CNN",
        "rss":        "http://rss.cnn.com/rss/edition.rss",
        "color":      (204, 0,   0),
        "text_color": (255, 255, 255),
        "hashtags":   "#CNN #বিশ্বসংবাদ",
    },
    {
        "name":       "BBC News",
        "short":      "BBC NEWS",
        "rss":        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "color":      (187, 25,  25),
        "text_color": (255, 255, 255),
        "hashtags":   "#BBC #আন্তর্জাতিক",
    },
    {
        "name":       "The Washington Post",
        "short":      "WASHINGTON POST",
        "rss":        "https://feeds.washingtonpost.com/rss/world",
        "color":      (0,   40,  85),
        "text_color": (255, 255, 255),
        "hashtags":   "#WashingtonPost #বিশ্বরাজনীতি",
    },
    {
        "name":       "TRT World",
        "short":      "TRT WORLD",
        "rss":        "https://www.trtworld.com/rss",
        "color":      (0,   113, 187),
        "text_color": (255, 255, 255),
        "hashtags":   "#TRTWorld #আন্তর্জাতিক_সংবাদ",
    },
    {
        "name":       "The Jerusalem Post",
        "short":      "JERUSALEM POST",
        "rss":        "https://www.jpost.com/rss/rssfeedsfrontpage.aspx",
        "color":      (0,   100, 60),
        "text_color": (255, 255, 255),
        "hashtags":   "#JerusalemPost #মধ্যপ্রাচ্য",
    },
]

# ============================================================
#  STEP 1 — সব source থেকে news scrape
# ============================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def scrape_all_sources():
    all_articles = []
    loaded_urls  = load_posted_urls()

    for source in NEWS_SOURCES:
        print(f"\n📰 {source['name']} থেকে news নিচ্ছি...")
        articles = scrape_rss(source, MAX_PER_SOURCE, loaded_urls)
        print(f"   ✅ {len(articles)}টি নতুন article")
        all_articles.extend(articles)

    random.shuffle(all_articles)
    return all_articles[:MAX_POSTS_PER_RUN]


def scrape_rss(source, max_articles, loaded_urls):
    articles = []
    try:
        resp = requests.get(source["rss"], headers=HEADERS, timeout=15)
        resp.raise_for_status()

        try:
            soup = BeautifulSoup(resp.content, "xml")
        except Exception:
            soup = BeautifulSoup(resp.content, "html.parser")

        items = soup.find_all("item")

        for item in items:
            if len(articles) >= max_articles:
                break

            title = item.find("title")
            link  = item.find("link")
            desc  = item.find("description")

            if not title or not link:
                continue

            if link.text and link.text.strip().startswith("http"):
                url = link.text.strip()
            elif link.get("href"):
                url = link["href"].strip()
            else:
                try:
                    url = link.find_next_sibling(string=True).strip()
                except Exception:
                    continue

            if not url or not url.startswith("http"):
                continue
            if url in loaded_urls:
                continue

            raw_title = title.get_text(strip=True)
            raw_title = re.sub(r'<!\[CDATA\[|\]\]>', '', raw_title).strip()
            if not raw_title or len(raw_title) < 10:
                continue

            raw_desc = ""
            if desc:
                raw_desc = desc.get_text(strip=True)
                raw_desc = re.sub(r'<!\[CDATA\[|\]\]>', '', raw_desc)
                raw_desc = re.sub(r'<[^>]+>', '', raw_desc).strip()[:400]

            image_url = extract_image_from_item(item, url)

            articles.append({
                "title":       raw_title,
                "url":         url,
                "description": raw_desc,
                "image_url":   image_url,
                "source":      source,
            })

    except Exception as e:
        print(f"   ❌ RSS error ({source['name']}): {e}")

    return articles


def extract_image_from_item(item, url):
    enc = item.find("enclosure")
    if enc and enc.get("url") and "image" in enc.get("type", "image"):
        return enc["url"]
    media = item.find("media:content") or item.find("content")
    if media and media.get("url"):
        return media["url"]
    thumb = item.find("media:thumbnail") or item.find("thumbnail")
    if thumb and thumb.get("url"):
        return thumb["url"]
    return fetch_og_image(url)


def fetch_og_image(url):
    try:
        resp = requests.get(url, headers=HEADERS, timeout=8)
        soup = BeautifulSoup(resp.text, "html.parser")
        og   = soup.find("meta", property="og:image")
        if og and og.get("content"):
            return og["content"]
        tw = soup.find("meta", attrs={"name": "twitter:image"})
        if tw and tw.get("content"):
            return tw["content"]
    except Exception:
        pass
    return None


# ============================================================
#  STEP 2 — Claude API দিয়ে বাংলায় edit
# ============================================================

def edit_with_claude(article):
    source_name = article["source"]["name"]
    print(f"  🤖 Claude edit [{source_name}]: {article['title'][:55]}...")

    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    prompt = f"""তুমি একজন বাংলাদেশী সংবাদ সম্পাদক। নিচের ইংরেজি সংবাদ পড়ে দুটি জিনিস তৈরি করো:

১. bangla_headline — সংক্ষিপ্ত ও আকর্ষণীয় বাংলা headline (সর্বোচ্চ ১২ শব্দ)
২. fb_caption — Facebook page-এর জন্য engaging বাংলা caption:
   - ৩-৫ বাক্য, প্রাসঙ্গিক emoji ব্যবহার করো
   - পাঠকের মনে কৌতূহল তৈরি করো
   - শেষে "সূত্র: {source_name}" উল্লেখ করো

**Headline:** {article['title']}
**Description:** {article.get('description', 'N/A')[:300]}
**Source:** {source_name}

শুধু JSON দাও, অন্য কিছু না:
{{
  "bangla_headline": "...",
  "fb_caption": "..."
}}"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}]
        )
        raw   = message.content[0].text.strip()
        match = re.search(r'\{.*\}', raw, re.DOTALL)
        if match:
            data = json.loads(match.group())
            article["bangla_headline"] = data.get("bangla_headline", article["title"])
            article["fb_caption"]      = data.get("fb_caption", article["title"])
        else:
            raise ValueError("JSON parse failed")

        print(f"  ✅ বাংলা: {article['bangla_headline'][:55]}...")
        return article

    except Exception as e:
        print(f"  ❌ Claude error: {e}")
        article["bangla_headline"] = article["title"]
        article["fb_caption"]      = f"📰 {article['title']}\n\nসূত্র: {source_name}"
        return article


# ============================================================
#  STEP 3 — Image overlay
# ============================================================

def create_image_with_overlay(article):
    source = article["source"]
    print(f"  🎨 Image তৈরি [{source['name']}]...")

    img = None
    if article.get("image_url"):
        try:
            resp = requests.get(article["image_url"], headers=HEADERS, timeout=10)
            img  = Image.open(io.BytesIO(resp.content)).convert("RGB")
            img  = img.resize((IMAGE_WIDTH, IMAGE_HEIGHT), Image.LANCZOS)
        except Exception:
            img = None

    if img is None:
        img = create_gradient_background(source["color"])

    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    grad_h  = int(IMAGE_HEIGHT * 0.58)
    for i in range(grad_h):
        alpha = int(215 * (i / grad_h))
        y     = IMAGE_HEIGHT - grad_h + i
        ov_draw.rectangle([(0, y), (IMAGE_WIDTH, y + 1)], fill=(0, 0, 0, alpha))

    img  = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    draw = ImageDraw.Draw(img)

    font_headline = load_font(FONT_SIZE_HEADLINE)
    font_badge    = load_font(FONT_SIZE_SOURCE)
    font_small    = load_font(20)

    # Source badge
    badge_text  = source["short"]
    badge_pad_x = 18
    badge_pad_y = 10
    try:
        bw = font_badge.getbbox(badge_text)[2] - font_badge.getbbox(badge_text)[0] + badge_pad_x * 2
    except Exception:
        bw = len(badge_text) * 16 + badge_pad_x * 2
    bh = FONT_SIZE_SOURCE + badge_pad_y * 2

    draw.rectangle([(20, 20), (20 + bw, 20 + bh)], fill=source["color"])
    draw.text((20 + badge_pad_x, 20 + badge_pad_y), badge_text,
              font=font_badge, fill=source["text_color"])

    # Headline
    headline = article.get("bangla_headline", article["title"])
    headline = wrap_text(headline, font_headline, IMAGE_WIDTH - 80)
    text_y   = IMAGE_HEIGHT - 175
    draw.text((42, text_y + 2), headline, font=font_headline, fill=(0, 0, 0, 180))
    draw.text((40, text_y),     headline, font=font_headline, fill=(255, 255, 255))

    # Date
    date_str = datetime.now().strftime("%d %b %Y  •  %H:%M")
    draw.text((40, IMAGE_HEIGHT - 36), f"📅 {date_str}",
              font=font_small, fill=(180, 180, 180))

    os.makedirs(IMAGE_OUTPUT_DIR, exist_ok=True)
    safe_name = re.sub(r'[^\w]', '_', article['title'][:40])
    path      = f"{IMAGE_OUTPUT_DIR}/{source['short'].replace(' ', '_')}_{safe_name}.jpg"
    img.save(path, "JPEG", quality=92)
    article["local_image_path"] = path

    print(f"  ✅ Image ready: {path}")
    return article


def create_gradient_background(brand_color):
    r0, g0, b0 = brand_color
    img  = Image.new("RGB", (IMAGE_WIDTH, IMAGE_HEIGHT))
    draw = ImageDraw.Draw(img)
    for i in range(IMAGE_HEIGHT):
        t = i / IMAGE_HEIGHT
        draw.rectangle(
            [(0, i), (IMAGE_WIDTH, i + 1)],
            fill=(
                min(int(r0 * 0.15 + r0 * 0.5  * t), 255),
                min(int(g0 * 0.15 + g0 * 0.35 * t), 255),
                min(int(b0 * 0.15 + b0 * 0.5  * t), 255),
            )
        )
    return img


def load_font(size):
    font_paths = [
        "/usr/share/fonts/truetype/noto/NotoSansBengali-Regular.ttf",
        "/usr/share/fonts/truetype/noto/NotoSansBengali-Bold.ttf",
        "/usr/share/fonts/truetype/noto/NotoSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()


def wrap_text(text, font, max_width):
    words, lines, current = text.split(), [], ""
    for word in words:
        test = (current + " " + word).strip()
        try:
            w = font.getbbox(test)[2] - font.getbbox(test)[0]
        except Exception:
            w = len(test) * (FONT_SIZE_HEADLINE // 2)
        if w <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines[:3])


# ============================================================
#  STEP 4 — Facebook post
# ============================================================

def post_to_facebook(article):
    source   = article["source"]
    caption  = article.get("fb_caption", article["title"])
    caption += f"\n\n🔗 বিস্তারিত: {article['url']}"
    caption += f"\n\n{source['hashtags']} #Breaking #সংবাদ"

    print(f"  📤 Facebook post [{source['name']}]...")

    image_path = article.get("local_image_path")
    try:
        if image_path and os.path.exists(image_path):
            endpoint = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/photos"
            with open(image_path, "rb") as f:
                resp = requests.post(
                    endpoint,
                    data={"caption": caption, "access_token": FB_PAGE_ACCESS_TOKEN},
                    files={"source": f},
                    timeout=30
                )
        else:
            endpoint = f"https://graph.facebook.com/v19.0/{FB_PAGE_ID}/feed"
            resp = requests.post(
                endpoint,
                data={"message": caption, "link": article["url"],
                      "access_token": FB_PAGE_ACCESS_TOKEN},
                timeout=30
            )

        result = resp.json()
        if "id" in result:
            print(f"  ✅ Post সফল! ID: {result['id']}")
            save_posted_url(article["url"])
            return True
        else:
            err = result.get("error", {})
            print(f"  ❌ FB Error [{err.get('code')}]: {err.get('message')}")
            return False

    except Exception as e:
        print(f"  ❌ Post error: {e}")
        return False


# ============================================================
#  HELPERS
# ============================================================

def load_posted_urls():
    if os.path.exists(POSTED_URLS_FILE):
        try:
            with open(POSTED_URLS_FILE, "r") as f:
                return set(json.load(f))
        except Exception:
            pass
    return set()


def save_posted_url(url):
    urls = load_posted_urls()
    urls.add(url)
    with open(POSTED_URLS_FILE, "w") as f:
        json.dump(list(urls), f, indent=2)


# ============================================================
#  MAIN PIPELINE
# ============================================================

def run_pipeline():
    print("\n" + "=" * 65)
    print(f"🚀 Pipeline: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 65)

    articles = scrape_all_sources()
    if not articles:
        print("⚠️  কোনো নতুন article নেই।")
        return

    print(f"\n📋 {len(articles)}টি article process হবে।")
    posted = 0

    for i, article in enumerate(articles, 1):
        print(f"\n{'─'*55}")
        print(f"📌 [{i}/{len(articles)}] {article['source']['name']}: {article['title'][:55]}...")

        article = edit_with_claude(article)
        article = create_image_with_overlay(article)
        success = post_to_facebook(article)
        if success:
            posted += 1

        if i < len(articles):
            time.sleep(8)

    print(f"\n{'='*65}")
    print(f"✅ সম্পন্ন! {posted}/{len(articles)}টি post সফল।")
    print("=" * 65)


# ============================================================
#  ENTRY POINT
# ============================================================

if __name__ == "__main__":
    print("╔══════════════════════════════════════════════════╗")
    print("║   Multi-Source News → Facebook Auto Poster       ║")
    print("║   Railway Deploy Version                         ║")
    print("╠══════════════════════════════════════════════════╣")
    for s in NEWS_SOURCES:
        print(f"║  ✓  {s['name']:<44}║")
    print("╠══════════════════════════════════════════════════╣")
    print(f"║  Interval : প্রতি {POST_INTERVAL_MINUTES} মিনিটে{' '*27}║")
    print(f"║  Per run  : সর্বোচ্চ {MAX_POSTS_PER_RUN}টি post{' '*31}║")
    print("╚══════════════════════════════════════════════════╝\n")

    # credentials check
    check_credentials()

    # প্রথমবার এখনই চালাও
    run_pipeline()

    # Schedule
    schedule.every(POST_INTERVAL_MINUTES).minutes.do(run_pipeline)
    while True:
        schedule.run_pending()
        time.sleep(30)
