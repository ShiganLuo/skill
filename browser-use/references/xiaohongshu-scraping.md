# 小红书抓取完整配方（2026-10 两轮实测）

覆盖：站内搜索 → token 直连详情 → caption 正文 → 轮播图（图内正文）→ OCR → 风控与收尾。
SKILL.md 已给要点，这里是可照抄的执行细节与踩坑原文。

## 1. 启动组合（一次成功过的命令）

```bash
# terminal(background=true)
google-chrome --headless=new --remote-debugging-port=9222 \
  --remote-allow-origins=* --user-data-dir=<dedicated-profile> \
  --no-first-run --no-default-browser-check --disable-gpu --no-proxy-server \
  --lang=zh-CN \
  --user-agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/<系统版本> Safari/537.36" \
  about:blank
```

- **`--user-agent` 是解 300012 的钥匙**（第二轮实测）：headless 默认 UA 带
  `HeadlessChrome`，XHS 直接判 300012「IP at risk」——直连、系统代理、换 profile
  全都无效；换成真实桌面 UA（版本对齐 `chrome --version`）后风控页立刻消失。
  第一轮没撞上是因为当时用的可见窗口（真 UA）。
- `--no-proxy-server`：绕开系统代理（gsettings 常为 manual）。UA 修好后直连即干净。
- `--remote-allow-origins=*`：否则 WS 被拒（日志见 `Rejected an incoming WebSocket connection`）。
- `.env` 注入（CLI 先起 daemon，代码内设 env 无效）写三处：会话 workspace、
  `~/.config/browser-harness/agent-workspace/`、`~/.config/browser-harness/`。
- **风控过后是登录墙**（"登录后查看搜索结果"，2026-10 起站内搜索强制登录）：
  用**可见窗口**让用户扫二维码 —— `DISPLAY=:0 ... --ozone-platform=x11` +
  持久专用 profile（如 `~/.config/xhs-scraper`），二维码在 `.login-modal` 的
  `img.qrcode-img`（base64 data URI，可直接落盘成 PNG 给用户扫）。登录态存在
  profile 里，**下次复用该 profile 免扫**。截图给用户前用 DOM 确认
  `login-modal` 打开且 qr `naturalWidth=128`，别让人扫过期图。

## 2. daemon 生命周期

- **换 Chrome 实例后必须 `restart_daemon()`**，且单独一次调用；紧接着的同一次调用里
  用 helper 会 `FileNotFoundError`（daemon 已杀、未起）。下一次调用自动重拉。
- 新 target 卡死（navigate/evaluate 超时）→ `new_tab(url)` 换页，别在旧 target 上重试。
- `js(expr, x)` 第二参是 **target_id**，不是变量注入；变量用 f-string 拼进表达式。

## 3. 搜索取 token

```python
for q in queries:   # 每组关键词约返回前 20-22 条
    goto_url("https://www.xiaohongshu.com/search_result?keyword=" + urllib.parse.quote(q)
             + "&source=web_search_result_notes")
    wait_for_load(); time.sleep(5)
    items = js("""(()=>{const f=window.__INITIAL_STATE__?.search?.feeds?.value
        ||window.__INITIAL_STATE__?.search?.feeds?._rawValue||[];
        return f.filter(x=>x&&x.id).map(x=>({id:x.id,title:x.displayTitle||'',
        token:x.xsecToken||''}));})()""")
```

- 按 id 去重存 JSON；目标不在窗口内就用它的**完整标题**当关键词重搜，仍无则记缺口。
- token 绑定该次搜索上下文，取完尽快用。

## 4. 直连详情与验证

```
https://www.xiaohongshu.com/explore/<id>?xsec_token=<tok>&xsec_source=pc_search
```

- **token 不可 URL 编码**：`quote()` 把 `=` 转 `%3D` → 全部 404（本配方第一大坑）。
- 验证：`document.title` 不含"页面不见了"、`#detail-text` 有正文。

## 5. 图内正文（用户会明确指出"你没滑图片"）

```js
[...new Set([...document.querySelectorAll('.swiper-slide:not(.swiper-slide-duplicate) img')]
    .map(i=>i.currentSrc||i.src).filter(u=>u&&u.includes('xhscdn')))]
```

- 图的 `src` 本来就在 DOM 里，**不需要翻轮播**；`naturalWidth===0` 只是未加载，
  绝不能按它过滤（9 页会被筛成 1 页）。
- 下载：execute_code 里 `urllib.request` + 8 线程直连 CDN（39 张约 10 秒；如被 403，
  请求头带 `Referer: https://www.xiaohongshu.com/`）。
- OCR：`sudo apt install tesseract-ocr-chi-sim`，然后
  `tesseract img.png stdout -l chi_sim+eng --psm 6`（39 张约 7 秒）。
  vision 附件读不出内容时 OCR 是兜底——**读不出就说读不出，不编转录**。
- **长截图（BOSS直聘 JD、1080×4000+ 手机长图）tesseract 会大面积乱码**，切块、
  2-3 倍放大、二值化都救不回来；首选直接调视觉模型整图识别：
  读 `.env` 的 `GLM_API_KEY` → POST `https://open.bigmodel.cn/api/paas/v4/chat/completions`，
  model `glm-4.5v`，`image_url` 用 base64 data URI，prompt「逐字提取全部文字按原始排版输出」，
  `max_tokens` 8000+——一次调用完整读出 4742px 长图，质量远超 tesseract。
- **视觉 API 选型原则（用户纠正过）**：某 API 服务不可用（429/到期）时，先查当前
  会话实际用的什么模型（看 `.env`/config 的 BASE_URL+MODEL），再调**对应厂商**的
  视觉模型——不要惯性沿用旧会话的方案（XIAOMI 已到期还在调就是踩过这个坑）。
- 批量走 vision 前先 PIL 拼接：600px 宽 × 最多 3 张/块，按笔记分块并保留编号映射。

## 6. 点击兜底（token 路线不可用时）

- JS `.click()` → `isTrusted=false` → `sec_cv` 风控；只能用 `click_at_xy`（CDP Input）。
- 虚拟列表 rect 与命中区错位（滚动动画中测量尤其糟）：点前用
  `document.elementFromPoint(x,y).closest('[data-note-id]')` 验证点属于目标卡；
  不行就整屏网格扫描找属于目标卡的点。视口 ≥1200×1000 更稳（800×513 易偏）。

## 7. 300012 风控梯子（按顺序，0 号解决过 90%）

0. **伪装桌面 UA**（第二轮定论）：`--user-agent="Mozilla/5.0 (X11; Linux
   x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/<ver> Safari/537.36"`
   —— `HeadlessChrome` 串才是被标的原因；直连/代理/换 profile 都治不了它。
1. `--no-proxy-server` 直连（UA 修好后通常即可）；
2. 换全新 `--user-data-dir`（新 cookie）；
3. 300012 消失但出现"登录后查看搜索结果" → 这是**登录墙不是风控**：
   可见窗口 + 持久 profile 让用户扫码（见 §1），登录后站内搜索/详情全通；
4. 以上全试过仍 300012 → 该 IP 真被标记，停手，改走公开渠道
   （牛客/应届生/知乎/官网），并在交付里如实写明缺口与原因。

## 8. 收尾（每次做）

kill Chrome（确认 9222 不再监听）→ 删三个 `.env`（否则后续会话全挂死端口上）。

## 内容甄别

- 抓完要验内容性质：牛客"面经"可能是 **AI 机器人客服回复**（AI牛可乐），不是面试记录。
- 同名公司易混：「镁伽科技」≠「镁佳科技」（汽车软件），面经张冠李戴要不得。
