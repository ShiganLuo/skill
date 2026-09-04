# MetaUtil.prepare_scRNAseq_meta — Multi-lane scRNAseq FASTQ handling

## Input format (meta_input.tsv)

```tsv
sample_id	design	group	fastq_dir	sample_prefix	organism
sampleA	ctr_age	youth	/path/to/Rawdata/sampleA	sampleA	mulatta
sampleB	ctr_POI	POI	/path/to/Rawdata/sampleB	sampleB	mulatta
```

One row per sample. Multi-lane files are in the same `fastq_dir` directory.

## What the function does

1. Scans `fastq_dir` for files matching `sample_prefix` + `fq_pattern` (default: `_R?([12])_\d+\.f(ast)?q\.gz$`)
2. Groups by read number (R1/R2)
3. Single-lane: symlink to `raw_fq_dir/{sample_id}/{sample_id}_{1,2}.fq.gz`
4. Multi-lane: cat-merge all R1 into one file, R2 same
5. Populates `samples_dict` with:
   - `fastq_1` / `fastq_2`: merged paths (STARsolo uses these via `--readFilesIn`)
   - `fastq_dir` / `sample_prefix`: original dir+prefix (Cell Ranger uses via `--fastqs`/`--sample`)
   - `layout`: auto-detected PE/SE
   - `design` / `group` / `organism`: from meta

## Output structure

```
raw_fq_dir/
  sampleA/
    sampleA_1.fq.gz  → symlink to single R1
    sampleA_2.fq.gz  → symlink to single R2
  sampleB/
    sampleB_1.fq.gz  ← cat merge of 3 lane R1 files
    sampleB_2.fq.gz  ← cat merge of 3 lane R2 files
```

## Cell Ranger vs STARsolo usage

- **Cell Ranger**: `--fastqs ${samples_dict[s].fastq_dir} --sample ${samples_dict[s].sample_prefix}`
  - Cell Ranger auto-discovers files by naming convention, no manual merge needed
  - Naming MUST be `{prefix}_S{samp}_L{lane}_{read}_{pair}.fastq.gz`
  - Cannot use custom file paths (no --read1/--read2 flags)
- **STARsolo**: `--readFilesIn ${samples_dict[s].fastq_1} ${samples_dict[s].fastq_2}`
  - Uses the merged file paths directly

## Cell Ranger FASTQ naming constraint

Cell Ranger strictly requires Illumina naming: `{sample}_S{samp}_L{lane}_{read}_{pair}.fastq.gz`

- `S{samp}`: sample number from bcl2fastq (S1, S2, ...)
- `L{lane}`: sequencing lane (L001, L002, ...)
- `{read}`: R1 or R2
- `{pair}`: split batch number (001, 002, ...)

Cell Ranger does NOT read I1/I2 (index already used for demultiplexing). Only R1 and R2 are used.

If files don't follow this naming, symlink or rename as workaround.

## Pitfalls

- Merged files (`{sample_id}_1.fq.gz`) are NOT recognizable by Cell Ranger's auto-discovery
- Cell Ranger needs `--create-bam=true` for downstream scTE analysis
- Index files (I1/I2) can be concatenated the same way as R1/R2, but Cell Ranger doesn't need them
