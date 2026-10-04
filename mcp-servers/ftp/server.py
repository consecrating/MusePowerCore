#!/usr/bin/env python3
"""
FTP MCP server (stdio transport).

Exposes the battle-tested ftp-deploy core (../scripts/ftp-deploy/ftp_deploy.py)
as MCP tools, so an agent gets native FTP capabilities instead of shelling out.

Config from env (preferred):
    FTP_HOST, FTP_USER, FTP_PASSWORD, FTP_PORT (default 21), FTP_TLS=1 (default)
Each tool also accepts optional host/user/password overrides (less preferred —
env keeps secrets out of tool-call logs).

Every mutating tool returns structured results. Errors come back as
{"ok": false, "error": "..."} — never tracebacks.

IMPORTANT: this server speaks JSON-RPC on stdout. The imported ftp_deploy
helpers print progress to stdout, so every tool body runs inside _quiet_stdio(),
which reroutes those prints to stderr.

Requires: pip install mcp
"""

import contextlib
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "..", "..", "scripts", "ftp-deploy"))
import ftp_deploy as core  # noqa: E402  (single source of truth for FTP logic)

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ftp")


@contextlib.contextmanager
def _quiet_stdio():
    """Route helper print()s to stderr so stdout stays clean for MCP."""
    with contextlib.redirect_stdout(sys.stderr):
        yield


def _err(e):
    return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def _session(host=None, user=None, password=None):
    """Build a session from explicit overrides falling back to env."""
    host = host or os.environ.get("FTP_HOST")
    user = user or os.environ.get("FTP_USER")
    if not password:
        password = os.environ.get("FTP_PASSWORD")
    tls = os.environ.get("FTP_TLS", "1").lower() not in ("0", "false", "no")
    try:
        port = int(os.environ.get("FTP_PORT", "21"))
    except ValueError:
        port = 21
    missing = [k for k, v in (("FTP_HOST", host), ("FTP_USER", user),
                              ("FTP_PASSWORD", password)) if not v]
    if missing:
        raise ValueError(
            f"missing credentials: {', '.join(missing)} — set "
            "FTP_HOST/FTP_USER/FTP_PASSWORD env vars or pass overrides")
    return core.FTPSession(host, port, user, password, use_tls=tls)


def _parse_mdtm(raw):
    """'213 20261005031500' -> ISO-ish '2026-10-05T03:15:00Z', else None."""
    try:
        digits = raw.strip().split()[-1]
        return f"{digits[0:4]}-{digits[4:6]}-{digits[6:8]}T{digits[8:10]}:{digits[10:12]}:{digits[12:14]}Z"
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Read tools
# --------------------------------------------------------------------------- #

@mcp.tool()
def ftp_list(path: str = "/", host: str = "", user: str = "", password: str = "") -> list:
    """List a remote directory. Returns [{name, size, mtime, is_dir}].
    Uses MLSD when the server supports it, falls back to NLST+SIZE/MDTM probes."""
    try:
        with _quiet_stdio():
            s = _session(host or None, user or None, password or None)
            try:
                def _ls(ftps):
                    try:
                        entries = []
                        for name, facts in ftps.mlsd(path):
                            if name in (".", ".."):
                                continue
                            entries.append({
                                "name": name,
                                "size": int(facts["size"]) if facts.get("size") else None,
                                "mtime": _parse_mdtm("213 " + facts["modify"]) if facts.get("modify") else None,
                                "is_dir": facts.get("type") == "dir",
                            })
                        return entries
                    except Exception:
                        # Fallback for servers without MLSD.
                        entries = []
                        for name in ftps.nlst(path):
                            base = name.rsplit("/", 1)[-1]
                            if base in (".", ".."):
                                continue
                            rp = path.rstrip("/") + "/" + base
                            try:
                                size = ftps.size(rp)
                                is_dir = False
                            except Exception:
                                size, is_dir = None, True
                            mtime = None
                            try:
                                mtime = _parse_mdtm(ftps.sendcmd(f"MDTM {rp}"))
                            except Exception:
                                pass
                            entries.append({"name": base, "size": size,
                                            "mtime": mtime, "is_dir": is_dir})
                        return entries

                return s.run(f"LIST {path}", _ls)
            finally:
                s.close()
    except Exception as e:
        return _err(e)


