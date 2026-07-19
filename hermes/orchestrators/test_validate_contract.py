from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from validate_contract import validate


VALID_CONTRACT = """# Contract

```text
/goal Complete one bounded workflow.
outcome: Produce one verified result or one concrete blocker.
verification: Independently read back the result.
constraints: Reconcile canonical state before acting.
boundaries: You may update the approved local artifact.
boundaries: Never publish, merge, or mutate infrastructure.
stop when: Authority or canonical state is incomplete.
```
"""


class ContractValidationTest(unittest.TestCase):
    def validate_text(self, text: str, *, allow_placeholders: bool = False) -> None:
        with tempfile.TemporaryDirectory(prefix="hermes-contract-test-") as directory:
            path = Path(directory) / "contract.md"
            path.write_text(text, encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                validate(path, allow_placeholders)

    def test_accepts_complete_contract(self) -> None:
        self.validate_text(VALID_CONTRACT)

    def test_rejects_missing_required_field(self) -> None:
        contract = VALID_CONTRACT.replace(
            "verification: Independently read back the result.\n", ""
        )
        with self.assertRaises(SystemExit):
            self.validate_text(contract)

    def test_rejects_wrong_field_order(self) -> None:
        contract = VALID_CONTRACT.replace(
            "outcome: Produce one verified result or one concrete blocker.\n"
            "verification: Independently read back the result.\n",
            "verification: Independently read back the result.\n"
            "outcome: Produce one verified result or one concrete blocker.\n",
        )
        with self.assertRaises(SystemExit):
            self.validate_text(contract)

    def test_requires_permission_and_prohibition(self) -> None:
        contract = VALID_CONTRACT.replace(
            "boundaries: Never publish, merge, or mutate infrastructure.\n", ""
        )
        with self.assertRaises(SystemExit):
            self.validate_text(contract)

    def test_placeholders_require_template_mode(self) -> None:
        contract = VALID_CONTRACT.replace("approved local artifact", "<artifact>")
        with self.assertRaises(SystemExit):
            self.validate_text(contract)
        self.validate_text(contract, allow_placeholders=True)


if __name__ == "__main__":
    unittest.main()
