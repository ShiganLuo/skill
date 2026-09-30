# Fast GTF Attribute Parsing for Large Annotation Files

When parsing GTF/GFF files with millions of lines (Ensembl annotation 500MB+, RepeatMasker TE GTF 600MB+ with 4M+ rows), `pandas.read_csv` + `Series.str.extract` is **fine**. First try them in pandas before reaching for a streamed Python parser.

> **Updated 2026-09:** Previous versions of this file recommended a stream-loop rewrite. The user pushed back — readability is worth more than 1.4-1.6x warm-cache speedup. The right answer is **pandas-only micro-optimizations** that preserve idiomatic style: `usecols=[N]` + filter-first.

## When this matters

- Ensembl GENCODE/ENSEMBL gene GTF (~500MB, ~3M rows, many duplicated gene_id lines across exons/transcripts)
- RepeatMasker-derived TE GTF (`rheMac10_rmsk_TE.gtf`-style, 600MB, 4M+ rows, attributes carry `family_id`/`class_id`)
- Any GTF where you only need a few columns + a few attribute keys (most summarization scripts)

If you only have a small GTF (<10MB) or need every column for downstream work, `pandas.read_csv` is fine — no optimization needed.

## Benchmark (real measurements on user files, 2026-09)

**Warm cache** (file already in OS page cache from a recent run):

| File | Function | pandas + regex | stream + split | Speedup |
|---|---|---|---|---|
| Ensembl GTF 542MB | extract unique (gene_id, gene_name, gene_type) | 12.04s | 7.63s | 1.6x |
| RepeatMasker TE GTF 613MB / 4.5M rows | per-segment (chrom, start, end, strand, gene_id, family_id, class_id) | 23.95s | 17.68s | 1.4x |

**Cold cache** (fresh disk read on each run — closer to real interactive use):

| File | pandas baseline | pandas + `usecols` + filter-first | Speedup |
|---|---|---|---|
| Ensembl GTF 542MB | 13.45s | 11.35s | 1.19x |
| RepeatMasker TE GTF 613MB / 4.5M rows | 26.86s | 24.82s | 1.08x |
| Human TE GTF 740MB / 4.8M rows | ~30s | 31.71s | ~1.0x (no benefit) |

The stream-loop version is faster in warm cache but only marginally faster in cold cache, and it costs significant readability. **The decision rule is:**

- **<2x speedup on a script that runs once a week or less** → not worth refactoring. Optimize inside pandas instead (see below).
- **>2x speedup, or runs in a hot path (per-sample N× in a Snakemake rule)** → consider `pyranges` (C extension, ~5x faster) before reaching for a hand-rolled Python loop.
- **Per-line attribute parsing inside a loop is unavoidable** (e.g. embedded in a per-row generator) → use the `_parseAttrs` helper below — it's ~10x faster than regex per attribute string and replaces a `re.search` cleanly.

## Recommended: pandas-only micro-optimizations

These preserve idiomatic style and give 10-20% speedup:

### `usecols=[N]` — skip parsing unused columns

```python
# Instead of:
gtf = pd.read_csv(gtf_path, sep="\t", comment="#", header=None, low_memory=False,
    names=["seqname", "source", "feature", "start", "end", "score", "strand", "frame", "attribute"])

# If you only need gene_id/gene_name/gene_type from the attribute column:
gtf = pd.read_csv(gtf_path, sep="\t", comment="#", header=None,
    names=["seqname", "_b", "_c", "_d", "_e", "_f", "_g", "_h", "attribute"],
    usecols=[8],  # column index, NOT name — when header=None, usecols takes positions
)
```

`usecols` skips type inference and parsing for the unused columns. ~1.2x on Ensembl; helps whenever you're extracting only a few attributes.

**Pitfall:** With `header=None, names=...`, `usecols` accepts **column positions** (`[8]`), NOT names (`["attribute"]`). pandas will raise if you pass names. LSP/pyright may also flag `list[int]` as incompatible — this is a pyright/pandas-stubs false positive; runtime accepts both.

### Filter-first — extract cheap column, dropna, then extract rest

