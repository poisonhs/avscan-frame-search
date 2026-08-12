---
name: avscan-frame-search
description: 通过 avscan.cc 免费 API 做识图反查日本 AV 番号与时间点。使用当用户提供视频截图/帧画面，需要反查作品番号、相似度或对应时间点时；支持本地图片、URL 图片和批量识别。
---

# AVScan Frame Search

通过 avscan.cc 的免费 `/search` 接口，对图片做向量检索，反查日本 AV 作品番号（video_code）、相似度（best_similarity）和对应时间点（从 image_name 解析）。免注册、免鉴权、无限次。

## 工作流

1. 确认输入图片来源：
   - 本地图片路径 → 直接传入 CLI
   - URL 图片 → 先下载到本地临时文件，再传入 CLI
   - 批量图片 → 用 `batch` 子命令，结果汇总为 CSV
2. 调用 `scripts/avscan.py` 识图反查：
   ```bash
   python scripts/avscan.py search <图片路径> --json
   ```
3. 返回接口给出的**全部结果**（服务端上限 20 条，无分页，实际可能少于 20——取决于匹配数量；`limit`/`top_k`/`page`/`offset` 等参数均被服务端忽略），按相似度降序。
4. **按番号分组交付**：每个番号一组，格式为「番号 → 该番号对应的所有缩略图」，从第 1 名逐组向下排列：
   ```
   1. OFJE-264  89.93%  @ 00:21:56 / 00:22:20 / 00:21:53 / 00:21:48
      [缩略图] [缩略图] [缩略图] [缩略图]   ← 该番号全部帧
   2. SSIS-783  89.85%  @ 00:26:27 / 00:26:30
      [缩略图] [缩略图]                     ← 该番号全部帧
   3. MIDV-103  89.54%  @ 00:44:43 / 00:45:29
      [缩略图] [缩略图]
   ```
5. **缩略图展示（必须内联渲染图片，不能只写文字）**：
   - **方式 A（推荐，任何支持 Markdown 的 Agent）**：直接用 Markdown 图片语法内联渲染，不要用 `[缩略图]` 之类的文字占位：
     ```markdown
     **1. OFJE-264** 89.93% @ 00:21:56 / 00:22:20 / 00:21:53 / 00:21:48
     ![](https://avscan.cc/thumb/OFJE-264/OFJE-264_00-21-56.webp) ![](https://avscan.cc/thumb/OFJE-264/OFJE-264_00-22-20.webp)
     **2. SSIS-783** 89.85% @ 00:26:27 / 00:26:30
     ![](https://avscan.cc/thumb/SSIS-783/SSIS-783_00-26-27.webp) ![](https://avscan.cc/thumb/SSIS-783/SSIS-783_00-26-30.webp)
     ```
   - **方式 B（有图片显示工具的 Agent）**：调用图片工具传入缩略图 URL 逐组展示。
   - 缩略图 URL 格式：`https://avscan.cc/thumb/{video_code}/{image_name去掉扩展名}.webp`（如 `OFJE-264_00-21-56.jpg` → `https://avscan.cc/thumb/OFJE-264/OFJE-264_00-21-56.webp`）
   - 每个番号最多 6 帧；多帧可验证匹配可靠性（不同时间点画面是否一致）
   - 极少数帧（无缩略图索引）返回灰色占位图（400×224，颜色数 <50），用 `--skip-placeholder` 自动跳过；也可用 `scripts/avscan.py thumbs` 下载到本地后再展示本地文件

## 常用命令

```bash
# 识图搜番（文本表格输出）
python scripts/avscan.py search 截图.jpg

# 识图搜番（JSON 输出，方便程序解析）
python scripts/avscan.py search 截图.jpg --json

# 识图并下载全部命中帧缩略图（跳过灰色占位图）
python scripts/avscan.py thumbs 截图.jpg -o ./thumbs --skip-placeholder

# 批量识图，输出 CSV
python scripts/avscan.py batch 图1.jpg 图2.jpg 图3.jpg -o results.csv

# 站点统计（今日检索量 / 收录量 / 热搜）
python scripts/avscan.py stats
```

## 要点

- 建议先裁剪到特征区域、去水印再搜，准确率更高；站点前端实际发送的是长边 1024px、JPEG 0.85 的压缩图，直接传原图效果相当。
- 上传 ≤8MB；非图片返回 `400 {"detail":"invalid image"}`。
- 相同图片会命中服务端结果缓存（秒回、结果一致）。
- 时间点解析：`MGNL-142_02-01-28.jpg` → `02:01:28`（第 2 分 1 秒 28 帧）。
- 相似度分档参考：≥85 高 / ≥70 中 / 其余低；纯色无特征图也可能得到虚高的相似度，需结合结果排序人工判断。
- 缩略图 400×224 WEBP，CDN 缓存一年（immutable），可放心批量下载；绝大多数帧是真实画面，极少数冷门帧返回灰色占位图。
- 高频调用可能触发 429 限流，批量时加 0.3–1s 间隔。

## 参考

- `references/api.md` — 接口细节、错误处理、Python 示例
