#!/usr/bin/env bash
# Integration tests for scripts/reconcile-hindsight.sh.
# All writes are isolated inside temporary HOME directories, removed on exit.
# --apply's installer step is not exercised here (network); rendering,
# precondition, and check reporting are.

set -u

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RECONCILER="$REPO_ROOT/scripts/reconcile-hindsight.sh"

TESTS=0
FAILURES=0
TMP_HOMES=()

cleanup() {
    local h
    for h in "${TMP_HOMES[@]-}"; do
        [[ -n "$h" ]] || continue
        rm -rf "$h"
    done
}
trap cleanup EXIT

new_home() {
    local h
    h="$(mktemp -d "${TMPDIR:-/tmp}/hindsight-test-home-XXXXXX")"
    TMP_HOMES+=("$h")
    NEW_HOME="$h"
}

check() { # <description> <expected-substring> <output>
    TESTS=$((TESTS + 1))
    local desc="$1" want="$2" got="$3"
    if [[ "$got" == *"$want"* ]]; then
        echo "ok: $desc"
    else
        echo "FAIL: $desc"
        echo "  wanted substring: $want"
        echo "  got: $got"
        FAILURES=$((FAILURES + 1))
    fi
}

# 1. Missing bearer fails loudly and mutates nothing.
new_home
H="$NEW_HOME"
out="$(HOME="$H" "$RECONCILER" --check 2>&1 || true)"
check "missing bearer is an error" "bearer missing" "$out"
[[ -e "$H/.hindsight" ]] && { echo "FAIL: check created ~/.hindsight"; FAILURES=$((FAILURES + 1)); }

# 2. Wrong bearer mode fails.
new_home
H="$NEW_HOME"
mkdir -p "$H/.secrets/hindsight"
echo fake-token > "$H/.secrets/hindsight/api-bearer"
chmod 644 "$H/.secrets/hindsight/api-bearer"
out="$(HOME="$H" "$RECONCILER" --check 2>&1 || true)"
check "world-readable bearer is an error" "must be mode 0600" "$out"

# 3. --check reports pending render without writing.
new_home
H="$NEW_HOME"
mkdir -p "$H/.secrets/hindsight"
echo fake-token > "$H/.secrets/hindsight/api-bearer"
chmod 600 "$H/.secrets/hindsight/api-bearer"
out="$(HOME="$H" "$RECONCILER" --check 2>&1 || true)"
check "check reports pending render" "would render" "$out"
[[ -f "$H/.hindsight/coding-agent.json" ]] && { echo "FAIL: check wrote config"; FAILURES=$((FAILURES + 1)); }

# 4. Rendered config (via the same python path the reconciler uses) carries
#    the token, expands HOME, and stays valid JSON.
rendered="$(python3 - "$REPO_ROOT/hindsight/coding-agent.template.json" <<PYEOF
import json, sys
text = open(sys.argv[1], encoding="utf-8").read()
text = text.replace("{{API_TOKEN}}", "fake-token").replace("{{HOME}}", "/Users/testuser")
cfg = json.loads(text)
assert cfg["apiToken"] == "fake-token"
assert "/Users/testuser/second-brain" in cfg["mapPathToBank"]
assert cfg["mapPathToBank"]["/Users/testuser/second-brain"] == "bryan-general"
assert cfg["pageTriggerType"] == "cron"
assert cfg["autoUpdate"] is True
assert cfg["banks"]["bryan-general"]["manageBankConfig"] is False
assert "observationScopes" not in cfg["banks"]["bryan-general"]
print("render-ok")
PYEOF
)"
check "template enables upstream auto-update and protects only bryan-general bank config" "render-ok" "$rendered"

# 5. --apply restores the caller's umask after writing the mode-0600 config.
#    Otherwise a fresh ~/.cache is created without execute permission and the
#    installer's own temporary npm cache cannot be created inside it.
new_home
H="$NEW_HOME"
mkdir -p "$H/.secrets/hindsight" "$H/bin"
printf 'fake-token\n' > "$H/.secrets/hindsight/api-bearer"
chmod 600 "$H/.secrets/hindsight/api-bearer"
printf '#!/bin/sh\nexit 0\n' > "$H/bin/npx"
printf '#!/bin/sh\nprintf 200\n' > "$H/bin/curl"
chmod +x "$H/bin/npx" "$H/bin/curl"
out="$(HOME="$H" PATH="$H/bin:$PATH" "$RECONCILER" --apply 2>&1)"
status=$?
check "apply reaches the installer on a fresh home" "rendered:" "$out"
if [[ $status -ne 0 || ! -x "$H/.cache" ]]; then
    echo "FAIL: apply left a fresh ~/.cache without directory execute permission"
    FAILURES=$((FAILURES + 1))
else
    echo "ok: apply preserves usable directory permissions after secret rendering"
fi

# 6. Reconciliation installs current Coding Agents instead of restoring a stale
#    compatibility pin. The staged runtime owns subsequent supported updates.
reconciler_source="$(<"$RECONCILER")"
check "apply bootstraps Coding Agents from the current release" \
    '@vectorize-io/hindsight-coding-agents@latest' "$reconciler_source"
if [[ "$reconciler_source" == *"HINDSIGHT_CODING_AGENTS_PIN"* ]]; then
    echo "FAIL: reconciler still carries the retired compatibility pin"
    FAILURES=$((FAILURES + 1))
else
    echo "ok: retired compatibility pin is absent"
fi

echo
echo "$TESTS tests, $FAILURES failures"
exit "$((FAILURES > 0 ? 1 : 0))"
