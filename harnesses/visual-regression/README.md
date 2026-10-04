# Visual Regression Harness

Before/after screenshot diffing for client-site deploys. Run a baseline
capture **before** a change, capture again **after**, and diff — so you see
exactly what moved instead of relying on eyeballs.

## Setup

```bash
cd harnesses/visual-regression
npm install
npx playwright install chromium
```

## Configure

Edit `sites.json` — array of sites, each with `name`, `url`, `viewports[]`
(`name`, `width`, `height`), optional `waitMs` (settle time before capture)
and `fullPage` (default true):

```json
{
  "sites": [
    {
      "name": "coaching",
      "url": "https://demo3.sanctify.co/coaching.html",
      "viewports": [
        { "name": "desktop", "width": 1440, "height": 900 },
        { "name": "mobile",  "width": 390,  "height": 844 }
      ],
      "waitMs": 1500
    }
  ]
}
```

Tune sensitivity in `playwright.config.js` (`failThreshold` — fraction of
differing pixels that fails a page; default 0.001 = 0.1%).

## Usage

```bash
# 1. BEFORE the change — capture baselines
npm run capture:baseline

# 2. Make the change, deploy it

# 3. AFTER the change — capture current state
npm run capture

# 4. Diff and generate the report
npm run compare
# exits 1 if any page exceeds the threshold; opens report.html for the verdict
```

`compare.js` writes `diffs/*.diff.png` (red overlay where pixels differ) and
`report.html` with baseline / current / diff side-by-side per page and a
PASS/FAIL badge.

## Workflow fit

- `markup-round` → deploy via `site-deploy` → `live-verify` → run this
  harness → attach the diff verdict to the round report.
- Pages present in `current/` with no baseline are marked NEW (not failures).

## Notes

- Captures are cache-busted (`?cb=<timestamp>`) so you never diff a stale copy.
- Screenshots of different sizes are normalized to the larger canvas before
  diffing, so a height change shows up as a real diff instead of a crash.
