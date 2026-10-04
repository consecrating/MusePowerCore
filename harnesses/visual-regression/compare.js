/**
 * compare.js — diff current/ against baselines/ with pixelmatch.
 *
 *   node compare.js
 *
 * For every matching <site>-<viewport>.png pair:
 *   - writes diff PNGs into diffs/ (red overlay where pixels differ)
 *   - writes report.html with side-by-side + diff overlay + PASS/FAIL per page
 *   - exits non-zero if any page exceeds the fail threshold
 *
 * Pages present in current/ but missing from baselines/ are reported as NEW
 * (not failures) — run `node capture.js --baseline` first for a clean run.
 */
const fs = require('fs');
const path = require('path');
const { PNG } = require('pngjs');
const pixelmatch = require('pixelmatch');
const cfg = require('./playwright.config.js');

function readPng(file) {
  return PNG.sync.read(fs.readFileSync(file));
}

function esc(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function main() {
  const root = __dirname;
  const baseDir = path.join(root, cfg.dirs.baseline);
  const curDir = path.join(root, cfg.dirs.current);
  const diffDir = path.join(root, cfg.dirs.diff);
  fs.mkdirSync(diffDir, { recursive: true });

  if (!fs.existsSync(curDir)) {
    console.error(`No ${cfg.dirs.current}/ directory — run "node capture.js" first.`);
    process.exit(2);
  }

  const currentFiles = fs.readdirSync(curDir).filter((f) => f.endsWith('.png')).sort();
  if (currentFiles.length === 0) {
    console.error(`No screenshots in ${cfg.dirs.current}/ — run "node capture.js" first.`);
    process.exit(2);
  }

  const results = [];
  let failures = 0;

  for (const file of currentFiles) {
    const curPath = path.join(curDir, file);
    const basePath = path.join(baseDir, file);
    const label = file.replace(/\.png$/, '');

    if (!fs.existsSync(basePath)) {
      console.log(`${label}: NEW (no baseline) — not a failure`);
      results.push({ label, status: 'NEW', pct: null, base: null, cur: file, diff: null });
      continue;
    }

    const imgCur = readPng(curPath);
    const imgBase = readPng(basePath);
    const w = Math.max(imgCur.width, imgBase.width);
    const h = Math.max(imgCur.height, imgBase.height);

    // Normalize to the same canvas size so pixelmatch never throws.
    const norm = (img) => {
      if (img.width === w && img.height === h) return img;
      const out = new PNG({ width: w, height: h });
      PNG.bitblt(img, out, 0, 0, Math.min(img.width, w), Math.min(img.height, h), 0, 0);
      return out;
    };
    const nCur = norm(imgCur);
    const nBase = norm(imgBase);
    const diffImg = new PNG({ width: w, height: h });

    const diffPixels = pixelmatch(
      nBase.data, nCur.data, diffImg.data, w, h, cfg.pixelmatchOptions
    );
    const pct = diffPixels / (w * h);
    const status = pct > cfg.failThreshold ? 'FAIL' : 'PASS';
    if (status === 'FAIL') failures++;

    const diffFile = file.replace(/\.png$/, '.diff.png');
    fs.writeFileSync(path.join(diffDir, diffFile), PNG.sync.write(diffImg));

    console.log(`${label}: ${status} (${(pct * 100).toFixed(3)}% pixels differ, threshold ${(cfg.failThreshold * 100).toFixed(3)}%)`);
    results.push({ label, status, pct, base: file, cur: file, diff: diffFile });
  }

  // report.html — self-contained, references local PNGs relatively.
  const rows = results.map((r) => {
    const badge = r.status === 'PASS'
      ? '<span class="badge pass">PASS</span>'
      : r.status === 'FAIL'
        ? '<span class="badge fail">FAIL</span>'
        : '<span class="badge new">NEW</span>';
    const pct = r.pct === null ? '—' : (r.pct * 100).toFixed(3) + '%';
    const imgs = r.status === 'NEW'
      ? `<div class="shots"><figure><img src="${cfg.dirs.current}/${esc(r.cur)}"><figcaption>current (no baseline)</figcaption></figure></div>`
      : `<div class="shots">
           <figure><img src="${cfg.dirs.baseline}/${esc(r.base)}"><figcaption>baseline</figcaption></figure>
           <figure><img src="${cfg.dirs.current}/${esc(r.cur)}"><figcaption>current</figcaption></figure>
           <figure><img src="${cfg.dirs.diff}/${esc(r.diff)}"><figcaption>diff overlay</figcaption></figure>
         </div>`;
    return `<section class="card ${r.status.toLowerCase()}">
      <h2>${esc(r.label)} ${badge} <small>${pct} differ</small></h2>${imgs}</section>`;
  }).join('\n');

  const html = `<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Visual Regression Report — ${new Date().toISOString()}</title>
<style>
body{font-family:system-ui,sans-serif;background:#111;color:#eee;margin:0;padding:24px}
h1{font-size:1.4rem}.card{background:#1c1c1c;border-radius:8px;padding:16px;margin:16px 0;border-left:6px solid #888}
.card.pass{border-color:#2ea043}.card.fail{border-color:#da3633}.card.new{border-color:#9e7bea}
.badge{font-size:.7rem;padding:3px 10px;border-radius:20px;color:#fff;vertical-align:middle}
.pass{background:#2ea043}.fail{background:#da3633}.new{background:#9e7bea}
small{color:#999;font-weight:normal}.shots{display:flex;gap:12px;flex-wrap:wrap}
figure{margin:0;flex:1;min-width:260px}img{width:100%;border:1px solid #333;border-radius:4px;background:#fff}
figcaption{font-size:.75rem;color:#999;margin-top:4px}
.summary{font-size:1rem;margin-bottom:8px}
</style></head><body>
<h1>Visual Regression Report</h1>
<p class="summary">${results.length} pages checked — ${results.filter(r=>r.status==='PASS').length} pass, ${failures} fail, ${results.filter(r=>r.status==='NEW').length} new. Threshold: ${(cfg.failThreshold*100).toFixed(3)}%.</p>
${rows}</body></html>`;

  fs.writeFileSync(path.join(root, cfg.reportFile), html);
  console.log(`\nReport: ${cfg.reportFile} — ${failures} failure(s).`);
  process.exit(failures > 0 ? 1 : 0);
}

main();
