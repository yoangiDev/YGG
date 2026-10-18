"""Generates the optimised web assets from the Flutter client's originals.

The rank badges were PNGs of 300-670 KB each (almost 4 MB in total,
P11). Here they are resized to the maximum size at which they are shown (x2 for
retina screens) and encoded as WebP.

The Flutter client is not part of this repository: put its original assets in
apps/flutter/assets and run

    python apps/web/scripts/optimize_assets.py

Requires Pillow. The result (apps/web/public) is versioned.
"""

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "apps" / "flutter" / "assets"
PUBLIC = ROOT / "apps" / "web" / "public"

RANK_BADGE_PX = 176  # they are shown at 88 px at most
ROLE_ICON_PX = 96  # they are shown at 48 px at most


def _to_webp(source: Path, target: Path, size: int, quality: int = 82) -> tuple[int, int]:
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(source) as image:
        image = image.convert("RGBA")
        image.thumbnail((size, size), Image.Resampling.LANCZOS)
        image.save(target, "WEBP", quality=quality, method=6)
    return source.stat().st_size, target.stat().st_size


def _smallest_icon(source: Path, target_dir: Path, size: int) -> tuple[int, int]:
    """Tiny icons: WebP doesn't always beat a 1 KB PNG. The lighter one is kept."""
    webp = target_dir / f"{source.stem}.webp"
    png = target_dir / f"{source.stem}.png"
    before, webp_size = _to_webp(source, webp, size, quality=90)
    if source.stat().st_size <= webp_size:
        webp.unlink()
        png.write_bytes(source.read_bytes())
        return before, before
    png.unlink(missing_ok=True)
    return before, webp_size


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
    print(f"\nTotal: {before / 1024:.0f} KB → {after / 1024:.0f} KB")


if __name__ == "__main__":
    main()
