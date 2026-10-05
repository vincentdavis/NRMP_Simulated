"""Render the site's link preview image and icons (run from the repository root; needs Playwright's Chromium).

- static/img/social-card.png, 1200 x 630, from docs/assets/social-card.html;
- static/img/icon-96.png (the browser tab and search results: a multiple of 48 pixels) and icon-180.png (home
  screens, on a white background), from static/NRMP_Simulations_logo.png.
"""

from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
IMAGES = ROOT / "static" / "img"
LOGO = (ROOT / "static" / "NRMP_Simulations_logo.png").as_uri()
ICON = """<body style="margin:0;background:{background}"><img src="{logo}" style="display:block;width:{size}px;
height:{size}px;padding:{padding}px;box-sizing:border-box"></body>"""

IMAGES.mkdir(parents=True, exist_ok=True)
with sync_playwright() as playwright:
    browser = playwright.chromium.launch()
    page = browser.new_page(viewport={"width": 1200, "height": 630})
    page.goto((ROOT / "docs" / "assets" / "social-card.html").as_uri())
    page.screenshot(path=str(IMAGES / "social-card.png"))
    for size, background, padding in ((96, "transparent", 0), (180, "#ffffff", 14)):
        page.set_viewport_size({"width": size, "height": size})
        page.set_content(ICON.format(background=background, logo=LOGO, size=size, padding=padding))
        page.screenshot(path=str(IMAGES / f"icon-{size}.png"), omit_background=background == "transparent")
    browser.close()
print(*(f"{path.name}: {path.stat().st_size:,} bytes" for path in sorted(IMAGES.glob("*.png"))), sep="\n")
