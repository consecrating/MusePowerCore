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

// Strings = Playwright built-in descriptors. Objects = custom profiles, used
// where no built-in exists — notably budget Android, the viewport most of
// India actually browses on and where mobile breakage hides.
const DEVICES = [
  'iPhone 15',
  'iPhone SE',
  'Pixel 8',            // Android flagship
  'Galaxy S23',         // Android flagship
  { name: 'Android Budget 360x640', label: 'Android (budget 360×640)', descriptor: {
      viewport: { width: 360, height: 640 }, deviceScaleFactor: 2,
      isMobile: true, hasTouch: true,
      userAgent: 'Mozilla/5.0 (Linux; Android 13; Redmi Note 12 5G) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
  } },
  { name: 'Android Tall 412x915', label: 'Android (tall 412×915)', descriptor: {
      viewport: { width: 412, height: 915 }, deviceScaleFactor: 2.625,
      isMobile: true, hasTouch: true,
      userAgent: 'Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Mobile Safari/537.36',
  } },
  'iPad Mini',
  // Desktop has no built-in descriptor; defined inline below.
  'Desktop 1440x900',
];

function devLabel(d) { return typeof d === 'string' ? d : (d.label || d.name); }

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
      for (const dev of DEVICES) {
        const devName = typeof dev === 'string' ? dev : dev.name;
        const descriptor = typeof dev === 'string'
          ? (devName === 'Desktop 1440x900'
              ? { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1, isMobile: false, hasTouch: false }
              : devices[devName])
          : dev.descriptor;
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

  const headerCells = DEVICES.map((d) => `<th>${esc(devLabel(d))}</th>`).join('');
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
