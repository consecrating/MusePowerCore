# asset-optimize

Web-optimize a directory of images: downscale, re-encode, strip EXIF, and
optionally emit WebP copies. Built for the recurring client-site problem of
heavy unoptimized backgrounds and photos slowing page loads.

**Safety rule: originals are never overwritten unless you pass `--in-place`.**
Default mode writes optimized copies to a separate output directory.

## Requirements

Python 3 + Pillow:

```bash
pip install pillow
```

## Usage

```bash
# Copy mode (safe default): originals untouched
python3 optimize.py assets/img assets/img-optimized

# Tighter: max 1600px wide, JPEG quality 78, plus WebP copies
python3 optimize.py assets/img assets/img-optimized --max-width 1600 --quality 78 --webp

# Convert photographic PNGs (no transparency) to much smaller JPEGs
python3 optimize.py assets/img assets/img-optimized --png-to-jpg --webp

# In-place (overwrites originals — no backup kept; only when you're sure)
python3 optimize.py assets/img --in-place
```

## Options

| Flag | Default | Purpose |
| ---- | ------- | ------- |
| `--max-width` | 1920 | Downscale wider images (keeps aspect ratio, never upscales). `0` disables. |
| `--quality` | 82 | JPEG quality 1–100. |
| `--png-to-jpg` | off | Convert PNGs without transparency to JPEG (big win for photos saved as PNG). |
| `--webp` | off | Also emit a `.webp` copy of every image. |
| `--webp-quality` | 80 | WebP quality 1–100. |
| `--in-place` | off | Overwrite originals instead of writing copies. |

## Output

Per-file lines (`before -> after`, bytes saved, operations applied) plus a
total savings summary at the end:

```
  hero-bg.png
    2.4 MB -> 380.2 KB  (-2123456 B, -84.2%)  [resized to 1920px wide; PNG->JPG (no transparency); + WebP copy (310.5 KB)]
  ...
TOTAL: 8.1 MB -> 1.2 MB  saved 6.9 MB (85.2%)
```

## Workflow fit

- Run on `assets/img/` before any deploy that adds or replaces images
  (`site-deploy` rounds) — heavy backgrounds are the #1 cause of the
  "page takes too long to load" complaint.
- EXIF is always stripped: smaller files and no GPS metadata leaking from
  client photos.
