#!/usr/bin/env python3
"""Production reference: filter intron/UTR regions from depth files using BED annotation.

This is the script produced in the 2026-06-12 session that handles:
- 833K-row BED file (ncbi_anno_rel104_db_b37_TXS_IVS.bed)
- 66 depth files × 5GB each (~52M lines per file)
- Parallel processing via ProcessPoolExecutor

Key decisions:
1. Sorted arrays + bisect_right instead of IntervalTree (no zero-width bug, cache-friendly)
2. BED [s, e) -> 1-based [s+1, e] (NOT [s+1, e-1])
3. Module-level _worker + _init_worker for multiprocessing (pickle compatibility)
4. Line-by-line streaming with maxsplit for constant memory

Usage:
    python filter_intron_utr.py \
        --bed /path/to/ncbi_anno_rel104_db_b37_TXS_IVS.bed \
        --depth-dir /path/to/depth/ \
        --output-dir /path/to/output/ \
        --workers 4
"""
