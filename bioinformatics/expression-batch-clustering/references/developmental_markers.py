"""
Marker genes for early embryo developmental stages and stem cells.
Based on published literature on human preimplantation development.

References:
- Yan et al. (2013) Cell Stem Cell - single-cell RNA-seq of human embryos
- Blakeley et al. (2015) Development - human embryo transcriptome
- Petropoulos et al. (2016) Cell - single-cell transcriptome of human embryos
- Stirparo et al. (2018) Cell Stem Cell - pluripotency markers
- Taft et al. (2019) Nature - totipotency markers
"""

# Oocyte-specific markers
OOCYTE_MARKERS = [
    "ZP1", "ZP2", "ZP3", "ZP4",           # zona pellucida
    "GDF9", "BMP15",                        # oocyte-secreted factors
    "FIGLA", "NOBOX", "SOHLH1", "SOHLH2",  # oocyte TFs
    "H1FOO", "OOEP", "FLOPED", "TLE6",     # oocyte-specific
    "BMPR2", "MOS", "WEE2",                 # oocyte signaling
    "PATL2", "TUBB8",                       # oocyte maturation
]

# Zygote markers (fertilization, maternal-to-zygotic transition)
ZYGOTE_MARKERS = [
    "DPPA3", "PADI6", "NLRP5", "KHDC1L",   # maternal factors
    "STELLA", "MATER",                       # zygote-specific
    "TRIM36", "BRDT",                        # zygote expressed
    "ZPBP2", "IZUMO1",                       # fertilization
]

# 2-cell markers (major zygotic genome activation, ZGA)
TWO_CELL_MARKERS = [
    "ZSCAN4", "ZSCAN4C",                     # ZGA marker
    "DUX", "DUX4",                           # double homeobox (ZGA driver)
    "LEUTX", "TPRX1", "TPRX2",             # ZGA TFs
    "PRAMEF1", "PRAMEF2",                   # PRAME family
    "MBD3L2", "MBD3L3",                     # ZGA-associated
    "KHDC3", "TDRD5",                       # 2-cell specific
    "OTOP1", "FOXI1",                       # early ZGA
    "TMEM92", "C2orf16",                    # novel ZGA genes
]

# 4-cell markers (minor ZGA, transition)
FOUR_CELL_MARKERS = [
    "MBD3L2", "TRIM60",                     # 4-cell enriched
    "NLRP7", "NLRP2",                       # NACHT family
    "USP17", "USP17L2",                    # ubiquitin pathway
    "ZNF675", "ZNF676",                    # zinc finger
]

# 8-cell markers (compaction begins, major EGA)
EIGHT_CELL_MARKERS = [
    "GATA3", "GATA4",                       # GATA family
    "SOX17", "HNF4A",                       # endoderm priming
    "KLF17",                                # 8-cell specific TF
    "DPPA2", "DPPA5",                      # developmental pluripotency
    "BNC2", "BNC1",                        # transcription factors
]

# Morula markers (compaction, cell polarization)
MORULA_MARKERS = [
    "CDX2", "TEAD4", "YAP1",              # TE specification
    "KRT18", "KRT8",                       # cytoskeleton
    "GATA3",                               # trophectoderm
    "PKP1", "PKP3",                        # desmosomes
    "TJP1", "OCLN",                        # tight junctions
]

# Blastocyst ICM markers (inner cell mass)
BLASTOCYST_ICM_MARKERS = [
    "NANOG", "POU5F1", "SOX2",             # core pluripotency
    "KLF4", "TBX3", "ESRRB",              # pluripotency network
    "FGF4", "GDF3", "LEFTY2",             # signaling
    "PRDM14", "TCL1A",                     # ICM-specific
    "DNMT3A", "DNMT3B",                    # epigenetic
    "SALL4", "ZFP42",                      # pluripotency
]

# Blastocyst TE markers (trophectoderm)
BLASTOCYST_TE_MARKERS = [
    "CDX2", "GATA3", "EOMES",             # TE TFs
    "KRT18", "KRT8", "KRT7",             # cytoskeleton
    "GCM1", "HAND1", "DLX3",             # TE differentiation
    "ELF5", "TFAP2C",                      # TE-specific
    "ITGA6", "ITGB4",                      # TE surface
]

