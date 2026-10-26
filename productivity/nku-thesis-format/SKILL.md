---
name: nku-thesis-format
description: "南开大学硕士毕业论文 docx 排版格式规范。生成/校对毕业论文 Word 文档时使用。"
version: 1.0.0
platforms: [linux]
metadata:
  hermes:
    tags: [thesis, docx, formatting, 南开大学]
---

# 南开大学毕业论文格式规范

生成或校对毕业论文 .docx 时严格按本规范设置（python-docx 中对应参数附后）。

## 一、页面设置
- 页边距：上 2.54cm、下 2.54cm、左 3.67cm、右 2.67cm
- 页眉距边界 1.5cm，页脚距边界 1.75cm
- 行间距 1.35 倍

## 二、目录
- "目录"两字：小三号宋体加粗
- 目录内容：小四号宋体，页码数字对齐（右对齐制表位 + 前导点）

## 三、页眉和页码
- 页眉和页码从"中文摘要"开始出现
- 页眉内容 = 该部分标题（如"中文摘要"、"Abstract"、"第一章 …"）
- 页码分段编排：
  - 中文摘要、Abstract、目录 → 罗马数字 I, II, III……（每部分可各自重新起或连续，按学校要求）
  - 正文第一章起 → 阿拉伯数字 1, 2, 3……从 1 重新开始
- 实现要点：摘要之前（封面等）用无页码节；摘要/Abstract/目录一个节用罗马数字；正文新节 `w:pgNumType` 重起编号、格式改十进制

## 四、摘要
### 中文摘要
- 论文标题：小二号宋体加粗
- "专业、学号、姓名、指导教师"行：五号宋体
- "摘要"两字：四号宋体
- 摘要内容：小四号宋体
- "关键词"三字：小四号宋体加粗

### 英文摘要
- 论文标题：小二号 Times New Roman 加粗
- "Abstract"：四号 Times New Roman
- Abstract 内容：小四号 Times New Roman
- "Keyword"（Keywords）：小四号 Times New Roman 加粗

## 五、正文
- 章节标题：四号宋体
- 正文内容：小四号宋体

## 六、图表
- 图表内容（题注、表内文字）：五号宋体

## 七、参考文献
- "参考文献"四字：四号宋体
- 文献条目：小四号宋体，英文条目用小四号 Times New Roman

## 八、致谢
- "致谢"两字：四号宋体
- 致谢内容：小四号宋体

## 字号对照（python-docx 用 Pt 值）
| 中文字号 | Pt |
|---------|-----|
| 小二 | 18 |
| 四号 | 14 |
| 小四 | 12 |
| 五号 | 10.5 |
| 小三 | 15 |

## 实现要点（python-docx）
- 中文字体需同时设 `run.font.name` 和 `r.rPr.rFonts` 的 `w:eastAsia` 属性，否则中文回退默认字体
- 行距 1.35 倍：`paragraph_format.line_spacing = 1.35`
- 页边距：`section.top_margin = Cm(2.54)` 等；页眉/页脚距边界：`section.header_distance = Cm(1.5)`、`footer_distance = Cm(1.75)`
- 罗马/阿拉伯页码切换靠插入分节符（新节），再改该节 `sectPr/pgNumType` 的 `fmt`（upperRoman/lowerRoman 按学校模板，此处用大写 I, II）与 `start`
- 页眉每节设 `header.is_linked_to_previous = False` 后单独填标题文字

## 关联约束
- 论文要求 3-5 万字，输出 .docx
- 写作风格：叙事驱动不堆数据，章节标题是故事节点（Hook→观察→机制→后果→模型）
