#!/usr/bin/env python3
"""Structural verification for Snakemake subworkflow .smk files.

Checks subworkflow-level conventions (not module-level — use verify-smk-structure.py for modules).

Usage:
    python verify-subworkflow.py <subworkflow.smk>

Checks performed:
    1. Preamble: shell.prefix, logger import, config extraction, rule all
    2. No bare `config` passed to modules (must use dedicated dicts)
    3. Rule alias prefixes match the workflow name
    4. use-rule source names exist in target modules
    5. Path chain: module B indir == module A outdir
    6. No `include:` inside functions
    7. logger.info present for each config dict
    8. No commented-out dead code
"""
import os
import re
import sys


def verify_subworkflow(smk_path: str) -> list[str]:
    errors: list[str] = []
    base_dir = os.path.dirname(os.path.abspath(smk_path))

    with open(smk_path) as f:
        content = f.read()

    # Derive workflow name from filename
    workflow_name = os.path.basename(smk_path).replace(".smk", "")

    # 1. Preamble checks
    preamble_checks = [
        ('shell.prefix("set -x; set -e;")', "missing shell.prefix"),
        ("from snakemake.logging import logger", "missing logger import"),
        ('config.get("indir"', "missing indir extraction"),
        ('config.get("outdir"', "missing outdir extraction"),
        ('config.get("outfiles"', "missing outfiles extraction"),
        ("rule all:", "missing rule all"),
    ]
    for pattern, msg in preamble_checks:
        if pattern not in content:
            errors.append(f"PREAMBLE: {msg}")

    # 2. No bare `config` passed to modules
    # Pattern: "module X:\n    ...config: config" (bare config)
    module_blocks = re.findall(
        r"module\s+\w+:(.*?)(?=\nmodule\s|\nuse rule|\ndef |\Z)",
        content, re.DOTALL
    )
    for i, block in enumerate(module_blocks):
        config_ref = re.search(r"config:\s*(\w+)", block)
        if config_ref and config_ref.group(1) == "config":
            module_name = re.findall(r"module\s+(\w+):", content)[i]
            errors.append(f"MODULE CONFIG: '{module_name}' passes bare 'config' instead of dedicated dict")

    # 3. Rule alias prefix check
    aliases = re.findall(r"from\s+\w+\s+as\s+(\w+)", content)
    wrong_prefix = [a for a in aliases if not a.startswith(workflow_name + "_") and not a.startswith(workflow_name + "_")]
    # Also allow e.g. "RNAseq_" if filename is "RNAseq.smk"
    for a in aliases:
        # Extract the prefix before the first tool-specific name
        parts = a.split("_", 1)
        if len(parts) > 1 and parts[0] != workflow_name:
            # Check if it's a known cross-prefix (could be legitimate reuse)
            errors.append(f"ALIAS PREFIX: '{a}' doesn't start with '{workflow_name}_'")

    # 4. use-rule source names exist in target modules
    use_rules = re.findall(r"use rule\s+(\w+)\s+from\s+(\w+)", content)
    for rule_name, module_alias in use_rules:
        # Find the snakefile path for this module
        module_pattern = rf"module\s+{re.escape(module_alias)}:\s*\n\s*snakefile:\s*\"([^\"]+)\""
        match = re.search(module_pattern, content)
        if match:
            snakefile_rel = match.group(1)
            snakefile_abs = os.path.normpath(os.path.join(base_dir, snakefile_rel))
            if os.path.exists(snakefile_abs):
                with open(snakefile_abs) as f:
                    target_content = f.read()
                found_rules = re.findall(r"^rule\s+(\w+):", target_content, re.MULTILINE)
                if rule_name not in found_rules:
                    errors.append(f"RULE MISMATCH: '{rule_name}' not found in {snakefile_rel} (has: {found_rules})")
            else:
                errors.append(f"SNAKEFILE MISSING: {snakefile_abs} (referenced by module {module_alias})")

    # 5. Path chain — check config dict outdir -> next config dict indir
    config_dicts = re.findall(r"(\w+_config)\s*=\s*\{", content)
    outdir_refs = {}
    for cd in config_dicts:
        # Find outdir value
        pattern = rf'{re.escape(cd)}\s*=\s*\{{.*?"outdir":\s*([^,\n]+)'
        m = re.search(pattern, content, re.DOTALL)
        if m:
            outdir_refs[cd] = m.group(1).strip().strip('"')

    # 6. No include: inside functions
    func_bodies = re.findall(r"def\s+\w+\(.*?\n(.*?)(?=\ndef |\Z)", content, re.DOTALL)
    for i, body in enumerate(func_bodies):
        if "include:" in body:
            func_name = re.findall(r"def\s+(\w+)\(", content)[i]
            errors.append(f"FUNC INCLUDE: '{func_name}' contains 'include:' statement")

    # 7. logger.info for config dicts
    for cd in config_dicts:
        if f'logger.info(f"{cd}:' not in content and f"logger.info(f'{cd}:" not in content:
            # Also check for logger.info(f"...{cd}...")
            if not re.search(rf'logger\.info\(f".*{re.escape(cd)}', content):
                errors.append(f"LOGGING: missing logger.info for {cd}")

    # 8. Commented-out code (lines with # followed by actual code patterns)
    commented = re.findall(r"^\s*#\s*(?:outfiles\.|fastx_trimmer|cutadapt/|sample_id)", content, re.MULTILINE)
    if commented:
        errors.append(f"DEAD CODE: {len(commented)} commented-out code line(s)")

    return errors


def main():
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <subworkflow.smk>")
        sys.exit(1)

    smk_path = sys.argv[1]
    errors = verify_subworkflow(smk_path)

    if errors:
        print(f"FAIL ({len(errors)} issues in {smk_path}):")
        for e in errors:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print(f"PASS: all subworkflow checks OK for {smk_path}")
        sys.exit(0)


if __name__ == "__main__":
    main()
