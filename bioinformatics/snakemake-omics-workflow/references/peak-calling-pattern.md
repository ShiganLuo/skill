# Peak Calling Workflow Pattern (ChIP-seq / DIP-seq)

## Workflow structure

```
trimming (cutadapt) → bowtie2_index → bowtie2_align → macs3_callpeak
```

## Key design: IP/Input sample mapping

### In run.py `runPeakCalling()`

```python
ip_samples = []
input_samples = []
sample_ip_input_map = {}

for sample_id, sample_info in samples_info_dict.items():
    if sample_info.design == "ip":
        ip_samples.append(sample_id)
    elif sample_info.design == "input":
        input_samples.append(sample_id)

# Map each IP to its control (use first available Input)
if input_samples:
    default_input = input_samples[0]
    for ip_sample in ip_samples:
        sample_ip_input_map[ip_sample] = default_input
else:
    for ip_sample in ip_samples:
        sample_ip_input_map[ip_sample] = None

datajson["ip_samples"] = ip_samples
datajson["input_samples"] = input_samples
datajson["sample_ip_input_map"] = sample_ip_input_map
```

### In macs3 module (modules/macs3/macs3.smk)

Use `unpack()` for conditional control input:

```python
def get_macs3_input(wildcards):
    sample = wildcards.sample_id
    bam_treatment = f"{indir}/{sample}/{sample}.bam"
    input_sample = sample_ip_input_map.get(sample)
    if input_sample:
        bam_control = f"{indir}/{input_sample}/{input_sample}.bam"
        return {"bam_treatment": bam_treatment, "bam_control": bam_control}
    return {"bam_treatment": bam_treatment}

rule macs3_callpeak:
    input:
        unpack(get_macs3_input)
    shell:
        """
        {params.macs3} callpeak \
            -t {input.bam_treatment} \
            {('-c ' + input.bam_control) if 'bam_control' in input else ''} \
            ...
        """
```

### Outfiles generation

Only IP samples get peak calling outputs. Both IP and Input samples get trimming + alignment outputs.

## Config template (config/PeakCalling.json)

Key fields:
- `ip_samples`, `input_samples`: sample lists
- `sample_ip_input_map`: IP→Input mapping
- `genomes`: list of genome versions (default `["mm"]`)
- `Params.macs3.bw`, `Params.macs3.pvalue`, `Params.macs3.genome_size`

## MACS3 module files

- `modules/macs3/macs3.smk` — rules
- `modules/macs3/macs3.json` — config template
- `modules/macs3/macs3.yaml` — conda env (macs3>=3.0.0)
