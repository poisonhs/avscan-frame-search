# avscan-frame-search

通过 [avscan.cc](https://www.avscan.cc) 免费 API 做**识图反查日本 AV 番号**的 LiveAgent Skill。

上传一张视频截图/帧画面，毫秒级反查作品番号（video_code）、相似度（best_similarity）与对应时间点，并返回命中帧缩略图。免注册、免鉴权、无限次。

## 功能

- 🔍 **识图搜番**：上传截图，反查番号 + 相似度 + 时间点（`image_name` 中自动解析 `HH:MM:SS`）
- 🖼 **缩略图交付**：每个番号一组，展示该番号命中的所有帧缩略图（最多 6 帧），逐组排列
- 📦 **全部结果**：返回接口给出的全部番号（服务端上限 20 条，无分页）
- 🧹 **灰图过滤**：自动识别并跳过灰色占位图（`is_placeholder()`）
- 📊 **批量识别**：支持多张图片批量反查，可导出 CSV

## 安装

### 方式一：LiveAgent SkillsManager（推荐）

```bash
SkillsManager(action=install, source=https://github.com/poisonhs/avscan-frame-search)
```

或下载本仓库的 `avscan-frame-search.skill` 归档后本地安装：

```bash
SkillsManager(action=install, source=./avscan-frame-search.skill)
```

安装后会自动启用，可直接使用。

### 方式二：手动复制

将 `SKILL.md` 与 `references/` 目录放入 LiveAgent 的 skills 根目录，然后在聊天中启用。

## 使用

在对话中直接提供截图即可触发（支持本地图片、URL 图片）：

> 反查番号 [上传图片]

交付格式：

```
1. OFJE-264  89.93%  @ 00:21:56 / 00:22:20 / 00:21:53 / 00:21:48
   [缩略图] [缩略图] [缩略图] [缩略图]
2. SSIS-783  89.85%  @ 00:26:27 / 00:26:30
   [缩略图] [缩略图]
...
```

## 核心接口

### POST /search — 识图搜番

```
POST https://www.avscan.cc/search
Content-Type: multipart/form-data
表单字段: file=<图片>   (image/*, ≤8MB)
```

响应（最多 20 条，按相似度降序）：

```json
{
  "results": [
    {
      "video_code": "MGNL-142",
      "best_similarity": 99.98,
      "frames": [
        { "image_name": "MGNL-142_00-00-09.jpg", "similarity": 99.98 },
        { "image_name": "MGNL-142_02-01-28.jpg", "similarity": 97.55 }
      ]
    }
  ]
}
```

- `image_name` 格式 `{番号}_{时-分-秒}.jpg`，时间点即画面在片中的位置
- `limit`/`top_k`/`page`/`offset` 等参数均被服务端忽略，无分页

### GET /thumb/{code}/{base}.webp — 命中帧缩略图

```
https://avscan.cc/thumb/CSCT-002/CSCT-002_02-15-20.webp
```

400×224 WEBP，绝大多数为真实画面；CDN 缓存一年（immutable），可批量下载。

## 快速调用示例

### curl

```bash
curl -s --max-time 30 -X POST https://www.avscan.cc/search \
  -F "file=@截图.jpg;type=image/jpeg"
```

### Python

```python
import requests

def search_frame(image_path: str, top_n: int = 10):
    r = requests.post(
        "https://www.avscan.cc/search",
        files={"file": (image_path.split("/")[-1], open(image_path, "rb"), "image/jpeg")},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["results"][:top_n]

def parse_timestamp(image_name: str) -> str:
    """'MGNL-142_02-01-28.jpg' -> '02:01:28'"""
    base = image_name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return base.rsplit("_", 1)[-1].replace("-", ":")

for v in search_frame("截图.jpg"):
    print(v["video_code"], v["best_similarity"],
          parse_timestamp(v["frames"][0]["image_name"]))
```

更多示例（缩略图下载、灰图过滤、批量 CSV）见 `references/api.md`。

## 提示

- 建议先裁剪到特征区域、去水印再搜，准确率更高
- 上传 ≤8MB；非图片返回 `400 {"detail":"invalid image"}`
- 相同图片会命中服务端结果缓存（秒回、结果一致）
- 高频调用可能触发 429 限流，批量时加 0.3–1s 间隔
- 相似度分档参考：≥85 高 / ≥70 中 / 其余低

## 声明

该工具用于成人内容检索的元数据查询；结果可能涉及成人作品番号。请遵守当地法律法规，仅用于合法用途。
