# AVScan API 细节

## 接口一览

| 接口 | 方法 | 用途 |
|---|---|---|
| `/search` | POST | 识图反查番号（核心） |
| `/thumb/{code}/{base}.webp` | GET | 预览帧缩略图，`base` = image_name 去扩展名 |
| `/stats/daily` | GET | 今日检索量 `{"date":"2026-08-12","count":77593}` |
| `/stats/indexed` | GET | 收录量 `{"title_count":0,"frame_count":75102578}` |
| `/stats/hot?limit=N` | GET | 热搜番号 `[{"code":"MIDV-854","count":1673}]` |

基础域名：`https://www.avscan.cc`（Cloudflare 托管，无需 Cookie/鉴权）。

## POST /search

### 请求

```
POST https://www.avscan.cc/search
Content-Type: multipart/form-data
表单字段: file=<图片>
```

限制：`image/*`、≤8MB（服务端实测不强制，但按官方口径传）。

### 成功响应 (200)

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

- 最多返回 20 条（服务端上限，无分页；实际可能少于 20，取决于匹配数量。实测 `limit`/`top_k`/`page`/`offset` 等参数均被忽略），按 `best_similarity` 降序；`frames` 为该片命中的预览帧，`similarity` 为单帧相似度。
- `image_name` 格式 `{番号}_{时-分-秒}.jpg`，时间点即画面在片中的位置。

### 错误响应

| 状态码 | 响应 | 说明 |
|---|---|---|
| 400 | `{"detail":"invalid image"}` | 非图片文件 |
| 429 | nginx limit_req | 频率过高，稍后重试 |
| 其他 | `{"detail":"..."}` | 服务器错误 |

## GET /thumb/{code}/{base}.webp — 命中帧缩略图

HTTP 200 返回 WEBP（400×224）。**绝大多数帧是真实画面**（实测真实截图搜索返回的帧几乎全部有真实缩略图），仅极少数帧（冷门作品、纯色无特征图命中的帧）返回灰色占位图。CDN 缓存一年（`Cache-Control: public, max-age=31536000, immutable`），可批量下载。

```bash
curl -s -o thumb.webp "https://avscan.cc/thumb/CSCT-002/CSCT-002_02-15-20.webp"
```

验证方法（判断是否为占位图）：下载后用 PIL 统计颜色数，<50 种颜色即为占位图。

```python
from PIL import Image

def is_placeholder(path: str) -> bool:
    im = Image.open(path).convert("RGB")
    n = len(im.getcolors(maxcolors=1_000_000) or [])
    return n < 50  # 真实帧通常数百~数千种颜色，占位图 2~100 种
```

Python 示例（下载帧缩略图，跳过占位图）：

```python
import requests

MAX_FRAMES = 6  # 与站点前端展示上限一致

def thumb_url(video_code: str, image_name: str) -> str:
    base = image_name.rsplit(".", 1)[0]  # 去扩展名
    return f"https://avscan.cc/thumb/{video_code}/{base}.webp"

def download_thumbs(results: list[dict], out_dir: str = ".",
                    max_frames: int = MAX_FRAMES, top_videos: int | None = None):
    """下载每条结果的帧缩略图（只保留非占位图）。
    - 每条结果取前 max_frames 帧
    - top_videos 限制处理的结果条数（None = 全部）
    返回 [(video_code, timestamp, 本地路径), ...]
    """
    paths = []
    for v in results[:top_videos] if top_videos else results:
        code = v["video_code"]
        for f in v["frames"][:max_frames]:
            url = thumb_url(code, f["image_name"])
            r = requests.get(url, timeout=30)
            r.raise_for_status()
            p = f"{out_dir}/thumb_{len(paths)}.webp"
            open(p, "wb").write(r.content)
            if not is_placeholder(p):
                ts = f["image_name"].rsplit("_", 1)[-1].rsplit(".", 1)[0].replace("-", ":")
                paths.append((code, ts, p))
    return paths
```

## Python 示例

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

## 批量识别

```python
import csv, requests

def batch_search(images: list[str], out_csv: str):
    rows = []
    for p in images:
        try:
            r = requests.post("https://www.avscan.cc/search",
                              files={"file": open(p, "rb")}, timeout=30)
            r.raise_for_status()
            top = r.json()["results"][0]
            rows.append([p, top["video_code"], top["best_similarity"],
                         top["frames"][0]["image_name"]])
        except Exception as e:
            rows.append([p, "ERROR", str(e), ""])
    with open(out_csv, "w", newline="") as f:
        csv.writer(f).writerows(rows)
```

## 注意

- 该站为成人内容检索工具，结果可能涉及成人作品番号；按用户需求处理，不做额外审核改写。
- 高频调用可能触发 429 限流，批量时加 0.3–1s 间隔。
- 结果带服务端缓存：相同图片重复搜秒回且结果一致。
