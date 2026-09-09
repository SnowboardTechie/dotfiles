#!/usr/bin/env python3
"""Report TypeSpec fix-release status on each scheduled workday."""

import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request


FIX = "e0f67bdf3c5a0875dfa98b475648af37caac71a6"
PR = "https://github.com/HHS/simpler-grants-protocol/pull/1093"
API = "https://api.github.com/repos/microsoft/typespec"



def fetch(url):
    request = urllib.request.Request(url, headers={"User-Agent": "sgg-typespec-fix-watch/1"})
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read(2 * 1024 * 1024 + 1)
    if len(body) > 2 * 1024 * 1024:
        raise ValueError("source response exceeded size limit")
    result = json.loads(body)
    if not isinstance(result, dict):
        raise ValueError("source response was not an object")
    return result


def ready_version():
    versions = []
    for name in ("compiler", "openapi3"):
        data = fetch(f"https://registry.npmjs.org/@typespec%2f{name}/latest")
        version = data.get("version", "")
        if data.get("name") != f"@typespec/{name}":
            raise ValueError("npm package identity mismatch")
        if data.get("repository", {}).get("url") != "git+https://github.com/microsoft/typespec.git":
            raise ValueError("unexpected npm source repository")
        if not isinstance(version, str) or not re.fullmatch(r"\d+\.\d+\.\d+", version):
            return None  # Never notify for a prerelease.
        expected = f"https://registry.npmjs.org/@typespec/{name}/-/{name}-{version}.tgz"
        if data.get("dist", {}).get("tarball") != expected:
            raise ValueError("unexpected npm release artifact")
        versions.append(version)
    if versions[0] != versions[1]:
        return None  # Wait for both packages to finish publishing.
    version = versions[0]
    tag = "typespec-stable@" + version
    try:
        release = fetch(f"{API}/releases/tags/{urllib.parse.quote(tag, safe='')}")
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None  # npm and release publication may not be simultaneous.
        raise
    if release.get("tag_name") != tag:
        raise ValueError("upstream release tag mismatch")
    if release.get("draft") is not False or release.get("prerelease") is not False:
        return None
    if not release.get("published_at"):
        return None
    comparison = fetch(f"{API}/compare/{FIX}...{urllib.parse.quote(tag, safe='')}")
    status = comparison.get("status")
    if status in ("ahead", "identical"):
        return version
    if status in ("behind", "diverged"):
        return None
    raise ValueError("unrecognized upstream commit comparison")


def main():
    try:
        version = ready_version()
        if version is None:
            print("@bryan:snowboardtechie.com PR #1093 reminder: "
                  "No qualifying stable TypeSpec fix release verified yet.\n\n"
                  "We are waiting for the upstream path-traversal fix to reach stable npm packages "
                  "rather than merging with an audit suppression. "
                  "Once available: update the PR, remove the suppressions, rerun CI/audits, and request reviews.\n"
                  f"PR: {PR}\n"
                  "Upstream fix: https://github.com/microsoft/typespec/pull/11777")
            return 0
        print(f"@bryan:snowboardtechie.com TypeSpec {version} is available on npm for both "
              "@typespec/compiler and @typespec/openapi3, and its stable release tag contains the path-traversal fix.\n\n"
              f"You can resume PR #1093: {PR}\n"
              "Update the coordinated TypeSpec dependencies at the root and in both templates, "
              "remove GHSA-2q42-4q24-7rgv from all three audit exceptions, regenerate the lockfiles, "
              "and rerun CI and audits before requesting reviews.\n\n"
              "This confirms upstream release availability, not compatibility with our repository or audit-database freshness. "
              "No PR changes or review requests were made.\n"
              f"Release: https://github.com/microsoft/typespec/releases/tag/typespec-stable@{version}\n"
              "Fix: https://github.com/microsoft/typespec/pull/11777")
        return 0
    except (OSError, ValueError, urllib.error.URLError) as exc:
        print(f"@bryan:snowboardtechie.com TypeSpec release monitor failed: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
