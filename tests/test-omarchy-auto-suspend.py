#!/usr/bin/env python3
"""Regression guard for the repository-owned Omarchy auto-suspend service."""

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "omarchy/plugins/snowboardtechie.auto-suspend"
MANIFEST = json.loads((PLUGIN / "manifest.json").read_text())
SERVICE = (PLUGIN / "Service.qml").read_text()

assert MANIFEST["schemaVersion"] == 1
assert MANIFEST["id"] == "snowboardtechie.auto-suspend"
assert MANIFEST["kinds"] == ["service"]
assert MANIFEST["entryPoints"] == {"service": "Service.qml"}

# The safety contract is deliberately explicit in this small unsandboxed plugin.
assert re.search(r"suspendTimeoutSeconds:\s*45\s*\*\s*60", SERVICE)
assert 'stayAwakeDir + "/stay-awake"' in SERVICE
assert 'command: ["test", "!", "-f", root.stayAwakePath]' in SERVICE
assert "stayAwakeStateLoaded && !stayAwake" in SERVICE
assert "respectInhibitors: true" in SERVICE
assert 'command: ["systemctl", "suspend"]' in SERVICE
assert 'target: "autoSuspend"' in SERVICE

# Suspending must not be routed through a shell or bundled with unrelated actions.
assert 'command: ["bash"' not in SERVICE
assert "omarchy-system-lock" not in SERVICE

print("Omarchy auto-suspend contract: ok")
