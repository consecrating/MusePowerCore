#!/usr/bin/env python3
"""
asset-optimize — web-optimize a directory of images.

Reads every image in INPUT_DIR, writes optimized copies to OUTPUT_DIR.
Never touches the originals unless --in-place is passed.

Operations:
  - downscale to --max-width (default 1920, keeps aspect ratio; never upscales)
  - JPEG: re-encode at --quality (default 82), progressive
  - PNG: optimize (lossless, strips metadata); large PNGs can be converted
    to JPEG with --png-to-jpg when they have no transparency
  - --webp: also emit a WebP copy of every image (quality --webp-quality, default 80)
  - EXIF metadata is always stripped (privacy + bytes)

Prints per-file before/after bytes and a total savings summary.

Usage:
  python3 optimize.py assets/img optimized/img
  python3 optimize.py assets/img optimized/img --max-width 1600 --quality 78 --webp
  python3 optimize.py assets/img --in-place   # overwrites originals (use with care)

Requires: Pillow  (pip install pillow)
"""
import argparse
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageOps
except ImportError:
    sys.exit("Pillow is required: pip install pillow")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".tiff"}


def fmt_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024
    return f"{n:.1f} GB"


def optimize_one(src: Path, dst: Path, args) -> tuple[int, int, list[str]]:
    """Returns (bytes_before, bytes_after_primary, notes). WebP copies counted separately."""
    before = src.stat().st_size
    notes: list[str] = []

    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)  # honor EXIF orientation, then drop EXIF
        has_alpha = im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info)

        # Downscale if wider than max-width (never upscale).
        if im.width > args.max_width:
            ratio = args.max_width / im.width
            im = im.resize((args.max_width, int(im.height * ratio)), Image.LANCZOS)
            notes.append(f"resized to {im.width}px wide")

        dst.parent.mkdir(parents=True, exist_ok=True)
        ext = dst.suffix.lower()

        if ext in (".jpg", ".jpeg") or (args.png_to_jpg and ext == ".png" and not has_alpha):
            if args.png_to_jpg and ext == ".png" and not has_alpha:
                dst = dst.with_suffix(".jpg")
                notes.append("PNG->JPG (no transparency)")
            if im.mode in ("RGBA", "LA", "P"):
                im = im.convert("RGB")
            im.save(dst, "JPEG", quality=args.quality, optimize=True, progressive=True)
        elif ext == ".png":
            im.save(dst, "PNG", optimize=True)
        elif ext == ".webp":
            im.save(dst, "WEBP", quality=args.webp_quality, method=6)
        else:
            # GIF/BMP/TIFF and anything else: normalize to PNG to stay web-safe.
            dst = dst.with_suffix(".png")
            im.save(dst, "PNG", optimize=True)
            notes.append("converted to PNG")

        # WebP companion copy.
        if args.webp:
            webp_dst = dst.parent / (dst.stem + ".webp")
            w = im.copy()
            if w.mode in ("RGBA", "LA", "P") and not has_alpha:
                w = w.convert("RGB")
            w.save(webp_dst, "WEBP", quality=args.webp_quality, method=6)
            notes.append(f"+ WebP copy ({fmt_bytes(webp_dst.stat().st_size)})")

    after = dst.stat().st_size
    return before, after, notes


def main() -> int:
    ap = argparse.ArgumentParser(description="Web-optimize a directory of images.")
    ap.add_argument("input_dir", help="directory of source images")
    ap.add_argument("output_dir", nargs="?", help="directory for optimized copies (omit with --in-place)")
    ap.add_argument("--in-place", action="store_true",
                    help="overwrite originals instead of writing copies (no backup is kept)")
    ap.add_argument("--max-width", type=int, default=1920,
                    help="downscale images wider than this (default 1920; 0 disables)")
    ap.add_argument("--quality", type=int, default=82, help="JPEG quality 1-100 (default 82)")
    ap.add_argument("--png-to-jpg", action="store_true",
                    help="convert PNGs without transparency to JPEG (much smaller for photos)")
    ap.add_argument("--webp", action="store_true", help="also emit a WebP copy of every image")
    ap.add_argument("--webp-quality", type=int, default=80, help="WebP quality 1-100 (default 80)")
    args = ap.parse_args()

    if args.in_place and args.output_dir:
        ap.error("--in-place cannot be combined with output_dir")

    src_dir = Path(args.input_dir)
    if not src_dir.is_dir():
        ap.error(f"input_dir not found: {src_dir}")

    files = sorted(p for p in src_dir.rglob("*") if p.is_file() and p.suffix.lower() in IMAGE_EXTS)
    if not files:
        print(f"No images found in {src_dir}")
        return 0

    total_before = total_after = 0
    print(f"Optimizing {len(files)} image(s) from {src_dir}")
    print(f"  max-width={args.max_width or 'off'}  jpeg-quality={args.quality}  webp={'on' if args.webp else 'off'}  "
          f"mode={'IN-PLACE (originals overwritten)' if args.in_place else 'copy'}")
    print("-" * 72)

    for src in files:
        rel = src.relative_to(src_dir)
        dst = src if args.in_place else Path(args.output_dir) / rel
        try:
            before, after, notes = optimize_one(src, dst, args)
        except Exception as e:  # noqa: BLE001 — report and continue with the rest
            print(f"  SKIP {rel}: {e}")
            continue
        total_before += before
        total_after += after
        saved = before - after
        pct = (saved / before * 100) if before else 0
        note_str = f"  [{'; '.join(notes)}]" if notes else ""
        print(f"  {rel}\n    {fmt_bytes(before)} -> {fmt_bytes(after)}  "
              f"({saved:+,} B, {pct:+.1f}%){note_str}")

    print("-" * 72)
    saved = total_before - total_after
    pct = (saved / total_before * 100) if total_before else 0
    print(f"TOTAL: {fmt_bytes(total_before)} -> {fmt_bytes(total_after)}  "
          f"saved {fmt_bytes(saved)} ({pct:.1f}%)")
    if args.in_place:
        print("NOTE: originals were overwritten in place. No backups kept.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
