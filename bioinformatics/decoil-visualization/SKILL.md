---
name: decoil-visualization
description: Decoil ecDNA 结果可视化集成 — 统计图/跨样本对比/IGV HTML,规则与 bin 脚本约定。
triggers:
  - decoil 可视化
  - ecDNA plots
  - igv_ecdna
  - decoil_plot
---

# Decoil ecDNA 可视化模块(decoil.smk 内置)

Omics 项目 `modules/decoil/decoil.smk` 已集成 3 条可视化规则(2026-10-12):

- `decoil_plot`(每样本):summary.txt + reconstruct.ecDNA.filtered.bed → 尺寸分布(log 直方图)+ topology 组成 + ecDNA 区域表。bin 脚本 `decoil_plot.py`,支持 `--mode single|compare`。
- `decoil_compare`(聚合):跨样本 counts/尺寸叠加/topology 堆叠 + shared/unique 区域表(键 = 完整坐标 `chr:start-end` 字符串,不缩写)。
- `decoil_igv`(每样本):生成 track.py igv 模式所需 config(`decoil_igv_config.py`)+ 调 `modules/track/bin/track.py --mode igv` → 交互 HTML,locus 默认 = 最大 ecDNA 区域。

## 布局演化教训(2026-10-14,多轮返工后定稿)

- **环形图路线已废弃**。arc 上画基因模型(标签/引线/碰撞推挤)在密集基因区必然失败;DECOIL 官方 decoil-viz 也是横向 track 堆叠(gTrack),论文 Fig3/4 全是这种。最终版:`draw_cycle(ax_cov, ax_gene, ...)` 双轴三轨道——重建灰条+覆盖度面积(上)、基因模型逐行(下),共享参考基因组 x 轴,片段并排窗口化(每片段间 PAD 20kb)。
- 关键几何坑:`to_theta`/wrap 归一化在截断基因跨断点时必然算错(曾致 90° 巨弧盖满全环);线性 x 轴彻底规避此类问题。
- 长内含子(>30kb)画双斜杠断线,不画贯穿点线;基因名标签**永远水平**、上下交替防撞;外显子先裁剪到片段范围再映射(越界外显子曾画出 77° 巨块)。
- <0.4% 环长的小基因不画(只进 TSV);重建条按片段均值覆盖度灰度着色。
- **环的表示**:线性图上用连接弧——相邻片段末端之间画红色小弧(标 B1/B2...)、末片段右端回连首片段左端画紫色大弧(标 circular join),弧端点配虚线引导到重建条。没有这些弧,读者看不出"这是个环"。ylim 需预留弧高(3.6),否则弧被裁剪。
- 早期还有 5 个连环 bug 的教训:碰撞检测跑在 set_xlim 之前(像素度量失真)、旋转文字 AABB 高估、贪心推签不感知环绕等——全随环形布局一起删除,线性布局天然免疫。

## 复用要点

- IGV HTML 不用新写渲染器:构造 track.py 的 config JSON(ref + tracks 数组含 bigwig/bed/gtf)喂给 track.py 即可;`igv` 段放工作流 config(参照 config/PacVar.json:js/id/publicPathMap/fastaURL/indexURL/cytobandURL/tracks)。
- BED 作为 IGV annotation track:format=bed, type=annotation。
- decoil.sif 里有 matplotlib+pandas,但 apptainer exec 必须显式 `--bind /data/pub:/data/pub`,否则模块路径不可见。
- ecDNA 片段合并:BED 按 (sample_id, circ_id) groupby 取 min(start)/max(end);不同样本起点差 1bp(如 chr9 ...700 vs ...699)会使 shared 表把它们判为 unique——是坐标本身差异,不是 bug。
- node.py outfiles 需同步:每样本 visualization/decoil_stats.png + igv_ecdna.html + ucsc_track.txt,聚合 eccdna/visualization/decoil_compare.png + _shared_unique.tsv。
- 参数结构(用户纠正后定稿):多 rule 模块的参数不建平级键(如 Params.visualization),而是在模块父键下按 rule 分子字段 —— Params.decoil.{reconstruct, plot, compare, igv.locus};多 rule 共用的参数(如 formats)放父级。rule 级键通过 fallback 函数(resolve rule子字段 → 父字段 → 默认)读,兼容旧平级写法。工作流模板 config/PacVar.json 和模块 decoil.json 必须同步此结构。
- `decoil_ucsc` 规则用 track.py --mode ucsc;track.py 原来不认 .bed(_track_type 一律返回 bigWig),已修:'.bed/.bed.gz → bed'。ucsc track 线的 bigDataUrl 是相对路径,track 文件要和输出目录保持相对位置才有意义。
- track.py 的 ucsc 模式会对输入排序后写 track 线;igv 模式则要求 config JSON。两模式都在 decoil.sif(python 3.9)里跑。

