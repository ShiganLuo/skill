# StringTie Gene Abundance Merging

## Working Script: merge_stringtie_abundance.py

Usage:
```
python3 merge_stringtie_abundance.py <gene_abundance.tsv> [-o output.tsv]
```

Default output: `<input>_merged.tsv`

### Script

```python
#!/usr/bin/env python3
"""Aggregate StringTie gene_abundance.tsv by gene_id.

Merging rules:
  - TPM:       direct sum (per-million normalization preserves additivity)
  - FPKM:      direct sum (per-gene normalization preserves additivity)
  - Coverage:  length-weighted average across regions
  - Start/End: min start / max end of merged loci (int type)
"""

from __future__ import annotations

import argparse
import csv
import sys
from collections import defaultdict, OrderedDict
from pathlib import Path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Merge duplicate StringTie gene abundance rows by gene_id."
    )
    p.add_argument("input", help="Path to StringTie gene_abundance.tsv")
    p.add_argument("-o", "--output", default=None,
                   help="Output file path (default: <input>_merged.tsv)")
    return p.parse_args()


def load_abundance(path: str) -> tuple[list[str], list[dict]]:
    rows: list[dict] = []
    header: list[str] = []

    with open(path) as fh:
        reader = csv.reader(fh, delimiter="\t")
        header = next(reader)
        header = [h.strip() for h in header]

        first_row = next(reader)
        if first_row[0].lower() in ("gene_id", "gene id"):
            pass  # skip repeated header
        else:
            rows.append(_row_to_dict(header, first_row))

        for line in reader:
            if not line or not line[0].strip():
                continue
            rows.append(_row_to_dict(header, line))

    return header, rows


def _row_to_dict(header: list[str], fields: list[str]) -> dict:
    d = {}
    for i, col in enumerate(header):
        val = fields[i].strip() if i < len(fields) else ""
        if col in ("Start", "End"):
            try:
                d[col] = int(val)
            except ValueError:
                d[col] = val
        elif col in ("Coverage", "FPKM", "TPM"):
            try:
                d[col] = float(val)
            except ValueError:
                d[col] = val
        else:
            d[col] = val
    return d


def merge_rows(header: list[str], rows: list[dict]) -> list[dict]:
    gene_id_col = "Gene ID" if "Gene ID" in header else "gene_id"
    gene_name_col = "Gene Name" if "Gene Name" in header else "gene_name"
    ref_col = "Reference" if "Reference" in header else "ref"
    strand_col = "Strand" if "Strand" in header else "strand"

    groups: dict[str, list[dict]] = OrderedDict()
    for row in rows:
        gid = row[gene_id_col]
        if gid not in groups:
            groups[gid] = []
        groups[gid].append(row)

    merged: list[dict] = []
    for gid, group in groups.items():
        if len(group) == 1:
            merged.append(group[0])
            continue

        ref_row = group[0]
        lengths = [r["End"] - r["Start"] for r in group]
        total_length = sum(lengths)

        if total_length > 0:
            coverage = sum(r["Coverage"] * l for r, l in zip(group, lengths)) / total_length
        else:
            coverage = 0.0

        tpm = sum(r["TPM"] for r in group)
        fpkm = sum(r["FPKM"] for r in group)

        merged.append({
            gene_id_col: gid,
            gene_name_col: ref_row[gene_name_col],
            ref_col: ref_row[ref_col],
            strand_col: ref_row[strand_col],
            "Start": min(r["Start"] for r in group),
            "End": max(r["End"] for r in group),
            "Coverage": round(coverage, 6),
            "FPKM": round(fpkm, 6),
            "TPM": round(tpm, 6),
        })

    return merged


def write_output(header: list[str], rows: list[dict], path: str) -> None:
    with open(path, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=header, delimiter="\t",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    args = parse_args()
    in_path = args.input

    if args.output:
        out_path = args.output
    else:
        p = Path(in_path)
        out_path = str(p.with_name(p.stem + "_merged.tsv"))

    header, rows = load_abundance(in_path)
    n_before = len(rows)

    merged = merge_rows(header, rows)
    n_after = len(merged)

    write_output(header, merged, out_path)

    n_dup = n_before - n_after
    if n_dup > 0:
        print(f"Merged {n_dup} duplicate gene rows ({n_before} -> {n_after})")
    else:
        print(f"No duplicate gene_ids found. Output unchanged ({n_after} rows).")

    print(f"Output: {out_path}")


if __name__ == "__main__":
    main()
```

## Example: COPG2

COPG2 (ENSG00000158623) has transcripts in two non-overlapping regions:
- Region 1: chr7:130,146,089-130,148,500 (~2.4kb, transcripts COPG2-001/COPG2-003)
- Region 2: chr7:130,295,820-130,353,598 (~58kb, transcripts COPG2-201/COPG2-002)
- Gap: ~147kb with no shared exonic overlap

StringTie output (two rows):
```
ENSG00000158623  COPG2  7  -  130146089  130148500  95.105  10.416  24.145
ENSG00000158623  COPG2  7  -  130295820  130353598  93.046   7.077  16.404
```

Merged result:
```
ENSG00000158623  COPG2  7  -  130146089  130353598  93.126  17.493  40.549
Coverage weighted: (95.105*2411 + 93.046*57778) / (2411+57778) ≈ 93.13
```
