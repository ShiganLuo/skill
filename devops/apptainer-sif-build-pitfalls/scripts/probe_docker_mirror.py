#!/usr/bin/env python3
"""Probe a list of Docker v2 registry mirrors for a given repo:tag.

Standalone version of EnvUtil.probe_registry_mirror() — usable without
the workflow checkout. Emits a ✓/✗ table with HTTP status codes so the
operator can pick a working mirror at a glance.

Usage:
    probe_docker_mirror.py [--repo REPO] [--tag TAG] [--mirror HOST ...]

Defaults probe the same 8 mirrors EnvUtil._diagnose_build_mirror uses,
for `mambaorg/micromamba:latest`. Exit code 0 if at least one mirror
resolves the manifest, 1 if none do.

Examples:
    # Default probe
    probe_docker_mirror.py

    # Probe a different image
    probe_docker_mirror.py --repo condaforge/miniforge3 --tag latest

    # Add a custom mirror
    probe_docker_mirror.py --mirror my.corp.registry --mirror other.io
"""
from __future__ import annotations

import argparse
import socket
import sys
from typing import List, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

DEFAULT_MIRRORS: List[str] = [
    "dockerproxy.net",
    "docker.1ms.run",
    "docker.m.daocloud.io",
    "dockerproxy.net",  # de-duplicated at runtime
    "docker.ketches.cn",
    "docker.mirrors.ustc.edu.cn",
    "hub-mirror.c.163.com",
    "mirror.baidubce.com",
]


def probe(mirror: str, repo: str, tag: str, timeout: float) -> Tuple[bool, str]:
    url = f"https://{mirror}/v2/{repo}/manifests/{tag}"
    req = Request(
        url,
        method="HEAD",
        headers={
            "Accept": (
                "application/vnd.docker.distribution.manifest.v2+json,"
                " application/vnd.oci.image.manifest.v1+json,"
                " application/vnd.docker.distribution.manifest.list.v2+json,"
                " application/vnd.oci.image.index.v1+json"
            ),
            "User-Agent": "probe_docker_mirror/1.0",
        },
    )
    try:
        with urlopen(req, timeout=timeout) as resp:
            return True, f"HTTP {resp.status}"
    except HTTPError as exc:
        if exc.code == 401:
            return True, f"HTTP 401 (auth required)"
        return False, f"HTTP {exc.code}: {exc.reason}"
    except (URLError, socket.timeout, TimeoutError) as exc:
        return False, f"{type(exc).__name__}: {exc}"
    except Exception as exc:  # noqa: BLE001
        return False, f"{type(exc).__name__}: {exc}"


def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Probe Docker v2 registry mirrors for repo:tag"
    )
    parser.add_argument("--repo", default="mambaorg/micromamba",
                        help="Repo path (default: mambaorg/micromamba)")
    parser.add_argument("--tag", default="latest",
                        help="Image tag (default: latest)")
    parser.add_argument("--mirror", action="append", default=[],
                        help="Extra mirror to probe (repeatable)")
    parser.add_argument("--timeout", type=float, default=6.0,
                        help="Per-mirror timeout in seconds (default: 6)")
    args = parser.parse_args(argv)

    # De-duplicate while preserving order.
    seen = set()
    mirrors: List[str] = []
    for m in DEFAULT_MIRRORS + args.mirror:
        if m not in seen:
            seen.add(m)
            mirrors.append(m)

    print(f"Probing {len(mirrors)} mirrors for {args.repo}:{args.tag} "
          f"(timeout {args.timeout}s each)")

    working: List[str] = []
    for mirror in mirrors:
        ok, detail = probe(mirror, args.repo, args.tag, args.timeout)
        marker = "✓" if ok else "✗"
        print(f"  {marker} {mirror:<35} {detail}")
        if ok:
            working.append(mirror)

    print()
    if working:
        print(f"Working mirrors: {', '.join(working)}")
        print(f"Recommended for FROM: {working[0]}/{args.repo}:{args.tag}")
        return 0
    print("NO working mirror found. Check network/proxy.")
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
