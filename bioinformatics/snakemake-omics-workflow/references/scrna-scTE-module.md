# scTE Module Pattern (single-cell TE quantification)

## Overview

scTE quantifies transposable element (TE) expression from single-cell BAM files. It takes Cell Ranger BAM as input and produces a TE count matrix per cell.

## Module structure

```
modules/scTE/
  scTE.smk              # rules: scTE_build_index, scTE_quantify
  scTE.yaml             # conda env (pip install scTE)
  scTE.json             # default config
  bin/scTE_quantify.py  # wrapper: calls scTE CLI → converts CSV → h5ad
```

## Two rules

1. **scTE_build_index**: Dual-mode rule.
   - Resource-based: `scTE_build -gene <gtf> -te <bed> -o <prefix> -m <mode> -g other`
   - Download-based: `scTE_build -g <genome> -o <prefix> -m <mode>`
   - Output: single `.idx` file (e.g. `results/scTE/index/hg38.exclusive.idx`)
   - Branches on `Params.scTE.gene_gtf` and `Params.scTE.te_bed` being set
2. **scTE_quantify**: Calls `bin/scTE_quantify.py` which runs `scTE -i <bam> -o <outdir> -x <index> -CB CB -UMI UB` and converts CSV output to h5ad.

## Config

```json
{
    "Procedure": {
        "scTE": null,
        "scTE_build": null
    },
    "Params": {
        "scTE": {
            "genome": "hg38",
            "mode": "exclusive",
            "cb_tag": "CB",
            "umi_tag": "UB",
            "gene_gtf": null,
            "te_bed": null
        }
    }
}
```

- `gene_gtf` + `te_bed`: set both to use local resource files; leave null to download
- `mode`: `exclusive` (default), `inclusive`, `nointron` — affects output filename
- `cb_tag`: Cell Ranger uses `CB`, STARsolo uses `CR`
- `umi_tag`: Cell Ranger uses `UB`, STARsolo uses `UR`

## TE BED format

4 columns: `chr start end subfamily_name`

```
chr1  67108753  67109046  L1P5
chr1  8388315   8388618   AluY
```

Convert from rmsk TE GTF:
```bash
awk -v OFS='\t' '{match($0, /gene_id "([^"]+)"/, m); print $1, $4-1, $5, m[1]}' input.gtf > output.bed
```

The 4th column is the **subfamily** name (gene_id from GTF, repName from rmsk). This is the granularity of the final expression matrix — each subfamily gets its own count column.

## scTE index output

The index is a single binary `.idx` file produced by `genelist.save()`.
- Path pattern: `{outdir}/index/{genome}.{mode}.idx`
- `scTE_quantify` passes it via `-x <path>` flag
- Snakemake `output:` cannot be a function — compute as module-level variable:
  ```python
  _scTE_genome = config.get("Params", {}).get("scTE", {}).get("genome", "hg38")
  _scTE_mode = config.get("Params", {}).get("scTE", {}).get("mode", "exclusive")
  _scTE_index = f"{outdir}/index/{_scTE_genome}.{_scTE_mode}.idx"
  ```

## scTE CLI usage

```bash
# Build index (downloads GTF + rmsk automatically)
scTE_build -g hg38 -o /path/to/index -m exclusive

# Build from local resources
scTE_build -gene gencode.v30.annotation.gtf.gz -te rmsk.bed -o /path/to/hg38 -m exclusive -g other

# Quantify from Cell Ranger BAM
scTE -i possorted_genome_bam.bam -o output -x /path/to/hg38.exclusive.idx \
    -p 20 -CB CB -UMI UB

# STARsolo BAM uses different tags
scTE -i Aligned.out.bam -o output -x /path/to/hg38.exclusive.idx \
    -p 20 -CB CR -UMI UR
```

## Available TE BED files (local)

| Species | Path |
|---------|------|
| Human (hg38) | `/home/luosg/Database/Reference/human/GENCODE/GRCh38/GRCh38_GENCODE_rmsk_TE.bed` |
| Mouse (GRCm39) | `/home/luosg/Database/Reference/mouse/GENCODE/GRCm39/GRCm39_GENCODE_rmsk_TE.bed` |
| Mulatta (rheMac10) | `/home/luosg/Database/Reference/mulatta/ENSEMBL/Mmul_10/rheMac10_rmsk_TE.bed` |

## Pitfalls

- `scTE_build -te` only accepts **uncompressed** files (uses `open()` not `gzip.open()`). `-gene` accepts both `.gz` and plain text.
- Snakemake `output:` **cannot use a function call**. Compute the path as a module-level variable and reference it directly.
- **Do NOT create a standalone Python wrapper script** just to call `scTE_build` with different args. Inline the CLI call directly in the rule's `run:` block with an `if/else` branch. User explicitly corrected: "既然是简单调用,不需要单独脚本,直接在规则里面用就行,不必多此一举".
