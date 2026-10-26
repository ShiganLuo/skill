# scRNA-seq 跨组分析报告方法学要求

为 scRNA-seq 跨组分析报告（DEG + GO/KEGG + TE + 跨组织对比）补充
scientific-report-ppt 没有覆盖的方法学要求。这些是用户在多次
scRNA-seq 跨组分析会话中明确要求的硬性约束。

## DEG: 必须 pseudo-bulk

**为什么**: 单细胞 Wilcoxon / t-test 把每个细胞当独立样本，
忽略了 donor 间生物学变异，p 值过于宽松（frequentist "double
dipping"）。Pseudo-bulk 把每个 (donor × cell_type) 当一个样本，
用 edgeR/DESeq2 负二项分布，更接近 bulk RNA-seq 流程。

**参考**: `/home/<USER>/Data/genomeStability/workflow/Omics/src/scRNAseq/scripts/python/utils/DEG.py`
`aggregate_and_filter` 函数 (按 sample × cell_type 求和)

**实现路径**:
```python
# Python 端 aggregate（每 sample × cell_type 求和到 raw counts）
import scanpy as sc
NUM_CELL_PER_SAMPLE = 30  # 过滤 cells<30 的 sample
sub = adata[adata.obs['cell_type'] == ct]
for sample in samples:
    counts = np.array(sub[sub.obs['sample_id']==sample].raw.X.sum(axis=0)).flatten()
    # 写 CSV
```

```r
# R 端 edgeR
suppressPackageStartupMessages(library(edgeR))
y <- DGEList(counts = counts, group = sample)
keep <- filterByExpr(y)
y <- y[keep, , keep.lib.sizes=FALSE]
y <- calcNormFactors(y)
design <- model.matrix(~ group)
y <- estimateDisp(y, design)
fit <- glmQLFit(y, design)
qlf <- glmQLFTest(fit, coef = 2)  # group_b vs group_a
tt <- topTags(qlf, n = Inf, sort.by = "none")$table
```

**禁用的方式**: scanpy `rank_genes_groups` (Wilcoxon) 对单细胞数据；
pyDESeq2 直接处理 h5ad (数据格式不对)。gseapy 不用于 DEG，只用于 GO。

## GO/KEGG: 必须 R 镜像 + OrgDb，不用 gseapy

**为什么**: gseapy 只支持 human/mouse/yeast/zebrafish/worm/fly/c.elegans，
**不支持恒河猴 (Macaca mulatta)**。Enrichr API 也不支持 macaque。
clusterProfiler + Bioconductor 的 `org.Mmu.eg.db` 是标准解法。

**镜像**: `/home/<USER>/Database/env/function/function.sif`
（已加 org.Mmu.eg.db + edger + deseq2 + libxml2 到 function.yaml）

**运行方式**（必须隔离 HOME）:
```bash
apptainer exec --home /tmp/sandbox \
    /home/<USER>/Database/env/function/function.sif \
    bash -c 'export R_LIBS_USER=/tmp/sandbox/Rlib; cd <outdir> && Rscript <script>.R'
```
不隔离会读宿主 `/home/<USER>/R/library` 旧版包冲突。

**物种 → OrgDb 映射**:
- human → `org.Hs.eg.db`, kegg_org="hsa"
- mouse → `org.Mm.eg.db`, kegg_org="mmu"
- macaque → `org.Mmu.eg.db`, kegg_org="mcc"

**脚本**:
- `/home/<USER>/Data/genomeStability/workflow/Omics/modules/function/bin/go-kegg.r`
- `/home/<USER>/Data/genomeStability/workflow/Omics/modules/function/bin/go-kegg_back.r`
- 都已加 `macaque` 选项

