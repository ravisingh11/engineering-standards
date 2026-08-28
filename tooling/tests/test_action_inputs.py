from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
ACTION = ROOT / "action.yml"


def evaluate_step() -> tuple[dict[str, str], str]:
    block = ACTION.read_text(encoding="utf-8").split(
        "    - name: Evaluate attestation\n", 1
    )[1]
    env_text, run_text = block.split("      run: |\n", 1)
    environment = dict(
        re.findall(r"^        ([A-Z_]+): \$\{\{ inputs\.([^ }]+) \}\}$", env_text, re.MULTILINE)
    )
    lines = []
    for line in run_text.splitlines():
        if line and not line.startswith("        "):
            break
        lines.append(line[8:] if line else "")
    return environment, "\n".join(lines) + "\n"


class CompositeActionInputTests(unittest.TestCase):
    def test_file_inputs_are_literal_argv_not_rendered_bash(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fake_bin = root / "bin"
            fake_bin.mkdir()
            captured = root / "arguments.json"
            fake_python = fake_bin / "python3"
            fake_python.write_text(
                "#!/bin/sh\nprintf '%s\\n' \"$@\" > \"$CAPTURED_ARGUMENTS\"\n",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            sentinels = {
                name: root / f"{name}-executed"
                for name in ("profiles-file", "catalog-file", "providers-file")
            }
            inputs = {
                "policy-file": "policy.json",
                "evidence-file": "evidence.json",
                "profiles-file": f'$(touch "{sentinels["profiles-file"]}")',
                "catalog-file": f'$(touch "{sentinels["catalog-file"]}")" "quote-broken',
                "providers-file": f'$(touch "{sentinels["providers-file"]}")',
                "operation": "change",
                "revision": "abc123",
                "subject-type": "git-commit",
            }
            action_environment, script = evaluate_step()
            environment = dict(os.environ)
            environment.update(
                {
                    variable: inputs[input_name]
                    for variable, input_name in action_environment.items()
                }
            )
            environment.update(
                {
                    "PATH": f"{fake_bin}:{environment['PATH']}",
                    "CAPTURED_ARGUMENTS": str(captured),
                    "GITHUB_ACTION_PATH": str(ROOT),
                }
            )
            rendered = re.sub(
                r"\$\{\{ inputs\.([^ }]+) \}\}",
                lambda match: inputs[match.group(1)],
                script,
            )

            completed = subprocess.run(
                ["bash", "-c", rendered],
                cwd=root,
                env=environment,
                text=True,
                capture_output=True,
            )

            self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
            self.assertTrue(captured.is_file())
            arguments = captured.read_text(encoding="utf-8").splitlines()
            for option, input_name in (
                ("--profiles", "profiles-file"),
                ("--catalog", "catalog-file"),
                ("--providers", "providers-file"),
            ):
                self.assertEqual(arguments[arguments.index(option) + 1], inputs[input_name])
                self.assertFalse(sentinels[input_name].exists())


if __name__ == "__main__":
    unittest.main()
