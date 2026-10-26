# Run-Module Invocation (run_module.py)

Module = an independent unit with its OWN config JSON (`modules/<m>/**/<m>.json`),
own Snakefile, and own inputs — NO meta.tsv, NO workflow coupling. run_module.py
runs one module directly. run.py is the reference ONLY for environment
machinery: server path switching (SERVER_DATABASE_DIR), bind-path auto-mounting,
SIF/conda backend handling, mem_mb auto-detect. Module params come from the
module JSON, loaded by the runner and overridable per invocation via dotted
`--key.value` args. Any change coupling standalone module runs to workflow
metadata contradicts the design. (The `--workflow` mode at the bottom is a
separate legacy feature; the standalone mode above is the primary interface.)

## Standalone module mode: NEVER fake targets by rewriting output expressions

Modules lack `rule all`; their first rule carries wildcards, so snakemake
rejects it as a default target. Do NOT solve this by parsing/eval-ing rule
`output:` expressions and substituting `{sample_id}` to synthesize file
targets — that fixes only the target side. Input functions
(`get_alignment_input` etc.) run at DAG-build time and read config
(`genome_paired_samples[genome]`, `genome.references`); with wildcard values
not yet bound they look up the literal `{genome}` and raise. Every module
invents new config reads, so this approach breaks per module.

The correct pattern is a generated wrapper Snakefile in the run outdir:

```python
# <outdir>/<module>.wrapper.smk — include the real module smk, then:
include: "modules/star/polygenomes/star.smk"

rule all:
    input: expand("outdir/{genome}/{sample_id}/{sample_id}.bam",
                  genome=GENOMES, sample_id=SAMPLES)
```

`expand()` binds wildcards at DAG-build time so input functions see real
genome/sample values. run_module.py generates the wrapper from
`--samples/--rules` and points snakemake at the wrapper (never at the module
smk directly).

**expand() emission detail**: bare `expand("path/{wildcard}")` without
explicit values raises WildcardError — expand cannot infer unconstrained
wildcards. run_module substitutes CONCRETE values into the pattern string
before emitting it: `{sample_id}` from `--samples`, `{genome}` from the
effective config's `genome_paired/single_samples` keys filtered per sample
(each sample may map to a different genome; `--genome` narrows further).
The wrapper then contains only literal paths; rule all needs no expand at all
in that case, but keep expand() so multi-value emission stays uniform.

Other standalone-mode rules (verified working):

- Discover (snakefile, config) via `modules/<m>/**/<m>.smk`, PREFER the
  `polygenomes/` copy when both exist — the module-root copy is the legacy
  single-genome variant and fails on current config shapes (star: monolithic
  smk reads flat `genome.fasta`/`paired_samples`, polygenomes reads
  `genome.references.*`/`genome_paired_samples`). `--snakefile` overrides the
  discovery (e.g. `--snakefile modules/star/star.smk` for the single-genome
  variant); the config JSON TRAVELS WITH the snakefile — sibling
  `<stem>.json` in the same directory (polygenomes/star.smk →
  polygenomes/star.json, star.smk → star.json), only `--config` breaks that
  binding. run_module never writes to modules/ — the effective config goes
  to `<outdir>/<module>.config.json`.
- **Discovery must validate include: paths AND fall back across name
  variants.** Fibertools: only `polygenomes/fibertools.smk` matches
  `<module>.smk` exactly and its include (`../../../common/...`) escapes
  modules/ (3 climbs = workflow/, not modules/common) — unresolvable orphan.
  The runnable entry points are `fibertools_prepare.smk`/`fibertools_analysis.smk`.
  When exact-name candidates all fail include-validation, fall back to other
  smks in the module whose stem matches the module tag with -/_ normalized
  (msisensor-pro tag vs msisensor_pro.smk stem: dash vs underscore).
  Raised as a real bug only when run_module started running every module
  standalone; subworkflows always hardcoded the correct path so it lay hidden.
