# DECOIL topology 分类（summary.txt 的 topology_name 列）

decoil 2.0.2 `decoil/output/metrics.py` 的 `get_topology()` 是封闭枚举，只返回 0–6 七类，不会出现其他标签。

## 七类定义（复杂度递增）

| topology_name | 含义 |
|---|---|
| simple_circle | 单片段简单切离环：基因组一段整体切下首尾相连，环内无 SV |
| simple_sv | 环内含一个简单 SV（小缺失 DEL 或倒位 INV 二选一），2–10 片段 |
| mixed_sv | 环内同时含小缺失和倒位（SMALL_DEL=1 且 INV=1） |
| multi_region_intra_chr | 同一染色体 ≥2 个不相邻区域拼接成环（可含 DEL/INV/TRA） |
| multi_region_inter_chr | 跨染色体：环由 ≥2 条染色体的片段拼成 |
| simple_duplications | 同一 fragment 在环内出现 ≥2 次（串联重复） |
| foldbacks | 两个坐标重叠的片段在环中直接相邻相连（倒位重复标志，amplicon 复杂重排） |

## 判定是顺序覆盖，不是互斥分类

每环统计布尔特征（N_FRAG / SMALL_DEL / DUP / INV / INTERCHR / MULTI_REGION / FOLDBACK），按顺序赋值、后者覆盖前者：

```
topology = simple_circle（默认）
N_FRAG==1 → 直接返回 simple_circle
SMALL_DEL → simple_sv；INV 覆盖为 simple_sv；SMALL_DEL+INV 再覆盖为 mixed_sv
MULTI_REGION → multi_region_intra_chr；INTERCHR → multi_region_inter_chr
DUP → simple_duplications；FOLDBACK → foldbacks（最高优先级，最终覆盖）
```

多特征共存时标签 = 列表中最后命中的类别，只说明"最复杂特征"，不代表没有其他成分（如 DUP+INTERCHR 共存 → 标 simple_duplications）。

## 分布预期

正常/对照组织的 eccDNA 以 simple_circle 为绝对主导（常 >90%，源于 excision）；multi_region / foldbacks 等复杂类别是需要重点关注的少数。

## 对应图例

`modules/decoil/bin/topology_legend.py`（matplotlib 生成，非 HTML）以闭合环 + 图形语言表达七类：颜色=片段/来源染色体；白窄缝=excision 断点（仅 simple_circle 画，1.5° 发丝级，多段环靠颜色交界表达拼接点，不画白缝）；橙虚线弧=SV 段；绿弧+白色大箭头（逆环向，蓝弧上画顺时针参照箭头）=倒位；深浅红 A/A′=重复拷贝；双层橙弧=foldback。标记元素禁用黑色。Wedge 缝隙角度陷阱：(32,392) 画满整圈无缝，必须写 (30.75,389.25)。容器内无 CJK 字体：宿主 cp .ttc 到 /tmp/fonts/ 后 fontManager.addfont() 显式注册，零 Glyph missing 警告才算中文渲染成功。

图例 QA 两道机检（改动后必跑）：① renderer bbox 全对扫描文字重叠
（`Text.get_window_extent`，>4px² 计重叠，浮标贴近标题/说明最易撞）；
②调色板 mask+最大连通域+极坐标中半径扫描断口（0.2°=抗锯齿伪影）。
环内标签放空腔（r≈0.55），不放环外围——外围标签撞标题/说明。
