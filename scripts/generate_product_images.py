"""Generate local labeled product SVGs (no CDN)."""

from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "static" / "images"

PRODUCTS = [
    ("headphones.svg", "Headphones", "#0f4c81", "#38bdf8"),
    ("smart-watch.svg", "Smart Watch", "#581c87", "#d8b4fe"),
    ("running-shoes.svg", "Running Shoes", "#14532d", "#86efac"),
    ("leather-wallet.svg", "Leather Wallet", "#78350f", "#fdba74"),
    ("cookware.svg", "Cookware Set", "#7f1d1d", "#fca5a5"),
    ("desk-lamp.svg", "Desk Lamp", "#1e3a8a", "#93c5fd"),
]

TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800" viewBox="0 0 800 800" role="img" aria-label="{label}">
  <rect width="800" height="800" fill="{bg}"/>
  <rect x="70" y="70" width="660" height="660" rx="40" fill="#ffffff"/>
  <rect x="130" y="130" width="540" height="300" rx="28" fill="{accent}"/>
  <circle cx="400" cy="280" r="78" fill="none" stroke="{bg}" stroke-width="16"/>
  <rect x="220" y="470" width="360" height="78" rx="18" fill="{bg}"/>
  <text x="400" y="522" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="36" font-weight="700" fill="#ffffff">{label}</text>
  <text x="400" y="620" text-anchor="middle" font-family="Segoe UI, Arial, sans-serif" font-size="28" fill="#64748b">ShopSphere</text>
</svg>
"""


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for fname, label, bg, accent in PRODUCTS:
        path = OUT / fname
        path.write_text(
            TEMPLATE.format(label=label, bg=bg, accent=accent),
            encoding="utf-8",
        )
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