```python
# Instead of: extract all 3 attrs, then dropna on gene_id
gtf["gene_id"]    = gtf["attribute"].str.extract(r'gene_id\s*"(.*?)"')
gtf["family_id"]  = gtf["attribute"].str.extract(r'family_id\s*"(.*?)"')
gtf["class_id"]   = gtf["attribute"].str.extract(r'class_id\s*"(.*?)"')
gtf = gtf.dropna(subset=["gene_id"])  # only now do we know what survived

# Do: extract the cheap filter column first, then the rest on the subset
gtf["gene_id"] = gtf["attribute"].str.extract(r'gene_id\s*"(.*?)"')
gtf = gtf.dropna(subset=["gene_id"])  # ~halves the frame on Ensembl; near-identical on TE GTFs (where almost every row has gene_id)
gtf["family_id"] = gtf["attribute"].str.extract(r'family_id\s*"(.*?)"')
gtf["class_id"]  = gtf["attribute"].str.extract(r'class_id\s*"(.*?)"')
```

Filter-first is helpful when a meaningful fraction of rows lack the filter attribute (Ensembl: many comment/region rows lack `gene_id`; helps a lot). On TE GTFs where every row has `gene_id`, filter-first still wins by a small margin (~1.08x) — worth keeping for consistency.

### Things that DON'T help (or hurt)

- **`dtype=dict`** — forcing `int32`/etc. costs more than the inference it avoids on typical GTF data. Don't bother.
- **`low_memory=False`** alone — doesn't help read speed; only suppresses mixed-type warnings.
- **PyArrow backend** — `pd.read_csv(..., engine="pyarrow")` is often faster but adds a dependency; not worth it for a script that runs once a month.

## When you DO need stream-loop (rare)

Use a streamed Python parser + `_parseAttrs` helper ONLY when:
- The script is in a per-sample Snakemake rule that gets called N× times
- The GTF parsing is embedded inside a per-row generator (e.g. yielding rows to a downstream streaming consumer)
- You're explicitly told "this needs to be fast" and the user has confirmed the readability tradeoff

In those cases, the `_parseAttrs` helper below is genuinely useful — it replaces a regex per attribute string with a couple of `str.split` calls.

### `_parseAttrs` helper

```python
def _parseAttrs(attr: str) -> dict:
    """Fast GTF attribute parser: key "value"; key "value"; -> dict.

    ~10x faster than regex per attribute string. Assumes well-formed GTF:
    keys separated by '; ', values quoted with ".
    """
    out = {}
    if not attr:
        return out
    for part in attr.rstrip(';\n').split('; '):
        if not part:
            continue
        sp = part.split(' ', 1)
        if len(sp) != 2:
            continue
        k, v = sp[0], sp[1]
        if len(v) >= 2 and v[0] == '"' and v[-1] == '"':
            v = v[1:-1]
        out[k] = v
    return out
```

### Stream-parse template (only when needed)

```python
def geneIDAnnotation(gtf_path):
    gids, gnames, gtypes = [], [], []
    seen = set()
    with open(gtf_path, 'r') as fh:
        for line in fh:
            if not line or line[0] == '#':
                continue
            parts = line.rstrip('\n').split('\t', 8)
            if len(parts) < 9:
                continue
            attr = _parseAttrs(parts[8])
            gid = attr.get('gene_id')
            if gid is None:
                continue
            gname = attr.get('gene_name', '')
            gtype = attr.get('gene_type')
            if gtype is None:
                gtype = attr.get('gene_biotype', '')
            if not gname or not gname.strip():
                gname = gid
            key = (gid, gname, gtype)
            if key in seen:
                continue
            seen.add(key)
            gids.append(gid); gnames.append(gname); gtypes.append(gtype)
    import pandas as pd
    return pd.DataFrame({"gene_id": gids, "gene_name": gnames, "gene_type": gtypes})
```

Key tricks:
- `split('\t', 8)` instead of `split('\t')` — preserves seqname fields with tabs in them (rare but possible)
- Append to parallel Python lists, then construct the DataFrame once at the end
- For BED output, do `int(parts[3]) - 1` inline to convert 1-based inclusive → 0-based half-open as you read