@mcp.tool()
def ftp_diff(local_dir: str, remote_dir: str = "/",
             manifest_name: str = ".ftp-deploy-manifest.json") -> dict:
    """Compare a local dir against the deploy manifest: what WOULD upload.
    Returns {upload:[{path, bytes, kind}], skip_unchanged:n, missing_local:[...]}.
    missing_local = files in the manifest whose local copy is gone (prune candidates)."""
    try:
        with _quiet_stdio():
            if not os.path.isdir(local_dir):
                return {"ok": False, "error": f"not a directory: {local_dir}"}
            old = core.MANIFEST_NAME
            core.MANIFEST_NAME = manifest_name
            try:
                manifest = core.load_manifest(local_dir)
                local_files = core.scan_local(local_dir, manifest)
            finally:
                core.MANIFEST_NAME = old
            to_upload, unchanged, _ = core.plan(local_files, manifest, prune=False)
            missing = sorted(set(manifest) - set(local_files))
            return {"ok": True, "remote_dir": remote_dir,
                    "upload": [{"path": r, "bytes": i["size"], "kind": k}
                               for r, i, k in to_upload],
                    "skip_unchanged": len(unchanged),
                    "missing_local": missing}
    except Exception as e:
        return _err(e)


@mcp.tool()
def ftp_list_backups(local_dir: str) -> dict:
    """List rollback backup sets for a local dir: {backups:[{timestamp, files}]}."""
    try:
        root = os.path.join(local_dir, core.BACKUP_ROOT)
        out = []
        if os.path.isdir(root):
            for ts in sorted(os.listdir(root)):
                n = 0
                idx = os.path.join(root, ts, "index.json")
                if os.path.isfile(idx):
                    try:
                        n = len(json.load(open(idx, encoding="utf-8"))["files"])
                    except Exception:
                        pass
                out.append({"timestamp": ts, "files": n})
        return {"ok": True, "backups": out}
    except Exception as e:
        return _err(e)


# --------------------------------------------------------------------------- #
# Write tools
# --------------------------------------------------------------------------- #

@mcp.tool()
def ftp_upload(local_path: str, remote_path: str,
               host: str = "", user: str = "", password: str = "") -> dict:
    """Upload one file and verify via remote SIZE. Returns {ok, bytes, verified_size}."""
    try:
        with _quiet_stdio():
            if not os.path.isfile(local_path):
                return {"ok": False, "error": f"local file not found: {local_path}"}
            s = _session(host or None, user or None, password or None)
            try:
                core.ensure_remote_dir(s, os.path.dirname(remote_path) or "/")
                ok, rsize = core.upload_and_verify(s, local_path, remote_path)
                res = {"ok": ok, "bytes": os.path.getsize(local_path),
                       "verified_size": rsize}
                if not ok:
                    res["error"] = (f"size mismatch: local {res['bytes']} "
                                    f"vs remote {rsize}")
                return res
            finally:
                s.close()
    except Exception as e:
        return _err(e)


@mcp.tool()
def ftp_download(remote_path: str, local_path: str,
                 host: str = "", user: str = "", password: str = "") -> dict:
    """Download one remote file. Returns {ok, bytes}."""
    try:
        with _quiet_stdio():
            s = _session(host or None, user or None, password or None)
            try:
                parent = os.path.dirname(os.path.abspath(local_path))
                os.makedirs(parent, exist_ok=True)

                def _retr(ftps):
                    with open(local_path, "wb") as f:
                        ftps.retrbinary(f"RETR {remote_path}", f.write)

                s.run(f"RETR {remote_path}", _retr)
                return {"ok": True, "bytes": os.path.getsize(local_path)}
            finally:
                s.close()
    except Exception as e:
        return _err(e)


@mcp.tool()
def ftp_mkdir(path: str, host: str = "", user: str = "", password: str = "") -> dict:
    """Create a remote directory (mkdir -p; existing dirs are fine)."""
    try:
        with _quiet_stdio():
            s = _session(host or None, user or None, password or None)
            try:
                core.ensure_remote_dir(s, path)
                return {"ok": True, "path": path}
            finally:
                s.close()
    except Exception as e:
        return _err(e)


@mcp.tool()
def ftp_delete(path: str, host: str = "", user: str = "", password: str = "") -> dict:
    """Delete one remote file. There is no undo — prefer ftp_deploy's backups."""
    try:
        with _quiet_stdio():
            s = _session(host or None, user or None, password or None)
            try:
                s.run(f"DELE {path}", lambda ftps: ftps.delete(path), attempts=1)
                return {"ok": True, "path": path}
            finally:
                s.close()
    except Exception as e:
        return _err(e)


@mcp.tool()
def ftp_rename(from_path: str, to_path: str,
               host: str = "", user: str = "", password: str = "") -> dict:
    """Rename / move a remote file."""
    try:
        with _quiet_stdio():
            s = _session(host or None, user or None, password or None)
            try:
                s.run(f"RNFR/RNTO {from_path}",
                      lambda ftps: ftps.rename(from_path, to_path), attempts=1)
                return {"ok": True, "from": from_path, "to": to_path}
            finally:
                s.close()
    except Exception as e:
        return _err(e)


