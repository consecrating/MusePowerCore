#!/usr/bin/env python3
"""
ftp-deploy — loud, safe, changed-files-only FTP deploys.

Fixes the four classic FTP pains:
  1. SILENT   -> every file is announced as it uploads; nothing happens quietly.
  2. SLOW     -> sha256 manifest: only new/changed files are uploaded.
  3. NERVOUS  -> --dry-run prints the full plan first; --prune needs --yes.
  4. UNVERIFIED-> remote SIZE is checked after every upload; mismatches fail loudly.

Connection model matches the proven Sanctify pattern: explicit FTPS
(FTP_TLS + auth() + prot_p() + passive mode) to hosts like ftp.sanctify.co.

Credentials (in priority order): --password flag, FTP_PASSWORD env var,
or a secure interactive prompt. They are NEVER written to disk by this tool.

Exit codes: 0 = clean deploy, 1 = failures, 2 = dry-run (plan only).

Stdlib only: ftplib, hashlib, json, argparse, getpass, os, sys, time.
"""

import argparse
import getpass
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from ftplib import FTP, FTP_TLS, error_temp, error_perm
from pathlib import Path

MANIFEST_NAME = ".ftp-deploy-manifest.json"
BACKUP_ROOT = ".ftp-deploy/backups"
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".ftp-deploy", ".venv", "venv"}

# Network-level failures worth retrying. error_perm (5xx) is permanent and
# fails fast — e.g. SIZE on a missing file, permission denied.
TRANSIENT = (error_temp, TimeoutError, ConnectionError, EOFError)


# --------------------------------------------------------------------------- #
# Small utilities
# --------------------------------------------------------------------------- #

def human(n):
    """1_048_576 -> '1.0 MB'."""
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{n} B"
        n /= 1024


def utc_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def remote_join(base, rel):
    """'/'+base+'/'+rel with no doubled slashes. rel is posix-style."""
    parts = [p for p in (base.strip("/"), rel.strip("/")) if p]
    return "/" + "/".join(parts)


# --------------------------------------------------------------------------- #
# FTP session with reconnect + retry
# --------------------------------------------------------------------------- #

class FTPSession:
    """One logical FTP connection; transparently reconnects on transient errors."""

    def __init__(self, host, port=21, user="", password="", use_tls=True, timeout=20):
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.use_tls = use_tls
        self.timeout = timeout
        self._ftps = None

    def _open(self):
        self.close()
        if self.use_tls:
            ftps = FTP_TLS()
            ftps.connect(self.host, self.port, timeout=self.timeout)
            ftps.auth()        # upgrade control channel to TLS (explicit FTPS)
            ftps.prot_p()      # encrypt data channel too
        else:
            ftps = FTP()
            ftps.connect(self.host, self.port, timeout=self.timeout)
        ftps.login(self.user, self.password)
        ftps.set_pasv(True)    # passive mode: client opens data ports (firewall-friendly)
        self._ftps = ftps
        return ftps

    def close(self):
        if self._ftps is not None:
            try:
                self._ftps.quit()
            except Exception:
                pass
            self._ftps = None

    def run(self, label, fn, attempts=3):
        """Run fn(ftps). On transient network errors: reconnect and retry
        with exponential backoff (1s, 2s). Raises RuntimeError after `attempts`."""
        delay = 1.0
        last_err = None
        for attempt in range(attempts):
            try:
                ftps = self._ftps if self._ftps is not None else self._open()
                return fn(ftps)
            except TRANSIENT as e:
                last_err = e
                self.close()  # force a fresh connection on the next attempt
                if attempt < attempts - 1:
                    print(f"  !! {label}: transient error ({type(e).__name__}: {e}); "
                          f"retrying in {delay:.0f}s...")
                    time.sleep(delay)
                    delay *= 2
        raise RuntimeError(f"{label}: failed after {attempts} attempts ({last_err})")


# --------------------------------------------------------------------------- #
# Local scan + manifest
# --------------------------------------------------------------------------- #

