# Overflow Hunter

Finds horizontal overflow on mobile viewports and names the guilty element —
so "the page scrolls sideways on my phone" becomes a selector path, a pixel
count, and a red-outlined screenshot instead of a guessing game.

## Setup

```bash
cd harnesses/overflow-hunter
npm install
npx playwright install chromium
```

## Configure

Edit `sites.json`:

```json
{
  "urls": ["https://demo3.sanctify.co/coaching.html"],
  "viewports": [
    { "name": "mobile-390", "width": 390, "height": 844 },
    { "name": "mobile-360", "width": 360, "height": 844 }
  ]
}
```

## Usage

```bash
npm run hunt
# exits 1 if any page×viewport overflows
# -> report.html  (human-readable: badges, offender table, red-outlined screenshots)
# -> findings.json (machine-readable: selector paths + dimensions)
```

## How it detects

1. Checks `document.documentElement.scrollWidth > window.innerWidth`
   (the page-level signal).
2. Walks every element for `scrollWidth > clientWidth` or rects extending
   past the viewport edges (deep nodes first).
3. Dedupes to the **outermost** offender per ancestor chain, so you get one
   actionable selector instead of 40 nested divs.
4. Outlines offenders in red and screenshots the viewport.

Common culprits it surfaces: fixed-width images, `white-space: nowrap`
headlines, absolutely-positioned decorations, negative-margin sections,
unwrapped long URLs.

## Workflow fit

- Run after every layout-affecting round, before `live-verify` signs off on
  mobile. A page that overflows at 390px is not "verified".
- Feed `findings.json` selectors straight into the next `markup-round` fix.
