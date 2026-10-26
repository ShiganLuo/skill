# Per-Rule Resources Pattern (config["resources"])

Class-level procedure for adding per-rule thread/memory control to a workflow,
mirroring the Fiberseq implementation. Use when a user asks to add or tune a
`resources` field for a subworkflow.

## Architecture (4 layers, all required)

1. **`modules/common/common.smk`** — provides `rule_res(name)`:
   merge order `resources.default` < `resources[name]`; missing keys fall back
   through default; rules with no entry inherit default entirely.
2. **`config/<Workflow>.json`** — top-level `resources` section:
   `{"default": {"threads": 2, "mem_mb": 8000}, "<rule>": {"threads": 4, "mem_mb": 16000}}`
3. **`subworkflow/<Workflow>.smk`** — EVERY module config dict gets
   `"resources": config.get("resources", {})` passthrough. Omitting it silently
   disables tuning for that module (rule_res falls back to in-code defaults).
4. **Module .smk rules** —
   ```python
   threads: rule_res("<rule>").get("threads", <original_value>)
   resources:
       mem_mb=rule_res("<rule>").get("mem_mb", <original_value>),
   ```

4b. **In-code fallback = JSON optimized value** (user decision, RNAseq): the
   `.get("threads", N)` fallback must equal the workflow JSON's optimized value,
   NOT the old hardcoded value. Rationale: if the JSON is mis-edited or the key
   is missing, the rule still runs with correct optimized resources. This trades
   strict backward-compat for safety; the resources passthrough in layer 3 means
   other subworkflows sharing the module get the optimized values too (they pass
   `{}` only when their own config JSON has no resources section — then default
   applies). Document the value-provenance change when adopting.

Schema (`config/<Workflow>.schema.json`): add a resources entry (Fiberseq ships
without one, but the user wants the constraint declared). Shape:
```json
"resources": {
  "type": "dict", "required": false,
  "properties": { "<rule_name>": {"type": "dict", "required": false,
    "properties": {"threads": {"type": "int", "required": false},
                   "mem_mb": {"type": "int", "required": false}}}, ... },
  ... "default" key gets the same rule_schema()
}
```
One property per key in the workflow JSON's resources (37 keys for RNAseq).
Pre-existing schema/validator mismatch (top-level `genome_paired_samples`
required but runtime raw.json keeps it under `Params.workflow`) is unrelated —
filter those errors when validating.

## Procedure

1. Measure before tuning: parse `<project>/log/<run>.log` for
   `localrule <name>:` ... `Finished jobid` timestamp pairs (second timestamp on
   the `\[<date>\]` line before `Finished`) to get per-rule wall times; set
   resources from real bottleneck data, not guesses. Sort rules by max runtime.
2. Add the resources section to the workflow JSON (default + per-rule keys).
3. Passthrough in subworkflow: every `*_config` dict (including dicts inside
   if/elif branches and dicts named `*_for_*`) gets the resources line.
   Verify count: `grep -c '"resources": config.get' subworkflow/<Wf>.smk` must
   equal the number of `module <name>:` blocks.
4. Convert rule directives in each module smk. For rules with NO existing
   threads directive, insert both threads + resources before the first
   `conda:`/`container:`/`log:`/`params:` line. Set the in-code fallback to the
   JSON optimized value (see 4b).
5. Validate: `run.py --test <Workflow>` needs BOTH the smk env's python AND
   its bin on PATH (snakemake binary lookup fails otherwise):
   `PATH=<smk-env>/bin:$PATH <smk-env>/bin/python run.py --test <Workflow>`.
   Then verify the scheduled values, not just that the dry-run parses: grep the
   dry-run output for `rule <name>:` / `threads: N` pairs and diff against the
   JSON — parse success alone does not prove the config reached the scheduler.
   Git push needs the right SSH key in core.sshCommand; `ssh -T git@github.com`
   through the SOCKS proxy with each `~ssh/*.pub` counterpart finds which one
   authenticates (Permission denied on a fetch with the proxy already open
   means the key is wrong, not the network).

## Naming rule: one key per RULE, not per pipeline stage

`rule_res()` resolves by snakemake rule name. When one rule serves multiple
pipeline instances (e.g. `star_align` reused for TEtranscripts, featureCounts,
SNP, and fusion passes), snakemake cannot vary threads per wildcard — the
resources key must be the single rule name (`star_align`), never per-stage
keys like `star_align_for_SNP`. Per-stage keys in the JSON silently never match.

## Schema placement

RNAseq.schema.json has NO top-level `tmp_dir` key — anchor the resources entry
after `ROOT_DIR` when inserting programmatically (keying on tmp_dir silently
inserts nothing because the loop condition never matches; re-load the written
file and assert the key exists).
Write the schema back with `indent=2` — the file's existing style; json.dump
with indent=4 reflows every line and produces a 1000+-line diff for a 500-line
addition.

## Pitfalls

- **Shared modules and fallback provenance**: star/bowtie2/gatk/featureCounts
  modules are included by several subworkflows. With fallback = optimized value,
  those other workflows silently inherit the optimized resources — intended per
  user (correct even on JSON mis-edit). If strict per-workflow isolation is ever
  required, revert fallbacks to old hardcoded values and rely solely on JSON.
- **Editing .smk dict literals programmatically**: when inserting a key into a
  `*_config = {...}` block, the previous line often lacks a trailing comma
  (snakemake dicts tolerate this, plain Python does not) — insertions before the
  closing brace produce `SyntaxError` at snakemake parse time. After batch
  edits, ALWAYS run the dry-run test; do not trust brace-balance counts.
- **Test-mode metadata + fastq fixtures**: `--test` reads
  `assests/test/meta_<Workflow>.tsv`; the organism column must hold a resolvable
  alias (GRCm39/GRCh38/Mmul_10) AND dummy fastqs must exist at
  `assests/test/data/fastq/<sample>/<sample>_[12].fq.gz` (created on first run),
  else samples are skipped and arriba's input function raises
  'No passed fusion files found' during DAG build.
- **Known pre-existing bug to check first**: `node.py::_init_raw_json` referenced
  `tmp_dir` before assignment when the template's `tmp_dir` was non-null.
  If `--test` fails with 'cannot access local variable tmp_dir', fix by
  `tmp_dir = datajson.get("tmp_dir") or os.path.join(outdir, "tmp")` before the
  branch.
- **threads in command vs scheduling**: rules that pass `str(threads)` into the
  tool command (featureCounts -T, stringtie -p) get the change for free; rules
  hardcoding a thread count inside the command string need a separate check.
