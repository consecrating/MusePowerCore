---
name: site-deploy
description: "Deploy static client-site changes via FTP with live narration and post-deploy verification. Activate for any round that uploads files to a live static site (e.g. demo3.sanctify.co): edits to HTML/CSS/JS/assets. Encodes the hard rules: fewest files possible, narrate slow work out loud, stop instantly on 'stop', never batch unrelated changes, always verify live afterwards."
metadata:
  version: "1.0"
  author: consecrating
---

# site-deploy — FTP Deploy for Static Client Sites

One job: take a finished, reviewed local change and put it live on a static
client site (pattern: demo3.sanctify.co), with zero ambiguity about what is
happening and proof it landed.

## Hard Rules

1. **Fewest files possible.** Upload exactly the files this round changed —
   nothing adjacent, nothing "while I'm in here". A 1-file change is a 1-file
   upload.
2. **Narrate slow work out loud.** Any multi-file or multi-step upload gets
   progress narration: "Uploading…", "Verifying…". Silent operations read as
   broken/stuck to the user. A quiet deploy is a failed deploy from their
   perspective.
3. **Stop instantly.** When the user says stop, stop immediately — no
   finishing the current upload, no "just one more file". Acknowledge and stop.
4. **Never batch.** One round = one deploy = the change the user asked for.
   Unrelated fixes wait for their own round.
5. **Always verify live.** Upload success is not "done". After every upload,
   hand off to the `live-verify` skill and report only what was observed.
6. **Never store credentials.** FTP passwords are transient, per the user's
   explicit authorization for that task. Never write them to memory or files.

## Workflow

### 1. Confirm the file list
Before touching anything, state exactly which files will go up and why:
> "This round changes `coaching.html` only (card button colors). Uploading 1 file."

If more than one file, list each with its reason. If you cannot justify a
file in the list, remove it from the list.

### 2. Announce the start
Say "Uploading…" (or equivalent) before the first byte moves. This is the
narration rule — the user must never wonder whether work started.

### 3. Upload with progress narration
- Upload files one at a time (or in the smallest batches the tool allows).
- Between steps, narrate: "Uploading `coaching.html`… done. Verifying…"
- If anything takes longer than ~20 seconds, say so: "Still uploading —
  connection is slow, nothing is stuck."
- On any error: stop, report exactly what failed and which files did/didn't
  land. Do not retry blindly more than once; a repeated failure needs the
  user's input.

### 4. Verify live
Run `live-verify` on the deployed page(s): fetch fresh with cache-busting,
confirm the intended change is actually visible. Only report "live" for what
was observed.

### 5. Report plainly
End with a short, factual report:
- What was uploaded (file list)
- What was verified live (specific observations, not assumptions)
- Anything that did NOT get deployed (deferred to a later round)

## What "done" looks like

> Uploaded: `coaching.html` (1 file). Verified live: card buttons now show
> solid teal (#008080) and brick-red (#A4412F), corners square, no other
> sections affected. Desktop + mobile checked.

## Anti-patterns (learned the hard way)

- Uploading 6 files when the round changed 2 → user reads it as "stuck",
  then "stop everything immediately".
- Saying "deployed" when the FTP client returned success but the page was
  never re-fetched → the change wasn't actually live.
- Bundling "oh, and I also fixed…" into someone else's round → the client
  sees an unapproved change.
