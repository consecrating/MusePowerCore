# Device Matrix Harness

Screenshot every page on real Playwright device profiles and build a
contact-sheet report — rows are pages, columns are devices. This is what
"check mobile" should have always meant: actual iPhone/Pixel/Galaxy rendering
(real UA, viewport, pixel ratio, touch flags), not DevTools responsive mode.

## Setup

```bash
cd harnesses/device-matrix
npm install
npx playwright install chromium
```

## Configure

Edit `sites.json`:

```json
{ "urls": ["https://demo3.sanctify.co/coaching.html"] }
```

Device list lives at the top of `matrix.js` (`DEVICES`). Defaults:

- iPhone 15, iPhone SE (Playwright built-in descriptors)
- Pixel 8, Galaxy S23 — Android flagships (built-in descriptors)
- Android Budget 360x640 — custom profile (Redmi-class UA, 360×640 viewport):
  the most common real-world Android in India, where mobile breakage hides
- Android Tall 412x915 — custom tall-Android profile
- iPad Mini, Desktop 1440x900

## Usage

```bash
npm run matrix
# screenshots -> shots/, contact sheet -> report.html
```

Each thumbnail links to the full-size screenshot. Failed captures are marked
in red with the error message instead of silently dropping the cell.

## Workflow fit

- After any layout/spacing round (`markup-round` + `site-deploy`), run this
  before telling the user it's verified — catches the "desktop fine, phone
  broken" class of failures the client would otherwise find first.
- Pairs with `overflow-hunter`: matrix shows you the breakage, hunter names
  the offending element.
