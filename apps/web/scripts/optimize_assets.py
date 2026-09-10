"""Genera los assets web optimizados a partir de los originales del cliente Flutter.

Las insignias de rango eran PNG de 300-670 KB cada una (casi 4 MB en total,
P11). Aquí se redimensionan al tamaño máximo al que se muestran (x2 para
pantallas retina) y se codifican en WebP. DM Sans pasa de TTF a WOFF2 con solo
los glifos latinos.

El cliente Flutter ya no está en main; los originales se recuperan de la
etiqueta v1.0-tfg sin tocar el índice de git:

    git archive v1.0-tfg apps/flutter/assets | tar -x
    python apps/web/scripts/optimize_assets.py

Requiere Pillow, fontTools y brotli. El resultado (apps/web/public) sí está versionado.
"""

from pathlib import Path

from fontTools import subset
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "apps" / "flutter" / "assets"
PUBLIC = ROOT / "apps" / "web" / "public"

RANK_BADGE_PX = 176  # se muestran como mucho a 88 px
ROLE_ICON_PX = 96  # se muestran como mucho a 48 px


def _to_webp(source: Path, target: Path, size: int, quality: int = 82) -> tuple[int, int]:
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image = image.convert("RGBA")
        image.thumbnail((size, size), Image.Resampling.LANCZOS)
        image.save(target, "WEBP", quality=quality, method=6)
    return source.stat().st_size, target.stat().st_size


def _smallest_icon(source: Path, target_dir: Path, size: int) -> tuple[int, int]:
    """Iconos diminutos: WebP no siempre gana a un PNG de 1 KB. Se queda el más ligero."""
    webp = target_dir / f"{source.stem}.webp"
    png = target_dir / f"{source.stem}.png"
    before, webp_size = _to_webp(source, webp, size, quality=90)
    if source.stat().st_size <= webp_size:
        webp.unlink()
        png.write_bytes(source.read_bytes())
        return before, before
    png.unlink(missing_ok=True)
    return before, webp_size


def _font(weight: str, suffix: str) -> tuple[int, int]:
    source = SOURCE / "fonts" / f"DMSans-{weight}.ttf"
    target = PUBLIC / "fonts" / f"dm-sans-latin{suffix}.woff2"
    target.parent.mkdir(parents=True, exist_ok=True)
    options = subset.Options()
    options.flavor = "woff2"
    options.layout_features = ["*"]
    font = subset.load_font(str(source), options)
    subsetter = subset.Subsetter(options)
    # Latín básico + Latín-1 (acentos y ñ) + puntuación tipográfica.
    subsetter.populate(unicodes=[*range(0x20, 0x7F), *range(0xA0, 0x100), *range(0x2010, 0x2030), 0x20AC])
    subsetter.subset(font)
    subset.save_font(font, str(target), options)
    return source.stat().st_size, target.stat().st_size


def main() -> None:
    before = after = 0
    for badge in sorted((SOURCE / "rank_badges").glob("*_badge.png")):
        tier = badge.stem.removesuffix("_badge")
        b, a = _to_webp(badge, PUBLIC / "img" / "ranks" / f"{tier}.webp", RANK_BADGE_PX)
        before, after = before + b, after + a
        print(f"{badge.name:28} {b / 1024:7.0f} KB → {a / 1024:5.1f} KB")
    for role in sorted((SOURCE / "roles").glob("*.png")):
        b, a = _smallest_icon(role, PUBLIC / "img" / "roles", ROLE_ICON_PX)
        before, after = before + b, after + a
        print(f"{role.name:28} {b / 1024:7.0f} KB → {a / 1024:5.1f} KB")
    for weight, suffix in (("Regular", ""), ("Bold", "-700")):
        b, a = _font(weight, suffix)
        print(f"{'DMSans-' + weight + '.ttf':28} {b / 1024:7.0f} KB → {a / 1024:5.1f} KB (woff2 latino)")
        before, after = before + b, after + a
    print(f"\nTotal: {before / 1024:.0f} KB → {after / 1024:.0f} KB")


if __name__ == "__main__":
    main()
