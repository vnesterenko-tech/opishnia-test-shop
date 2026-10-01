#!/usr/bin/env python3
"""Збирає статичний сайт з products.csv у папку _site/.

Запускається автоматично GitHub Actions після кожного коміту в main.
Локально: python build.py  ->  відкрити _site/index.html
Лише стандартна бібліотека Python, нічого встановлювати не треба.
"""
import csv, html, json, shutil, sys
from pathlib import Path

BASE_URL = "https://vnesterenko-tech.github.io"
SHOP_NAME = "Опішнянська полиця"
CURRENCY = "UAH"
# Віджет Huntbot (тест). Вставляється в кінець <body> на всіх сторінках. Порожній рядок = без віджета.
WIDGET_SCRIPT = '<script src="https://api-test.huntbot.ai/api/v1/widget/69f0c65bddbbc842644c2fa7/widget.js" async></script>'
ROOT = Path(__file__).parent
OUT = ROOT / "_site"

STATUSES = {
    "В наявності": "https://schema.org/InStock",
    "Немає в наявності": "https://schema.org/OutOfStock",
    "Під замовлення": "https://schema.org/BackOrder",
    "Очікується": "https://schema.org/PreOrder",
}
GLAZES = ["#22408C", "#3F6B4A", "#B5651D", "#7A2E2E", "#C98A1B", "#4B5D8A"]
TRANSLIT = dict(zip("абвгґдеєжзиіїйклмнопрстуфхцчшщьюя",
    ["a","b","v","h","g","d","e","ie","zh","z","y","i","i","i","k","l","m","n","o","p","r","s","t","u","f","kh","ts","ch","sh","shch","","iu","ia"]))


def slugify(text):
    out = "".join(TRANSLIT.get(c, c) for c in text.lower())
    out = "".join(c if c.isalnum() and c.isascii() else "-" for c in out)
    return "-".join(p for p in out.split("-") if p)


def esc(s):
    return html.escape(str(s))


def money(v):
    return f"{v:,}".replace(",", " ") + " грн"


def to_int(value, field, row_no, required=False):
    value = (value or "").strip()
    if not value:
        if required:
            fail(row_no, f"поле {field} обов'язкове")
        return None
    try:
        return int(float(value.replace(" ", "").replace(",", ".")))
    except ValueError:
        fail(row_no, f"поле {field} має бути числом, а не «{value}»")


def fail(row_no, msg):
    sys.exit(f"products.csv, рядок {row_no}: {msg}")


def load_products():
    products, seen = [], set()
    with open(ROOT / "products.csv", encoding="utf-8-sig", newline="") as f:
        for row_no, r in enumerate(csv.DictReader(f), start=2):
            sku = (r.get("sku") or "").strip()
            if not sku:
                continue
            if sku in seen:
                fail(row_no, f"артикул {sku} повторюється")
            seen.add(sku)
            name = (r.get("name") or "").strip() or fail(row_no, "поле name обов'язкове")
            category = (r.get("category") or "").strip() or "Інше"
            status = (r.get("status") or "").strip()
            if status and status not in STATUSES:
                fail(row_no, f"невідомий status «{status}». Допустимі: {', '.join(STATUSES)}")
            products.append({
                "sku": sku, "slug": slugify(sku), "name": name,
                "category": category, "cat_slug": slugify(category),
                "price": to_int(r.get("price"), "price", row_no, required=True),
                "old_price": to_int(r.get("old_price"), "old_price", row_no),
                "qty": to_int(r.get("qty"), "qty", row_no),
                "status": status,
                "delivery_days": to_int(r.get("delivery_days"), "delivery_days", row_no),
                "description": (r.get("description") or "").strip(),
            })
    return products


def availability(p):
    """Правило 1: є кількість. Правило 2: лише статус. Правило 3: нічого."""
    if p["qty"] is not None:
        if p["qty"] > 0:
            return f"В наявності: {p['qty']} шт.", STATUSES["В наявності"], p["qty"]
        return "Немає в наявності (0 шт.)", STATUSES["Немає в наявності"], 0
    if p["status"]:
        return p["status"], STATUSES[p["status"]], None
    return None, None, None


def pot_svg(p, i):
    c = GLAZES[i % len(GLAZES)]
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 400 400">
<rect width="400" height="400" fill="#E6E9E4"/>
<path d="M150 90 h100 v20 q-10 10 -8 30 q70 40 70 120 q0 70 -112 80 q-112 -10 -112 -80 q0 -80 70 -120 q2 -20 -8 -30z" fill="{c}"/>
<path d="M112 230 q88 40 176 0" stroke="#F3F1E8" stroke-width="10" fill="none"/>
<path d="M120 270 q80 34 160 0" stroke="#C98A1B" stroke-width="6" fill="none"/>
<text x="200" y="370" font-family="sans-serif" font-size="22" text-anchor="middle" fill="#1B1E24">{esc(p['sku'])}</text>
</svg>"""


def layout(title, body, cats, up, jsonld=None):
    nav = "".join(f'<a href="{up}category/{s}.html">{esc(n)}</a>' for s, n in cats)
    ld = f'\n<script type="application/ld+json">\n{json.dumps(jsonld, ensure_ascii=False, indent=2)}\n</script>' if jsonld else ""
    return f"""<!doctype html>
