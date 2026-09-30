# scRNA-seq 跨组分析 — Pseudo-bulk DEG / GO / TE 模式

scRNA-seq 跨组分析（按 cell type × sample 比较）下游：pseudo-bulk
DEG（edgeR）、GO/KEGG 富集（clusterProfiler + 恒河猴）、TE 分类与
TE fraction 分析的执行模式与踩坑。适用于 Omics 项目里"细胞组成 +
差异表达 + 富集分析 + TE 变化"组合任务。

## 1. DEG 必须 pseudo-bulk

**为什么**: scanpy `rank_genes_groups` (Wilcoxon) 把每个细胞当
独立样本，p 值过于宽松（"double dipping"）。Pseudo-bulk 把每个
`(donor × cell_type)` 合并为一个样本，用 edgeR/DESeq2 负二项
分布建模，更接近 bulk RNA-seq 流程。

**实现路径**: 把 `DEG.py` 的 `aggregate_and_filter` 拆成
Python 端 + R 端两个工程化脚本：

- `workflow/Omics/src/scRNAseq/scripts/python/utils/pseudobulk_prepare.py`
  按 cell type 聚合单细胞到 pseudo-bulk counts (每 sample 一行)
- `workflow/Omics/src/scRNAseq/scripts/python/utils/pseudobulk_edger.R`
  edgeR DEG（CLI: --counts-dir, --out-dir, --label, --comparisons）

CLI 调用：
```bash
python pseudobulk_prepare.py --h5ad <X>.h5ad --out-dir counts/ --label ovaries
Rscript pseudobulk_edger.R \
  --counts-dir counts/ --out-dir deg/ --label ovaries \
  --comparisons luanchao-21310-10XSC3:luanchao-11238-10XSC3
```

## 2. n=1 per group: exactTest (not glmQLTest)

**踩坑**: 2 sample × 2 sample 的设计（如卵巢只有 2 个样本），
`estimateDisp()` 返回 NA, `glmQLFit` 直接报错
`NA dispersions not allowed` 或
`glmFit: No residual df: setting dispersion to NA`。

**修复**: 改用 `exactTest` (Lun et al. 2018) — 专为 n=1 per group
设计，不需要 residual df：

```r
y <- DGEList(counts = counts, group = group)
y <- y[filterByExpr(y), , keep.lib.sizes = FALSE]
y <- calcNormFactors(y)
y$common.dispersion <- 0.1   # fixed dispersion (no replicates)
et <- exactTest(y, pair = c(group_a, group_b), dispersion = 0.1)
tt <- topTags(et, n = Inf, sort.by = "none")$table
# exactTest columns: logFC, logCPM, PValue, FDR (not qval!)
tt$pval_adj <- tt$FDR
```

**列名陷阱**: `exactTest` 输出列是 `PValue` 和 `FDR`，`glmQLTest`
是 `PValue` 和 `qval`。在脚本里同时处理两种情况：

```r
if ("qval" %in% colnames(tt)) {
  tt$pval_adj <- tt$qval
} else {
  tt$pval_adj <- tt$FDR
}
```

## 3. R read.csv 把 sample 列当 index

**踩坑**: pandas `df.set_index("sample")` 写出的 CSV，第一列
`sample,sample,...`（重复）或者 `sample,cell_type,n_cells,...`。
R 的 `read.csv(file, row.names=1)` 把第一列当行名。

**修复**: R 端用 `df$sample <- rownames(df)` 恢复。Python 端避免
`set_index(drop=False)`（产生重复列名）。在 `pseudobulk_prepare.py` 中：

```python
df = pd.DataFrame(rows)
if "sample" in df.columns:
    df = df.set_index("sample")   # NOT drop=False
    df.index.name = "sample"
```

## 4. GO/KEGG: clusterProfiler + org.Mmu.eg.db（恒河猴）

**为什么不用 gseapy**: gseapy 仅支持
human/mouse/yeast/zebrafish/worm/fly/c.elegans，**不支持 macaque**。
Enrichr API 也不支持 macaque。

**镜像**: `/home/<USER>/Database/env/function/function.sif`
（已含 org.Mmu.eg.db + edgeR + deseq2 + clusterProfiler）

**物种映射** (在 `go-kegg.r` / `go-kegg_back.r` 中实现):
- human → org.Hs.eg.db, kegg_org="hsa"
- mouse → org.Mm.eg.db, kegg_org="mmu"
- macaque → org.Mmu.eg.db, kegg_org="mcc"

**调用**:
```bash
apptainer exec --home /tmp/sandbox \
    /home/<USER>/Database/env/function/function.sif \
    bash -c 'export R_LIBS_USER=/tmp/sandbox/Rlib
             Rscript <go-kegg>.R -i <DEG>.tsv -o out/ -s macaque'
```

## 5. Apptainer HOME 隔离

