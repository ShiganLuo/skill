# deeptools_heatmap module pitfalls

## plotHeatmap parameter names (verify with `--help`)

```bash
singularity exec /path/to/deeptools.sif plotHeatmap --help
```

| Purpose | Correct param | WRONG guesses |
|---|---|---|
| Sample track labels | `--samplesLabel label1 label2` | `--labels`, `--labelName` |
| Show metagene plot | `--whatToShow "plot, heatmap and colorbar"` | `"heatmap, colorbar, metagene"`, `"metagene and heatmap"` |
| Title | `--plotTitle "title"` | — |
| Region labels | `--regionsLabel label1 label2` | — |
| TSS label text | `--startLabel TSS` | — |
| TES label text | `--endLabel TES` | — |
| DPI | `--dpi 300` | — |

**Valid `--whatToShow` choices:** `plot, heatmap and colorbar`, `plot and heatmap`, `heatmap only`, `heatmap and colorbar`

## computeMatrix does NOT do background subtraction

Passing multiple `-S` files shows them as separate tracks, NOT as IP/Input ratio. To subtract background:
- Use `bigwigCompare -b1 IP.bigwig -b2 Input.bigwig --operation ratio --pseudocount 1 -o ratio.bigwig` BEFORE computeMatrix
- Do this inside `run_heatmap.py` when `--input-bigwig` is provided — no extra Snakemake rule needed

## TE names in GTF are specific subfamilies

RepeatMasker TE GTF uses `gene_id` for subfamily names with numeric suffixes:
- `L1MdTf` → `L1MdTf_I`, `L1MdTf_II`, `L1MdTf_III` (prefix match)
- `ORR1` → `ORR1A0`, `ORR1B1`, `ORR1C1`, ... (18 variants)
- `MERVL` → `MERVL-int`, `MERVL_2A-int`
- `MT2` → `MT2A`, `MT2B`, `MT2B1`, `MT2B2`, `MT2C_Mm`, `MT2_Mm`
- `LINE1` does NOT exist — use individual L1 subfamilies or `class_id: "LINE"`
- `GSAT_MM`, `IMPB_01`, `RMER12B` → exact match ✓

Config must use exact `gene_id` values. Check with:
```bash
grep -oP 'gene_id "[^"]*"' TE.gtf | sort -u | grep -i "pattern"
```

## `--merge` behavior in generate_genes_bed()

- **Gene GTF + merge**: all exons → one BED row (gene body including introns). Correct for scale-regions mode.
- **TE GTF + merge**: all loci across chromosomes → one BED row. WRONG — strand from first locus only, TSS/TES meaningless.
- **TE GTF + no merge**: each locus independent BED row with correct strand. Correct.

Rule: `gtf: "te"` in config → script must NOT merge.

## scale-regions for genes mode

Genes mode should force `scale-regions` + `TSS` to show both TSS and TES labels on x-axis. `reference-point` only shows one reference point.

Do NOT read mode from config (`cm_params.get("mode", "scale-regions")`) — config may have `"reference-point"` from peaks mode, which overrides the default. Force it directly: `mode = "scale-regions"`.

## matrix.gz temp file naming

When running multiple heatmap_gene jobs in parallel, `tempfile.mktemp(suffix="_matrix.gz")` can collide. Include gene name or mode in suffix:
```python
matrix_label = args.gene_names[0] if args.gene_names else args.region_mode or "regions"
matrix_path = tempfile.mktemp(suffix=f"_{matrix_label}_matrix.gz")
```

## .sh script argument quoting

When writing commands to `.sh` scripts, use `shlex.quote()` for each argument. Without it, `--title "Rpp14IP ORR1C1 vs Rpp14Input"` and `--whatToShow "plot, heatmap and colorbar"` get split by shell on spaces/commas:
```python
# WRONG
f.write(" ".join(cmd) + "\n")
# CORRECT
f.write(" ".join(shlex.quote(str(c)) for c in cmd) + "\n")
```

## Snakemake flow control (output determines flow)

- node.py registers output files → Snakemake reverse-engineers which rules to run
- Input functions are PASSIVE — they prepare data, never control flow
- `per_gene: true` → node.py registers `{sample}_{gene}_heatmap.png` → triggers `heatmap_gene` rule
- `per_gene: false` → node.py registers `{sample}_genes_heatmap.png` → triggers `heatmap` rule
- Do NOT use input function return values to "block" rules

## HEATMAP_SUFFIX must NOT include per_gene

`heatmap` rule handles tss/peaks/genes (combined). `per_gene` mode uses `heatmap_gene` rule. `HEATMAP_SUFFIX` only needs: `tss`, `peaks`, `genes`, `heatmap` (fallback).
