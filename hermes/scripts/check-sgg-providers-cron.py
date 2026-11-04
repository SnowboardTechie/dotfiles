#!/usr/bin/env python3
"""The no-agent cron entry for check-sgg-providers.py: `--cron --live`.

Hermes runs a cron job's script with its own interpreter and no arguments, so this wrapper
supplies them. Install both files in ~/.hermes/scripts/.
"""

import runpy
import sys
from pathlib import Path

sys.argv = [str(Path(__file__).with_name("check-sgg-providers.py")), "--cron", "--live"]
runpy.run_path(sys.argv[0], run_name="__main__")
