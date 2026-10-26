---
name: app-performance-diagnosis
description: "诊断桌面应用卡慢（Obsidian/VSCode 等 Electron 重插件应用），用户报'慢'时用."
version: 1.0.0
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [performance, diagnosis, electron, obsidian, 慢, 卡]
---

# 桌面应用卡慢诊断

用户说"XX 应用为什么这么慢/这么卡"时的通用排查框架。核心纪律：**先排除硬件层，再查应用层**；逐层收集证据，不要上来就猜。

## 第一步：排除硬件层（10 秒）

```bash
ps aux | grep -i <app> | grep -v grep    # 进程 RSS 总量(合计子进程)、运行时长
free -h                                   # 看 available，不是 used
iostat -x 1 2                             # %iowait 应接近 0
lsblk -d -o NAME,ROTA                     # ROTA=0 是 SSD；HDD 上一切卡先怪磁盘
df -h <数据目录>                          # 磁盘满也会卡
```

硬件层无辜的判据：SSD、内存 available 充足、CPU idle 高、应用进程 IO≈0 → 问题在应用配置层。

## 第二步：数据目录规模与巨型文件

应用慢的头号常见原因不是插件多，是**单个巨型文件**：

```bash
find <数据目录> -name '*.md' -size +500k    # 巨型笔记
du -sh <数据目录>/*/ | sort -rh             # 哪个子目录占大头
find <数据目录> -type f | wc -l             # 总文件数(索引/同步压力)
```

判据：单文件 >500KB 且含大量代码块/嵌入 → 打开/滚动该文件卡是必然，插件高亮会放大。

## 第三步：插件三层清点（装了 ≠ 启用 ≠ instant 启动）

```bash
ls <数据目录>/.xxx/plugins/ | wc -l
cat <数据目录>/.xxx/community-plugins.json            # 实际启用的
python3 -c "import json; d=json.load(open('<...>/lazy-plugins/data.json')); [print(k,'->',v.get('startupType')) for k,v in d.get('desktop',{}).get('plugins',{}).items()]"
```

重型插件黑名单（Obsidian）：dataview（全库索引线性涨）、excalidraw、codeblock-customizer（逐代码块高亮，遇巨型文件爆炸）、smart-connections、多套同步插件同开（fast-note-sync + remotely-save + 官方 sync = 多套文件监听）。

## 第四步：插件配置细节（data.json 找激进参数）

```bash
# 同步类: 无防抖 + 大附件 + 启动即同步 = 三连坑
python3 -c "import json; d=json.load(open('<...>/fast-note-sync/data.json')); print({k:d.get(k) for k in ['syncEnabled','pdfSyncEnabled','syncUpdateDelay','startupDelay']})"
# 核心插件白开(官方 Sync 未订阅却启用 = 空转)
python3 -c "import json; d=json.load(open('<...>/core-plugins.json')); print([k for k,v in d.items() if v])"
# 主题: Blue Topaz = 最重
cat <数据目录>/.obsidian/appearance.json
```

## 修复性价比排序（实测案例验证）

1. **巨型文件移出/拆分** —— 单文件 3.8MB/7.8 万行/446 代码块，打开卡 10 秒+，移出立竿见影
2. **同步插件排除大附件目录** + 关 pdfSync + 加 syncUpdateDelay（防抖）
3. **关闲置核心插件**（官方 sync 未用却开着）
4. **装饰性插件从 instant 改 lazy 加载**
5. **主题对照试验**：切默认主题跑两天，定位渲染占比

## 坑

- 别把"内存 used 高"当病因——Linux buff/cache 占用正常，看 available。
- Electron 应用多进程，`ps aux` 要合计所有子进程 RSS 才是真实占用。
- 用户说"慢"要问清哪种慢：启动慢→instant 插件数；打开特定文件慢→巨型文件；全局慢→dataview/索引/主题；保存慢→同步无防抖+lint。
