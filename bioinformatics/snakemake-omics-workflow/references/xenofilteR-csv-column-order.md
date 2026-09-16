# XenofilteR CSV Column Order Pitfall

## The bug

XenofilteR's CSV input has two columns: graft (first) and host (second). The `filterBam` call writes the output BAM from the **graft** column (first). Swapping the columns causes the output BAM to contain the contaminant genome's contigs.

## Correct order

```
host_bam,contaminant_bam    # CORRECT — output is host (target) BAM
```

## Wrong order

```
contaminant_bam,host_bam    # WRONG — output is contaminant BAM
```

## Source code evidence

From XenofilteR R package `ActualFilter` function:

```r
Human <- scanBam(sample.paths.graft[i])   # reads graft = first CSV column
Mouse <- scanBam(sample.paths.host[i])    # reads host = second CSV column
# ... filtering logic ...
filterBam(sample.paths.graft[i], destination, filter = filt)  # writes from graft
```

The variable naming (`Human` = graft, `Mouse` = host) is confusing but the key is `filterBam` reads from `sample.paths.graft[i]` = CSV first column.

## How to inspect R package source in singularity containers

```bash
cat > /tmp/dump.R << 'EOF'
library(XenofilteR)
sink("/tmp/body.txt")
print(body(XenofilteR))
sink()
EOF
singularity exec <sif> Rscript /tmp/dump.R
cat /tmp/body.txt
```

Inline `Rscript -e` has shell escaping issues — use temp file approach.

## Diagnosis

GATK SplitNCigarReads reports `incompatible contigs` with different chromosome lengths between reference and reads — check XenofilteR output BAM header:

```bash
singularity exec <star.sif> samtools view -H <output.bam> | grep "^@SQ" | head -5
```

If the BAM has contigs from the wrong genome, the CSV column order is the likely cause.