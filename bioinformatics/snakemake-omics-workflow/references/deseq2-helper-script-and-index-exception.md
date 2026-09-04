# DESeq2 helper-script and bowtie2-index failure notes

## 1) DESeq2 helper script must not import `snakemake`

Observed failure:
- `modules/DESeq2/bin/write_group_tsv.py` used `from snakemake import config`
- When executed via `python script.py ...` inside the conda env, the env did not provide the `snakemake` module
- Result: `ModuleNotFoundError: No module named 'snakemake'`
- Consequence: `group.tsv` was never created, and `DESeq2.r` failed on missing input

Fix pattern:
- Make helper scripts standalone CLIs with `argparse`
- Pass all values explicitly from the Snakemake `run:` block (`-c`, `-t`, `-p`, `-e`, `-o`)
- Avoid reading `config`/`wildcards` from inside helper scripts

Verification pattern:
- Run the helper directly with a temp output path
- Assert the generated TSV content exactly matches the expected rows

## 2) Bowtie2 index rule: do not `raise` after success

Observed failure pattern in `bowtie2_index`:
- The shell script produced the `.bt2.tmp` files and renamed them successfully
- But the Snakemake rule still failed because the `except` block/`raise` handling was malformed
- A bare `raise` (or `raise e` misplaced outside `except`) can make a successful external tool invocation look failed and can hide the real issue

Fix pattern:
- In `run:` blocks, only re-raise inside `except`
- Use `raise RuntimeError(... ) from e` for explicit chaining
- Keep error logging inside the `except` block only

## 3) Ad-hoc verification used in this session

- `python -m py_compile workflow/Omics/modules/DESeq2/bin/write_group_tsv.py`
- Direct invocation of the helper with a `/tmp/hermes-verify-*.tsv` output
- Checked exact TSV content and removed the temp file afterward
