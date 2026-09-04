# tidk (Telomere Identification Toolkit) API Reference

## Version
tidk 0.2.65 (Rust binary)

## Subcommands

### tidk build
Build reference database from GitHub. Required before `find` subcommand.
```
tidk build
```
Database location: `~/.local/share/tidk/tidk_database.csv`

### tidk search
Search assembly/reads for telomeric repeats.
```
tidk search --string <MOTIF> --output <PREFIX> --dir <DIR> <FASTA>
```
- `--string` / `-s`: Telomeric repeat motif (e.g., `TTAGGG`)
- `--output` / `-o`: Output filename prefix (without extension)
- `--dir` / `-d`: Output directory
- `--window` / `-w`: Window size for counting (default: 10000)
- `--extension` / `-e`: Output format: `tsv` (default) or `bedgraph`
- `--log`: Output a log file

Output: `<dir>/<prefix>_telomeric_repeat.tsv`

### tidk find
Find telomeric repeats by clade name (requires `tidk build` first).
```
tidk find --clade <CLADE> --output <PREFIX> --dir <DIR> <FASTA>
```

### tidk explore
Explore k-mer sizes to find potential telomeric repeats.
```
tidk explore --length <LEN> <FASTA>
```

### tidk plot
Generate SVG plot from tidk search TSV output.
```
tidk plot --tsv <INPUT> --output <PREFIX> --dir <DIR>
```

## No `tidk count` subcommand
There is NO `tidk count` subcommand. Do not use it.

## Pitfalls
- Short flags `-s`/`-o` are NOT valid for `search` — must use `--string`/`--output`
- Database must be built first with `tidk build` for `find` subcommand
- `search` works without database build (uses provided `--string`)
- Warning "No clades found in the database" means `tidk build` hasn't been run — only affects `find`, not `search`
