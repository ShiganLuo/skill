# Scanpy Module Parameter Chain

The scanpy module has a **counter-specific** config structure (scTE vs cellranger) unlike most other modules.

## Config Nesting

```
Params.scanpy.<counter>.<stage>.<param>
```

Where `<counter>` is `"scTE"` or `"cellranger"`, and `<stage>` is `"qc"`, `"cluster"`, `"annotate"`, or `"advanced"`.

## Full Stack (6 layers)

| Layer | File | Key Path |
|-------|------|----------|
| 1. Workflow config | `config/scRNAseq.json` | `Params.scanpy.scTE.cluster.X` AND `Params.scanpy.cellranger.cluster.X` |
| 2. Schema | `config/scRNAseq.schema.json` | 3 sections: `scanpy.cluster` (main), `scanpy.cellranger.cluster`, `scanpy.scTE.cluster` |
| 3. node.py | `node.py::runscRNAseq()` | Transparent for cluster params (only overrides QC params) |
| 4. Module template | `modules/scanpy/scanpy.json` | `Params.scanpy.cluster.X` (single section, no counter split) |
| 5. Snakemake rule | `modules/scanpy/scanpy.smk` | `params.get(wildcards.counter,{}).get("cluster",{}).get("X", default)` |
| 6. Python script | `modules/scanpy/bin/scRNAseq.py` | argparse `--x` flag → `mode_cluster(x=...)` |

## Adding a New Parameter (Checklist)

1. **config/scRNAseq.json**: Add to BOTH `scTE.cluster` AND `cellranger.cluster`
2. **config/scRNAseq.schema.json**: Add to ALL 3 cluster sections (main + scTE + cellranger)
   - Watch indentation: main has 6-space indent, counter-specific have 8-space
3. **modules/scanpy/scanpy.json**: Add to the single `cluster` section
4. **modules/scanpy/scanpy.smk**: Add lambda param + conditional `cmd.append()`
5. **modules/scanpy/bin/scRNAseq.py**: Add argparse arg + function parameter
6. **modules/scanpy/bin/plot.py**: If visualization needed, add plot method

## Pitfall: Schema Has 3 Cluster Sections

The schema JSON has `cluster` at 3 different nesting levels:
- `scanpy.cluster` (line ~380, 6-space indent) — shared defaults
- `scanpy.cellranger.cluster` (line ~533, 8-space indent)
- `scanpy.scTE.cluster` (line ~661, 8-space indent)

Using `replace_all=true` only catches matching indentation. You may need 2 patch calls:
one for 6-space indent, one for 8-space indent (covers both counter-specific sections).

## Pitfall: node.py Does NOT Touch Cluster Params

`runscRNAseq()` only overrides QC params (min_genes, max_genes, scrublet).
Cluster params flow through unchanged from the workflow JSON to raw.json.
Do NOT add cluster param overrides in node.py unless there's a specific need.
