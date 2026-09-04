---
name: trip-planning
description: "Create structured travel itineraries in Obsidian with driving stats, accommodation risk assessment, cost modeling by group size, visual references, and checklists."
tags: [travel, obsidian, planning, itinerary]
---

# Travel Itinerary Planning

Create comprehensive, actionable travel itineraries in Obsidian. This skill encodes the full structure, user corrections, and pitfalls discovered through iterative refinement.

## Standard Document Structure

Every trip itinerary should contain these sections in order:

```
1. Header (目的地、时间、交通方式)
2. 路线总览 (route map with visual)
3. 目标景点表 (attractions table with门票、游玩时长、备注)
4. 每日行程 (daily itinerary — the core)
5. 行前 Checklist (行前准备倒推时间线)
6. 注意事项 (高反、防晒、信号等)
7. 美食 (local food recommendations)
8. 预计花费 (cost breakdown by group size)
```

## Daily Itinerary — Required Elements

Every day MUST include ALL of these:

```markdown
### Day N（M月D日）：起点 → 终点

![[景点图片1.jpg]]       <- visual expectation
![[景点图片2.jpg]]

- 时间线：具体时刻 + 活动
- 住宿：**具体区域** + 价位 + 风险说明（不能只写城市名）

> 弹性：如果XXX，可以YYY（备选方案，每个必须有）

**驾驶里程**：约 XXXkm | **驾驶时间**：约 X 小时
  - 路段1：XXkm（~Xh，道路类型）
  - 路段2：XXkm（~Xh，道路类型）
```

### Driving Time Estimates

Use realistic speeds by road type:
- 高速公路 (G30连霍等): ~100km/h average
- 国道/省道 (G109, G315等): ~60-70km/h average
- 山路 (祁连段): ~40-50km/h average
- 戈壁公路 (G315): ~70-80km/h average
- 城市道路: ~30-40km/h average

Always break down by segment, not just total.

### Accommodation — Risk-Rated

Each accommodation entry must include:
- **具体区域**（不是城市名，要精确到镇/区域）
- **价位范围**（每人或每间）
- **风险等级**（红/黄/绿）+ 原因
- **预订建议**（提前多久、哪个平台、是否需要电话确认）

Common pitfalls:
- 旺季平台标"有房"实际超售 → 建议电话确认
- 小镇（如黑马河）条件差 → 提醒降低预期
- 省会城市一般不紧张 → 可以晚订

### Flexibility Notes

Every day MUST have a flexibility note explaining:
- What to cut if behind schedule
- What to do if weather is bad
- What to skip if tired

User explicitly corrected: "方案没有冗余" — plans without buffer are unacceptable.

## Cost Modeling — By Group Size

**PITFALL**: User corrected costs must account for group size ceiling effects.

### Cost Categories

**Fixed costs (split by group size):**
- 租车/包车费用
- 油费
- 保险

**Semi-fixed costs (depend on room count):**
- 住宿 — this is where the ceiling effect happens

**Per-person costs (don't change with group size):**
- 门票
- 餐饮
- 其他消费

### Group Size Economics

```
2人: 交通分摊贵，住宿1间刚好 → 人均最高
3人: 交通分摊合理，住宿仍1间 → 性价比甜点
4人: 交通最划算，但住宿变2间 → 边际收益递减
```

**Key insight**: 4人住宿从1间变2间，总费用跳增1200-2050元，人均只比3人便宜500-700元。必须明确指出这个拐点。

### Required Cost Table Format

Show both:
1. **费用明细表** — 总费用 per category (not per person)
2. **按人数估算表** — 人均费用 for 2人/3人/4人, 自驾 vs 包车
3. **对比总结** — 最省钱/最省心/最贵方案 + 性价比拐点说明

## Checklist — 倒推时间线

Create a checklist with:
- 住宿风险排序表（按紧迫度红/黄/绿）
- 租车/包车注意事项（异地还车、车型选择、保险）
- 门票预约（莫高窟等限流景点必须立即预约）
- **时间节点倒推表**（距出发X天 → 必须完成什么）

## Visual References

For each day, add Obsidian image embeds for the main attractions:
```markdown
![[景点名-特色.jpg]]
```

User can download actual photos and save with matching filenames, or replace with web URLs.

## User Corrections (Pitfalls)

These are hard-won lessons — do NOT repeat these mistakes:

1. "行程过于紧张" — Don't pack every hour. Include buffer time
2. "方案没有冗余" — Every plan needs a fallback for each day
3. "住宿不够明确" — City name alone is insufficient. Need: specific area, price range, risk level, booking timeline
4. "费用存在上限" — Cost per person doesn't decrease linearly. Model the ceiling effect
5. "没有风景图片" — Visual expectations are mandatory, not optional

## Workflow

1. First pass: Create basic route + daily schedule (just attractions + time)
2. Second pass: Add driving time estimates per segment
3. Third pass: Add accommodation details + risk ratings
4. Fourth pass: Add flexibility notes
5. Fifth pass: Add checklist with reverse timeline
6. Sixth pass: Add cost breakdown by group size
7. Seventh pass: Add visual references (images)

This is iterative — user will refine through multiple rounds. Don't try to get everything right in one pass.

## File Safety

When editing existing itineraries in Obsidian:
- Use `patch` for targeted changes, not `write_file`
- Always read the file first before patching
