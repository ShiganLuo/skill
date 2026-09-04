# Atomic module and verification lessons

This reference captures a recurring correction from population-genomics and scRNA-seq implementation work.

## Architecture gate

- `subworkflow/<workflow>.smk` is orchestration only: read top-level config, build module-specific config dictionaries, declare `module`, expose selected rules with `use rule`, and define the final aggregation rule (normally `rule all`). It must not contain implementation rules.
- One biological workflow is not automatically one module. Inventory executable tools and independently reusable analysis steps first. Put each independent tool/atomic step in its own `modules/<tool>/` directory. A tightly coupled chain may share a module only when its steps are not independently reusable.
- Reuse an existing module only when its semantics match the required DAG. For GATK cohort calling, an existing per-sample ordinary-VCF germline module cannot replace per-sample `-ERC GVCF` -> GenomicsDB import -> joint genotyping.
- For shared environments, follow the parent/submodule layout, e.g. `modules/gatk/<submodule>/` with `conda: "../gatk.yaml"`. Submodules can share the parent's yaml OR have their own `<subtool>.yaml` -- both are valid. When a submodule needs a different environment, it must have its own `<subtool>.yaml` with a unique filename stem (container naming requirement). Do NOT assume every submodule must have its own yaml; most share the parent's.

## Module scaffold and config flow

Use the repository convention where applicable:

```text
modules/<tool>/
  <tool>.smk
  <tool>.json
  <tool>.yaml
  bin/                 # only for helper scripts
```

The JSON is a default template, not runtime truth. Trace every config key through JSON -> `run.py` runtime population (if exposed by the CLI) -> subworkflow config bridge -> module `config.get()` -> command/script arguments. Do not modify only one layer.

## Standard run block

Executable rules use `run:`, never a bare `shell:` block. In each rule: clear/create the log; use the common logger where applicable; create a timestamped, rule/sample-unique command script; build command arguments as a list; write `set -euo pipefail`; execute with `shell("bash <script> >> <log> 2>&1")`; catch/log exceptions and re-raise. Append optional arguments in Python; do not put Python conditional expressions inside shell templates. Parallel rules must never share a fixed script path.

## DAG and verification

- Optional heavy analyses must be controlled by config switches and every enabled switch must add its outputs to `outfiles`/`rule all`.
- Validate both default/disabled and fully enabled option sets with placeholder inputs. A dry-run proves parsing and DAG construction only; it does not prove external tools, environments, biological input semantics, or actual output suffixes.
- After edits, use a fresh temporary `/tmp/hermes-verify-*` script, clean it up, and report the result explicitly as ad-hoc verification, not as the project test suite being green.

## Failure patterns to avoid

- Rules in a subworkflow.
- One giant multi-tool module.
- JSON changed without `run.py` and subworkflow updates.
- Optional rules omitted from final outputs.
- Bare/under-specified `run:` blocks with no timestamps, error logging, or unique scripts.
- Calling a dry-run “pipeline verified.”
