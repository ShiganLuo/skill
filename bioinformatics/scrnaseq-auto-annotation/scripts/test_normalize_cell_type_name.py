#!/usr/bin/env python3
"""Unit tests for _normalize_cell_type_name.

The normalizer is tissue-agnostic: it maps any LLM-returned cell type name
to a canonical entry in the dynamically-built `tissue_cell_types` dict
(no hardcoded marker dictionaries). This script exercises the four match
strategies: exact, case-insensitive, suffix-stripped, and substring.

Usage:
    python test_normalize_cell_type_name.py

Exit codes:
    0 - all tests pass
    1 - one or more tests fail
"""
import importlib
import sys
from pathlib import Path

SCANPY_BIN = Path("/home/luosg/Data/genomeStability/workflow/Omics/modules/scanpy/bin")

# Mock tissue_cell_types from the Step 0 query of a real macaque ovary run.
# Keys are the canonical names; values are marker lists (not used by the
# normalizer, only included for shape parity with the real dict).
TISSUE_CELL_TYPES = {
    "Granulosa cells": ["FOXL2", "CYP19A1", "AMH"],
    "Theca cells": ["CYP17A1", "STAR", "HSD3B2"],
    "Smooth muscle cells": ["ACTA2", "MYH11", "TAGLN"],
    "Endothelial cells": ["PECAM1", "VWF", "CDH5"],
    "Fibroblasts": ["DCN", "COL1A1", "PDGFRB"],
    "Macrophages": ["CD68", "CD163", "CSF1R"],
    "T cells": ["CD3E", "CD3D", "CD3G"],
}

# (raw_input, expected_normalized)
CASES = [
    # Strategy 1 — exact match
    ("Granulosa cells", "Granulosa cells"),
    ("Smooth muscle cells", "Smooth muscle cells"),
    # Strategy 2 — case-insensitive
    ("granulosa cells", "Granulosa cells"),
    ("FIBROBLASTS", "Fibroblasts"),
    # Strategy 3 — suffix stripping
    ("Granulosa-like", "Granulosa cells"),
    ("Theca-like", "Theca cells"),
    ("Tcell", "T cells"),
    ("T_cell", "T cells"),
    ("Fibroblast", "Fibroblasts"),
    ("Macrophage", "Macrophages"),
    # Strategy 4 — substring
    ("Smooth_muscle", "Smooth muscle cells"),
    ("Smooth muscle", "Smooth muscle cells"),
    # No match — kept as-is
    ("Unknown", "Unknown"),
    ("Brand_new_type", "Brand_new_type"),
    # Edge cases
    ("", ""),
]


def main():
    sys.path.insert(0, str(SCANPY_BIN))
    try:
        import scRNAseq as scr
    except ImportError as e:
        print(f"FAIL: cannot import scRNAseq from {SCANPY_BIN}: {e}", file=sys.stderr)
        return 1

    importlib.reload(scr)

    normalize = scr._normalize_cell_type_name

    failures = []
    for raw, expected in CASES:
        got, changed = normalize(raw, TISSUE_CELL_TYPES)
        status = "OK" if got == expected else "FAIL"
        if got != expected:
            failures.append((raw, expected, got))
        print(f"  [{status}] {raw!r:25s} -> {got!r:25s} (changed={changed}, expected {expected!r})")

    total = len(CASES)
    passed = total - len(failures)
    print(f"\n{passed}/{total} pass")
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