def scan_local(local_dir, manifest):
    """Return {rel_posix: {sha256, size, mtime}} for all deployable files.

    Optimization: if the manifest already has this path with identical size
    and mtime (1s tolerance), reuse the stored hash instead of re-hashing.
    """
    base = Path(local_dir)
    files = {}
    for root, dirs, filenames in os.walk(base):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for fn in filenames:
            if fn.startswith("."):
                continue  # dotfiles are never deployed (incl. the manifest itself)
            full = Path(root) / fn
            rel = full.relative_to(base).as_posix()
            st = full.stat()
            old = manifest.get(rel)
            if old and old.get("size") == st.st_size and abs(old.get("mtime", 0) - st.st_mtime) < 1:
                files[rel] = old
            else:
                files[rel] = {"sha256": sha256_file(full), "size": st.st_size,
                              "mtime": st.st_mtime}
    return files


def manifest_path(local_dir):
    return os.path.join(local_dir, MANIFEST_NAME)


def load_manifest(local_dir):
    p = manifest_path(local_dir)
    if os.path.isfile(p):
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except (json.JSONDecodeError, OSError):
            print(f"WARNING: manifest {p} unreadable — rebuilding from scratch.")
    return {}


def save_manifest(local_dir, manifest):
    with open(manifest_path(local_dir), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1, sort_keys=True)


def plan(local_files, manifest, prune=False):
    """Split into (to_upload, unchanged, to_delete)."""
    to_upload, unchanged = [], []
    for rel in sorted(local_files):
        info = local_files[rel]
        old = manifest.get(rel)
        if old and old.get("sha256") == info["sha256"]:
            unchanged.append(rel)
        else:
            to_upload.append((rel, info, "new" if old is None else "changed"))
    to_delete = sorted(set(manifest) - set(local_files)) if prune else []
    return to_upload, unchanged, to_delete


# --------------------------------------------------------------------------- #
# Remote operations
# --------------------------------------------------------------------------- #

def ensure_remote_dir(session, remote_dir):
    """mkdir -p over FTP; existing dirs are silently fine."""
    if remote_dir in ("/", ""):
        return

    def _mk(ftps):
        parts = [p for p in remote_dir.split("/") if p]
        cur = ""
        for part in parts:
            cur += "/" + part
            try:
                ftps.mkd(cur)
            except error_perm:
                pass  # already exists (or no permission — upload will surface it)

    session.run(f"MKD {remote_dir}", _mk)


def remote_size(session, remote_path):
    """Remote file size in bytes, or None if the file does not exist."""
    try:
        return session.run(f"SIZE {remote_path}", lambda ftps: ftps.size(remote_path),
                           attempts=1)
    except (error_perm, RuntimeError):
        return None


def upload_and_verify(session, local_path, remote_path):
    """Upload one file; verify with remote SIZE. Returns (ok, remote_bytes)."""
    size_local = os.path.getsize(local_path)

    def _stor(ftps):
        with open(local_path, "rb") as f:  # reopened per attempt so retries start at 0
            ftps.storbinary(f"STOR {remote_path}", f)

    session.run(f"STOR {remote_path}", _stor)
    rsize = remote_size(session, remote_path)
    return (rsize == size_local), rsize


def backup_remote_file(session, remote_path, backup_dir):
    """Download the CURRENT remote file before we overwrite it. Returns True if
    a backup was taken (False when the remote file doesn't exist = new file)."""
    if remote_size(session, remote_path) is None:
        return False
    dest = os.path.join(backup_dir, remote_path.lstrip("/"))
    os.makedirs(os.path.dirname(dest), exist_ok=True)

    def _retr(ftps):
        with open(dest, "wb") as f:
            ftps.retrbinary(f"RETR {remote_path}", f.write)

    session.run(f"RETR {remote_path} (backup)", _retr)
    return True


# --------------------------------------------------------------------------- #
# Deploy / rollback
# --------------------------------------------------------------------------- #