## 图例生成(2026-10 定稿)

- 图例(topology_legend)必须用 matplotlib 纯代码生成(topology_legend.py),禁止 HTML+Chrome 截图——HTML 方案几何不可控,被用户连续否决。
- 容器内无 CJK 字体:从宿主 cp NotoSansCJK-Regular.ttc 到 /tmp/fonts/,fontManager.addfont() 显式注册。零 Glyph missing 警告才算中文渲染成功。
- 白色窄缝语义(用户明确要求):simple_circle 画唯一 4° 全带宽白缝=excision 断点;multi_region 等多段环**不画白缝**(颜色交界已表达拼接点);白缝=窄缝,不是缺一半。
- Wedge 角度陷阱:(32,392) 会画满整圈无缝(392=360+32),缝隙宽度必须用 (32,388) 这种终点<360+起点-缝宽 的写法。
- 倒位段表示:绿弧本身末端收成箭头尖(SnapGene feature 惯例,ccw 弧 tip 在 t2,taper 底边必须取 body_hi 不是 body_lo,否则画出穿心大三角)。**只给倒位弧一个尖**;给蓝弧也加尖做"参照"必然尖端对撞(拓扑必然,用户明确反感对顶箭头)。
- 像素审计陷阱:axes 只占 figure 一部分,scale≠W/xlim;必须用 ax.transData.transform 换算,y 需要 H-py 翻转('flip' 约定)。scale 算错会误报"渲染 bug"(2026-10-15 两次误判)。
- 交付前自查:审计指标要对应真实视觉问题(尖端数量/位置/宽度),不是只验证闭合覆盖;几何审计两次都"通过"的版本实际有 5 个尖端和对顶碰撞。
- 几何验证方法:调色板 mask + 最大连通域 + 极坐标中半径扫描数断口(0.2° 为抗锯齿伪影可忽略);审计启发式若把文字像素混进来会误报。

## topology 示意环(decoil_structure.py,2026-10-17 定稿)

