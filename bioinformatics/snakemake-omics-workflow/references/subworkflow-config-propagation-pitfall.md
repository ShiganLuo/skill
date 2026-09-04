# Pitfall: subworkflow config propagation

When a subworkflow (e.g. `scRNAseq.smk`) constructs a config dict to pass to a module via `module X: config: x_config`, it must explicitly list EVERY param the module reads. If a new param is added to the top-level config JSON but NOT added to the subworkflow's config dict construction, the module receives `None` and silently falls back to its default.

## Real example

Adding `limitSjdbInsertNsj` to `config/scRNAseq.json` and `modules/star/star.smk` had no effect until it was also added to the `star_config` dict in `subworkflow/scRNAseq.smk` (line ~36). The Snakemake metadata confirmed the param was `1000000` (default) despite config having `3000000`.

The flow is:
```
config/<Workflow>.json  -->  subworkflow/<Workflow>.smk (builds <module>_config dict)  -->  module <tool>.smk (reads from config)
```

If step 2 doesn't pass a param, step 3 gets `None`.

## Params sub-dict pattern

Modules that accept user-configurable parameters read from `config.get("Params", {}).get("<module>", {})`. The subworkflow MUST pass this through:

```python
# In subworkflow/<Workflow>.smk:
<module>_config = {
    "ROOT_DIR": ROOT_DIR,
    "outdir": ...,
    "Procedure": { ... },
    "Params": {                                    # MUST include this
        "<module>": config.get("Params", {}).get("<module>", {}),
    },
    "genome": { ... },
}
```

Without the `"Params"` key, the module reads `config.get("Params", {})` → `{}` and all user config is silently ignored.

## Report module: configurable input directories

When a report module's input paths don't match the subworkflow's directory structure (e.g., peaks live under `results/peaks/` not `peaks/`), pass explicit directory paths through config:

```python
report_config = {
    "outdir": outdir,
    "logdir": f"{logdir}/sample",
    "peaks_dir": f"{outdir}/results/peaks",          # explicit override
    "annotation_dir": f"{outdir}/results/annotation", # explicit override
    "qc_dir": f"{outdir}/QC/3_frip_score",
    "log_sample_dir": f"{logdir}/sample",
    "markdup_dir": f"{outdir}/common/4_markdup_bam",
    "Params": {
        "report": config.get("Params", {}).get("report", {})
    }
}
```

The module reads these with fallbacks:
```python
peaks_dir = config.get("peaks_dir", outdir + "/peaks")
annotation_dir = config.get("annotation_dir", outdir + "/annotation")
```

## Rule

When adding a new param to a module's JSON config, ALWAYS check if the subworkflow that includes that module has a manually-constructed config dict. If so, add the param there too. Search pattern: `config: xxx_config` in the subworkflow .smk file. Pay special attention to the `Params` sub-dict — it must be explicitly passed through.
