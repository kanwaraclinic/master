"""
สร้างบทความใหม่ด้วย Gemini แล้วเพิ่มลิงก์ลงใน index.html

วิธีใช้:
    set GEMINI_API_KEY=xxxx            (Windows)  /  export GEMINI_API_KEY=xxxx  (Mac/Linux)
    python scripts/new_article.py "หัวข้อบทความ"

ใช้แค่ Python มาตรฐาน ไม่ต้อง pip install อะไรเพิ่ม
"""
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "คลินิกรักษาสิว-กรุงเทพ.html"   # หน้าต้นแบบ (สี/เลย์เอาต์/เมนู/ฟุตเตอร์)
INDEX = ROOT / "index.html"
SITE = "https://www.กัญวราคลินิก.com"

# ลองตามลำดับ: ถ้ารุ่นแรกใช้ไม่ได้ (ถูกปิดแล้ว) จะลองรุ่นถัดไปให้อัตโนมัติ
# เปลี่ยนได้ด้วย env GEMINI_MODEL เช่น  GEMINI_MODEL=gemini-2.5-flash
MODELS = [m for m in [os.environ.get("GEMINI_MODEL")] if m] + [
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-flash-latest",
]

START = "<!-- AUTO-ARTICLES:START -->"
END = "<!-- AUTO-ARTICLES:END -->"
ITEMS_START = "<!-- AUTO-ARTICLES:ITEMS -->"

PROMPT = """คุณคือ พญ.กัญวรา นวอนุรักษ์ (หมอเหมี่ยว) แพทย์เจ้าของ "กัญวราคลินิก" คลินิกรักษาสิวและผิวพรรณ
ที่ 104/9 หมู่บ้านไอดีไซน์ ถนนเลียบคลองสอง แขวงบางชัน เขตคลองสามวา กรุงเทพฯ โทร 091-795-4884
เทคโนโลยีของคลินิก: Cellec Acne Laser, Healite II, Made Collagen, Ultraformer III, Xeomin
จุดยืน: จริงใจ ไม่เลี้ยงไข้ ไม่ยัดเยียดคอร์ส หมอตรวจเอง

เขียนบทความ SEO ภาษาไทย หัวข้อ: "{title}"
- ยาวประมาณ 1,200-1,800 คำ อ่านง่าย น้ำเสียงอบอุ่น เป็นกันเอง น่าเชื่อถือ แบบแพทย์อธิบายให้คนไข้ฟัง
- ข้อมูลทางการแพทย์ต้องถูกต้อง ไม่กล่าวอ้างเกินจริง ไม่การันตีผล 100%
- ใส่คีย์เวิร์ดหลักของหัวข้อแบบเป็นธรรมชาติ ใช้ <strong> เน้นคีย์เวิร์ดสำคัญ
- ปิดท้ายด้วยส่วนคำถามที่พบบ่อย (FAQ) 3-5 ข้อ

ตอบเป็น JSON เท่านั้น ตามโครงสร้างนี้:
{{
  "h1": "หัวข้อ H1 ของบทความ (ใกล้เคียงหัวข้อที่ให้มา)",
  "meta_title": "title สำหรับ SEO ไม่เกิน 65 ตัวอักษร ลงท้ายด้วย - กัญวราคลินิก",
  "meta_description": "คำอธิบาย 140-160 ตัวอักษร",
  "keywords": "คีย์เวิร์ด 5-8 คำ คั่นด้วยจุลภาค",
  "excerpt": "สรุปสั้น 1-2 ประโยค สำหรับการ์ดหน้าแรก",
  "emoji": "อีโมจิ 1 ตัวที่เข้ากับหัวข้อ",
  "keyword_tag": "คีย์เวิร์ดหลักสั้นๆ ไม่มีช่องว่าง สำหรับทำแฮชแท็ก",
  "cta_heading": "หัวข้อชวนนัดหมายสั้นๆ",
  "cta_text": "ข้อความชวนนัดหมาย 1-2 ประโยค",
  "sections": [
    "<div class=\\"content-section\\">...</div>",
    "..."
  ]
}}

กติกาของ sections (สำคัญมาก):
- แต่ละรายการคือ HTML 1 กล่อง ครอบด้วย <div class="content-section"> ... </div>
- กล่องแรกเป็นบทนำ มีแค่ <p> (ไม่มี h2)
- กล่องถัดไปเริ่มด้วย <h2> แล้วตามด้วย <p>, <h3>, <ul><li>, <ol><li>, <strong> ได้
- ห้ามใช้ tag อื่น ห้ามใส่ style, class อื่น, script, รูปภาพ, ลิงก์ หรือ markdown
- รวม 5-8 กล่อง
"""


