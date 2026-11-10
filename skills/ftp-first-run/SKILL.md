---
name: ftp-first-run
description: "First-run FTP rescue for a fresh Muse: probe the data channel once with a short timeout, stop retrying direct FTP when it is blackholed, and get the upload done through the browser web-FTP client instead. Activate on the first FTP upload in a new session, on any FTP upload for a brand-new user, or whenever a direct FTP upload stalls or times out."
metadata:
  version: "1.0"
  author: consecrating
---

# ftp-first-run — First-Run FTP Rescue

A brand-new Muse wastes its first FTP round doing the same thing over and
over: direct `ftplib` / `curl` uploads that never complete. The failure has a
signature, and this skill teaches the agent to recognise it in under a
minute instead of struggling for a session: the FTP control channel
(port 21) connects fine, but the DATA channel (PASV ports) is blackholed,
so every `LIST` / `RETR` / `STOR` hangs until timeout. The fix is not a
better retry — it is a different route (browser web-FTP client), chosen
once the probe proves the block.

## Hard Rules

1. **Probe once, short timeout, then decide.** One control connect plus
   one data attempt (`LIST`) with a 15-second timeout, using
   `scripts/ftp-probe.py`. Control OK + data timeout = `BLOCKED`. Never
   run the `ftp-deploy` retry loop as the probe, and never re-run direct
   `ftplib` / `curl` after a `BLOCKED` verdict in the same session.
2. **Narrate inside the first minute.** Before the probe finishes, the
   user hears the plan in plain words: what will be uploaded, what
   credential is needed, and what happens if direct FTP is blocked. A
   silent FTP attempt reads as stuck — that is exactly the struggle this
   skill exists to prevent.
3. **Credentials once, transient only.** Ask for host / user / password
   once, use them for the authorised task only, never write them to disk,
   memory, or any file. Verify the login succeeds before uploading
   anything. A web client's saved-login fill may pair the wrong account's
   password — if auth fails, type the password fresh; re-approving the
   same fill just resubmits the wrong password.
4. **One zip, not many files.** Package the changed files into ONE zip,
   upload once, extract on the server. Never push files one by one through
   a web client — slow, error-prone, and each file is a fresh chance to
   stall.
5. **Check the zip layout before extracting.** List the zip's top-level
   entries first. A flat zip (no folder prefix) extracts INSIDE the target
   directory; a zip with a top-level folder extracts from the parent, or
   it creates a duplicate nested folder and leaves the live files
   untouched.
6. **Verify sizes and permissions after extract.** Every uploaded file
   must show the expected byte size; files `644`, folders `755`. Some
   hosts extract as `660` / `770` (403 until chmod) and others as
   `644` / `755` already — verify every time, assume neither.
7. **Never claim live from upload success.** Hand off to `live-verify`:
   fetch fresh, look at the rendered page. "Uploaded" is not "live".
8. **Stop, don't grind.** Auth fails twice → stop and ask the user. The
   web client is down or demands signup → stop, try the host file
   manager / cPanel, or ask the user — do not burn the session retrying
   a dead client. A known-down client stays down (net2ftp.com was down
   with a PHP fatal error, 2026-10-07; browserftp.com requires signup).

## Workflow

### 1. Intake (30 seconds, before touching anything)
State the plan out loud: exact file list, target site and remote path,
and the one credential needed. If host or user is missing, ask once —
in plain words, no jargon:
> "First upload here, so I'll check in under a minute whether direct
> FTP works from my side. If it's blocked I'll upload through the
> browser instead — same files, same result. I need the FTP host,
> username, and password for this site."

If the user is brand-new to Muse, add one line: the password is used
once for this upload and never stored.

### 2. Probe (≤ 60 seconds)
Run the probe. Without credentials it can only do the control check;
with credentials it does the full check:

```bash
# Control channel only (no credentials needed):
python3 skills/ftp-first-run/scripts/ftp-probe.py --host ftp.example.com --control-only
# Full probe (password via FTP_PASSWORD env var, never on the command line):
FTP_PASSWORD='...' python3 skills/ftp-first-run/scripts/ftp-probe.py --host ftp.example.com --user 'user@example.com'
```

Verdict table — the probe prints exactly one:

