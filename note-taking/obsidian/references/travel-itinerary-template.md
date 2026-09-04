# Travel Itinerary Template

Structured travel plan format used in this vault. Based on the 青甘大环线 session (2025-W31).

## Document Structure

```
---
tags: 旅游
---
<title> centered, colored

目的地 / 出行时间 / 出发地 / 交通方式

## 路线总览 (text route + map image)
## 目标景点 (table: 景点|特色|门票|游玩时长|备注)
## 每日行程 (per-day sections with images, schedule, tips)
## 行前 Checklist
  - 🌦️ 天气与行程影响
  - 🏨 住宿 (risk-ranked)
  - 🚗 租车/包车
  - 🎫 门票预约
  - ⏰ 时间节点 (countdown)
  - 📱 必备准备
## 注意事项 (高反, 防晒, etc.)
## 美食
## 预计花费 (cost breakdown by group size)
```

## Daily Section Format

Each day follows this exact pattern with HTML image table + structured sections:

```html
### Day X（日期）：标题

<table width="100%"><tr>
<td width="50%" align="center"><img src="img1.png" style="width:100%;height:250px;object-fit:cover;"><br><sub>景点A</sub></td>
<td width="50%" align="center"><img src="img2.png" style="width:100%;height:250px;object-fit:cover;"><br><sub>景点B</sub></td>
</tr></table>

> 📍 **今日关键词：** 关键词1 · 关键词2 · 关键词3

**⏰ 行程安排：**
- 时间线...
- 🏨 住宿：地点（价位，注意事项）

> 💡 弹性：可砍项/备选方案

**🚗 驾驶信息：** 总距离 | 总时间
  - 分段1 距离（时间，路况）
  - 分段2 距离（时间，路况）
```

Emoji sections: 📍关键词、⏰行程、🏨住宿、💡弹性、🚗驾驶

## Key Patterns

### 1. Every day has a "弹性" (buffer/escape)
No day is fully packed with no alternatives. Each day has a "what to cut if behind" option. Critical for tight itineraries.

### 2. Accommodation ranked by booking urgency
Not just listing hotels — rank by HOW SOON you must book:
- 🔴 极高: book NOW (旺季热门城市)
- 🟡 中等: book 2 weeks ahead (小城市, limited supply)
- 🟢 低: book anytime (大城市, abundant supply)

### 3. Cost breakdown by group size
Travel costs don't scale linearly. Key insight: there's a "sweet spot" (usually 3 people) where per-person cost drops most, then diminishing returns (accommodation jumps from 1 room to 2 rooms).

Format: separate tables for 2人 and 3人, with自驾 vs 包车. Include a summary table showing the拐点.

### 4. Weather impact analysis
For outdoor destinations, add a weather sensitivity table:
- 🔴 致命: attraction ruined without specific weather
- 🟠 较高: significantly degraded
- 🟡 中等: some impact
- 🟢 无影响: indoor or weather-proof

Include a "如果..." contingency table.

### 5. Driving time estimates with segment breakdowns
Don't just state total km — break into segments with estimated time by road type:
- 高速: ~100km/h
- 国道: ~60-70km/h
- 山路: ~40-50km/h
- 戈壁公路: ~70-80km/h
- 城市: ~30-40km/h

### 6. Pre-trip countdown timeline
Work backwards from departure:
- 3-4 weeks: hardest-to-get tickets, most constrained bookings
- 2 weeks: accommodation, vehicle confirmation
- 1 week: vehicle check, offline maps, gear
- 1-3 days: remaining tickets, cash, final confirmations

## Pitfalls

- Markdown tables auto-size columns — use HTML `<table width="100%">` for images that must fill width
- August is rainy season for 青甘线 eastern segment — always add weather contingency
- 敦煌 in August: extreme heat (35°C+), schedule outdoor activities for morning/evening
- 黑马河 accommodation is basic — set expectations, offer alternative (共和县)
- 祁连 mountain roads dangerous in rain — always note this in弹性 section
- 莫高窟 A类票 must be booked 1 month ahead, 8月 is hardest month