@mcp.tool()
def ftp_deploy(local_dir: str, remote_dir: str = "/", dry_run: bool = True,
               host: str = "", user: str = "", password: str = "") -> dict:
    """Changed-files-only deploy (the tool the site-deploy skill should prefer).
    dry_run=True (default) returns the plan without changing anything.
    dry_run=False uploads new/changed files, backs up overwritten remote copies
    to .ftp-deploy/backups/<timestamp>/, verifies every upload via remote SIZE,
    and updates the manifest. Returns per-file results as structured JSON."""
    try:
        with _quiet_stdio():
            if not os.path.isdir(local_dir):
                return {"ok": False, "error": f"not a directory: {local_dir}"}
            # Planning is manifest-based and needs no connection.
            manifest = core.load_manifest(local_dir)
            local_files = core.scan_local(local_dir, manifest)
            to_upload, unchanged, _ = core.plan(local_files, manifest, prune=False)
            plan_list = [{"path": r, "bytes": i["size"], "kind": k}
                         for r, i, k in to_upload]
            if dry_run:
                return {"ok": True, "dry_run": True, "remote_dir": remote_dir,
                        "upload": plan_list, "skip_unchanged": len(unchanged)}
            s = _session(host or None, user or None, password or None)
            try:
                stamp = core.utc_stamp()
                backup_dir = os.path.join(local_dir, core.BACKUP_ROOT, stamp)
                index = {"created_utc": stamp, "remote_base": remote_dir, "files": []}
                results = []
                for rel, info, kind in to_upload:
                    rp = core.remote_join(remote_dir, rel)
                    entry = {"path": rel, "bytes": info["size"], "kind": kind}
                    try:
                        if core.backup_remote_file(s, rp, backup_dir):
                            index["files"].append({"backup": rel, "remote": rp})
                        core.ensure_remote_dir(s, os.path.dirname(rp) or "/")
                        ok, rsize = core.upload_and_verify(
                            s, os.path.join(local_dir, rel), rp)
                        entry["ok"] = ok
                        entry["verified_size"] = rsize
                        if ok:
                            manifest[rel] = info
                        else:
                            entry["error"] = (f"size mismatch: local {info['size']} "
                                              f"vs remote {rsize}")
                    except Exception as e:
                        entry["ok"] = False
                        entry["error"] = f"{type(e).__name__}: {e}"
                    results.append(entry)

                if index["files"]:
                    os.makedirs(backup_dir, exist_ok=True)
                    with open(os.path.join(backup_dir, "index.json"), "w",
                              encoding="utf-8") as f:
                        json.dump(index, f, indent=1)
                core.save_manifest(local_dir, manifest)
                failed = sum(1 for r in results if not r.get("ok"))
                return {"ok": failed == 0, "dry_run": False, "remote_dir": remote_dir,
                        "backup": stamp if index["files"] else None,
                        "uploaded": sum(1 for r in results if r.get("ok")),
                        "failed": failed, "skip_unchanged": len(unchanged),
                        "files": results}
            finally:
                s.close()
    except Exception as e:
        return _err(e)


@mcp.tool()
def ftp_rollback(local_dir: str, timestamp: str,
                 host: str = "", user: str = "", password: str = "") -> dict:
    """Restore a backup set (see ftp_list_backups). Re-uploads + verifies each file."""
    try:
        with _quiet_stdio():
            bdir = os.path.join(local_dir, core.BACKUP_ROOT, timestamp)
            idx = os.path.join(bdir, "index.json")
            if not os.path.isfile(idx):
                return {"ok": False,
                        "error": f"no backup set '{timestamp}' under {local_dir}"}
            with open(idx, encoding="utf-8") as f:
                files = json.load(f)["files"]
            s = _session(host or None, user or None, password or None)
            try:
                results = []
                for entry in files:
                    lp = os.path.join(bdir, entry["backup"])
                    rp = entry["remote"]
                    rec = {"path": entry["backup"], "remote": rp}
                    try:
                        ok, rsize = core.upload_and_verify(s, lp, rp)
                        rec.update({"ok": ok, "verified_size": rsize})
                        if not ok:
                            rec["error"] = "size mismatch after restore"
                    except Exception as e:
                        rec.update({"ok": False,
                                    "error": f"{type(e).__name__}: {e}"})
                    results.append(rec)
                failed = sum(1 for r in results if not r.get("ok"))
                return {"ok": failed == 0, "timestamp": timestamp,
                        "restored": sum(1 for r in results if r.get("ok")),
                        "failed": failed, "files": results}
            finally:
                s.close()
    except Exception as e:
        return _err(e)


if __name__ == "__main__":
    mcp.run(transport="stdio")