# ---------------------------------------------------------------- Gemini

def call_gemini(title: str) -> dict:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("ไม่พบ GEMINI_API_KEY  (ขอฟรีได้ที่ https://aistudio.google.com/apikey)")

    body = json.dumps({
        "contents": [{"parts": [{"text": PROMPT.format(title=title)}]}],
        "generationConfig": {"temperature": 0.7, "responseMimeType": "application/json"},
    }).encode("utf-8")

    last_error = ""
    for model in MODELS:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        for attempt in range(4):
            req = urllib.request.Request(url, data=body, headers={
                "Content-Type": "application/json", "x-goog-api-key": key})
            try:
                with urllib.request.urlopen(req, timeout=180) as r:
                    data = json.load(r)
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                print(f"ใช้โมเดล: {model}")
                return parse_json(text)
            except urllib.error.HTTPError as e:
                last_error = f"{model}: HTTP {e.code} {e.read()[:300]!r}"
                if e.code in (429, 500, 503):          # ติดโควต้า/เซิร์ฟเวอร์ยุ่ง → รอแล้วลองใหม่
                    wait = 20 * (attempt + 1)
                    print(f"{model} ตอบ {e.code} รอ {wait} วินาที แล้วลองใหม่...")
                    time.sleep(wait)
                    continue
                print(f"{model} ใช้ไม่ได้ (HTTP {e.code}) → ลองรุ่นถัดไป")
                break                                   # 400/403/404 → ข้ามไปรุ่นถัดไป
            except (KeyError, IndexError, ValueError) as e:
                last_error = f"{model}: คำตอบผิดรูปแบบ ({e})"
                print(last_error + " → ลองใหม่")
    sys.exit("เรียก Gemini ไม่สำเร็จ: " + last_error)


def parse_json(text: str) -> dict:
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    data = json.loads(text)
    for field in ("h1", "meta_description", "excerpt", "sections"):
        if not data.get(field):
            raise ValueError(f"ไม่มีช่อง {field}")
    return data


# ---------------------------------------------------------------- HTML helpers

ALLOWED = {"div", "p", "h2", "h3", "ul", "ol", "li", "strong", "em", "br"}


def clean_section(fragment: str) -> str:
    """ตัด tag/attribute ที่ไม่อนุญาตออก ให้เหลือเฉพาะโครงสร้างแบบเดียวกับบทความเดิม"""
    fragment = re.sub(r"(?is)<(script|style|iframe)[^>]*>.*?</\1>", "", fragment)

    def fix(m):
        closing, tag = m.group(1), m.group(2).lower()
        if tag not in ALLOWED:
            return ""
        if closing:
            return f"</{tag}>"
        return '<div class="content-section">' if tag == "div" else f"<{tag}>"

    fragment = re.sub(r"<(/?)([a-zA-Z0-9]+)[^>]*>", fix, fragment).strip()
    if not fragment.startswith('<div class="content-section">'):
        fragment = f'<div class="content-section">{fragment}</div>'
    return fragment