def do_deploy(session, local_dir, remote_base, to_upload, to_delete, manifest, local_files):
    """Execute the plan loudly. Returns (uploaded, failed, pruned)."""
    stamp = utc_stamp()
    backup_dir = os.path.join(local_dir, BACKUP_ROOT, stamp)
    index = {"created_utc": stamp, "remote_base": remote_base, "files": []}

    uploaded, failed, pruned = 0, 0, 0
    total = len(to_upload)

    for i, (rel, info, kind) in enumerate(to_upload, 1):
        local_path = os.path.join(local_dir, rel)
        remote_path = remote_join(remote_base, rel)
        tag = "NEW" if kind == "new" else "CHG"
        print(f"[{i}/{total}] UPLOAD {rel} ({human(info['size'])}) [{tag}] ... ", end="",
              flush=True)

        # Rollback safety: back up the current remote copy before overwriting.
        if backup_remote_file(session, remote_path, backup_dir):
            index["files"].append({"backup": rel, "remote": remote_path})
        ensure_remote_dir(session, os.path.dirname(remote_path) or "/")

        ok, rsize = upload_and_verify(session, local_path, remote_path)
        if ok:
            uploaded += 1
            manifest[rel] = info
            print(f"OK (verified {rsize} bytes)")
        else:
            failed += 1
            print(f"FAILED (size mismatch: local {info['size']} vs remote {rsize})")

    if index["files"]:
        with open(os.path.join(backup_dir, "index.json"), "w", encoding="utf-8") as f:
            json.dump(index, f, indent=1)
        print(f"Backed up {len(index['files'])} overwritten file(s) -> "
              f".ftp-deploy/backups/{stamp}/")

    for rel in to_delete:
        remote_path = remote_join(remote_base, rel)
        print(f"PRUNE  {rel} ... ", end="", flush=True)
        try:
            session.run(f"DELE {remote_path}", lambda ftps: ftps.delete(remote_path),
                        attempts=1)
            manifest.pop(rel, None)
            pruned += 1
            print("deleted")
        except Exception as e:
            failed += 1
            print(f"FAILED ({e})")

    return uploaded, failed, pruned


def list_backups(local_dir):
    root = os.path.join(local_dir, BACKUP_ROOT)
    if not os.path.isdir(root):
        print("No backups found.")
        return []
    out = []
    for ts in sorted(os.listdir(root)):
        idx = os.path.join(root, ts, "index.json")
        n = 0
        if os.path.isfile(idx):
            try:
                n = len(json.load(open(idx, encoding="utf-8"))["files"])
            except (json.JSONDecodeError, OSError, KeyError):
                pass
        print(f"  {ts}  ({n} file(s))")
        out.append(ts)
    return out


def do_rollback(session, local_dir, timestamp):
    """Re-upload a backup set, verifying each file."""
    bdir = os.path.join(local_dir, BACKUP_ROOT, timestamp)
    idx = os.path.join(bdir, "index.json")
    if not os.path.isfile(idx):
        print(f"ERROR: no backup set '{timestamp}'. Available:")
        list_backups(local_dir)
        return 1
    with open(idx, encoding="utf-8") as f:
        index = json.load(f)
    files = index["files"]
    ok_n, fail_n = 0, 0
    for i, entry in enumerate(files, 1):
        local_path = os.path.join(bdir, entry["backup"])
        remote_path = entry["remote"]
        print(f"[{i}/{len(files)}] RESTORE {entry['backup']} -> {remote_path} ... ",
              end="", flush=True)
        ok, rsize = upload_and_verify(session, local_path, remote_path)
        if ok:
            ok_n += 1
            print(f"OK (verified {rsize} bytes)")
        else:
            fail_n += 1
            print("FAILED")
    print(f"Rollback {timestamp}: {ok_n} restored, {fail_n} failed.")
    return 0 if fail_n == 0 else 1


# --------------------------------------------------------------------------- #
# Config + CLI
# --------------------------------------------------------------------------- #

def load_config_file(path):
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError("config file must contain a JSON object")
    return data


def resolve_password(args):
    if args.password:
        return args.password
    env = os.environ.get("FTP_PASSWORD")
    if env:
        return env
    try:
        pw = getpass.getpass(f"FTP password for {args.user}@{args.host}: ")
    except Exception:
        pw = input(f"FTP password for {args.user}@{args.host} (visible): ")
    if not pw:
        print("ERROR: empty password.", file=sys.stderr)
        sys.exit(1)
    return pw


