/**
 * hunt.js — detect horizontal overflow on mobile viewports.
 *
 *   node hunt.js
 *
 * For each URL × viewport in sites.json:
 *   1. Loads the page, checks document.documentElement.scrollWidth > innerWidth.
 *   2. Walks the DOM for elements whose scrollWidth > clientWidth (deep nodes
 *      first), then dedupes to the outermost offender in each ancestor chain.
 *   3. Records a selector path + dimensions for each offender.
 *   4. Screenshots the page with offenders outlined in red.
 *   5. Writes findings.json (machine-readable) and report.html (human-readable).
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

function slug(s) {
  return String(s).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

// Runs inside the page. Returns outermost overflowing elements.
function findOffenders() {
  const vw = window.innerWidth;
  const docOverflow = document.documentElement.scrollWidth - vw;

  const cssPath = (el) => {
    const parts = [];
    let node = el;
    while (node && node.nodeType === 1 && node !== document.documentElement && parts.length < 6) {
      let sel = node.tagName.toLowerCase();
      if (node.id) { sel += '#' + node.id; parts.unshift(sel); break; }
      const cls = (node.className && typeof node.className === 'string')
        ? node.className.trim().split(/\s+/).slice(0, 2).join('.') : '';
      if (cls) sel += '.' + cls;
      const parent = node.parentElement;
      if (parent) {
        const sibs = Array.from(parent.children).filter((c) => c.tagName === node.tagName);
        if (sibs.length > 1) sel += `:nth-of-type(${sibs.indexOf(node) + 1})`;
      }
      parts.unshift(sel);
      node = node.parentElement;
    }
    return parts.join(' > ');
  };

  // Deep nodes first so we can dedupe ancestors later.
  const all = Array.from(document.querySelectorAll('body *'));
  const bad = [];
  for (const el of all) {
    // Skip hidden / zero-size nodes — they can't cause visible overflow.
    const rect = el.getBoundingClientRect();
    if (rect.width === 0 && rect.height === 0) continue;
    const style = getComputedStyle(el);
    if (style.display === 'none' || style.visibility === 'hidden') continue;
    if (el.scrollWidth > el.clientWidth + 1 || rect.right > vw + 1 || rect.left < -1) {
      bad.push(el);
    }
  }

  // Dedupe: keep only outermost offenders (drop any element that has an
  // already-recorded ancestor in the bad set).
  const badSet = new Set(bad);
  const outermost = bad.filter((el) => {
    let p = el.parentElement;
    while (p && p !== document.body) {
      if (badSet.has(p)) return false;
      p = p.parentElement;
    }
    return true;
  });

  return {
    viewportWidth: vw,
    documentOverflowPx: docOverflow,
    offenders: outermost.slice(0, 25).map((el) => {
      const rect = el.getBoundingClientRect();
      return {
        selector: cssPath(el),
        tag: el.tagName.toLowerCase(),
        rectRight: Math.round(rect.right),
        rectLeft: Math.round(rect.left),
        scrollWidth: el.scrollWidth,
        clientWidth: el.clientWidth,
      };
    }),
  };
}

async function main() {
  const { urls, viewports } = JSON.parse(fs.readFileSync(path.join(__dirname, 'sites.json'), 'utf8'));
  const shotsDir = path.join(__dirname, 'shots');
  fs.mkdirSync(shotsDir, { recursive: true });

  const browser = await chromium.launch();
  const findings = [];

  try {
    for (const url of urls) {
      for (const vp of viewports) {
        const label = `${url} @ ${vp.name} (${vp.width}x${vp.height})`;
        console.log(`Hunting ${label}...`);
        const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
        const entry = { url, viewport: vp.name, width: vp.width, overflow: false, offenders: [], screenshot: null, error: null };
        try {
          await page.goto(url + (url.includes('?') ? '&' : '?') + 'cb=' + Date.now(),
            { waitUntil: 'networkidle', timeout: 60000 });
          await page.waitForTimeout(1200);

          const result = await page.evaluate(findOffenders);
          entry.overflow = result.documentOverflowPx > 1;
          entry.documentOverflowPx = result.documentOverflowPx;
          entry.offenders = result.offenders;

          if (entry.overflow || entry.offenders.length > 0) {
            // Outline offenders in red, then screenshot.
            await page.evaluate(() => {
              const all = Array.from(document.querySelectorAll('body *'));
              for (const el of all) {
                const r = el.getBoundingClientRect();
                if (r.width === 0 && r.height === 0) continue;
                if (el.scrollWidth > el.clientWidth + 1 || r.right > window.innerWidth + 1 || r.left < -1) {
                  el.style.outline = '3px solid red';
                  el.style.outlineOffset = '-1px';
                }
              }
            });
          }
          const shotFile = `${slug(url.replace(/^https?:\/\//, '').split(/[?#]/)[0]) || 'page'}-${slug(vp.name)}.png`;
          await page.screenshot({ path: path.join(shotsDir, shotFile), fullPage: false });
          entry.screenshot = `shots/${shotFile}`;

          if (entry.overflow) {
            console.log(`  OVERFLOW: document is ${result.documentOverflowPx}px wider than viewport; ${result.offenders.length} offender(s)`);
            for (const o of result.offenders) console.log(`    - ${o.selector} (right edge ${o.rectRight}px vs viewport ${vp.width}px)`);
          } else {
            console.log('  clean — no horizontal overflow');
          }
        } catch (err) {
          entry.error = err.message;
          console.error(`  FAILED: ${err.message}`);
        } finally {
          await page.close();
        }
        findings.push(entry);
      }
    }
  } finally {
    await browser.close();
  }

  fs.writeFileSync(path.join(__dirname, 'findings.json'), JSON.stringify(findings, null, 2));

  const totalOverflow = findings.filter((f) => f.overflow).length;
  const cards = findings.map((f) => {
    const badge = f.error
      ? '<span class="badge err">ERROR</span>'
      : f.overflow
        ? '<span class="badge fail">OVERFLOW</span>'
        : '<span class="badge pass">CLEAN</span>';
    const offenders = f.offenders.length === 0
      ? '<p class="none">No offending elements found.</p>'
      : '<table><tr><th>selector</th><th>right edge</th><th>scrollW / clientW</th></tr>' +
        f.offenders.map((o) =>
          `<tr><td><code>${esc(o.selector)}</code></td><td>${o.rectRight}px (viewport ${f.width}px)</td><td>${o.scrollWidth} / ${o.clientWidth}</td></tr>`
        ).join('') + '</table>';
    const shot = f.screenshot
      ? `<a href="${esc(f.screenshot)}" target="_blank"><img src="${esc(f.screenshot)}"></a>`
      : '';
    const errLine = f.error ? `<p class="errline">${esc(f.error)}</p>` : '';
    return `<section class="card ${f.error ? 'error' : f.overflow ? 'fail' : 'pass'}">
      <h2>${esc(f.url)} <small>@ ${esc(f.viewport)}</small> ${badge}</h2>
      ${errLine}${offenders}${shot}</section>`;
  }).join('\n');

  const html = `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Overflow Hunter Report — ${new Date().toISOString()}</title>
<style>
body{font-family:system-ui,sans-serif;background:#111;color:#eee;margin:0;padding:24px}
h1{font-size:1.3rem}p.summary{color:#bbb}.card{background:#1c1c1c;border-radius:8px;padding:16px;margin:16px 0;border-left:6px solid #888}
.card.pass{border-color:#2ea043}.card.fail{border-color:#da3633}.card.error{border-color:#9e7bea}
.badge{font-size:.7rem;padding:3px 10px;border-radius:20px;color:#fff}
.pass{background:#2ea043}.fail{background:#da3633}.err{background:#9e7bea}
small{color:#999}table{border-collapse:collapse;width:100%;margin:8px 0}
th,td{border:1px solid #333;padding:6px 10px;text-align:left;font-size:.8rem}
code{color:#7dd3fc}.none{color:#999}.errline{color:#da3633}
img{max-width:420px;border:1px solid #444;border-radius:4px;background:#fff;margin-top:8px}
</style></head><body>
<h1>Overflow Hunter Report</h1>
<p class="summary">${findings.length} page×viewport checks — ${totalOverflow} with horizontal overflow. Generated ${new Date().toISOString()}. Full data in findings.json.</p>
${cards}</body></html>`;

  fs.writeFileSync(path.join(__dirname, 'report.html'), html);
  console.log(`\nDone: ${totalOverflow} overflowing of ${findings.length} checks. See report.html / findings.json.`);
  process.exit(totalOverflow > 0 ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(1); });