| Verdict | Meaning | Route |
| ------- | ------- | ----- |
| `OK` | Data channel works | Direct: hand off to `site-deploy` + `scripts/ftp-deploy` |
| `BLOCKED` | Control connects, data fails / times out | Browser web-FTP client (step 3) — do not retry direct |
| `AUTH-FAILED` | Login rejected | Re-check credentials once (fresh password, not a saved fill); fail twice → ask the user |
| `CONTROL-UNREACHABLE` | Port 21 does not answer | Host, port, or firewall is wrong — ask the user, do not guess another host |
| `NEEDS-CREDENTIALS` | No password supplied | Ask the user once, then re-probe |

Tell the user the verdict in one sentence, then move. A `BLOCKED`
verdict is a diagnosis, not a failure — say so.

### 3. Browser route (only when `BLOCKED`)
Use a web FTP client through the browser task, explicit FTPS:
- **First choice: FTPWeb.Net** (`https://ftpweb.net/noindex/mainapp/`) —
  proven with explicit FTPS to `ftp.sanctify.co`. Log in fresh in each
  new browser window: the login does NOT persist across windows, and a
  window showing an empty login dialog is not a stall — it is waiting
  for credentials.
- **Do not use:** net2ftp.com (down, 2026-10-07), browserftp.com
  (requires signup). If FTPWeb.Net is down, use the host's own file
  manager / cPanel upload, or ask the user.
- Give the browser task the zip file (file grant) and the full
  credentials in the task brief — text credentials sent mid-task do not
  always clear the login step. Before declaring a stall, check the
  window's live state (working vs waiting) and the served file sizes
  directly.

### 4. Package
Build ONE zip of exactly the changed files (fewest-files rule from
`site-deploy`). List its top-level entries and record flat vs foldered,
so the extract location in step 5 matches. Note the byte size of every
file inside — that is the verify baseline.

### 5. Upload + extract + permissions
Upload the single zip via the chosen route, extract it in the matching
location (flat zip → inside the target directory; foldered zip → from
its parent), then verify: every file present at the expected byte size,
files `644`, folders `755` (chmod via the web client if the extract
came out `660` / `770`). Same-URL re-upload of an image does NOT
reliably replace a cached copy — for a corrected asset, use a fresh
filename instead of purging repeatedly.

### 6. Verify
Run `live-verify` on the deployed page(s): fetch fresh with
cache-busting, confirm the intended change is actually visible.
Only report "live" for what was observed.

### 7. Report
End with a short, factual report:
- Probe verdict (`OK` / `BLOCKED` / …) and the route taken
- What was uploaded (the one zip, its files)
- What was verified live (specific observations)
- The durable note for next time: record the host's route
  ("`ftp.example.com`: data channel blocked, use browser route") in
  `AGENTS.md` so the next fresh session skips the struggle entirely

## Worked example

First upload to `demo3.sanctify.co`, one file changed
(`coaching.html`).

1. Intake: "First upload here — I'll probe direct FTP (under a minute)
   and fall back to the browser uploader if it's blocked. I need the
   FTP password for this site."
2. Probe: control connects in 1s; `LIST` times out at 15s → verdict
   `BLOCKED`. Reported: "Direct FTP is blocked from my side — control
   connects but uploads hang. Switching to the browser uploader, same
   file."
3. Package: `coaching-v1.zip`, flat layout, `coaching.html` 12,408 B.
4. Browser route: FTPWeb.Net, explicit FTPS, fresh login in the new
   window, zip granted to the task. Upload, extract inside the site
   root, sizes match, perms `644`.
5. Verify: `live-verify` fetches fresh — card buttons solid teal /
   brick-red, square corners, no collateral damage.
6. Report: "Uploaded `coaching.html` via the browser route (direct FTP
   blocked here). Verified live: buttons solid teal and brick-red,
   square corners. Noted in AGENTS.md: this host needs the browser
   route."

## Anti-patterns

- Retrying direct FTP 3–5 times with longer timeouts after the first
  data timeout → the block is at the network level; retries only burn
  the session and the user's patience. One probe, one verdict, switch
  routes.
- Uploading 6 files one by one through a web client → each file is a
  separate stall risk; one zip, one upload, one extract.
- Trusting a saved-login fill after an auth failure → the fill can pair
  another account's password with this username; re-approving it fails
  identically. Type the password fresh.
- Extracting a foldered zip inside the target directory → creates
  `target/target/` and leaves the live files untouched; the deploy
  "succeeds" and nothing changes. List the zip layout first.
- Re-uploading a corrected image under the same URL and purging cache
  repeatedly → stale copies survive purges; a fresh filename is what
  actually takes effect live.
- Reporting "live" because the web client said the upload succeeded →
  the page was never re-fetched. `live-verify` or it didn't happen.