# hESC markers (pluripotent stem cells)
HESC_MARKERS = [
    "NANOG", "POU5F1", "SOX2",             # core pluripotency
    "KLF4", "KLF2", "KLF5",              # KLF family
    "TDGF1", "DPPA4", "DPPA5",           # pluripotency surface
    "LIN28A", "LIN28B",                    # RNA binding
    "DNMT3B", "TERT",                      # epigenetic/telomere
    "ESRRB", "TFCP2L1",                    # naive pluripotency
    "PRDM14", "TCL1A",                     # hESC-specific
]

# Totipotency markers (ci8CLC, ciTotiSC)
TOTIPOTENCY_MARKERS = [
    "ZSCAN4", "ZSCAN4C",                   # totipotency marker
    "DUX", "DUX4",                         # totipotency driver
    "LEUTX", "TPRX1",                     # ZGA TFs
    "TP63",                                # totipotency
    "HMGA1", "HMGA2",                     # chromatin
    "TBX3", "TFCP2L1",                    # totipotency network
    "GBX2", "NR5A2",                      # totipotency TFs
]

# prEpiSC markers (primed pluripotency, epiblast)
PRPESC_MARKERS = [
    "FGF5", "EOMES", "OTX2",             # primed state
    "SOX17", "GATA6",                     # primitive endoderm
    "NANOG", "POU5F1",                    # maintained pluripotency
    "DUSP6", "ETV5",                      # FGF signaling
    "CDX2", "GATA3",                      # some TE markers
]

# Mouse-specific markers (for mouse data)
MOUSE_TOTIPOTENCY_MARKERS = [
    "Zscan4", "Zscan4c",
    "Dux", "Duxbl",
    "Tcstv1", "Tcstv3",
    "Gm12840", "Gm13421",
    "Eif1a", "Eif1ad",
]

MOUSE_EMBRYO_MARKERS = {
    "Zygote": ["Stella", "Mater", "Zar1"],
    "Early-2-cell": ["Zscan4", "Dux", "Eif1a"],
    "Mid-2-cell": ["Zscan4", "Dux", "Tcstv1"],
    "Late-2-cell": ["Zscan4", "Dux", "Gm12840"],
    "4-cell": ["Mbd3l2", "Trim60"],
    "8-cell": ["Gata3", "Sox17", "Cdx2"],
    "16-cell": ["Cdx2", "Gata3", "Tead4"],
    "Early-blastocyst": ["Nanog", "Pou5f1", "Sox2"],
    "Mid-blastocyst": ["Nanog", "Pou5f1", "Cdx2"],
    "Late-blastocyst": ["Nanog", "Pou5f1", "Cdx2", "Gata3"],
}


def get_human_markers():
    """Return all human marker genes grouped by stage."""
    return {
        "Oocyte": OOCYTE_MARKERS,
        "Zygote": ZYGOTE_MARKERS,
        "2-cell": TWO_CELL_MARKERS,
        "4-cell": FOUR_CELL_MARKERS,
        "8-cell": EIGHT_CELL_MARKERS,
        "Morula": MORULA_MARKERS,
        "Blastocyst_ICM": BLASTOCYST_ICM_MARKERS,
        "Blastocyst_TE": BLASTOCYST_TE_MARKERS,
        "hESC": HESC_MARKERS,
        "ci8CLC": TOTIPOTENCY_MARKERS,
        "prEpiSC": PRPESC_MARKERS,
    }


def get_all_human_markers():
    """Return flat list of all unique human marker genes."""
    markers = set()
    for gene_list in get_human_markers().values():
        markers.update(gene_list)
    return sorted(markers)


def get_mouse_markers():
    """Return mouse marker genes grouped by stage."""
    return MOUSE_EMBRYO_MARKERS


if __name__ == "__main__":
    human = get_human_markers()
    print("Human marker genes by stage:")
    for stage, genes in human.items():
        print(f"  {stage}: {len(genes)} genes")
    print(f"\nTotal unique human markers: {len(get_all_human_markers())}")
    print("\nAll markers:", ", ".join(get_all_human_markers()))
