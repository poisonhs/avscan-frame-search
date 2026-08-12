#!/usr/bin/env python3
"""AVScan - 识图反查日本 AV 番号的通用 CLI 工具

通过 avscan.cc 免费 API 识图反查番号、相似度、时间点，并下载命中帧缩略图。
免注册、免鉴权。任何 Agent / 脚本均可调用。

用法:
  python avscan.py search <图片路径> [--json] [--top N]
  python avscan.py thumbs <图片路径> [-o 输出目录] [--max-frames N] [--skip-placeholder]
  python avscan.py batch <目录或列表> [-o out.csv]
  python avscan.py stats

依赖: 仅标准库 (urllib)。缩略图占位检测可选 PIL(无则跳过该功能)。
"""

import argparse
import csv
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

API_BASE = "https://avscan.cc"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
MAX_FRAMES = 6  # 每个番号最多展示帧数（与站点前端一致）


def http_request(url, data=None, method=None, timeout=30, content_type=None):
    """通用 HTTP 请求，返回 (status, body_bytes)。"""
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", UA)
    if content_type:
        req.add_header("Content-Type", content_type)
    if data is not None and not isinstance(data, bytes):
        # multipart 用 bytes
        raise ValueError("multipart body must be bytes")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def search(image_path, top_n=None):
    """上传图片搜索，返回 results 列表（最多 20 条，无分页）。"""
    boundary = "----avscan" + str(int(time.time() * 1000))
    with open(image_path, "rb") as f:
        file_bytes = f.read()
    ext = os.path.splitext(image_path)[1].lower() or ".jpg"
    mime = {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".webp": "image/webp", ".gif": "image/gif", ".bmp": "image/bmp",
    }.get(ext, "application/octet-stream")
    fname = os.path.basename(image_path)

    parts = []
    parts.append(f"--{boundary}\r\n".encode())
    parts.append(f'Content-Disposition: form-data; name="file"; filename="{fname}"\r\n'.encode())
    parts.append(f"Content-Type: {mime}\r\n\r\n".encode())
    parts.append(file_bytes)
    parts.append(f"\r\n--{boundary}--\r\n".encode())
    body = b"".join(parts)

    status, resp = http_request(
        f"{API_BASE}/search", data=body, method="POST",
        content_type=f"multipart/form-data; boundary={boundary}")
    if status != 200:
        raise RuntimeError(f"search failed: HTTP {status}: {resp.decode(errors='replace')[:300]}")
    data = json.loads(resp.decode())
    results = data.get("results", [])
    return results[:top_n] if top_n else results


def parse_timestamp(image_name):
    """'MGNL-142_02-01-28.jpg' -> '02:01:28'"""
    base = image_name.rsplit("/", 1)[-1].rsplit(".", 1)[0]
    return base.rsplit("_", 1)[-1].replace("-", ":")


def thumb_url(video_code, image_name):
    base = image_name.rsplit(".", 1)[0]
    return f"{API_BASE}/thumb/{video_code}/{base}.webp"


def is_placeholder_webp(data):
    """用 PIL 判断 WEBP 是否为灰色占位图（颜色数 <50）。无 PIL 时返回 False。"""
    try:
        from PIL import Image
    except ImportError:
        return False
    try:
        im = Image.open(io.BytesIO(data)).convert("RGB")
        n = len(im.getcolors(maxcolors=1_000_000) or [])
        return n < 50
    except Exception:
        return False


def download_thumbs(results, out_dir=".", max_frames=MAX_FRAMES, skip_placeholder=False):
    """下载每条结果前 max_frames 帧缩略图。
    返回 [(video_code, timestamp, 本地路径), ...]"""
    os.makedirs(out_dir, exist_ok=True)
    saved = []
    for v in results:
        code = v["video_code"]
        for f in v["frames"][:max_frames]:
            url = thumb_url(code, f["image_name"])
            status, data = http_request(url)
            if status != 200:
                continue
            if skip_placeholder and is_placeholder_webp(data):
                continue
            ts = parse_timestamp(f["image_name"])
            p = os.path.join(out_dir, f"{code}_{ts.replace(':', '-')}.webp")
            with open(p, "wb") as fp:
                fp.write(data)
            saved.append((code, ts, p))
    return saved


def cmd_search(args):
    results = search(args.image, top_n=args.top)
    if args.json:
        print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
        return
    # 文本表格
    for i, v in enumerate(results, 1):
        times = " / ".join(parse_timestamp(f["image_name"]) for f in v["frames"])
        print(f"{i}. {v['video_code']}  {v['best_similarity']}%  @ {times}")


def cmd_thumbs(args):
    results = search(args.image, top_n=args.top)
    saved = download_thumbs(results, out_dir=args.out,
                            max_frames=args.max_frames,
                            skip_placeholder=args.skip_placeholder)
    print(f"下载 {len(saved)} 张缩略图到 {os.path.abspath(args.out)}:")
    for code, ts, p in saved:
        print(f"  {code}  @ {ts}  ->  {p}")


def cmd_batch(args):
    images = args.images if isinstance(args.images, list) else args.images
    rows = []
    for p in images:
        try:
            results = search(p)
            if results:
                top = results[0]
                rows.append([p, top["video_code"], top["best_similarity"],
                             parse_timestamp(top["frames"][0]["image_name"])])
            else:
                rows.append([p, "NO_MATCH", "", ""])
        except Exception as e:
            rows.append([p, "ERROR", str(e), ""])
    out = args.out or "avscan_results.csv"
    with open(out, "w", newline="", encoding="utf-8") as fp:
        csv.writer(fp).writerows(rows)
    print(f"已写入 {out} ({len(rows)} 张图片)")


def cmd_stats(args):
    for path in ("/stats/daily", "/stats/indexed", "/stats/hot?limit=10"):
        status, resp = http_request(f"{API_BASE}{path}")
        if status == 200:
            print(f"{path}: {resp.decode()}")
        else:
            print(f"{path}: HTTP {status}")


def main():
    parser = argparse.ArgumentParser(
        prog="avscan", description="识图反查日本 AV 番号 (avscan.cc 免费 API)")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("search", help="识图搜番")
    p1.add_argument("image", help="图片路径")
    p1.add_argument("--json", action="store_true", help="输出 JSON")
    p1.add_argument("--top", type=int, default=None, help="只显示前 N 条")
    p1.set_defaults(func=cmd_search)

    p2 = sub.add_parser("thumbs", help="识图并下载命中帧缩略图")
    p2.add_argument("image", help="图片路径")
    p2.add_argument("-o", "--out", default=".", help="输出目录")
    p2.add_argument("--top", type=int, default=None, help="处理前 N 条")
    p2.add_argument("--max-frames", type=int, default=MAX_FRAMES, help=f"每番号最多帧数 (默认 {MAX_FRAMES})")
    p2.add_argument("--skip-placeholder", action="store_true", help="跳过灰色占位图 (需 PIL)")
    p2.set_defaults(func=cmd_thumbs)

    p3 = sub.add_parser("batch", help="批量识图，输出 CSV")
    p3.add_argument("images", nargs="+", help="多张图片路径")
    p3.add_argument("-o", "--out", default=None, help="输出 CSV 路径")
    p3.set_defaults(func=cmd_batch)

    p4 = sub.add_parser("stats", help="站点统计")
    p4.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    try:
        args.func(args)
    except Exception as e:
        print(f"错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