def build_parser():
    p = argparse.ArgumentParser(
        description="Loud, safe, changed-files-only FTP deploys (explicit FTPS).")
    p.add_argument("--host", help="FTP host, e.g. ftp.sanctify.co")
    p.add_argument("--port", type=int, default=21)
    p.add_argument("--user", help="FTP username")
    p.add_argument("--password", help="FTP password (prefer FTP_PASSWORD env or prompt)")
    p.add_argument("--local", help="Local site directory to deploy")
    p.add_argument("--remote", default="/", help="Remote base directory (default /)")
    p.add_argument("--config", help="JSON config file (host/user/port/local/remote)")
    p.add_argument("--no-tls", action="store_true",
                   help="Use plain FTP instead of explicit FTPS (not recommended)")
    p.add_argument("--dry-run", action="store_true",
                   help="Print the full plan and change nothing (exit 2)")
    p.add_argument("--prune", action="store_true",
                   help="Delete remote files missing locally (requires --yes)")
    p.add_argument("--yes", action="store_true",
                   help="Confirm destructive actions (prune deletions)")
    p.add_argument("--rollback", metavar="TIMESTAMP",
                   help="Restore a backup set, e.g. --rollback 20261005-031500")
    p.add_argument("--list-backups", action="store_true",
                   help="List available rollback backup sets and exit")
    return p


def print_plan(to_upload, unchanged, to_delete):
    print("DRY RUN — no changes will be made.\n")
    print(f"UPLOAD ({len(to_upload)}):")
    for rel, info, kind in to_upload:
        print(f"  + {rel} ({human(info['size'])}) [{kind}]")
    if not to_upload:
        print("  (none — everything up to date)")
    print(f"\nSKIP unchanged ({len(unchanged)})")
    if to_delete:
        print(f"\nDELETE ({len(to_delete)}) [--prune]:")
        for rel in to_delete:
            print(f"  - {rel}")
    print()


def main(argv=None):
    args = build_parser().parse_args(argv)

    # Config file fills any value the CLI didn't set explicitly.
    # (Explicit CLI flags always win; argparse defaults are just placeholders.)
    if args.config:
        cfg = load_config_file(args.config)
        if not args.host and cfg.get("host"):
            args.host = cfg["host"]
        if not args.user and cfg.get("user"):
            args.user = cfg["user"]
        if not args.local and cfg.get("local"):
            args.local = cfg["local"]
        if cfg.get("port") and args.port == 21:
            args.port = cfg["port"]
        if cfg.get("remote") and args.remote == "/":
            args.remote = cfg["remote"]

    for key in ("host", "user", "local"):
        if not getattr(args, key):
            print(f"ERROR: --{key} is required (or set it in --config).", file=sys.stderr)
            return 1

    local_dir = os.path.abspath(args.local)
    if not os.path.isdir(local_dir):
        print(f"ERROR: not a directory: {local_dir}", file=sys.stderr)
        return 1

    password = resolve_password(args)
    session = FTPSession(args.host, args.port, args.user, password,
                         use_tls=not args.no_tls)

    try:
        session.run("LOGIN", lambda ftps: None)  # connect + login now, fail fast
        print(f"Connected to {args.host} as {args.user} "
              f"({'FTPS' if not args.no_tls else 'plain FTP'}).")
    except RuntimeError as e:
        print(f"ERROR: connection failed: {e}", file=sys.stderr)
        return 1

    try:
        if args.list_backups:
            list_backups(local_dir)
            return 0

        if args.rollback:
            return do_rollback(session, local_dir, args.rollback)

        manifest = load_manifest(local_dir)
        first_sync = not manifest and not os.path.isfile(manifest_path(local_dir))
        local_files = scan_local(local_dir, manifest)
        if first_sync:
            print("WARNING: no manifest found — performing one FULL sync to build "
                  "the baseline. Future runs upload only changed files.")

        to_upload, unchanged, to_delete = plan(local_files, manifest,
                                               prune=args.prune)

        if args.dry_run:
            print_plan(to_upload, unchanged, to_delete)
            if to_delete and not args.yes:
                print("NOTE: pass --prune --yes (without --dry-run) to execute deletions.")
            return 2

        if args.prune and to_delete and not args.yes:
            print("ERROR: --prune deletes remote files; re-run with --yes to confirm, "
                  "or --dry-run to preview.", file=sys.stderr)
            return 1

        if not to_upload and not to_delete:
            print(f"Nothing to do: {len(unchanged)} file(s) already in sync.")
            return 0

        t0 = time.time()
        uploaded, failed, pruned = do_deploy(session, local_dir, args.remote,
                                             to_upload, to_delete, manifest, local_files)
        save_manifest(local_dir, manifest)
        dt = time.time() - t0
        print(f"\nDone: {uploaded} uploaded, {len(unchanged)} skipped (unchanged), "
              f"{pruned} pruned, {failed} failed in {dt:.1f}s.")
        return 0 if failed == 0 else 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