**镜像 yaml 更新**:
```yaml
dependencies:
  - r-base=4.3
  - libxml2  # clusterProfiler igraph 依赖
  - bioconductor-clusterprofiler
  - bioconductor-org.hs.eg.db
  - bioconductor-org.mm.eg.db
  - bioconductor-org.mmu.eg.db  # 恒河猴
  - bioconductor-edger
  - bioconductor-deseq2
  # ... 其他不变
```
重建: `cd /home/<USER>/Data/genomeStability/workflow/Omics/src/common/util && \
/home/<USER>/miniconda3/bin/python EnvUtil.py apptainer all \
-y /home/<USER>/Data/genomeStability/workflow/Omics/modules/function/function.yaml \
--build-timeout 3600`

## TE 分类: 必须 GTF 的 class_id

**为什么**: scTE 输出用 `-int` / `_int` 后缀或 family 名（如 `Alu`,
`L1PA8A`），不能 pattern matching 分类。Ensembl RepeatMasker GTF
有 `class_id` 字段直接给出标准 TE 分类。

**GTF**: `/home/<USER>/Database/Reference/mulatta/ENSEMBL/Mmul_10/rheMac10_rmsk_TE.gtf`

**实现**:
```python
import re
te_map = {}  # gene_id -> {family, class}
with open(GTF) as f:
    for line in f:
        if line.startswith('#'): continue
        attrs = line.split('\t')[8]
        gene_id = re.search(r'gene_id "([^"]+)"', attrs)
        family_id = re.search(r'family_id "([^"]+)"', attrs)
        class_id = re.search(r'class_id "([^"]+)"', attrs)
        if all([gene_id, family_id, class_id]):
            te_map[gene_id.group(1)] = {
                'family': family_id.group(1),
                'class': class_id.group(1)
            }
```

**标准 class_id 类别**: SINE / LINE / LTR / DNA / Satellite / Unknown
（每类还可细分 subfamily: LTR → ERV1, ERVL, ERVK, Gypsy 等）

## 数据位置: TE 不在 HVG，必须用 raw

**为什么**: scanpy 默认 HVG=3000（高变基因），TE 基因表达低、
变异小，几乎全在 HVG 之外。`adata.X` 是 HVG 矩阵，`adata.raw` 是
全基因矩阵（~19,141）。DEG 和 TE 分析都必须用 raw。

**验证**:
```python
te_genes = adata.raw.var[adata.raw.var['gene_type']=='TE'].index.tolist()
# Ovaries: 1,272 TE genes in raw, 0 in HVG
te_in_X = [g for g in te_genes if g in adata.var_names]
print(f'TE in X (HVG): {len(te_in_X)}')  # 0
```

## PPT 风格: 故事线驱动，不堆砌结果

**用户明确要求**:
1. 标题中文 + 正文中文 + 图片英文标签（不混搭）
2. 完整 sample_id（如 `zigong-21310-10XSC3`），区分大小写
3. 不使用 "首次发现" "首次报道" 等修饰词
4. 按科学问题组织故事线（不是 "Stage 1 结果 / Stage 2 结果"）
5. 每个科学问题页必须有：结论 + 具体基因 + 通路/机制

**禁用**:
- "请审核" "需要确认的问题" 等交互语言（写完即结束）
- "基线参考说明" 等冗余上下文（"对照是参考"是显然的）
- 对照组状态作为科学问题（"ctr_POI 是什么状态" 不是科学问题）
- 标题括号补充说明（"Ovaries（老化 vs 青年）"）
- 废话如 "样本数小" 等

**Plot 要求**:
- 图片英文，完整 sample ID，不用缩写 token
- heatmap 只放主对比组（不放参考评估）
- 标题/轴标签写明比较对象（如 "luanchao-11238-10XSC3 vs luanchao-21310-10XSC3"）
- 保持长宽比不扭曲（`_add_picture` 用 PIL.Image 计算 aspect）

## 工作流纪律

- 镜像**不能手动改**，必须改 yaml 重新构建（`EnvUtil.py apptainer all`）
- Apptainer 跑 R 必须隔离 HOME（`--home /tmp/sandbox`）
- 长任务 (>60s) background+立刻 poll，不要前台等待
- meta_input.tsv 等 raw 数据路径不进 plan（h5ad 是最终数据源）
