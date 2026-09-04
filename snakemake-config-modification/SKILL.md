---
name: snakemake-config-modification
description: Modify config-driven values in Snakemake pipelines — trace config flow before changing anything.
tags: [snakemake, pipeline, config, bioinformatics]
---

# Snakemake Config Modification

When a user asks to replace hardcoded values with config-driven ones, or to modify config parameters in a Snakemake pipeline, follow this workflow BEFORE making any edits.

## Step 0: Read Project Docs

Always read project README/docs first. The user expects this. Check:
- Root README.md or AGENTS.md
- `workflow/` or `pipeline/` level README
- Module-level README if modifying a specific module

## Step 1: Trace the Full Config Flow

Config-driven pipelines have a chain. Find every link before editing:

1. **Source JSON** — Where is the original config file? Look in `config/` or similar.
2. **Loader/Dispatcher** — A Python script (often `run.py`) that loads the JSON, sets defaults, writes an intermediate `raw.json` or similar.
3. **Subworkflow bridge** — `.smk` files that read from config and construct module-specific config dicts.
4. **Module consumer** — The final `.smk` or Python script that reads the config value.

**Do NOT assume the module's own JSON template is the source of truth.** The actual runtime config often comes from a different file.

## Step 2: Edit All Links in the Chain

When adding or modifying a config field, update EVERY file in the chain:
- Source JSON (add field with default)
- Loader script (set default if not present in JSON)
- Subworkflow (pass field through to module config dict)
- Module smk (read from config dict)
- Consumer script (use the value, with fallback)

When REMOVING a config field, the chain is longer -- trace through to the final
Python script and clean up every trace:
- Source JSON (remove field)
- Schema JSON (remove field definition)
- Subworkflow (remove from config dict construction)
- Module smk (remove variable definition + CLI arg passing like `--flag`, str(val))
- Python script (remove argparse argument, function parameter, and any override
  logic that used the value)
- All call sites that passed the removed parameter to the function

Failure to clean up the full chain leaves dead argparse args, dangling function
parameters, or stale CLI pass-throughs that silently do nothing or cause errors.

## Step 3: Match Existing Namespace Conventions

Config values for modules typically live under `Params.<module_name>`, not at the top level. Check existing fields to see the pattern.

## Pitfalls

- **Editing only the module template** - The module's `.json` is often just a schema template, not the runtime config. The actual config comes from `config/<workflow>.json`.
- **Not reading docs first** - Users who know the pipeline well expect you to understand the architecture before editing. Reading READMEs is mandatory.
- **Skipping intermediate links** - If you add a field to JSON but forget the subworkflow bridge, the value never reaches the module. This is the #1 config bug in this project.
- **Explicit manual config dicts in subworkflows** - Some subworkflows (e.g., scRNAseq.smk) construct module config dicts with EXPLICIT per-field `config.get(...)` calls, NOT by passing through the whole Params block. Every new param MUST be added to both the source JSON AND the subworkflow's manual dict. Check the subworkflow's `*_config = { "Params": { ... } }` block before assuming a param will propagate.
- **Debugging config propagation with Snakemake metadata** - When a param seems correct in config but doesn't reach STAR, check `.snakemake/metadata/` files. They contain the serialized params array that Snakemake actually uses. Search for the param value (e.g., `"1000000"` vs `"3000000"`) to verify what the subprocess receives.
- **Redundant config fields** - Before adding a new config field, check if an existing field already controls the same behavior. Example: a `hard_clip_5p` field that overrides `clip5pNbases` inside the Python script is redundant -- the user should configure `clip5pNbases` directly. When you find such redundancy, remove the override field and let the canonical field control the behavior.
- **Mixing parameter categories** - Index-building parameters (e.g., `genomeSAindexNbases`, `sjdbOverhang`) belong in a dedicated `Params.<module>.index` sub-key, NOT mixed into alignment parameters like `passes.pass1`. Semantic grouping by function (index vs alignment vs filtering) keeps config readable and prevents fields from being misplaced.

## Semantic Grouping Convention

When a module has parameters for distinct phases (index building, alignment, filtering),
group them under sub-keys by function:

- `Params.STAR.index.sjdbOverhang` -- genomeGenerate index parameter
- `Params.STAR.alignEndsType` -- alignment parameter (flat under STAR)
- `Params.star_3pass_gene.index.genomeSAindexNbases` -- per-gene index parameter
- `Params.star_3pass_gene.passes.pass1.*` -- per-pass alignment parameters

This pattern applies whenever a module mixes genomeGenerate and alignment params.
Subworkflow configs must pass through the `.index` sub-key explicitly:
`"Params": {"STAR": {"index": config.get("Params", {}).get("STAR", {}).get("index", {})}}`

## References

- `references/genomeStability-flow.md` — Config flow architecture, conventions, module-specific structures
- `references/star-scrnaseq-pitfalls.md` — STAR alignment pitfalls: limitSjdbInsertNsj, soloBarcodeReadLength, scRNAseq config propagation
