#!/usr/bin/env python3
"""
ftp-probe — one-shot FTP data-channel probe for the ftp-first-run skill.

Asks the one question that decides the upload route: does the DATA channel
work from this machine, or only the control channel?

Verdicts (exactly one is printed as `VERDICT: <name>`):
  OK                  control connects, login works, LIST returns data.
  BLOCKED             control connects and login works, but the data
                      channel times out — the sandbox/host firewall is
                      blackholing PASV data ports. Do NOT retry direct
                      FTP; use the browser web-FTP route instead.
  AUTH-FAILED         login rejected (wrong user/password).
  CONTROL-UNREACHABLE port 21 does not answer at all.
  NEEDS-CREDENTIALS   no password supplied and no --control-only.

Usage:
  python3 ftp-probe.py --host ftp.example.com --control-only
  FTP_PASSWORD='...' python3 ftp-probe.py --host ftp.example.com --user 'u@example.com'
  python3 ftp-probe.py --host ftp.example.com --user 'u@example.com' --timeout 15

Stdlib only. Password comes from FTP_PASSWORD or a secure prompt —
never from a command-line argument (it would leak into shell history).
Exit codes: 0 = OK, 1 = BLOCKED, 2 = AUTH-FAILED, 3 = CONTROL-UNREACHABLE,
4 = NEEDS-CREDENTIALS / usage error.
"""

import argparse
import getpass
import os
import socket
import sys
from ftplib import FTP, FTP_TLS, error_perm

EXIT = {"OK": 0, "BLOCKED": 1, "AUTH-FAILED": 2,
        "CONTROL-UNREACHABLE": 3, "NEEDS-CREDENTIALS": 4}


def verdict(name, detail=""):
    print(f"VERDICT: {name}" + (f" — {detail}" if detail else ""))
    return EXIT[name]


def control_only(host, port, timeout):
    """TCP connect to port 21 and read the FTP banner. No login."""
    try:
        with socket.create_connection((host, port), timeout=timeout) as sock:
            sock.settimeout(timeout)
            banner = sock.recv(1024).decode("utf-8", "replace").strip()
    except (socket.timeout, TimeoutError):
        return verdict("CONTROL-UNREACHABLE",
                       f"port {port} connect timed out after {timeout}s")
    except OSError as exc:
        return verdict("CONTROL-UNREACHABLE", f"port {port}: {exc}")
    print(f"Banner: {banner}")
    return verdict("OK", "control channel answers (login not tested)")


def full_probe(host, port, user, password, use_tls, timeout):
    """Control connect + login + one LIST. The LIST is the data-channel test."""
    try:
        ftp = FTP_TLS(timeout=timeout) if use_tls else FTP(timeout=timeout)
        ftp.connect(host, port, timeout=timeout)
    except (socket.timeout, TimeoutError):
        return verdict("CONTROL-UNREACHABLE",
                       f"port {port} connect timed out after {timeout}s")
    except OSError as exc:
        return verdict("CONTROL-UNREACHABLE", f"port {port}: {exc}")

    try:
        ftp.login(user, password)
        if use_tls:
            ftp.prot_p()
        ftp.set_pasv(True)
        print("Login: OK")
    except error_perm as exc:
        ftp.close()
        return verdict("AUTH-FAILED", str(exc).strip())

    # The decisive step: a data-channel operation with a SHORT timeout.
    # On a blackholed data channel this hangs until the timeout fires.
    try:
        lines = []
        ftp.retrlines("LIST", lines.append)
        print(f"LIST: OK ({len(lines)} entries)")
    except (socket.timeout, TimeoutError, OSError) as exc:
        ftp.close()
        return verdict(
            "BLOCKED",
            f"control + login OK, but LIST (data channel) failed: {exc} "
            f"— use the browser web-FTP route")
    finally:
        try:
            ftp.quit()
        except Exception:
            ftp.close()
    return verdict("OK", "data channel works — direct FTP is usable")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Probe whether FTP data transfer works from this machine.")
    parser.add_argument("--host", required=True, help="FTP host, e.g. ftp.example.com")
    parser.add_argument("--port", type=int, default=21)
    parser.add_argument("--user", default="", help="FTP username")
    parser.add_argument("--timeout", type=int, default=15,
                        help="seconds for each step (default 15)")
    parser.add_argument("--no-tls", action="store_true",
                        help="plain FTP instead of explicit FTPS")
    parser.add_argument("--control-only", action="store_true",
                        help="only check the control channel (no login)")
    args = parser.parse_args(argv)

    if args.control_only:
        return control_only(args.host, args.port, args.timeout)

    password = os.environ.get("FTP_PASSWORD")
    if not args.user or not password:
        if not args.user:
            return verdict("NEEDS-CREDENTIALS", "no --user supplied")
        # Prompt securely only when attached to a terminal; in a
        # non-interactive run, fail cleanly instead of hanging.
        if not sys.stdin.isatty():
            return verdict("NEEDS-CREDENTIALS",
                           "set FTP_PASSWORD or run interactively")
        password = getpass.getpass(f"FTP password for {args.user}@{args.host}: ")
        if not password:
            return verdict("NEEDS-CREDENTIALS", "empty password")

    return full_probe(args.host, args.port, args.user, password,
                      use_tls=not args.no_tls, timeout=args.timeout)


if __name__ == "__main__":
    sys.exit(main())
