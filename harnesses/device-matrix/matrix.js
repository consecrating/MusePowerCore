/**
 * matrix.js — screenshot every URL on every device profile, then build a
 * contact-sheet report.html (rows = pages, columns = devices).
 *
 *   node matrix.js
 *
 * Devices use Playwright's built-in descriptors (real UA, viewport, pixel
 * ratio, touch, mobile flags) — this is far closer to a real phone than
 * DevTools responsive mode. URLs come from sites.json.
 */
const fs = require('fs');
const path = require('path');
const { chromium, devices } = require('playwright');

const DEVICES = [
  'iPhone 15',
  'iPhone SE',
  'Pixel 8',
  'Galaxy S23',
  'iPad Mini',
  // Desktop has no built-in descriptor; defined inline below.
  'Desktop 1440x900',
];

function slug(s) {
  return String(s).toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

async function main() {
  const { urls } = JSON.parse(fs.readFileSync(path.join(__dirname, 'sites.json'), 'utf8'));
  const shotsDir = path.join(__dirname, 'shots');
  fs.mkdirSync(shotsDir, { recursive: true });

  const browser = await chromium.launch();
  const grid = []; // grid[pageIdx][deviceIdx] = {file, label}

  try {
    for (const [pi, url] of urls.entries()) {
      grid[pi] = { url, cells: [] };
      for (const devName of DEVICES) {
        const descriptor = devName === 'Desktop 1440x900'
          ? { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, isMobile: false, hasTouch: false }
          : devices[devName];
        if (!descriptor) {
          console.error(`Unknown device descriptor: ${devName} — skipping`);
          continue;
        }
        const file = `${slug(url.replace(/^https?:\/\//, '').split(/[?#]/)[0]) || 'page'}-${slug(devName)}.png`;
        const context = await browser.newContext(descriptor);
        const page = await context.newPage();
        try {
          console.log(`Capturing ${url} on ${devName}...`);
          await page.goto(url + (url.includes('?') ? '&' : '?') + 'cb=' + Date.now(),
            { waitUntil: 'networkidle', timeout: 60000 });
          await page.waitForTimeout(1200);
          await page.screenshot({ path: path.join(shotsDir, file), fullPage: true });
          grid[pi].cells.push({ device: devName, file });
          console.log(`  saved shots/${file}`);
        } catch (err) {
          console.error(`  FAILED ${url} on ${devName}: ${err.message}`);
          grid[pi].cells.push({ device: devName, file: null, error: err.message });
        } finally {
          await context.close();
        }
      }
    }
  } finally {
    await browser.close();
  }

  const headerCells = DEVICES.map((d) => `<th>${esc(d)}</th>`).join('');
  const rows = grid.map((row) => {
    const cells = row.cells.map((c) => {
      if (!c.file) return `<td class="err">capture failed<br><small>${esc(c.error || '')}</small></td>`;
      return `<td><a href="shots/${esc(c.file)}" target="_blank"><img src="shots/${esc(c.file)}" loading="lazy"></a><div class="cap">${esc(c.device)}</div></td>`;
    }).join('');
    return `<tr><th class="rowhead">${esc(row.url)}</th>${cells}</tr>`;
  }).join('\n');

  const html = `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Device Matrix — ${new Date().toISOString()}</title>
<style>
body{font-family:system-ui,sans-serif;background:#111;color:#eee;margin:0;padding:24px}
h1{font-size:1.3rem}p{color:#999}table{border-collapse:collapse;width:100%}
th,td{border:1px solid #333;padding:8px;vertical-align:top;text-align:center}
th{background:#1c1c1c}.rowhead{max-width:220px;word-break:break-all;font-size:.75rem;text-align:left}
img{max-width:220px;border:1px solid #444;border-radius:4px;background:#fff}
.cap{font-size:.7rem;color:#999;margin-top:4px}.err{color:#da3633;font-size:.8rem}
</style></head><body>
<h1>Device Matrix</h1>
<p>${urls.length} page(s) × ${DEVICES.length} devices. Click any thumbnail for full size. Generated ${new Date().toISOString()}.</p>
<table><tr><th>page</th>${headerCells}</tr>${rows}</table>
</body></html>`;

  fs.writeFileSync(path.join(__dirname, 'report.html'), html);
  console.log('\nDone. Open report.html for the contact sheet.');
}

main().catch((e) => { console.error(e); process.exit(1); });
