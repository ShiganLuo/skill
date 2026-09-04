# Bioplatform Execution Architecture

## Omics run.py Flow

The actual execution chain when running a bioinformatics workflow:

```
User inputs:
  -m meta_input.tsv    (sample metadata: sample_id, fastq paths, design groups)
  -w workflow_name      (e.g. RNAseq, scRNAseq, Mutation)
  -o output_dir
  --Params.xxx yyy      (dot-notation parameter overrides)

↓ MetadataUtils(meta).run()
  Parses TSV → samples_info_dict, sample_pairs, group_pairs, raw_fastq_dir, raw_files
  Auto-detects layout: bam/pbi → PacBio, ms_file → MS, fastq_dir+sample_prefix → scRNA, else → FASTQ

↓ Load config template: config/{workflow}.json
  Template has null placeholders for system fields (ROOT_DIR, indir, outdir, logdir, raw_files)

↓ Merge extra CLI args into config (dot-notation → dict_set_by_path)

↓ WORKFLOW_DISPATCH[workflow_name](config, samples, pairs, groups, indir, outdir, meta, raw_files)
  e.g. runRNAseq() sets ROOT_DIR, indir, outdir, raw_files, outfiles, paired_samples, control/treatment groups
  Writes final config JSON to outdir/raw.json
  Returns (smk_filename, json_path)

↓ build_snakemake_cmd(root_dir, smk, json, threads, ...)
  → snakemake -s subworkflow/{wf}.smk --configfile outdir/raw.json --cores N
```

## Meta TSV Format

Standard FASTQ meta (RNAseq, ncRNAseq, CLIP, etc.):
```
sample_id    data_id      design    fastq_1                          fastq_2
Sample1      Sample1      control   /path/to/S1_1.fq.gz             /path/to/S1_2.fq.gz
Sample2      Sample2      treat     /path/to/S2_1.fq.gz             /path/to/S2_2.fq.gz
```

PacBio meta:
```
sample_id    bam              pbi
Sample1      /path/to/S1.bam  /path/to/S1.bam.pbi
```

scRNA-seq meta:
```
sample_id    fastq_dir          sample_prefix
Sample1      /path/to/fq_dir/   Sample1
```

## Data Model Hierarchy

```
workflow_templates (abstract template)
  ├── configTemplate: JSON template with null system fields
  ├── schemaJson: form schema for parameter editing
  └── snakemakePath: e.g. "subworkflow/RNAseq.smk"

pipelines (configured variant, bound to project)
  ├── templateId → workflow_templates.id
  ├── projectId → projects.id
  ├── metaContent: TSV text content OR server file path
  ├── metaType: "text" | "path"
  ├── extraParams: JSON dot-notation overrides (e.g. {"Params.cutadapt.quality": 30})
  ├── configJson: full config copied from template at creation time
  └── created from: project "new analysis" flow OR standalone creation

pipeline_executions (runtime instance)
  ├── pipelineId → pipelines.id
  ├── projectId → projects.id
  ├── inputParams: execution-specific overrides
  ├── status: PENDING → RUNNING → SUCCESS/FAILED
  └── outputPath, errorLog
```

## Platform Execution Flow (Target)

```
Project detail → "New Analysis"
  ① Select workflow template
  ② Input meta: TSV text OR server file path
  ③ Optional: override config params (schema form or JSON editor)
  ④ Backend: parse meta → merge with template config → auto-fill system fields → save as pipeline
  ⑤ Submit execution: generate final config JSON → call run.py equivalent
```

## System Fields (auto-filled, not user input)

These fields in the config template are auto-populated at execution time:
- `ROOT_DIR` — Omics repository root
- `indir` — raw FASTQ directory (from meta parsing)
- `outdir` — output directory
- `logdir` — log directory (usually outdir/log)
- `raw_files` — collected raw file paths from meta
- `outfiles` — expected output file paths
- `paired_samples` / `single_samples` — from meta layout detection
- `control_samples` / `treatment_samples` — from meta design column

## Key Files

- `Omics/run.py` — main entry point, arg parsing, workflow dispatch
- `Omics/node.py` — per-workflow config builders (runRNAseq, runscRNAseq, etc.)
- `Omics/src/common/util/MetaUtil.py` — MetadataUtils class, meta TSV parsing
- `Omics/config/{workflow}.json` — config templates
- `Omics/src/common/util/SchemaValidatorUtil.py` — schema validation, test path generation

## Implemented API Endpoints

```
POST /api/admin/projects/{projectId}/analyses   — Create analysis (pipeline) from project context
GET  /api/admin/projects/{projectId}/analyses   — List analyses (pipelines) for a project
POST /api/admin/pipelines/{id}/execute          — Execute a pipeline
```

CreateAnalysisRequest body:
```json
{
  "workflowTemplateName": "RNAseq",
  "name": "my-analysis",
  "metaContent": "sample_id\tdata_id\tdesign\tfastq_1\tfastq_2\n...",
  "metaType": "text",
  "extraParams": "{\"Params.cutadapt.quality\": 30}",
  "description": "optional"
}
```

The backend copies `configTemplate` from the workflow template into the pipeline's `configJson` at creation time. The meta content and extra params are stored separately for later use during execution.
