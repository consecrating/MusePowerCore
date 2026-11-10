# Changelog — ftp-first-run

## 1.0 — 2026-11-11
- Initial release: first-run FTP rescue — one 15s data-channel probe (`scripts/ftp-probe.py`), verdict table (OK / BLOCKED / AUTH-FAILED / CONTROL-UNREACHABLE / NEEDS-CREDENTIALS), browser web-FTP fallback (FTPWeb.Net, explicit FTPS), one-zip packaging, zip-layout check, size + 644/755 verification, live-verify handoff. Encodes the sandbox lesson: control channel connects, DATA channel blackholed — retrying direct FTP is the struggle, switching routes is the fix.
