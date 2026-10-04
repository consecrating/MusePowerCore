---
name: markup-round
description: "The one-round-at-a-time client edit loop. Input: a marked-up screenshot plus the user's one-liner. Apply exactly the requested change, measure spacing/position values in the file before uploading (never deploy guesses), verify live, then ask what's next. Activate whenever the user sends a screenshot with markup or a one-line visual fix for a client site."
metadata:
  version: "1.0"
  author: consecrating
---

# markup-round — One Round at a Time

The core client-work loop: user sends a marked-up screenshot + a one-liner →
you apply exactly that → deploy → prove it live → ask what's next.

## Hard Rules

1. **One change per round.** Apply exactly what was asked. Nothing adjacent,
   nothing "improved while I was there". A second change the user didn't ask
   for is a defect, not a bonus.
2. **Measure before uploading.** If the ask names a measurement ("equal 53px
   above and below", "align with the button level"), measure both sides IN
   THE FILE before uploading. Never deploy a guess and iterate live — that
   burns rounds and trust.
3. **Superlatives are bounded targets.** "Move it left a bit", "make it
   bigger", "push it down" = take a bold but bounded step, show it live, let
   the user tune. Do NOT max it out. Overshooting ("wrong, it went too much
   down") costs more rounds than undershooting.
4. **Locked regions are sacred.** If the user said don't touch something
   ("do not edit the left side lady picture", "do not mess with the right
   text alignment"), treat it as read-only. Only touch it on an explicit new
   instruction naming that region.
5. **Duplicates are not new rounds.** If the user sends a second screenshot
   of the same fix mid-upload, keep going — it's the same round, not a new
   instruction.
6. **Follow reversals without friction.** The user may reverse direction
   freely ("reduce it" → next round "enlarge it"). Apply the new instruction
   fully. Never comment on the contradiction.
7. **Anchor on words, not just images.** A marked-up image may not render for
   you; the user's words are always the actionable part. If the image is
   unreadable, say so and work from the text.

## Workflow

### 1. Read the round
- Read the user's one-liner first — it is the spec.
- Read the screenshot markup second — it localizes the spec.
- Restate the change in one sentence to confirm understanding (only when
  genuinely ambiguous; don't interrogate a clear instruction).

### 2. Locate and edit
- Find the exact selector/region in the file.
- Make the minimal edit that satisfies the spec.
- If the spec names a measurement, measure it in the file now and record the
  values (e.g. "margin-top: 53px above, margin-bottom: 53px below — confirmed
  in file").

### 3. Deploy
- Hand the file(s) to `site-deploy`: fewest files, narrated upload.
- Do not re-edit mid-upload. If you spot something, it becomes the next round.

### 4. Verify live
- Hand off to `live-verify`. Confirm the change is actually visible.
- For positional/spacing changes, verify the measured values in the rendered
  page, not just the file.

### 5. Close the round
Every round ends with the same three things:
1. **Plain report** — what changed, in concrete terms ("button now has 53px
   space above and below, measured in file and confirmed live").
2. **Verified-live proof** — what you observed on the live page.
3. **"What's next?"** — one line, then stop. Never start the next change
   unasked.

## Worked example

User: screenshot of contact page + "the Book a Discovery Call button needs
equal space above and below — 53px."

1. Spec: `margin-top` and `margin-bottom` on the button = 53px.
2. Edit file; read back both values from the file; confirm 53px / 53px.
3. Deploy via site-deploy (1 file, narrated).
4. live-verify: button spacing renders 53px top and bottom on live page.
5. Report: "Book a Discovery Call now has 53px above and below — measured in
   the file, confirmed live. What's next?"

## Anti-patterns (learned the hard way)

- Deploying a spacing guess, getting "wrong, too far down", re-deploying 4
  times → measure first, deploy once.
- Taking "move it left" as permission to slam it to the edge → bounded step.
- Touching the photo column during a text round because it "looked off" →
  locked regions stay locked.
- Replying to a duplicate screenshot with "starting a new round" → keep going.
