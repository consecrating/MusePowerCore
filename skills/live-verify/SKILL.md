---
name: live-verify
description: "Post-deploy verification for client-site changes. Fetch the page fresh with cache-busting, screenshot the affected region, and confirm the intended change is actually live before reporting it. Activate after every deploy or edit round — never say 'live' or 'verified' without observed evidence."
metadata:
  version: "1.0"
  author: consecrating
---

# live-verify — Prove It's Live

Upload success is not done. A change is "live" only when you have observed it
on the real page. This skill is the evidence gate every deploy passes through.

## Hard Rules

1. **Fetch fresh, always.** Bypass cache: hard refresh, cache-busting query
   params, or a fresh session. A cached copy "verifying" your change is a lie
   you tell yourself.
2. **Observe, don't infer.** Screenshot the affected region and look at it.
   "The upload succeeded so it must be live" is never verification.
3. **"Verified" requires evidence.** Use the words "live" / "verified" only
   for what you actually saw in the fetched page/screenshot. Everything else
   is "uploaded, not yet confirmed".
4. **Check for collateral damage.** Every verification includes a scan of the
   surrounding sections. A fix that breaks something else is a failed round.
5. **Spot-check mobile when layout was touched.** Any positional, spacing, or
   structural change gets a mobile-viewport check.

## Verification Checklist (per change type)

- [ ] **Content/text** — exact wording, spelling, line breaks match the spec
- [ ] **Position** — element is where the round asked it to be (left/right/
      centered, aligned with the named reference element)
- [ ] **Spacing** — measured values in the rendered page match the spec
      (e.g. 53px above and below — measure in the screenshot, not just the file)
- [ ] **Colors** — hex values render as specified (brand colors, button
      solids, accent letters)
- [ ] **Typography** — font family, weight, size, alignment as specified
- [ ] **No collateral damage** — sections above/below and adjacent elements
      unchanged; locked regions (photos, protected columns) untouched
- [ ] **Mobile viewport** — (when layout touched) no overflow, no overlap,
      no broken stacking at 390px width

## Workflow

### 1. Fetch
Load the target URL fresh (cache-busted). Note the exact URL and timestamp —
that is your evidence basis.

### 2. Capture
Screenshot the affected region at desktop width. If layout was touched, also
capture at 390px mobile width.

### 3. Compare against the spec
Walk the checklist above against what the round asked for. For measurements,
measure in the rendered output.

### 4. Report
- **Pass:** state exactly what was observed per checklist item, then "verified
  live".
- **Fail:** follow the failure protocol below. Never soften it into a pass.

## Failure Protocol

1. Say what failed, in concrete terms: "Button spacing renders 40px above /
   53px below — spec is 53px / 53px."
2. Say what you observed: the screenshot evidence, the URL, the viewport.
3. Propose the fix: the specific file edit that corrects it.
4. Do NOT re-deploy silently. The fix becomes the next round (via
   `markup-round` / `site-deploy`), with the user's go-ahead.

## Worked example

Round: coaching page card buttons → solid teal / brick-red, square corners.

Fetch `https://demo3.sanctify.co/coaching.html?cb=<ts>` fresh.
Screenshot cards section.
Checklist: buttons render solid #008080 and #A4412F ✓; border-radius 0 ✓;
button labels correct ✓; TRUE section below unchanged ✓; mobile 390px —
cards stack, no overflow ✓.
Report: "Verified live: card buttons solid teal and brick-red, square
corners, labels correct, no collateral damage, mobile clean."

## Anti-patterns (learned the hard way)

- Reporting "live" because the FTP client said success → the page had cached
  and the change wasn't visible for another hour.
- Checking only the changed element → missed that the section below it had
  shifted.
- Skipping mobile on a spacing change → the desktop fix broke the phone view
  and the client found it first.
