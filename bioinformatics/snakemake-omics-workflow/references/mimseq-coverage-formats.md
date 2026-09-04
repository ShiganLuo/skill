# mimseq Coverage Output Formats & Data-to-PPT Pipeline

## coverage_byaa.txt (TSV)
Path: `mimseq/coverage_byaa.txt`

Columns: `aa`, `bin`, `condition`, `bam`, `pos`, `cov`, `cov_norm`

- `aa`: amino acid name (e.g. Ala, Gln, mitoSer, mitoPro, mitoCys, mitoGlu)
- `bin`: position bin (integer)
- `condition`: experimental condition (e.g. GV, MII, 4C, 8C, E2C, L2C, Morula, Blastocyst, PN5)
- `bam`: full path to per-sample BAM (includes sample name in path)
- `pos`: bin center position
- `cov`: raw coverage count
- `cov_norm`: normalized coverage (fraction of total reads)

Rows: one per (aa, bin, condition, sample) combination.

### Aggregation for heatmaps/tables
Group by `(aa, condition)`, take mean of `cov_norm` across replicates.
12 amino acids typically used: Gln, Arg, mitoSer, Ala, Leu, mitoPro, Asp, Gly, Lys, His, iMet, Pro.

## coverage_bygene.txt (TSV)
Same structure but at per-gene (isodecoder) level instead of amino acid level.

## State pickle: `state/coverageData.pkl`
Intermediate state for pipeline continuity. Not for direct analysis consumption.

## Data-to-PPT Pipeline Pattern

When tRNA-seq PPT slides reference coverage data:
1. `coverage_byaa.txt` → aggregate (mean cov_norm per aa × condition)
2. Data hardcoded into JS script (e.g. `create_ppt_cn.js`) using `pptxgenjs`
3. JS generates `.pptx` → converted to per-slide `.jpg` images

To trace a slide back to source: read the JS file, find the slide index, locate the data array.

## Excel Export

When the active env lacks pandas, use: `conda run -n smk python3`
If openpyxl is missing: `conda run -n smk pip install -q openpyxl`

```python
import pandas as pd
df = pd.read_csv('coverage_byaa.txt', sep='\t')
embryo = df[df['condition'].isin(cond_order)]
pivot = embryo.groupby(['aa','condition'])['cov_norm'].mean().unstack('condition')
pivot.to_excel('output.xlsx', sheet_name='coverage_by_aa')
```
