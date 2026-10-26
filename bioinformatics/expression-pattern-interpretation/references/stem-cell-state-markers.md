# Stem cell state / lineage / contamination marker panels

For triage step 4 of expression-pattern-interpretation. Values read on log2(TPM+1).

## Pluripotency network (naive)
Pou5f1 (Oct4), Nanog, Sox2, Esrrb, Klf4, Tbx3, Dppa3

## 2C / early-embryo program
Zscan4d (and Zscan4 family), Tcstv1, Tcstv3, Dux, Dppa3, Eif4a3l2, Gm29216 (mouse), MuERVL/MT2_Mm TE expression
Deep 2C-like state signature: these high AND pluripotency network (Sox2/Esrrb/Nanog) collapsed.

## Primed / epiblast
Fgf5, Otx2, Dnmt3a, Dnmt3b (Oct4 high, Esrrb low)

## Primitive endoderm (PrE)
Gata6, Gata4, Sox7, Sox17, Foxa2, Pdgfra

## Trophectoderm (TE)
Cdx2, Eomes, Elf5, Gata3, Hand1, Krt8, Krt18

## Feeder / fibroblast contamination
Col1a1, Col1a2, Fn1, Ddr2, Pdgfra. Human cultures on mouse feeder show mouse reads — check the meta `contaminated_organism` column and mouse-read fraction. Note some ESC lines retain collagen expression without contamination — check several markers, not one.

## QC context
Detected genes (TPM>1), top-5 expressed genes and their TPM share (composition effect), mitochondrial gene share.

## Reading rules
- Module heatmap color fibroblast-like BUT collagen/Pdgfra low → not contamination; go to state markers.
- Identity correct + state markers shifted + lineage markers flat → state effect on the module (check step 5 specificity before claiming pathway regulation).