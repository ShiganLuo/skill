# Snakemake module architecture and verification gates

This reference records the project-specific lessons from implementing population-genomics, scRNA-seq, and spatial-transcriptomics workflows.

## Architecture gate

Before editing, inventory every executable tool/atomic step and map it to a module. One module should contain one tool or one inseparable chain; never create a workflow-named mega-module containing independent tools (for example GATK, bcftools, PLINK2, ADMIXTURE, vcftools, PopLDdecay, and easySFS together).

A `subworkflow/<workflow>.smk` is orchestration only: construct module-specific config dictionaries, declare `module`, expose rules with `use rule`, and define `rule all`. It must not contain implementation rules.

For a nested module under `modules/<parent>/<child>/`, resolve paths relative to that file. Typical paths are `../../common/common.smk` and `../<parent>.yaml`; test the module import through the real subworkflow.

## Standard rule gate

Every executable rule uses the repository `run:` pattern:

1. Convert `log` to a path and create its parent directory.
2. Clear/create the log and initialize the project logger with `setup_logger`.
3. Generate a timestamped command script under the rule output area.
4. Build command arguments as a list; append conditional arguments explicitly.
5. Write the script and execute `bash <script> >> <log> 2>&1` through `shell()`.
6. Catch exceptions, append a useful failure message, re-raise, and record completion in `finally`.

Do not hide required logging/error behavior in a generic helper, and do not use a plain `shell:` rule.

## Configuration gate

For a new workflow, keep defaults in module JSON, pass runtime values from the user-facing config through the subworkflow's module config dictionary, and read them in the module with `config.get()`. Do not assume that editing only a module JSON changes runtime behavior. If the project has a `run<Workflow>()` entry point, add the full config path there or explicitly document the input contract when the workflow is currently direct-Snakemake only.

## Verification gate

Create temporary fixtures with an OS-safe `/tmp/hermes-verify-*` path. Verify:

- the subworkflow has orchestration only and only its `rule all`;
- every expected module imports and contains `run:` rules without `shell:` blocks;
- optional config branches are represented in the DAG when enabled;
- the fully enabled workflow dry-runs with the repository's available Snakemake executable;
- helper scripts pass syntax checks;
- `git diff --check` passes before commit.

Clean the fixture directory. Report this as ad-hoc verification, not as the full project test suite.

## Documentation and delivery gate

When adding a workflow, update the root README and subworkflow README with input contracts, outputs, module ownership, and optional analyses. Before pushing, stage only intended source/config/docs files, exclude `test/`, `workflow.log`, and other runtime artifacts, run the focused verification again, commit with a conventional message, push the requested remote branch, and compare local `HEAD` with `git ls-remote`.
