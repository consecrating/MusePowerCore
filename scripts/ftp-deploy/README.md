# ftp-deploy — loud, safe, changed-files-only FTP deploys

Built because FTP was the shakiest part of the client-site workflow. Four
specific pains, four fixes:

| Pain | Fix |
| ---- | --- |
| **Silent** — uploads gave no feedback; "is it stuck?" | Every file is announced as it uploads (`[3/12] UPLOAD css/style.css (48.2 KB)`), plus a final summary. Nothing happens quietly. |
| **Slow** — whole site re-uploaded for a one-line CSS fix | sha256 manifest: only new/changed files upload. Unchanged files are skipped via size+mtime fast-path (no re-hashing). |
| **Nervous** — no way to preview before touching live | `--dry-run` prints the full plan (uploads / skips / deletions with sizes) and changes nothing. `--prune` deletions additionally require `--yes`. |
| **Unverified** — had to check by hand after every upload | Remote `SIZE` is checked after every upload; mismatches are reported as `FAILED` and the exit code is non-zero. |

Connection model: explicit FTPS (`FTP_TLS` + `auth()` + `prot_p()` + passive
mode) — the same pattern proven against `ftp.sanctify.co`. Use `--no-tls`
only if a host truly can't do FTPS.

Stdlib only. No pip installs.

## Quickstart

```bash
cd scripts/ftp-deploy

# 1. Preview (changes nothing, exit code 2)
python3 ftp_deploy.py --host ftp.sanctify.co --user 'demo3@demo3.sanctify.co' \
  --local /path/to/site --remote / --dry-run

# 2. Deploy (password via env var, or you'll be prompted securely)
export FTP_PASSWORD='...'
python3 ftp_deploy.py --host ftp.sanctify.co --user 'demo3@demo3.sanctify.co' \
  --local /path/to/site --remote /

# 3. Or keep settings in a config file (copy config.example.json first)
python3 ftp_deploy.py --config my-site.json --dry-run
```

First run on a site does one **full sync** (with a warning) to build the
manifest baseline. Every run after that uploads only what changed.

## Credential handling

Priority: `--password` flag → `FTP_PASSWORD` env var → secure interactive
prompt. Passwords are **never** written to disk — not in the config file, not
in the manifest, not in logs.

## How it works

- `.ftp-deploy-manifest.json` (in your local site dir) maps each deployed
  file to its `{sha256, size, mtime}`. **Add it to your site's `.gitignore`**
  along with `.ftp-deploy/` — it's per-machine state, not source.
- Before overwriting any remote file, the current remote copy is downloaded
  to `.ftp-deploy/backups/<UTC-timestamp>/` (mirroring remote paths) with an
  `index.json`. New files need no backup.
- Transient network errors (timeouts, 4xx) retry 3× with exponential backoff
  and automatic reconnect; permanent errors (5xx, auth) fail fast and loud.
- Shared hosts throttle parallel connections, so uploads are serial by
  design — reliability over speed.

## Rollback

```bash
# list backup sets
python3 ftp_deploy.py --host ... --user ... --local /path/to/site --list-backups
#   20261005-031500  (4 file(s))

# restore one (re-uploads + verifies each file)
python3 ftp_deploy.py --host ... --user ... --local /path/to/site \
  --rollback 20261005-031500
```

## Pruning deleted files

Remote files are **never** deleted by default. To sync deletions:

```bash
python3 ftp_deploy.py --config my-site.json --prune --dry-run   # preview first
python3 ftp_deploy.py --config my-site.json --prune --yes       # execute
```

## Exit codes

- `0` — clean (including "nothing to do")
- `1` — one or more failures (upload mismatch, connection failure, rollback failure)
- `2` — dry-run (plan printed, nothing changed)