<html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Commissioner:wght@400;600;800&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{up}style.css">{ld}
</head><body>
<header class="top"><a class="brand" href="{up}index.html">{esc(SHOP_NAME)}</a>
<nav>{nav}</nav></header>
<main>{body}</main>
<footer>Кераміка з Опішні. Доставка Новою поштою по Україні.</footer>
{WIDGET_SCRIPT}
</body></html>
"""


def item(p, up):
    return f"""<li><a href="{up}product/{p['slug']}.html">
<img src="{up}img/{p['slug']}.svg" alt="" width="72" height="72">
<span class="nm">{esc(p['name'])}</span></a></li>"""


def build():
    products = load_products()
    cats = list(dict.fromkeys((p["cat_slug"], p["category"]) for p in products))
    if OUT.exists():
        shutil.rmtree(OUT)
    for d in ("product", "category", "img"):
        (OUT / d).mkdir(parents=True)
    shutil.copy(ROOT / "style.css", OUT / "style.css")
    (OUT / ".nojekyll").write_text("")

    for i, p in enumerate(products, start=1):
        (OUT / "img" / f"{p['slug']}.svg").write_text(pot_svg(p, i), encoding="utf-8")
        text, schema_av, qty = availability(p)
        url = f"{BASE_URL}/product/{p['slug']}.html"
        offer = {"@type": "Offer", "price": str(p["price"]), "priceCurrency": CURRENCY, "url": url}
        if schema_av:
            offer["availability"] = schema_av
        if qty is not None:
            offer["inventoryLevel"] = {"@type": "QuantitativeValue", "value": qty}
        if p["delivery_days"]:
            d = p["delivery_days"]
            offer["shippingDetails"] = {"@type": "OfferShippingDetails", "deliveryTime": {
                "@type": "ShippingDeliveryTime", "transitTime": {
                    "@type": "QuantitativeValue", "minValue": d, "maxValue": d, "unitCode": "DAY"}}}
        jsonld = {"@context": "https://schema.org", "@type": "Product", "name": p["name"],
                  "sku": p["sku"], "productID": p["sku"], "description": p["description"],
                  "image": [f"{BASE_URL}/img/{p['slug']}.svg"], "category": p["category"], "offers": offer}
        old = ""
        if p["old_price"] and p["old_price"] > p["price"]:
            disc = round(100 - p["price"] * 100 / p["old_price"])
            old = f' <s>{money(p["old_price"])}</s> <span class="disc">−{disc}%</span>'
        av = f'<p class="av big">{esc(text)}</p>' if text else ""
        dl = f'<p>Термін доставки: {p["delivery_days"]} дн.</p>' if p["delivery_days"] else ""
        body = f"""<article class="product">
<img src="../img/{p['slug']}.svg" alt="{esc(p['name'])}" width="400" height="400">
<div><p class="crumb"><a href="../category/{p['cat_slug']}.html">{esc(p['category'])}</a></p>
<h1>{esc(p['name'])}</h1>
<p class="price">{money(p['price'])}{old}</p>{av}{dl}
<p class="desc">{esc(p['description'])}</p>
<p class="sku">Артикул: {esc(p['sku'])}</p></div></article>"""
        (OUT / "product" / f"{p['slug']}.html").write_text(layout(p["name"], body, cats, "../", jsonld), encoding="utf-8")

    for slug, name in cats:
        items = "".join(item(p, "../") for p in products if p["cat_slug"] == slug)
        body = f'<h1>{esc(name)}</h1><ul class="list">{items}</ul>'
        (OUT / "category" / f"{slug}.html").write_text(layout(name, body, cats, "../"), encoding="utf-8")

    items = "".join(item(p, "") for p in products)
    body = (f'<h1 class="hero">Глина, яку можна поставити на стіл</h1>'
            f'<p class="lead">{len(products)} виробів майстрів з Опішні</p><ul class="list">{items}</ul>')
    (OUT / "index.html").write_text(layout(SHOP_NAME, body, cats, ""), encoding="utf-8")

    urls = [f"{BASE_URL}/index.html"] + [f"{BASE_URL}/category/{s}.html" for s, _ in cats] + \
           [f"{BASE_URL}/product/{p['slug']}.html" for p in products]
    (OUT / "sitemap.xml").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "".join(f"  <url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n", encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE_URL}/sitemap.xml\n", encoding="utf-8")
    print(f"Зібрано {len(products)} товарів, {len(cats)} категорій -> {OUT}")


if __name__ == "__main__":
    build()