- **JSON null defeats smk defaults**: `config.get(key, default)` returns None
  (not the default) when the key EXISTS with null. Generated module JSONs must
  OMIT keys whose value would be null and whose smk reads them via
  `config.get(key, <fallback>)` (e.g. scanpy's `outdir_combine`,
  PeakCalling_report's `log_sample_dir`) — otherwise TypeError
  (NoneType + str) at parse.
- **Match smk's actual config shape, not intuition**: audit what each rule
  reads — `input_samples` is a LIST in PeakCalling_report (concatenated with
  ip_samples), `genome_pairs` is a FLAT pair `[g1, g2]` unpacked as
  `genome1, genome2 = ...` (a list-of-pairs fails with 'expected 2, got 1').
- Some modules hard-fail at parse on missing USER DATA by design
  (msisensor-pro reads samples4baseline/test tsvs at module level; star mono
  checks fasta exists). Parse errors there mean pass the real inputs, not a
  config bug.

## Module config schema validation (run_module)

`--no-schema-validate` skips; validation auto-runs when
`modules/<mod>/**/<stem>.schema.json` exists next to the config (173
generated by `scripts/generate_module_schemas.py`, re-runnable after JSON
edits).

`SchemaValidatorUtil.validate()` — **replaced in-place with the deep recursive
validator** (user decision; the shallow version had ZERO callers in the repo,
so no behavioral blast radius). The old shallow body (top-level + hardcoded
genome, required/nullable only, no type checks) is gone.

**`cast_extra_args()` should be reused for dotted overrides** (user pointed
out it already does schema-typed CLI injection; verified it resolves nested
dotted keys like `Params.cutadapt.quality` on module schemas too). Wiring it
into run_module's `apply_overrides` path is the pending piece; the deep
validate currently catches type mismatches anyway, so it's not blocking.

Deep semantics (all in SchemaValidatorUtil now):

- schema vocabulary: `type` (str/int/float/bool/dict/list/null), `nullable`,
  `required`, nested `properties`; extra config keys are allowed.
- a node may be BOTH typed (`type: dict`) and have `properties`: validate the
  type AND recurse (early-return on the type check skips all children).
- **the TOP-LEVEL schema is a bare properties map** (no wrapper `properties`
  key): `schema.get("properties")` is None at root — treat the schema itself
  as the properties map when it has no `properties`/`type` keys. Missing this
  makes root recursion a silent no-op (validation always passes).
- generator: ROOT_DIR is runtime-filled → always
  `{type: str, path: dir, nullable: true}` (never `type: null`, or runtime
  str values fail); only outdir/logdir are `required: true` — indir stays
  optional (data input, don't block discovery).
- generator: nulls in the JSON infer `type: null`; runtime-filled keys must
  be manually corrected in schemas (same pitfall as workflow schemas).

**CLI value type-casting also routes through SchemaValidatorUtil:**
`cast_extra_args(extra_args)` resolves NESTED dotted keys through the schema's
`properties` chain (verified: `Params.cutadapt.quality` → int leaf on the
cutadapt module schema), casts CLI strings to the declared type, and reports
mismatches as errors — exactly the schema-typed CLI injection run.py uses for
workflow extra args via `--schema-validate`. run_module's `apply_overrides`
still uses smart_cast for unknown keys (schema-typed path pending).

Sweep status (2026-10): 68/86 modules pass standalone dry-run+schema; the 18
fails split into smk-parse/config-shape bugs in the modules themselves (7),
include-orphans needing jsons or fixes (5: common/deeptools/fiberseq/fragpipe/
openms/scRNAseq_report), container-exec quirks (2), foreign-server permission
paths (2: gtfbuild/trimmomatic reference /data/16T), data-dependent by design
(msisensor-pro needs input tsvs).
- Inject `env.env_dir` into the effective config if absent (probe
  SERVER_DATABASE_DIR values for `<db>/env`) or `sif()` raises before any
  rule runs.
- **Pre-resolve SIF paths explicitly in the effective config** (env entry per
  conda-yaml stem, e.g. `env["star"] = <env_dir>/<module>/<stem>.sif`, found
  by walking `modules/<m>/` for `*.yaml`) — `sif()`'s fallback appends
  `workflow.basedir`, which under the wrapper is `<outdir>/.run_module/`,
  yielding a nonexistent `<env_dir>/.run_module/<stem>.sif`. Walk the MODULE
  root for yaml discovery, not the config file's dir (star: yamls live at
  `modules/star/`, config at `modules/star/polygenomes/`).
- **Eval namespace for `output:` expressions must include snakemake output
  marker functions** (`directory`, `protected`, `temp`, ...) mapping them to
  identity — `star_index`'s output is `directory(outdir + "/index/{genome}")`;
  an eval without `directory` throws, the pattern is silently skipped, and
  the run dies with 'No output patterns generated'.
- **Genome wildcard values come from the config, filtered by real
  references** — union of `genome_paired/single_samples` keys, then dropped
  for genomes whose `genome.references.<g>.fasta` is missing or a template
  placeholder (`path/to/genome.fa`); otherwise target generation expands a
  genome whose fasta is unset and the rule's input function raises.
- Server path migration: reuse `node.py`'s `SERVER_DATABASE_DIR`,
  `_detect_current_server_db`, `_replace_server_paths` on the loaded config.
- Dotted overrides (`--genome_paired_samples.GRCm39=S1`): keys ending in
  `*samples*` (leaf OR any ancestor containing 'sample') must coerce string
  values to single-element lists — downstream membership tests
  (`s in samples_list`) silently fail against a bare string. Parse unknown
  args so a bare value can only ever be consumed via `--key value` (one
  value max) or `--key=v1,v2` (comma-split); a multi-value grabber swallows
  the next flag's argument (`--sdm apptainer` → 'apptainer' eaten as a
  sample name). Dotted override KEY NAMES must match what the module smk
  actually reads — check the smk's `config.get` paths first (`--genome.fasta`
  is silently ignored by star: it reads `genome.references.<g>.fasta`).