- 用户要求把 topology_legend 的拓扑视觉语言**嵌进环图最内层**:hub(r=0.40)外沿 0.405–0.455 窄带画 topology 示意环,元素用**真实片段坐标**(_frag_angles: pos0=12点=math 90°,cw;Wedge 用 (t2,t1) ccw),不是图例式等分摆放——内环 junction 与外圈 coverage 环白缝径向对齐是核心卖点。
- 坐标原点陷阱:环回接点/excision 点在 12 点(math 90°),不是 180°;simple_circle 白缝、simple_sv/mixed_sv/foldback backbone 缝都以 90° 为中心,写法 (90+gap/2, 90+360-gap/2-0.2)。
- 片段 i/i+1 的接缝角 = arcs[i+1] 的 **t1**(低坐标端,=xs_{i+1}),不是 t2;t2 是片段自身高坐标端(朝下一片段起点方向)。弄反会把刻度画到 12 点盖住白缝。
- micro-gene 点带原在 r=0.46(hub 与 lane0 之间),被拓扑环占据后移到 lane0/lane1 之间 r=0.5075 天然空隙。
- 各 topology 渲染:simple_circle=蓝环+12点白缝;simple_sv=蓝环+接缝橙刻度(3°);mixed_sv 再叠加倒位连续 '-' 段绿弧+单侧箭头尖;multi_region_intra=同色深浅、inter=每染色体一色(CHR_COLORS),交界 flush 不留白缝(+0.25° eps 防抗锯齿发丝缝);simple_duplications=重复片段深红(A)/浅红(A');foldback=接缝双锥(浅橙+深橙)。
- Ring 布局(decoil_structure.py,2026-10-17 重构):半径区间收进 `RingBands` frozen dataclass(hub 0.34/topo 0.345-0.40/gene 0.45-0.68/cov 0.70-0.85/ruler 0.95/label 1.05,带 __post_init__ 严格递增校验),从 draw_cycle_circular(bands=None→默认实例)作形参逐层下传,禁止函数读全局半径常量——避免 ring 互相覆盖。六 ring 各一函数:_draw_hub/_draw_topology_ring/_draw_gene_ring/_draw_coverage_ring/_draw_ruler_ring(+图例)。lane 半径用 bands.lane_outer(lane),lane 数用 bands.max_lanes。grid/单环路径不传 bands 即用默认,改布局只改 dataclass 默认值。
- 断点缝一致性:拓扑环白缝与 coverage 环在环原点的白楔必须同宽同位(共用 TOPO_GAP_DEG=1.5°,用户确认 4° 太宽——断点要尽可能窄;coverage 侧用白色 Wedge zorder=4 显式切金环,不靠采样缝隙);backbone 类拓扑(simple_circle/simple_sv/mixed_sv/foldback)切缝,multi_region/duplications 等 flush 拼接拓扑不切(颜色交界已表达拼接)。缝隙两侧端点角度完全对称(90±gap/2,右边不加 -0.2 补丁,补丁曾导致缝歪)。
- 图例位置(用户两轮纠错后定稿):LEGEND_XY 钉死在画布右下角(x=1.68, y=-1.20, xlim 1.80/ylim -1.30),基因标签只能把图例往下推(扩 ylim),不允许左右移——曾因"避让标签"漂到画布中部偏右留下大片空白被否。
- 断点数语义:n 片段环 = n 个断点(环原点回接缝 + n-1 个片段间接缝),coverage 环在每个断点切同宽白缝(TOPO_GAP_DEG=0.8°,用户两轮收窄定稿:4°→1.5°→0.8°),multi_region 也切。hub 坐标行逐片段列出(fc:fs-fe + ...),>3 片段折叠为 (n segments);>46 字符在 '+' 处拆两行。
- hub 文字溢出教训(用户纠错两次):不能用 renderer 测量(get_window_extent)做自适应字号——bbox_inches="tight" 保存时才定 axes 尺寸,保存前测量结果失效;必须用确定性解析计算:fig_w_in 已知 → data_per_pt = ax_w/(fig_w*72),字号 = 可用宽/(最宽行字符数×0.60pt/字符),钟位 2.2–5.0,行数参与垂直居中。
- 拓扑环缝语义定稿(用户两轮纠偏后):**所有 topology 的所有片段交界(含环原点回接缝)都是真断点**,拓扑环每交界切同宽白缝(TOPO_GAP_DEG),与 coverage 环逐一对齐——multi_region 的 flush 拼接(无缝色界)和"只切原点"两种早期做法都被否:前者断点消失,后者断点数不对。实现:各色段两端各收 half=min(TOPO_GAP_DEG/2, (t1-t2)/4),自然回绕。教训:一次"修发丝缝"的 flush 重叠把整个语义改了,改几何前先确认视觉语义是否被改。
- "//" 断裂符号尺寸(用户反馈太大):slash_len = 0.45×外显子高、双斜间距 0.005、线宽 0.9(原 0.75/0.008/1.2);图例 swatch 同步(dx=0.008, dy=0.55×bar_h)。
- Wedge 画整环留缝必须终点 < 360+起点(见上图例教训)。docker 容器 python 3.9 兼容:新代码避开 walrus/match。
