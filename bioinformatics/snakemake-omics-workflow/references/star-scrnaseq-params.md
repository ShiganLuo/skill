# STAR scRNA-seq parameter pitfalls

## limitSjdbInsertNsj

Default is 1,000,000. For large scRNA-seq datasets (especially primates), the 2-pass Basic mode can detect >2M junctions in the first pass, causing:

```
Fatal LIMIT error: the number of junctions to be inserted on the fly =2115807 is larger than the limitSjdbInsertNsj=1000000
SOLUTION: re-run with at least --limitSjdbInsertNsj 2115807
```

Fix: set `"limitSjdbInsertNsj": 3000000` in config. Must also be passed through subworkflow config dict (see subworkflow-config-propagation-pitfall.md).

## soloBarcodeReadLength

Default check validates barcode read length matches expected. If actual read length differs (e.g. 150bp vs expected 98bp):

```
FATAL ERROR: barcode sequence length is 150, not equal to expected 98
SOLUTION: specify --soloBarcodeReadLength 0 to avoid checking
```

Fix: set `"soloBarcodeReadLength": 0` to skip validation. STAR will use whatever barcode sequence it finds. Safe for 10X data — STAR matches against whitelist regardless of read length.

## outMultimapperOrder capitalization

STAR expects `Random` (capital R), not `random`. Snakemake detects param changes and re-runs if casing differs.
