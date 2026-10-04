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

- iPhone 15, iPhone SE, Pixel 8, Galaxy S23, iPad Mini (Playwright built-in
  descriptors), Desktop 1440x900.

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
