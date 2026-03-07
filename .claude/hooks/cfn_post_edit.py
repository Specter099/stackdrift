#!/usr/bin/env python3
"""Run cfn-lint and yamllint after CloudFormation template edits."""

import json
import subprocess
import sys
from pathlib import Path


def main():
    hook_input = json.loads(sys.stdin.read())

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    if tool_name not in ["Edit", "Write"]:
        sys.exit(0)

    file_path = None
    if "file_path" in tool_input:
        file_path = Path(tool_input["file_path"])
    elif "path" in tool_input:
        file_path = Path(tool_input["path"])

    if not file_path or not file_path.exists():
        sys.exit(0)

    if file_path.suffix not in (".yaml", ".yml"):
        sys.exit(0)

    run_command(["cfn-lint", str(file_path)], "cfn-lint")
    run_command(["yamllint", "-d", "relaxed", str(file_path)], "yamllint")


def run_command(cmd, description):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            output = (result.stdout + result.stderr).strip()
            if output:
                print(f"{description}:\n{output}")
    except FileNotFoundError:
        print(f"{description}: tool not found ({cmd[0]})")
    except subprocess.TimeoutExpired:
        print(f"{description}: timed out")


if __name__ == "__main__":
    main()