- Write the effective (migrated + overridden) config to
  `<outdir>/<module>.config.json`; keep the module's own JSON pristine.
- **Anchor every relative logdir to outdir**: module JSONs carry relative
  values (`"logdir": "logs"`, `"logdir_index": "logs/index"`) and snakemake
  resolves them against its CWD (workflow/Omics), scattering `logs/` into the
  repo. Any config key containing 'logdir' with a relative value gets
  `os.path.join(outdir, value)` (note: `logdir_index` ENDSWITH 'index' — match
  on `"logdir" in key`, not endswith). Default logdir when absent:
  `<outdir>/log`.

Verified end-to-end: cutadapt module, synthetic PE fastq × 2 samples, conda
backend auto-created env, trimmed outputs + reports on disk, dry-run idempotent.
Verified star module standalone (the hard case): `--module star --indir ... -o ...
--genome.references.GRCm39.fasta/--gtf ... --genome_paired_samples.GRCm39=S1
--isGenomeSubdir=false --samples S1 --rules star_align --sdm apptainer --dry-run`
→ DAG = star_align(1) + star_index(1), exit 0. `--isGenomeSubdir=false` matters:
the polygenomes smk's input fn expects `indir/<genome>/<sample>/...` when true
(the template default) — point it at your actual layout via the dotted override.
Verified star_index-only on a tiny ecDNA fasta (`--rules star_index`, SIF backend):
index built under `<outdir>/index/GRCm39/`, exit 0. Small-genome caveats: the
smk hardcodes `sjdbOverhang=100`; for references tens-of-kb long override via
`--Params.star.index.sjdbOverhang <readlen-1>`. `genomeSAindexNbases` needs no
manual value (smk auto-computes). When the downstream alignment is STAR against
such a tiny reference, use `--seedSearchStartLmax 50` (2.7.11b; NO
seedSearchStartL1Nbases — unrecognized-parameter fatal error) plus
`--winAnchorMultimapNmax >= outFilterMultimapNmax`, or full-transcriptome runs
take 5-13 h/sample instead of seconds on a region-subset.

## Workflow-module mode (--workflow) — legacy, secondary

Runs one module *inside* a meta.tsv-driven workflow run by delegating to
run.py `execute_workflows()` with forcerun targets; `--list` prints the
module→prefixed-rule registry. Kept working, but the standalone mode above is
the primary interface for 'run module X with these inputs'.

### How module→rule resolution works

1. Parse `subworkflow/<wf>.smk` `use rule X from <module> as <Alias>` lines.
2. For `use rule *` lines, take the alias prefix and resolve concrete rule
   names from the module block's OWN snakefile (`module <tag>: snakefile:` in
   the subworkflow — NOT `modules/<tag>/`; tags don't map 1:1 to dirs:
   bowtie2_for_rRNA→bowtie2, gatk_prepare→gatk/polygenomes/gatk_prepare.smk).
   Follow the snakefile's `include:` lines too (relative, with `../` climbs).
3. Explicit `use rule A from m as Wf_alias` → prefixed name is the alias
   verbatim (never re-derive from the rule name; e.g.
   RNAseq_hisat2_align_for_TEtranscripts).

`--list` prints the registry; that is the fastest way to verify resolution.

### Wildcard targets

Plain `--until RULE` fails with WildcardError when the rule has wildcards
(`{genome}/{sample_id}`). The working form is snakemake's internal
`--target-jobs RULE:W1=V1,W2=V2` + `--force` (comma-joined wildcards).
run_module maps:

