/**
 * capture.js — screenshot every configured site × viewport.
 *
 *   node capture.js --baseline     # writes into baselines/ (do this BEFORE a change)
 *   node capture.js                 # writes into current/  (do this AFTER a change)
 *
 * Config lives in sites.json. Output files: <site>-<viewport>.png
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');
const cfg = require('./playwright.config.js');

const isBaseline = process.argv.includes('--baseline');
const outDir = isBaseline ? cfg.dirs.baseline : cfg.dirs.current;

function slug(s) {
  return String(s).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

async function main() {
  const sites = JSON.parse(fs.readFileSync(path.join(__dirname, 'sites.json'), 'utf8')).sites;
  fs.mkdirSync(path.join(__dirname, outDir), { recursive: true });

  const browser = await chromium.launch();
  try {
    for (const site of sites) {
      for (const vp of site.viewports || [{ name: 'desktop', width: 1440, height: 900 }]) {
        const file = `${slug(site.name)}-${slug(vp.name)}.png`;
        const dest = path.join(__dirname, outDir, file);
        const page = await browser.newPage({ viewport: { width: vp.width, height: vp.height } });
        try {
          console.log(`Capturing ${site.name} @ ${vp.name} (${vp.width}x${vp.height}) -> ${outDir}/${file}`);
          // Cache-bust so we never screenshot a stale copy.
          const url = site.url + (site.url.includes('?') ? '&' : '?') + 'cb=' + Date.now();
          await page.goto(url, { waitUntil: 'networkidle', timeout: 60000 });
          await page.waitForTimeout(site.waitMs || 1000);
          await page.screenshot({ path: dest, fullPage: site.fullPage !== false });
          console.log(`  saved ${dest}`);
        } catch (err) {
          console.error(`  FAILED ${site.name} @ ${vp.name}: ${err.message}`);
          process.exitCode = 1;
        } finally {
          await page.close();
        }
      }
    }
  } finally {
    await browser.close();
  }
  console.log(isBaseline ? 'Baseline capture complete.' : 'Current capture complete.');
}

main().catch((e) => { console.error(e); process.exit(1); });
