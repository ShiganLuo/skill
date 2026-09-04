# .smk File Escaping Pitfalls

## Problem

Embedding complex bash commands (sed regex, awk patterns) in Python strings within .smk files is fragile. Multiple layers of escaping (Python → bash → sed) create bugs.

## Wrong approach: list-based string construction

```python
# DON'T: list joining with inline sed/awk creates escaping hell
lines = [
    f"cat {shlex.quote(fasta_in)} \\",
    "    | sed -E 's/^(\\\\S+).*/>\\\\1 \\\\1/' \\",  # WRONG: quadruple backslashes
    "    | sed -E 's/^>([0-9]+|[XY]) />chr\\\\1 /' \\",  # WRONG
]
```

Problems:
- `\\\\S` in Python source → `\\S` in string → `\\S` in bash → sed sees literal `\S` (not non-whitespace)
- Each escaping layer doubles the backslashes
- Very hard to debug — the generated script looks correct but produces wrong results

## Correct approach: triple-quoted f-string template

```python
# DO: write the bash script as a triple-quoted f-string
q = shlex.quote
script_content = f"""#!/usr/bin/env bash
set -euo pipefail

# --- Modify FASTA headers ---
cat {q(fasta_in)} \\
    | sed -E 's/^>(\\S+).*/>\\1 \\1/' \\
    | sed -E 's/^>([0-9]+|[XY]) />chr\\1 /' \\
    | sed -E 's/^>MT />chrM /' \\
    > {q(fasta_modified)}

# --- Modify GTF IDs ---
ID="(ENS(MUS)?[GTE][0-9]+)\\.([0-9]+)"
cat {q(gtf_in)} \\
    | sed -E 's/gene_id '"'"'$ID'"'"';/gene_id "\\1"; gene_version "\\3";/' \\
    > {q(gtf_modified)}
"""
with open(script_path, "w") as f:
    f.write(script_content)
```

Why this works:
- In a triple-quoted f-string, `\\S` → `\S` in the string value (two chars: backslash + S)
- When written to bash file, sed sees `\S` which is the non-whitespace character class ✓
- `\\1` → `\1` in string → sed backreference ✓
- `\\.` → `\.` in string → sed literal dot ✓

## GTF sed with shell variable expansion

The `'"'"'` trick breaks out of single quotes to expand `$ID`:

```bash
| sed -E 's/gene_id '"'"'$ID'"'"';/gene_id "\\1"; gene_version "\\3";/'
```

This concatenates: `'s/gene_id "'` (single-quoted) + `"$ID"` (double-quoted) + `'";/gene_id "\\1"; gene_version "\\3";/'` (single-quoted)

## Verification approach

After generating the script, verify key sed patterns:
```python
# Check the generated bash script has correct patterns
assert "s/^>(\\S+)" in script_content
assert "s/^>([0-9]+|[XY]) />chr\\1" in script_content
assert 'gene_id "\\1"; gene_version "\\3"' in script_content
```

Or test the Python functions directly with tempfile:
```python
from cellranger_ref import modify_fasta_headers
with tempfile.NamedTemporaryFile(mode="w", suffix=".fa") as fi:
    fi.write(">1 dna:chromosome\nACGT\n>MT dna\nACGT\n")
    fi.flush()
    modify_fasta_headers(fi.name, fi.name + ".mod")
    # Verify output headers
```

## Rule of thumb

If a rule needs to generate bash with complex regex (sed, awk, grep), put the logic in a Python script under `bin/` and call it via `params.python, params.script`. Only use inline bash for simple commands (mkdir, cp, mv).
