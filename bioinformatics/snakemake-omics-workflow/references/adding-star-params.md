# Adding a new STAR parameter to the Omics pipeline

## Problem

STAR's `twopassMode Basic` can discover more splice junctions than the default
`--limitSjdbInsertNsj 1000000`. Error message:

```
Fatal LIMIT error: the number of junctions to be inserted on the fly =N
is larger than the limitSjdbInsertNsj=1000000
SOLUTION: re-run with at least --limitSjdbInsertNsj N
```

Common for single-cell RNA-seq (large datasets, many junctions).

## 3-file pattern for any new STAR param

Adding a new STAR parameter (e.g. `limitSjdbInsertNsj`) requires changes in
**exactly 3 files**. Follow this pattern for any STAR param, not just this one.

### 1. `config/scRNAseq.json` — set the value

Add to `Params.star`:

```json
"soloBarcodeReadLength": 98,
"limitSjdbInsertNsj": 3000000
```

### 2. `modules/star/star.json` — update the template

Same key/value in the template defaults.

### 3. `modules/star/star.smk` — two changes

**a) Read the param** (in the `params:` block of `star_align` rule):

```python
limitSjdbInsertNsj = config.get('Params',{}).get('star', {}).get('limitSjdbInsertNsj') or 1000000,
```

**b) Pass to STAR command** (in `cmd1` list):

```python
"--limitSjdbInsertNsj", str(params.limitSjdbInsertNsj),
```

## Verified values

| Param                 | Default   | Large scRNA-seq | Notes                          |
|-----------------------|-----------|-----------------|--------------------------------|
| limitSjdbInsertNsj    | 1000000   | 3000000         | Error if 1st-pass junctions > limit |
| winAnchorMultimapNmax | 50        | 100             | For highly repetitive genomes  |
| outFilterMultimapNmax | 10        | 100             | For TE quantification (scTE)   |

## Pitfalls

- Must change BOTH json files (scRNAseq.json + star.json). Forgetting the
  template means new projects won't get the param.
- The `config.get()` default (the `or N` fallback) must match star.json's
  default so behavior is consistent when param is absent.
- RNAseq.json doesn't have single-cell params (soloType etc.) — don't add
  scRNAseq-only params there unless the RNAseq workflow also needs them.
