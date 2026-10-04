---
name: skill-factory
description: "Meta-skill: build new MusePowerCore skills on demand. Activate when the user asks for a new capability ('make me a skill for X') or when a recurring workflow deserves to become a permanent skill. Scaffolds from the template, dry-run tests on a real task, installs, versions, and retires superseded skills."
metadata:
  version: "1.0"
  author: consecrating
---

# skill-factory — Build New Skills on Demand

Skills are how this system grows. When a workflow repeats twice, it earns a
skill. This skill is the assembly line: intake → scaffold → test → install →
version. A skill that isn't tested on a real task doesn't ship.

## Hard Rules

1. **No untested skills.** Every new skill gets a dry-run against a real
   task before install. A SKILL.md that has never been exercised is a draft,
   not a skill.
2. **Template first.** Always scaffold from
   `skills/skill-factory/templates/skill-template.md`. Same frontmatter,
   same section order, no improvising the structure.
3. **Frontmatter is mandatory.** `name` (kebab-case, matches directory),
   `description` (one line: what + when to activate), `metadata.version`,
   `metadata.author`.
4. **Hard rules, not suggestions.** The skill's rules section must contain
   specific, violation-recognizable rules ("never deploy a spacing guess")
   — never generic advice ("be careful with spacing").
5. **Version everything.** Each skill keeps a `CHANGELOG.md`. Bump the
   version on any shipped change.
6. **Retire, don't rot.** A superseded skill gets moved to
   `skills/_retired/<name>-<version>/` with a note saying what replaced it.
   Dead skills left active cause silent conflicts.

## Workflow

### 1. Intake
User describes capability X in plain words. Extract:
- **Trigger:** what situation activates this skill?
- **Input:** what does the agent receive?
- **Output:** what does "done" look like, concretely?
- **Failure modes:** what has gone wrong doing this manually before?

### 2. Clarify (only what's truly ambiguous)
Ask at most 2-3 short questions, and only about things that change the
skill's shape (scope, hard constraints). Never interrogate; prefer a sensible
default and note it.

### 3. Scaffold
Copy the template to `skills/<kebab-name>/SKILL.md` and fill every section:
- Frontmatter: name, description, version `1.0`, author.
- Hard Rules: 4-8 rules encoding the failure modes from intake.
- Workflow: numbered steps ending in verify + plain report.
- Worked example: one realistic end-to-end example, written concretely.
- Anti-patterns: 2-4 real failure modes with costs.

### 4. Dry-run test
Run the skill's workflow against a real (or realistic) task:
- [ ] Trigger correctly identified the situation
- [ ] Each workflow step produced its expected output
- [ ] Hard rules held (no violations needed correction)
- [ ] Verification step produced observable evidence
- [ ] Closing report was plain and complete
Fix the SKILL.md for anything that failed the dry-run. Repeat until clean.

### 5. Install
- Place the finished skill at `skills/<kebab-name>/`.
- Create `skills/<kebab-name>/CHANGELOG.md` with the 1.0 entry.
- Confirm it loads: read back the frontmatter, verify name matches
  directory, verify all template sections are present and non-empty.

### 6. Confirm
Report to the user: skill name, trigger, what it does in one line, dry-run
result, and where it lives.

## CHANGELOG.md format

```markdown
# Changelog — <skill-name>

## 1.0 — YYYY-MM-DD
- Initial release: <one-line scope>
```

## Retirement

When skill B replaces skill A:
1. `git mv skills/<a> skills/_retired/<a>-<version>/`
2. Add `RETIRED.md` inside: what replaced it, why, date.
3. Update the root README table.

## Worked example

User: "make me a skill for checking client sites for broken links after every
deploy."

1. Intake: trigger = post-deploy; input = site URL; output = broken-link
   report; failure mode = "we never checked and the client found the 404".
2. Clarify: "Crawl how deep — whole site or just changed pages?" → "Changed
   pages plus homepage/nav." (One question, then proceed.)
3. Scaffold `skills/link-patrol/SKILL.md` from the template: hard rules
   (crawl changed pages + homepage, report every 404 with the linking page,
   never silently skip external links), workflow, example, anti-patterns.
4. Dry-run on demo3.sanctify.co/coaching.html: found 0 broken, 1 slow image;
   skill's report format worked; added a rule to flag >2s assets.
5. Install + CHANGELOG 1.0. Confirm load.
6. Report: "link-patrol installed — runs after every deploy, reports 404s
   with the linking page. Dry-run clean."

## Anti-patterns

- Shipping a skill straight from the template with placeholder text → the
  dry-run exists to catch exactly this.
- Asking 8 clarifying questions for a simple skill → 2-3 max, then decide.
- Letting two skills cover the same trigger → retire one; overlap causes the
  agent to pick randomly.
- Version 1.0 forever → if the skill changed, the CHANGELOG and version
  changed with it.
