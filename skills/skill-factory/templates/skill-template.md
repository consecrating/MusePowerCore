---
name: skill-template
description: "Template for authoring a new MusePowerCore skill. Used by the skill-factory skill when scaffolding skills/<name>/SKILL.md."
metadata:
  version: "1.0"
  author: consecrating
---

# <Skill Name> — <one-line purpose>

<2-3 sentences: what this skill does, when it activates, what "good" looks
like. Write for a future agent session that has never seen this skill before.>

## Hard Rules

<Numbered, non-negotiable rules. Each rule must be specific enough that a
violation is recognizable. Prefer "never/always/must" over "should/consider".
Encode real failure modes here, not generic advice.>

1. **<Rule name>.** <Precise statement, with the concrete behavior.>
2. **<Rule name>.** <Precise statement.>

## Workflow

### 1. <Step name>
<What to do, what to say to the user, what to check before proceeding.>

### 2. <Step name>
<Continue the sequence. Every workflow ends with verification + a plain
report, never with an assumption.>

### 3. Verify
<How to confirm the work actually landed: what to observe, what counts as
evidence, what "verified" requires. Reference live-verify where relevant.>

### 4. Report
<What the closing report contains: what changed, what was verified, what was
deferred. End with the next question or handoff, not silence.>

## Worked example

<One concrete, realistic example: the input, the steps taken, the exact
closing report. No placeholders — write it as if it already happened.>

## Anti-patterns

<2-4 real failure modes this skill exists to prevent, phrased as
"X happened → the cost was Y → this skill does Z instead." Generic filler
("don't rush", "be careful") is not allowed here.>