def make_filename(title: str) -> str:
    name = re.sub(r'[\\/:*?"<>|#%&{}$!\'@+`=“”‘’?,.()\[\]]', " ", title)
    name = re.sub(r"\s+", "-", name.strip()).strip("-")
    return (name[:80] or "บทความ") + ".html"


def esc(s: str) -> str:
    return html.escape(str(s or "").strip(), quote=True)


# ---------------------------------------------------------------- build article

def build_article(title: str, a: dict, filename: str) -> str:
    page = TEMPLATE.read_text(encoding="utf-8")
    url = f"{SITE}/{filename}"
    meta_title = a.get("meta_title") or f"{a['h1']} - กัญวราคลินิก"

    page = re.sub(r"<title>.*?</title>", lambda m: f"<title>{esc(meta_title)}</title>", page, 1, re.S)
    page = re.sub(r'<meta name="description" content="[^"]*">',
                  lambda m: f'<meta name="description" content="{esc(a["meta_description"])}">', page, 1)
    page = re.sub(r'<meta name="keywords" content="[^"]*">',
                  lambda m: f'<meta name="keywords" content="{esc(a.get("keywords", title))}">', page, 1)

    ld = json.dumps({
        "@context": "https://schema.org/",
        "@type": "Article",
        "headline": a["h1"],
        "description": a["meta_description"],
        "url": url,
        "datePublished": date.today().isoformat(),
        "inLanguage": "th",
        "author": {"@type": "Person", "name": "พญ.กัญวรา นวอนุรักษ์ (หมอเหมี่ยว)"},
        "publisher": {"@type": "Organization", "name": "กัญวราคลินิก", "logo": f"{SITE}/logo.png"},
    }, ensure_ascii=False, indent=2)
    page = re.sub(r'<script type="application/ld\+json">.*?</script>',
                  lambda m: f'<script type="application/ld+json">\n{ld}\n</script>', page, 1, re.S)

    # ลิงก์โลโก้ในหน้าต้นแบบมี alt/title ของบทความเดิม → เปลี่ยนเป็นของบทความใหม่
    page = page.replace("คลินิกรักษาสิว กรุงเทพ ใกล้ฉัน", esc(a["h1"]))

    sections = "\n\n        ".join(clean_section(s) for s in a["sections"])
    main = f"""<main>
    <section>
      <div class="container">
        <h1>{esc(a['h1'])}</h1>
        {sections}

        <section class="cta-section">
          <div class="container">
            <h2>{esc(a.get('cta_heading') or 'ปรึกษาหมอเหมี่ยวได้เลย')}</h2>
            <p>{esc(a.get('cta_text') or 'ติดต่อกัญวราคลินิกเพื่อนัดหมายปรึกษาคุณหมอได้แล้ววันนี้')}</p>
            <a href="tel:0917954884" class="cta-button">โทรนัดหมาย: 091-795-4884</a>
          </div>
        </section>
      </div>
    </section>
  </main>"""
    page = re.sub(r"<main>.*?</main>", lambda m: main, page, 1, re.S)
    return page


# ---------------------------------------------------------------- update index.html