**踩坑**: `/home/<USER>/R/library` 里有冲突版本的 AnnotationDbi
(1.64.1) 等，clusterProfiler 加载失败：
```
package or namespace load failed for 'clusterProfiler' in dyn.load
  unable to load shared object '.../igraph/libs/igraph.so':
  libxml2.so.2: cannot open shared object file
```

**修复**: 必须用 `--home /tmp/sandbox`（或任意 writable empty HOME）
隔离：

```bash
apptainer exec --home /tmp/sandbox \
    /home/<USER>/Database/env/function/function.sif \
    Rscript script.R
```

不隔离时，宿主 `/home/<USER>/R/library` 会污染镜像内 R 的 lib path。

## 6. libxml2 版本: 锁到 2.13

**踩坑**: function.yaml 写 `libxml2>=2.10` 不够。conda-forge 当前
`libxml2-2.13.x` 提供 `.so.16`（不是 `.so.2`），igraph 链接
`.so.2` 失败。

**修复**: yaml 写死 `libxml2=2.13`（conda-forge 仓库里这个版本
提供 `.so.2` 链接）。重建镜像：
```yaml
dependencies:
  - r-base=4.3
  - libxml2=2.13
  - bioconductor-clusterprofiler
  - bioconductor-org.hs.eg.db
  - bioconductor-org.mm.eg.db
  - bioconductor-org.mmu.eg.db
  - bioconductor-edger
  - bioconductor-deseq2
  - bioconductor-enrichplot
  - bioconductor-fgsea
  - r-ggplot2
  - r-dplyr
  # ...
```

```bash
cd workflow/Omics/src/common/util
python EnvUtil.py apptainer all \
  -y workflow/Omics/modules/function/function.yaml \
  --build-timeout 3600
```

**永远不要手动改 .sif** — 镜像必须由 EnvUtil 从 yaml 构建。

## 7. TE 分类: 用 GTF class_id

**为什么**: scTE 输出 TE 用 `-int` / `_int` 后缀或 family 名
（如 `Alu`, `L1PA8A`），不能 pattern matching 分类。Ensembl
RepeatMasker GTF 有 `class_id` 字段直接给出标准 TE 分类。

**GTF**: `/home/<USER>/Database/Reference/mulatta/ENSEMBL/Mmul_10/rheMac10_rmsk_TE.gtf`

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

**类**: SINE, LINE, LTR, DNA, Satellite, Unknown
（每类还可细分：LTR → ERV1, ERVL, ERVK, Gypsy 等）

## 8. TE 不在 HVG, 必须用 raw

**为什么**: scanpy 默认 HVG=3000（高变基因），TE 基因表达低、
变异小，几乎全在 HVG 之外。`adata.X` 是 HVG 矩阵，
`adata.raw` 是全基因矩阵（~19,141）。DEG 和 TE 分析都必须用
`adata.raw.X`。

**验证**:
```python
te_genes = adata.raw.var[adata.raw.var['gene_type']=='TE'].index.tolist()
# Ovaries: 1,272 TE genes in raw, 0 in HVG
te_in_X = [g for g in te_genes if g in adata.var_names]
print(f'TE in X (HVG): {len(te_in_X)}')  # 0
```

TE fraction: `TE counts / total counts per cell` (从 raw 计算)。

## 9. PPT 风格: 故事线驱动

**用户明确要求**（多次纠正）:
1. 标题中文 + 正文中文 + 图片英文标签（不混搭）
2. 完整 sample_id（如 `zigong-21310-10XSC3`），**区分大小写**
3. 不用 "首次发现" "首次报道" 等修饰词
4. 按科学问题组织故事线（不是 "Stage 1 结果"）
5. 每个科学问题页必须有：结论 + 具体基因 + 通路
6. 实验设计页：用描述性名（Sham ctrl, OV-only），不是缩写 token

**Plot 要求**:
- 图片英文，完整 sample ID，不用缩写 token
- heatmap 只放主对比组（不放参考评估）
- 标题/轴标签写明比较对象（如
  "luanchao-11238-10XSC3 vs luanchao-21310-10XSC3"）
- 保持长宽比不扭曲（`_add_picture` 用 PIL.Image 计算 aspect）
- 完整 `pseudobulk_prepare.py` / `pseudobulk_edger.R` 脚本
  已在 `workflow/Omics/src/scRNAseq/scripts/python/utils/` 落地

**禁用**:
- "请审核" "需要确认的问题" 等交互语言
- 已知信息冗余（"对照是参考"）
- 标题括号补充说明
- meta_input.tsv 等中间文件路径入 plan

## 10. 工作流纪律

- 镜像**不能手动改**，必须改 yaml 重新构建
- Apptainer 跑 R 必须 `--home /tmp/sandbox` 隔离
- 长任务 (>60s) background+立刻 poll，不要前台等待
- `cell_type` 列已注释好，Stage 1 只需加载 + 确认，无需 QC