- `--sample S` → sample_id wildcard (repeatable)
- `--genome G` → genome wildcard (required by nearly every RNAseq rule)
- Each rule's wildcard needs are parsed from its `output:` paths (`{w}`
  tokens); only matching rules get wildcard specs, wildcard-free rules stay
  plain names (run.py's --until/--forcerun path).

### Verification

- `--list` on RNAseq: 25 modules with exact rule lists.
- `--module TEtranscripts --rule TEcount --sample E14-2 --genome GRCm39 --dry-run` → DAG = TEcount(1) + auto-upstream star_align_for_TEtranscripts.
- `--module featureCounts --rule featureCounts_merge --genome GRCm39 --dry-run` → 15-job subgraph (merge+paired+star+trim), no downstream rules.

### Pitfalls (both modes)

- `execute_workflows` requires `args._test_meta_map` (None for normal mode); a fabricated run.py Namespace must include it.
- Same backend contract as run.py: `--conda-prefix` required unless `--sdm apptainer`; validation replicated in run_module.
- `snakemake --list-rules` needs a `--configfile` whose `env` section is valid (sif() hard-fails otherwise); parsing module smk files is the reliable path.
- `sif()` fallback uses `workflow.basedir` — with a generated wrapper it becomes the wrapper's dir, yielding `<env_dir>/.run_module/<stem>.sif` (nonexistent). Standalone mode must pre-resolve: inject explicit `env[<yaml_stem>] = <env_dir>/<module>/<stem>.sif` for every yaml in the module dir (walk `modules/<module>/`, not the config's dir — polygenomes configs live one level deeper).
- Rule `output:` expressions may use snakemake markers (`directory()`, `protected()`); the eval namespace for target collection must include them (identity lambdas) or the rule is silently skipped and no targets are generated.
- `--genomeSAindexNbases` auto-computed in both star smks: `Params.star.index.genomeSAindexNbases` explicit wins; else scan fasta (chunked binary read, ~106 MB/s) and apply `max(2, min(14, int(log2(size)/2)-1))`. STAR's default 14 seg-faults/loses reads on small genomes (ecDNA ~1.76 Mb → 9). JSON templates carry the key as null.
- STAR "Could not move Log.out" warning under singularity: cross-mount rename (CWD → genomeDir on different binds) fails with EXDEV. Fix: generate the module .sh with `cd "<genomeDir>"` before the STAR command — Log.out lands in genomeDir, the move becomes same-filesystem, and the warning disappears (applied to both star smks' star_index).
- Relative logdir values in module JSONs (`logs`, `logs/index`) resolve against snakemake's CWD, scattering `logs/` into the repo; anchor any key containing 'logdir' to outdir.
- Dotted `--key.value` overrides and `--snakemake-args` pass through unchanged (same unknown-args loop as run.py).
- `--module` is optional when `--snakefile` is given: infer the module name from the path component right after `modules/` (`modules/gatk/polygenomes/gatk_prepare.smk` → `gatk`). Fail with `--module or --snakefile is required` when both are absent.
- **Missing `threads`/`mem_mb` declarations produce NO snakemake warnings** — undeclared mem is treated as 0 and silently exempt from the `--resources mem_mb` budget (can oversubscribe RAM with zero noise), and undeclared threads default to 1. If a budget guard is wanted, scan the target rules' smk bodies for `threads:`/`mem_mb` before the run and emit the warning yourself.
- The runner needs a python with BOTH pandas and snakemake, and snakemake on PATH (`export PATH=<env>/bin:$PATH`); the smk env (`smk`) has both. `--sdm` alone (action=store_const) needs no value; schema-validated modules with runtime-str fields (e.g. `genome.fasta` typed null) need `--no-schema-validate` when overriding those fields via dotted args.
- `--sdm apptainer` + SIF backend requires the Database env dir present (`/data/pub/<USER>/Database` on this server); run_module auto-probes SERVER_DATABASE_DIR for `env/`, so no manual env injection needed when Database exists.
- Long runs (multi-hour STAR) inside `run_module` rules: launch via a background terminal session with notify, never foreground — the 600s foreground cap kills the wrapper mid-DAG.
- Log-path templates are defined per module smk and differ between variants even in the same outdir (star: monolithic → `<logdir>/star/star_index.log`, no genome level, no wildcards; polygenomes → `<logdir_index>/star/{genome}/star_index.log`). Mixing variants in one outdir produces two log trees — check which smk a run actually used before comparing paths.

## User-clarified semantics (governs future changes)

A module is an independent unit with its own inputs and its own config JSON —
it has NO relationship to a workflow's meta.tsv. run_module must not require
`-m/--meta`. run.py is the reference ONLY for environment machinery: server
path switching (SERVER_DATABASE_DIR), bind-path auto-mounting, SIF/conda
backend handling. Module params come from `modules/<m>/**/<m>.json`, loaded
by the runner and overridable per invocation. Any future feature that couples
standalone module runs to workflow metadata contradicts this design.