BLOCK_CSS = """
  <style>
    .auto-articles { padding: 50px 0 60px; background: linear-gradient(135deg, #f6f9fb 0%, #eaf3f1 100%); }
    .auto-articles h2 { text-align: center; font-size: 32px; color: #235E6E; margin-bottom: 30px; font-weight: 600; }
    .auto-articles-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 24px; }
    .auto-card { display: flex; flex-direction: column; background: #fff; border-radius: 16px; overflow: hidden; box-shadow: 0 8px 25px rgba(35, 94, 110, 0.10); transition: transform 0.3s ease, box-shadow 0.3s ease; color: inherit; }
    .auto-card:hover { transform: translateY(-5px); box-shadow: 0 14px 35px rgba(35, 94, 110, 0.20); color: inherit; }
    .auto-card-visual { background: linear-gradient(135deg, #235E6E 0%, #51af99 100%); color: #fff; text-align: center; padding: 26px 16px; }
    .auto-card-emoji { font-size: 44px; line-height: 1.2; }
    .auto-card-tag { display: inline-block; margin-top: 8px; background: rgba(216, 175, 55, 0.95); padding: 4px 12px; border-radius: 20px; font-size: 13px; font-weight: 600; }
    .auto-card-body { padding: 22px 24px 24px; display: flex; flex-direction: column; flex: 1; }
    .auto-card-body h3 { font-size: 20px; color: #235E6E; line-height: 1.45; margin-bottom: 10px; font-weight: 600; }
    .auto-card-body p { font-size: 15px; color: #666; line-height: 1.7; margin-bottom: 16px; flex: 1; }
    .auto-card-cta { color: #51af99; font-weight: 600; }
    .auto-card:hover .auto-card-cta { color: #d8af37; }
  </style>"""


def build_card(a: dict, filename: str) -> str:
    tag = re.sub(r"\s+", "", a.get("keyword_tag") or a["h1"])[:30]
    return f"""      <a href="{esc(filename)}" class="auto-card" title="{esc(a['h1'])}">
        <div class="auto-card-visual">
          <div class="auto-card-emoji">{esc(a.get('emoji') or '✨')}</div>
          <div class="auto-card-tag">#{esc(tag)}</div>
        </div>
        <div class="auto-card-body">
          <h3>{esc(a['h1'])}</h3>
          <p>{esc(a['excerpt'])}</p>
          <span class="auto-card-cta">อ่านบทความ →</span>
        </div>
      </a>"""


def update_index(card: str) -> None:
    index = INDEX.read_text(encoding="utf-8")

    if START not in index:
        # ครั้งแรก: สร้างส่วน "บทความล่าสุด" ต่อจากส่วนบทความแนะนำ (Featured Article)
        block = f"""
  {START}
  <section class="auto-articles">
    <div class="container">
      <h2>บทความล่าสุด</h2>
      <div class="auto-articles-grid">
      {ITEMS_START}
      </div>
    </div>
  </section>{BLOCK_CSS}
  {END}
"""
        anchor = index.find('<section class="featured-article">')
        if anchor != -1:
            pos = index.find("</section>", anchor) + len("</section>")
        else:
            pos = index.find("<footer")
        index = index[:pos] + "\n" + block + index[pos:]

    # การ์ดใหม่อยู่บนสุดเสมอ
    index = index.replace(ITEMS_START, ITEMS_START + "\n" + card, 1)
    INDEX.write_text(index, encoding="utf-8", newline="\n")


# ---------------------------------------------------------------- main

def main():
    if hasattr(sys.stdout, "reconfigure"):   # ให้แสดงภาษาไทยได้ใน Windows console
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    title = " ".join(sys.argv[1:]).strip() or os.environ.get("ARTICLE_TITLE", "").strip()
    if not title:
        sys.exit('ใส่หัวข้อด้วย เช่น  python scripts/new_article.py "รักษาหลุมสิว ที่ไหนดี"')

    filename = make_filename(title)
    if (ROOT / filename).exists():
        sys.exit(f"มีไฟล์ {filename} อยู่แล้ว — เปลี่ยนหัวข้อเล็กน้อยแล้วลองใหม่")

    print(f"กำลังเขียนบทความ: {title}")
    article = call_gemini(title)

    (ROOT / filename).write_text(build_article(title, article, filename), encoding="utf-8", newline="\n")
    print(f"สร้างไฟล์แล้ว: {filename}")

    update_index(build_card(article, filename))
    print("อัปเดต index.html แล้ว")

    out = os.environ.get("GITHUB_OUTPUT")
    if out:
        with open(out, "a", encoding="utf-8") as f:
            f.write(f"filename={filename}\n")


if __name__ == "__main__":
    main()
