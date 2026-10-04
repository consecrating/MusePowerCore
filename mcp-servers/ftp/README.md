# FTP MCP server

Native FTP tools for the agent, over stdio. Instead of shelling out to the
CLI and parsing text, the agent calls tools and gets structured JSON back.
The FTP logic itself is shared with `scripts/ftp-deploy/ftp_deploy.py`
(single source of truth — this server imports it).

## Install

```bash
cd mcp-servers/ftp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt   # just: mcp
```

Then point your MCP client at it (see `mcp-config.example.json`):

```json
{
  "mcpServers": {
    "ftp": {
      "command": "/absolute/path/to/mcp-servers/ftp/.venv/bin/python",
      "args": ["/absolute/path/to/mcp-servers/ftp/server.py"],
      "env": { "FTP_HOST": "ftp.sanctify.co", "FTP_USER": "...", "FTP_TLS": "1" }
    }
  }
}
```

Credentials come from env: `FTP_HOST`, `FTP_USER`, `FTP_PASSWORD`,
`FTP_PORT` (default 21), `FTP_TLS=1` (default; `0` for plain FTP).
Every tool also accepts optional `host`/`user`/`password` overrides, but env
is preferred — overrides can end up in tool-call logs.

## Tool catalogue

| Tool | Purpose | Returns |
| ---- | ------- | ------- |
| `ftp_list(path="/")` | List a remote directory (MLSD, NLST fallback) | `[{name, size, mtime, is_dir}]` |
| `ftp_diff(local_dir, remote_dir="/")` | What *would* upload (manifest-based, no connection needed for the plan) | `{upload:[...], skip_unchanged:n, missing_local:[...]}` |
| `ftp_deploy(local_dir, remote_dir="/", dry_run=true)` | **The one the site-deploy skill should prefer.** Changed-files-only deploy with per-file results, backups, and SIZE verification | structured JSON plan/results |
| `ftp_upload(local_path, remote_path)` | Upload one file + verify | `{ok, bytes, verified_size}` |
| `ftp_download(remote_path, local_path)` | Download one file | `{ok, bytes}` |
| `ftp_mkdir(path)` | mkdir -p (idempotent) | `{ok}` |
| `ftp_delete(path)` | Delete one remote file (no undo) | `{ok}` |
| `ftp_rename(from_path, to_path)` | Rename / move a remote file | `{ok}` |
| `ftp_list_backups(local_dir)` | List rollback backup sets | `{backups:[{timestamp, files}]}` |
| `ftp_rollback(local_dir, timestamp)` | Restore a backup set, verifying each file | `{restored, failed, files}` |

Errors always come back as `{"ok": false, "error": "..."}` — never tracebacks.

Recommended agent flow: `ftp_diff` (or `ftp_deploy` with `dry_run=true`) →
show the plan → `ftp_deploy` with `dry_run=false` → done. Deletions are never
implicit; use `ftp_delete` explicitly per file.

## Security notes

- Secrets via env only. The example config deliberately has no password field —
  export `FTP_PASSWORD` in your shell (or your client's secrets store).
- The server opens a fresh FTPS connection per tool call (stateless, no
  credential caching between calls).
- Explicit FTPS by default (`FTP_TLS=1`): control + data channels encrypted,
  passive mode. Plain FTP only with `FTP_TLS=0`.
- `ftp_delete` has no undo. Overwrites via `ftp_deploy` are backed up
  automatically to `.ftp-deploy/backups/<timestamp>/`; single-file
  `ftp_upload` overwrites are not — use `ftp_download` first if it matters.
