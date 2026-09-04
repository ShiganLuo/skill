# scTE Debugging Reference

## Inspecting Container Code

The scTE container (`scTE.sif`) has `scte-quant` from PyPI installed at `/opt/conda/envs/scTE/`.

```bash
# Get base.py from container
apptainer exec scTE.sif cat $(apptainer exec scTE.sif find /opt/conda/envs/scTE -path "*/site-packages/scTE/base.py" | head -1)

# Get scTE binary from container
apptainer exec scTE.sif cat /opt/conda/envs/scTE/bin/scTE

# Load .idx and inspect chromosomes (run from /tmp to avoid local source contamination)
cd /tmp && apptainer exec scTE.sif /opt/conda/envs/scTE/bin/python3 -c "
from scTE.miniglbase import glload
gl = glload('path/to/index.exclusive.idx')
chrs = sorted(set(k['chr'] for k in gl['loc']))
print(chrs)
"
```

**Pitfall**: The scTE binary has `sys.path.append(os.path.join(os.path.split(sys.argv[0])[0], '../'))`. If CWD is the local `workflow/scTE/` source directory, Python picks up the LOCAL source instead of the container's installed package. Always run inspection from `/tmp` or another neutral directory.

## .idx Chromosome Name Case

The `.idx` index stores chromosome names in **UPPERCASE**, regardless of source:
- TE BED: `Un_NW_021161009v1` (mixed case) → index: `UN_NW_021161009V1`
- TE BED: `10_NW_021160241v1_random` → index: `10_NW_021160241V1_RANDOM`
- GTF: `1` → index: `1` (no change, already uppercase-compatible)
- GTF: `MT` → index: `MT`

This case conversion happens inside the `miniglbase` library during `genelist._optimiseData_compact()`.

## BAM vs Index Chromosome Mismatch

Common pattern with macaque (Mmul_10) genome:

| Source | Chromosomes |
|--------|------------|
| BAM (STARsolo/CellRanger) | `1-20, X, Y, MT, QNVO_xxx, ML_xxx` |
| GTF (Ensembl) | `1-20, X, Y, MT, QNVO_xxx, ML_xxx, ML143xxx` |
| TE BED (UCSC rmsk) | `1-20, X, Y, Un_NW_xxx, *_random` |
| .idx (built from GTF+TE BED) | `1-20, X, Y, MT` + `UN_NW_xxx, *_RANDOM` |

Key mismatches:
- **BAM has QNVO/ML contigs, index doesn't**: `scTE_build`'s `read_gtf` filters by `chr_list = [1-49, X, Y, M, MT]`, excluding QNVO/ML contigs. Reads on these contigs (~0.5% of total) are lost.
- **Index has scaffold chroms, BAM doesn't**: 2906 scaffold chromosomes from TE BED are in the index but not in the BAM. `split_chr` processes them but finds 0 reads — wasted time but no data loss.

## split_chr Grep Logic

For chromosomes 1, 2, 3: `grep -v ^1[0-9] | grep ^1` (excludes 10-19, keeps 1)
For all others: `grep ^%s` (text prefix match)

The BAM chromosome name (after `sed 's/^chr//g'`) must match the index chromosome name for reads to be counted. Since the index uses UPPERCASE and the BAM uses the original case, the grep works for standard chromosomes (1-20, X, Y, MT) but NOT for scaffold chromosomes (case mismatch between BAM and index).

## CR+UR vs CB+UB Impact on Cell Count

With `CR` (raw barcode) + `UR` (raw UMI):
- Each sequencing error in the 16bp barcode creates a "new" barcode
- Typical ratio: ~1 read per unique barcode per chromosome
- `filter_crs` requires ≥400 total counts → only true cell barcodes pass
- Expected result: 100-200 cells for a typical 10X experiment

With `CB` (corrected barcode) + `UB` (corrected UMI):
- Barcode correction merges error variants into the true barcode
- Much higher counts per barcode
- More cells pass the filter

**The BAM may not have CB/UB tags** — check with:
```bash
samtools view file.bam | head -1000 | grep -c "CB:Z:"
```

If no CB tags, CR is the only option. The cell count is then determined by the data quality.

## Log Interpretation

```
Before filter 25770583   ← total unique barcodes across all chromosomes
After filter 111         ← barcodes with ≥400 total counts
Detect 110 cells         ← barcodes with ≥200 unique gene/TE hits
```

The gap between "Before filter" and "After filter" is the key indicator of data quality with CR tags. A larger gap means more ambient RNA / barcode errors.
