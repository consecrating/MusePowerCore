# MusePowerCore

The agent power-core for Sanctify Goa's client-site work: battle-tested skills,
Playwright verification harnesses, and asset tooling — everything learned from
dozens of live deploy rounds, encoded as reusable machinery instead of memory.

## Components

| Component | Type | Purpose |
| --------- | ---- | ------- |
| `skills/site-deploy` | skill | FTP deploys for static client sites: fewest files, narrated progress, verify-live handoff |
| `skills/markup-round` | skill | The one-round-at-a-time edit loop: marked-up screenshot + one-liner → exact change → deploy → prove live → "what's next?" |
| `skills/live-verify` | skill | Post-deploy evidence gate: fetch fresh, screenshot, confirm the change is actually live — never claim from upload success alone |
| `skills/wp-plugin-ops` | skill | WordPress plugin build → zip → install → activate → verify, with ask-before-live and no-stored-credentials rules |
| `skills/skill-factory` | skill | Meta-skill: scaffold, dry-run-test, install, version, and retire new skills on demand |
| `harnesses/visual-regression` | Playwright | Before/after screenshot diffing per deploy — pixel-level change report with PASS/FAIL |
| `harnesses/device-matrix` | Playwright | Screenshot matrix across iPhone / Pixel / Galaxy / iPad / desktop — the contact sheet that replaces "check mobile" |
| `harnesses/overflow-hunter` | Playwright | Mobile horizontal-overflow detector — names the offending element (selector + pixels) with red-outlined screenshots |
| `scripts/asset-optimize` | Python | Web-optimize image directories: downscale, re-encode, strip EXIF, emit WebP — never overwrites originals by default |
| `scripts/ftp-deploy` | Python (stdlib) | Loud, safe, changed-files-only FTP deploys: sha256 manifest, per-file progress, dry-run plans, SIZE-verified uploads, automatic backups + rollback |
| `mcp-servers/ftp` | MCP server (stdio) | Native FTP tools for the agent — list/diff/deploy/upload/download/mkdir/delete/rename/rollback as structured JSON, sharing the ftp-deploy core |

## Quickstart

```bash
git clone https://github.com/consecrating/MusePowerCore
```

**Install the skills** — copy `skills/*` into your agent's skills directory
(e.g. `~/workspace/skills/`), or symlink them:

```bash
ln -s ~/workspace/MusePowerCore/skills/* ~/workspace/skills/
```

**Run a harness:**

```bash
cd harnesses/visual-regression
npm install && npx playwright install chromium
npm run capture:baseline   # before the change
# ... deploy the change ...
npm run capture            # after the change
npm run compare            # diff report -> report.html
```

**Optimize images:**

```bash
pip install pillow
python3 scripts/asset-optimize/optimize.py assets/img assets/img-optimized --webp
```

## Operating philosophy

These five rules are baked into every skill and harness in this repo:

1. **One round at a time.** Apply exactly what was asked. Never batch unrelated changes.
2. **Narrate slow work.** "Uploading…", "Verifying…" — silent operations read as stuck.
3. **Measure before uploading.** Spacing and position values get confirmed in the file first — never deploy guesses.
4. **Verify live before claiming.** "Live" means observed on the real page, not "upload succeeded".
5. **Ask before touching live sites.** Installs, activations, and production changes need an explicit yes — every time.

## Growing the core

Need a new capability? Use the `skill-factory` skill: describe it in plain
words, get a scaffolded + dry-run-tested skill installed, versioned, and
changelogged. Skills that stop earning their keep get retired to
`skills/_retired/` — never left to rot.
