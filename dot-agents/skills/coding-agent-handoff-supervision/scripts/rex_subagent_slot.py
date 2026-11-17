#!/usr/bin/env python3
"""The old name of rex_background_agent_slot.py.

Kept only so a launcher written before the rename (2026-11-17) keeps working while its session runs. It passes every
argument through. Delete this file once no script calls it.
"""
import os
import sys

target = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rex_background_agent_slot.py")
os.execv(sys.executable, [sys.executable, target, *sys.argv[1:]])
