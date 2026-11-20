#!/usr/bin/env python3
"""Bump pkgver in every linux-*/PKGBUILD to the latest kernel release.

Usage:
    update-linux-versions.py [--write] [--check] [--print-latest]
                             [--track stable|mainline|longterm]
                             [--package DIR] [--root DIR] [--releases-url URL] [--force]

    Default is a dry run: report what would change, touch nothing.
    --write  apply the bump (pkgver=<latest>, pkgrel=1) to outdated packages.
    --check  exit 1 when any package is outdated (for CI gating).
"""

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path

RELEASES_URL = "https://www.kernel.org/releases.json"
DEFAULT_TRACK = "stable"


def parse_version(v):
    base, _, suffix = v.partition("-")
    nums = tuple(int(p) if p.isdigit() else p for p in base.split("."))
    return (nums, suffix == "", suffix)


def fetch_latest(track, url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "linux-builds-version-check"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.load(resp)
    if track == "stable" and data.get("latest_stable", {}).get("version"):
        version = data["latest_stable"]["version"]
        source = next(
            (r.get("source") for r in data.get("releases", []) if r.get("version") == version),
            None,
        )
        return version, source
    candidates = [
        r for r in data.get("releases", [])
        if r.get("moniker") == track and not r.get("iseol") and r.get("version")
    ]
    if not candidates:
        raise RuntimeError(f"no usable '{track}' release in {url}")
    best = max(candidates, key=lambda r: parse_version(r["version"]))
    return best["version"], best.get("source")


def tarball_url(version, source_hint):
    if source_hint:
        return source_hint
    major = version.split(".")[0]
    return f"https://cdn.kernel.org/pub/linux/kernel/v{major}.x/linux-{version}.tar.xz"


def url_exists(url, timeout=30):
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "linux-builds-version-check"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status < 400
    except Exception:
        return False


def read_pkgbuild(path):
    text = path.read_text()
    base = re.search(r"^pkgbase=(.+)$", text, re.M).group(1).strip().strip("'\"")
    m = re.search(r"^pkgver=([^\n]+)$", text, re.M)
    ver = m.group(1).strip().strip("'\"") if m else None
    if ver is not None and "$" in ver:
        ver = None  # dynamic pkgver (resolved at build time), nothing to bump
    m = re.search(r"^pkgrel=(.+)$", text, re.M)
    rel = m.group(1).strip().strip("'\"") if m else None
    return text, base, ver, rel


def bump_pkgbuild(text, newver):
    text = re.sub(r"^pkgver=.*$", f"pkgver={newver}", text, count=1, flags=re.M)
    if re.search(r"^pkgrel=.*$", text, flags=re.M):
        text = re.sub(r"^pkgrel=.*$", "pkgrel=1", text, count=1, flags=re.M)
    else:
        text = re.sub(r"^(pkgver=.*)$", r"\1\npkgrel=1", text, count=1, flags=re.M)
    return text


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="apply version bumps")
    ap.add_argument("--check", action="store_true", help="exit 1 if any package is outdated")
    ap.add_argument("--print-latest", action="store_true", help="print latest version and exit")
    ap.add_argument("--track", default=DEFAULT_TRACK, choices=["stable", "mainline", "longterm"])
    ap.add_argument("--package", default=None,
                    help="only check this package dir (e.g. linux-amdkotleni)")
    ap.add_argument("--root", default=Path(__file__).resolve().parent.parent)
    ap.add_argument("--releases-url", default=RELEASES_URL)
    ap.add_argument("--force", action="store_true", help="skip tarball existence check")
    args = ap.parse_args()

    root = Path(args.root)
    try:
        latest, source = fetch_latest(args.track, args.releases_url)
    except Exception as e:
        print(f"error: cannot determine latest {args.track}: {e}", file=sys.stderr)
        return 2
    print(f"latest {args.track}: {latest}")
    if args.print_latest:
        print(latest)
        return 0

    if "-" in latest and not args.force:
        print(f"warning: '{latest}' is a pre-release; PKGBUILD tarball URL won't match, skipping", file=sys.stderr)
        return 0 if not args.check else 1

    if not args.force:
        url = tarball_url(latest, source)
        if not url_exists(url):
            print(f"warning: tarball not reachable ({url}), skipping", file=sys.stderr)
            return 0
        print(f"tarball ok: {url}")

    if args.package:
        cand = Path(args.package)
        cand = cand if cand.is_absolute() else root / cand
        pb = cand if cand.name == "PKGBUILD" else cand / "PKGBUILD"
        pkgbuilds = [pb] if pb.is_file() else []
        if not pkgbuilds:
            print(f"error: no PKGBUILD in {cand}", file=sys.stderr)
            return 2
    else:
        pkgbuilds = sorted(root.glob("linux-*/PKGBUILD"))
        if not pkgbuilds:
            print("error: no linux-*/PKGBUILD found", file=sys.stderr)
            return 2

    outdated = []
    for pb in pkgbuilds:
        text, base, ver, _rel = read_pkgbuild(pb)
        if ver is None:
            print(f"{base}: dynamic pkgver (resolved at build time), skipping")
            continue
        if parse_version(ver) >= parse_version(latest):
            print(f"{base}: {ver} (up to date)")
            continue
        outdated.append((pb, base, ver))
        if args.write:
            pb.write_text(bump_pkgbuild(text, latest))
            print(f"{base}: {ver} -> {latest} (updated)")
        else:
            print(f"{base}: {ver} -> {latest} (would update)")

    if outdated and args.check:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
