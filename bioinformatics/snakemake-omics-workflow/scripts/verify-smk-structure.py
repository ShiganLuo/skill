#!/usr/bin/env python3
"""Structural verification for Snakemake .smk module files.

Since .smk files are not valid Python (DSL keywords), py_compile/ast.parse
cannot be used. This script performs regex-based structural checks instead.

Usage:
    python verify-smk-structure.py <module.smk> [rule1,rule2,...]

Arguments:
    module.smk          Path to the .smk file
    rule1,rule2,...      Optional comma-separated expected rule names.
                        If omitted, checks all found rules.

Checks performed:
    1. include: "../common/common.smk" present
    2. Expected rule names exist
    3. Every rule uses run: (not pure shell:)
    4. No conda: + shell: conflict (conda: + run: is fine in Snakemake 9+)
    5. Every run: block has setup_logger, log_path=str(log), try/except, os.makedirs, log clear
    6. .json config template exists and covers all config.get() keys
    7. 3-file structure (.smk, .json, .yaml)
"""
import json
import os
import re
import sys


def verify(smk_path: str, expected_rules: list[str] | None = None) -> list[str]:
    errors: list[str] = []
    module_dir = os.path.dirname(smk_path)

    with open(smk_path) as f:
        content = f.read()

    # 1. include common.smk
    if 'include: "../common/common.smk"' not in content:
        errors.append("MISSING: include ../common/common.smk")

    # 2. Rule names
    found_rules = re.findall(r"^rule\s+(\w+):", content, re.MULTILINE)
    if expected_rules:
        for r in expected_rules:
            if r not in found_rules:
                errors.append(f"MISSING rule: {r}")

    # 3-5. Per-rule checks
    blocks = re.split(r"^rule\s+\w+:", content, flags=re.MULTILINE)[1:]
    names = found_rules
    for name, block in zip(names, blocks):
        if "run:" not in block:
            errors.append(f"'{name}': uses shell: instead of run:")
        # conda: + run: is fine in Snakemake 9+ (pitfall #19)
        # Only flag conda: + shell: as a conflict
        if "conda:" in block and "shell:" in block and "run:" not in block:
            errors.append(f"'{name}': conda: + shell: conflict — convert to run:")
        for check, msg in [
            ("setup_logger", "missing setup_logger"),
            ("os.makedirs", "missing os.makedirs"),
            ("log_path = str(log)", "missing log_path = str(log)"),
            ("open(log_path", "missing log clear (open/close)"),
        ]:
            if check not in block:
                errors.append(f"'{name}': {msg}")
        if "try:" not in block or "except" not in block:
            errors.append(f"'{name}': missing try/except")

    # 7. .json covers config.get() keys
    json_path = os.path.join(module_dir, os.path.basename(smk_path).replace(".smk", ".json"))
    if os.path.exists(json_path):
        with open(json_path) as f:
            tpl = json.load(f)
        for key in set(re.findall(r'config\.get\("(\w+)"', content)):
            if key not in tpl:
                errors.append(f"config key '{key}' missing from {os.path.basename(json_path)}")
    else:
        errors.append(f"MISSING config template: {json_path}")

    # 8. 3-file structure
    base = os.path.basename(smk_path).replace(".smk", "")
    for ext in [".smk", ".json", ".yaml"]:
        fpath = os.path.join(module_dir, base + ext)
        if not os.path.exists(fpath):
            errors.append(f"MISSING file: {base}{ext}")

    return errors


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <module.smk> [rule1,rule2,...]")
        sys.exit(1)

    smk_path = sys.argv[1]
    expected = None
    if len(sys.argv) >= 3:
        expected = [r.strip() for r in sys.argv[2].split(",")]

    errors = verify(smk_path, expected)
    if errors:
        print(f"FAIL ({len(errors)} issues):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        found = re.findall(r"^rule\s+(\w+):", open(smk_path).read(), re.MULTILINE)
        print(f"PASS: all structural checks OK")
        print(f"  Rules: {found}")
        sys.exit(0)


if __name__ == "__main__":
    main()
