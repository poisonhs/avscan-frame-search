# avscan-frame-search

通过 [avscan.cc](https://www.avscan.cc) 免费 API 做**识图反查日本 AV 番号**的通用 Agent Skill。

上传一张视频截图/帧画面，毫秒级反查作品番号（video_code）、相似度（best_similarity）与对应时间点，并返回命中帧缩略图。免注册、免鉴权、无限次。

不依赖任何特定 Agent 平台（LiveAgent / Claude / Codex / Cursor 均可使用）——核心是一个独立 Python CLI 脚本，只有标准库依赖。

## 功能

- 🔍 **识图搜番**：上传截图，反查番号 + 相似度 + 时间点（`image_name` 中自动解析 `HH:MM:SS`）
- 🖼 **缩略图交付**：下载每个番号命中的所有帧缩略图（最多 6 帧）
- 📦 **全部结果**：返回接口给出的全部番号（服务端上限 20 条，无分页）
- 🧹 **灰图过滤**：自动识别并跳过灰色占位图（需 PIL，可选）
- 📊 **批量识别**：多张图片批量反查，导出 CSV
- 📈 **站点统计**：今日检索量 / 收录量 / 热搜

## 快速开始

```bash
# 识图搜番（表格输出）
python scripts/avscan.py search 截图.jpg

# JSON 输出（方便程序解析）
python scripts/avscan.py search 截图.jpg --json

# 识图并下载全部命中帧缩略图
python scripts/avscan.py thumbs 截图.jpg -o ./thumbs --skip-placeholder

# 批量识图，导出 CSV
python scripts/avscan.py batch 图1.jpg 图2.jpg -o results.csv

# 站点统计
python scripts/avscan.py stats
```

依赖：Python 3.8+，仅标准库（`urllib`）。`--skip-placeholder` 需要 `Pillow`（可选）。

## 作为 Agent Skill 使用

1. 把本仓库加入 Agent 的知识/技能目录，或直接告诉 Agent 使用 `scripts/avscan.py`。
2. 用户提供截图时：
   - 本地图片 → 直接传给 CLI
   - URL 图片 → 先下载到本地临时文件
3. 解析 CLI 的 JSON 输出，按番号分组交付（**缩略图必须用 Markdown 图片语法内联渲染，不要用文字占位**）：

```
**1. OFJE-264**  89.93%  @ 00:21:56 / 00:22:20 / 00:21:53 / 00:21:48
![](https://avscan.cc/thumb/OFJE-264/OFJE-264_00-21-56.webp) ![](https://avscan.cc/thumb/OFJE-264/OFJE-264_00-22-20.webp)
**2. SSIS-783**  89.85%  @ 00:26:27 / 00:26:30
![](https://avscan.cc/thumb/SSIS-783/SSIS-783_00-26-27.webp) ![](https://avscan.cc/thumb/SSIS-783/SSIS-783_00-26-30.webp)
...
```

缩略图 URL 格式：`https://avscan.cc/thumb/{番号}/{帧名去掉扩展名}.webp`

## CLI 输出示例

```bash
$ python scripts/avscan.py search shot.png
1. OFJE-264  89.93%  @ 00:21:56 / 00:22:20 / 00:21:53 / 00:21:48
2. SSIS-783  89.85%  @ 00:26:27 / 00:26:30
3. MIDV-103  89.54%  @ 00:44:43 / 00:45:29
```

```bash
$ python scripts/avscan.py search shot.png --json
{
  "results": [
    {
      "video_code": "OFJE-264",
      "best_similarity": 89.93,
      "frames": [
        {"image_name": "OFJE-264_00-21-56.jpg", "similarity": 89.93},
        ...
      ]
    },
    ...
  ]
}
```

## 核心接口（直接用也可以）

### POST /search — 识图搜番

```
POST https://www.avscan.cc/search
Content-Type: multipart/form-data
表单字段: file=<图片>   (image/*, ≤8MB)
```

响应：`{"results":[{video_code, best_similarity, frames:[{image_name, similarity}]}, ...]}`，最多 20 条，按相似度降序。`limit`/`top_k`/`page`/`offset` 参数均被忽略，无分页。

### GET /thumb/{code}/{base}.webp — 命中帧缩略图

```
https://avscan.cc/thumb/CSCT-002/CSCT-002_02-15-20.webp
```

400×224 WEBP，绝大多数为真实画面；CDN 缓存一年（immutable）。

### 其他

| 接口 | 用途 |
|---|---|
| `GET /stats/daily` | 今日检索量 |
| `GET /stats/indexed` | 收录帧数 |
| `GET /stats/hot?limit=N` | 热搜番号 |

## 错误处理

| 状态码 | 含义 | 处理 |
|---|---|---|
| 400 | 非图片文件 | 检查文件格式 |
| 429 | 限流 | 稍后重试，批量时加 0.3–1s 间隔 |
| 其他 | 服务器错误 | 查看 `detail` 字段 |

## 提示

- 建议先裁剪到特征区域、去水印再搜，准确率更高
- 相同图片会命中服务端结果缓存（秒回、结果一致）
- 相似度分档参考：≥85 高 / ≥70 中 / 其余低
- 纯色无特征图可能得到虚高的相似度，需结合结果排序人工判断

## 目录结构

```
avscan-frame-search/
├── SKILL.md              # Skill 描述与工作流（通用格式）
├── README.md             # 本文档
├── scripts/
│   └── avscan.py         # 独立 CLI（仅标准库）
└── references/
    └── api.md            # 接口细节与 Python 示例
```

## 声明

该工具用于成人内容检索的元数据查询；结果可能涉及成人作品番号。请遵守当地法律法规，仅用于合法用途。
