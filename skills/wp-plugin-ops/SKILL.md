---
name: wp-plugin-ops
description: "WordPress plugin build → zip → install → activate → verify flow. Activate when creating, installing, or changing a plugin on a live WordPress site (pattern: Casino Pride at www.cpofficial.in). Hard rules: ask before touching anything live, never store credentials, safe plugin conventions, verify the frontend is unaffected."
metadata:
  version: "1.0"
  author: consecrating
---

# wp-plugin-ops — WordPress Plugin Operations

Build, ship, and verify small single-purpose WordPress plugins on live client
sites (pattern: Casino Pride, www.cpofficial.in). These plugins do one thing
well — a settings toggle, a popup — with zero side effects.

## Hard Rules

1. **Ask before touching anything live.** Install, activate, deactivate, or
   settings changes on the live site need an explicit user "yes" first —
   every time, no exceptions, no "you said yes last time".
2. **Never store credentials.** WP admin / FTP passwords are transient: used
   for the authorized task, never written to memory or files. Say so out loud
   when handling them ("using the password you shared, not storing it").
3. **One plugin, one job.** Each plugin does a single thing (toggle a popup,
   show a banner). No feature creep — a second job is a second plugin.
4. **Safe defaults.** Fresh install must be inert or obviously ON-and-safe.
   Never ship a plugin whose default state breaks the frontend.
5. **No interference.** The plugin must not touch themes, other plugins, or
   core. Namespaced everything: option names, function prefixes, CSS classes.
6. **Verify the frontend is unaffected.** After activate/deactivate, load the
   homepage and confirm nothing else changed.

## Plugin Conventions

- **Settings page** under Settings → with a clear name ("Calendar Popup").
- **ON/OFF toggle** as the primary control, instant-save (AJAX, no page
  reload), with a visible saved-state confirmation.
- **Show-once / frequency options** where popups are involved (per-visit,
  always, never).
- **Media-library picker with live preview** for image-based popups; bundle a
  sane default image.
- **Cache awareness:** on toggle, attempt best-effort purges for common
  caching plugins (list which were attempted in the settings page footer —
  honesty over magic).
- **Version constant** in the plugin header and a `PLUGIN_VERSION` define;
  bump on every shipped change.

## Workflow

### 1. Build
- Scaffold: `plugin-slug/plugin-slug.php` (header), `assets/`, `README.txt`.
- Implement the single job + settings page per conventions above.
- Zip as `plugin-slug.zip` (vX.Y.Z in the filename).

### 2. Confirm before live
State exactly what will happen: "I will upload `sanctify-popup-1.0.0.zip`,
install it, and activate it on www.cpofficial.in. Nothing else changes."
Wait for the explicit yes.

### 3. Install → Activate
- Upload the zip through the WP admin plugin installer.
- Activate. Narrate each step ("Uploading…", "Activating…").

### 4. Verify
- [ ] Plugin appears in Installed Plugins as **active**, correct version.
- [ ] Settings → page loads; toggle is in the expected state.
- [ ] Toggle OFF → behavior stops (e.g. popup no longer renders); toggle ON
      → behavior resumes. Test both directions.
- [ ] Frontend homepage loads normally — no console errors, no layout shift,
      no interference with other plugins/theme.
- [ ] Settings persist across page reload (instant-save actually saved).

### 5. Report
Plain report: what was installed (name, version), toggle state verified both
directions, frontend check result, and "no themes, pages, or other plugins
were touched."

## Worked example

"Calendar Popup Switch" v1.0.0: Settings → Calendar Popup ON/OFF toggle.
ON leaves the `#cp-ov` overlay unchanged; OFF prevents the overlay from
opening and stops its iframe calendar page from loading. Verified: toggle ON
→ popup works; toggle OFF → no overlay, no iframe request; homepage clean.

## Anti-patterns

- Activating without asking because "it's just a toggle" → the rule is
  absolute: explicit yes, every time.
- Saving the admin password "for next time" → never. Transient only.
- A settings page that requires Save + page reload with no confirmation →
  instant-save with visible state.
- Forgetting the frontend check → a PHP notice broke the homepage layout and
  nobody looked until the client called.
