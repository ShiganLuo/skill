# Pitfall 69: Report module across multiple subworkflow branches

When a subworkflow has multiple aligner/mode branches (hisat2, star, star_3pass, star_3pass_gene), each producing different output structures:

1. **Move report config to the shared area** after the if/elif/else block — never inside one branch.
2. **Pass `aligner` through config** so the module and Python script know which paths to check.
3. **Use `unpack(_report_inputs)`** in the module .smk to conditionally include only the inputs the active branch produces.
4. **Python script accepts `--aligner`** and adapts data collection paths (BAM dir, tail CSV dir, gene manifest).
5. **Skip PPT slides** when data is None (e.g. no gene_assignment slide if no per-gene BAM, no tail slides if no tailer).

Full pattern: see `report-module-across-branches.md` in same references/ directory.

# Pitfall 70: Investigate full data flow before modifying a module

Before modifying a module to "support new branches", trace the complete data flow:

1. Read node.py / run.py to see what config keys each branch passes.
2. Read the subworkflow to see which branches exist and what each produces.
3. Read the module .smk and Python script to see what paths are hardcoded.
4. Only THEN make changes.

User correction: "不要自以为是,没调查就判断" (don't assume without investigating). Jumping to modify code without understanding the full context leads to wrong assumptions about which branches need what data.

# Pitfall 71: STAR log file naming ≠ star.Log.final.out

STAR produces `{outPrefix}Log.final.out`. With `outPrefix = outdir + "/{sample_id}/{sample_id}."`, the log is `{sample_id}.Log.final.out` — NOT `star.Log.final.out`. For `star_3pass`/`star_3pass_gene`, STAR is invoked inside `three_pass_align.py` with per-pass prefixes; no standalone STAR log exists as a declared output.

Never include STAR log files in report module `_report_inputs()`. The Python script's `parse_star_log()` handles missing files gracefully.

# Pitfall 72: Non-declared outputs cause MissingInputException

Files produced as side effects (not in rule `output:` section) cannot be used as Snakemake inputs. Example: `genes.tsv` and `read_gene_overlaps.tsv` are created by `gene_specific_align.py` but not declared in the rule. Using them in another rule's input causes `MissingInputException` even though they exist on disk after the rule runs.

Only use declared outputs in `_report_inputs()`. Read side-effect files at runtime in the Python script, handling missing gracefully.

# Pitfall 73: node.py outfiles must exactly match rule outputs

When a rule declares `output: file_inventory = outdir + "/X_files.xlsx"`, node.py must append the exact same path to `outfiles`. A mismatch (e.g. `X.xlsx` vs `X_files.xlsx`) causes permanent `MissingInputException` in `rule all`. Always verify after modifying rule outputs.

# Pitfall 74: Test all branches before reporting done

User correction: "能不能自己好好测试一下各种工况,不要我来反馈,修改好再通知我" (test all conditions yourself, don't make me report issues).

When modifying a module to support multiple branches, run `--dry-run` for each aligner type (hisat2, star, star_3pass, star_3pass_gene) before declaring the work complete. Check:
1. No `MissingInputException` for any branch
2. outfiles in node.py match rule outputs exactly
3. No duplicate outfiles entries
