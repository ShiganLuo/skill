# site.txt Format and Parsing

## Column Layout (0-indexed)

| Index | Name | Type | Description |
|-------|------|------|-------------|
| 0 | chromosome | str | Chromosome name |
| 1 | location | int | Genomic position |
| 2 | repeat_unit_length | int | Length of repeat unit (1=homopolymer, 2-6=microsatellite) |
| 3 | repeat_unit_binary | int | Binary-encoded repeat unit |
| 4 | repeat_times | int | **REFERENCE** repeat count |
| 5 | left_flank_binary | int | Binary-encoded left flank |
| 6 | right_flank_binary | int | Binary-encoded right flank |
| 7 | repeat_unit_bases | str | Repeat unit sequence (e.g., "AC", "GAA") |
| 8 | left_flank_bases | str | Left flank sequence |
| 9 | right_flank_bases | str | Right flank sequence |
| 10 | repeat_dict | str | Distribution "obs_count:read_count,..." |
| 11 | depth | int | Total reads at this locus |

## Critical Parsing Detail

The `repeat_dict` (col 10) uses **OBSERVED** repeat counts as keys, NOT reference.

Example:
```
repeat_times = 8        (reference)
repeat_dict = "6:2,7:17,8:159,9:1"
depth = 179
```

This means:
- 2 reads with 6 repeats
- 17 reads with 7 repeats
- 159 reads with 8 repeats (matches reference)
- 1 read with 9 repeats

Correct alt_ratio calculation:
```python
counts = {6: 2, 7: 17, 8: 159, 9: 1}
ref_count = counts.get(repeat_times, 0)  # counts.get(8, 0) = 159
alt_ratio = 1 - ref_count / depth        # 1 - 159/179 = 0.112
```

**WRONG** approach (using observed max):
```python
# DO NOT do this
max_observed = max(counts.keys())  # 9
ref_count = counts.get(max_observed, 0)  # Wrong!
```

## Pandas Reading

```python
df = pd.read_csv(site_file, sep='\t', header=None)
# df.shape = (n_loci, 12)

# Access columns
repeat_times = df.iloc[:, 4]
repeat_dict = df.iloc[:, 10]
depth = df.iloc[:, 11]
unit_len = df.iloc[:, 2]
```

## Feature Extraction Example

```python
def extract_locus_features(row):
    repeat_times = int(row[4])
    dist_str = str(row[10])
    depth = int(row[11])
    unit_len = int(row[2])
    
    if depth < 10:  # min depth filter
        return None
    
    # Parse distribution
    counts = {}
    for item in dist_str.split(','):
        parts = item.split(':')
        if len(parts) == 2:
            counts[int(parts[0])] = int(parts[1])
    
    if not counts:
        return None
    
    # Reference count
    ref_count = counts.get(repeat_times, 0)
    alt_ratio = 1 - ref_count / depth
    
    # Entropy
    probs = np.array(list(counts.values())) / depth
    entropy = -np.sum(probs * np.log2(probs + 1e-10))
    
    # Max shift
    observed = np.array(list(counts.keys()))
    max_shift = np.max(np.abs(observed - repeat_times))
    
    return {
        'unit_len': unit_len,
        'repeat_times': repeat_times,
        'depth': depth,
        'alt_ratio': alt_ratio,
        'entropy': entropy,
        'max_shift': max_shift,
    }
```

## Sample-Level Aggregation

```python
def aggregate_locus_features(locus_features_list):
    lf = pd.DataFrame(locus_features_list)
    
    return {
        'n_loci': len(lf),
        'mean_alt': lf['alt_ratio'].mean(),
        'max_alt': lf['alt_ratio'].max(),
        'median_alt': lf['alt_ratio'].median(),
        'q90_alt': lf['alt_ratio'].quantile(0.9),
        'mean_entropy': lf['entropy'].mean(),
        'max_entropy': lf['entropy'].max(),
        'mean_shift': lf['max_shift'].mean(),
        'max_shift': lf['max_shift'].max(),
        'high_alt_ratio': (lf['alt_ratio'] > 0.5).mean(),
    }
```

## Discrimination Power

From BL dataset (CRC, n=3221):
- `mean_alt_ratio`: AUC = 0.976
- `mean_entropy`: AUC = 0.972
- `high_alt_ratio`: AUC = 0.978

Single-feature performance is very strong. Multi-feature anomaly detection often performs worse due to noise from non-sensitive loci.