## TE GTF subfamily ambiguity

When collapsing per-segment TE rows to per-gene mappings (e.g. `teBed` → `adata.var['family_id']`), expect **inconsistent annotations for the same subfamily**:

- Human TE BED (`GRCh38_GENCODE_rmsk_TE.bed`, 4.8M rows, 1278 unique subfamilies): ~52 subfamilies (4%) appear with two or more different `(family_id, class_id)` pairs. Examples:
  - `MamRep137` → `(TcMar-Tigger, DNA)` OR `(TcMar, DNA)`
  - `MER63C` → `(hAT-Tip100, DNA)` OR `(hAT-Blackjack, DNA)`
  - `MamRep605` → `(LTR, LTR?)` OR `(LTR, LTR)`
- These are RepeatMasker parent/child reclassifications across the annotation history.

**Pick a tiebreaker explicitly when building per-gene mappings.** Options (in increasing complexity):
- **First wins** (default — keeps the first occurrence's pair, deterministic, matches the previous `set`-based behavior where a gene was either TE or not)
- **Most-frequent wins** (majority vote across all segments of that subfamily — more accurate for genuinely-moved subfamilies but slower)
- **Multi-value retention** (store all pairs as a list per gene — usually not what you want)

Always document the choice in the docstring. The TE BED writer at `/home/<USER>/Data/genomeStability/workflow/Omics/src/annotation/geneIDAnntation.py:teBed` uses first-wins; downstream `annotate_gene_type` reads that dict and stores it in `adata.var["family_id"]` / `adata.var["class_id"]`.

## When NOT to use either approach

- Need to filter by `feature == 'exon'` or `source == 'rheMac10_rmsk'` — load pandas with `low_memory=False` and filter there
- File is <50MB — pandas is fast enough, simplicity wins
- Need to do operations across columns (joins, groupby on coordinates) — use `pyranges` instead
- Need to handle malformed attributes (unquoted, missing semicolons) — fall back to regex with try/except per line

## Pitfalls

- **`usecols` with `header=None`** — takes `[N]` positions, not `["attribute"]`. pyright/pandas-stubs may flag `list[int]` as incompatible — false positive; runtime accepts both.
- **`_parseAttrs` assumes well-formed GTF.** If you see malformed entries (unquoted values, missing semicolons), wrap with try/except and fall back to `re.search`. In practice this almost never happens with Ensembl/RepeatMasker output.
- **Coordinate system.** GTF is 1-based inclusive, BED is 0-based half-open. The helper above does the `-1` conversion inline. If your downstream expects GTF coords (e.g. HOMER), skip the conversion.
- **Empty gene_name fallback.** Ensembl sometimes has `gene_name ""` — replace with `gene_id` so downstream lookup keys stay consistent:
  ```python
  if not gname or not gname.strip():
      gname = gid
  ```
- **Mixed-type warnings.** When you do fall back to `pd.read_csv`, pass `low_memory=False` or you'll get `Columns (X) have mixed types` DtypeWarning on chromosomes longer than 500MB.
- **Don't dedupe the TE GTF.** RepeatMasker output has many segment lines per TE locus — keep all of them (BED-style per-exon), don't collapse to one row per `gene_id`. If you need per-locus ranges, groupby with `agg({'start': 'min', 'end': 'max'})` in a separate function.
- **Categorical dtype for low-cardinality annotation columns.** When TE `family_id`/`class_id` columns are stored in `adata.var`, use `pd.Categorical(values)` — only 5-20 unique values across thousands of genes, so category storage is much smaller and downstream `.cat.categories` ordering works. The scRNA-seq codebase uses `.astype("category")` for `cell_type`, `sample_id`, `batch`; match that convention.

## Reference implementation

See `/home/<USER>/Data/genomeStability/workflow/Omics/src/annotation/geneIDAnntation.py` — functions `geneIDAnnotation` and `teBed` are the canonical pandas-style examples with `usecols` + filter-first, `gene_name` fallback, and 0-based BED conversion built in.