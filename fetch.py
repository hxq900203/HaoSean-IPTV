# ============================================================
# 电视直播源自动抓取程序
#
# 这个程序做三件事：
#   1. 从 iptv-org（一个整理全球公开免费电视源的项目）下载频道列表
#   2. 一个个试播，看哪些频道现在能看
#   3. 把能看的频道整理成播放列表文件（.m3u），手机 App 直接就能用
#
# 你不需要自己运行它，GitHub 每天会自动运行。
# 只用到 Python 自带的功能，不需要额外安装任何东西。
# ============================================================

import re
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

# ------------------------------------------------------------
# 【可以改的设置】
# ------------------------------------------------------------

BASE = "https://iptv-org.github.io/iptv"

# 要抓哪些频道：左边是在 App 里显示的分组名，右边是频道列表的下载地址。
# 想加别的国家，照着格式加一行就行，比如日本是 countries/jp.m3u
SOURCES = {
    "中国大陆": [f"{BASE}/countries/cn.m3u"],
    "港澳台": [f"{BASE}/countries/hk.m3u", f"{BASE}/countries/mo.m3u", f"{BASE}/countries/tw.m3u"],
    "国际新闻": [f"{BASE}/categories/news.m3u"],
}

# 国内频道没测通时，不直接删掉，而是放进这个分组。
# 原因：检测是在 GitHub 的海外服务器上做的，有些频道只允许国内访问，
# 在海外测不通，但你在国内其实能看。
BACKUP_GROUP = "中国大陆（备用）"

TIMEOUT = 8  # 试播一个频道最多等几秒，超过就算不能看
WORKERS = 64  # 同时试播多少个频道（数字越大检测越快）

# 假装自己是普通浏览器，有些频道会拒绝不像浏览器的访问
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


# ------------------------------------------------------------
# 【第 1 步】下载频道列表
# ------------------------------------------------------------

def download(url):
    """下载一个网址的内容。失败会自动重试 3 次，避免网络偶尔抽风。"""
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5)  # 等 5 秒再试


def parse_m3u(text):
    """读懂播放列表文件。

    .m3u 文件里，每个频道占两行：
        #EXTINF:-1 group-title="分组",频道名   <- 频道信息
        http://xxx/xxx.m3u8                     <- 播放地址
    这里把它们配成一对一对的：[(频道信息, 播放地址), ...]
    """
    channels = []
    info = None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXTINF"):
            info = line
        elif line and not line.startswith("#") and info:
            channels.append((info, line))
            info = None
    return channels


def set_group(info, group):
    """把频道原来的分组名换成我们自己的（比如“中国大陆”），App 里看着更整齐。"""
    if 'group-title="' in info:
        return re.sub(r'group-title="[^"]*"', f'group-title="{group}"', info)
    return info.replace("#EXTINF:-1", f'#EXTINF:-1 group-title="{group}"', 1)


def channel_name(info):
    """从频道信息里取出频道名（逗号后面那部分）。"""
    return info.rsplit(",", 1)[-1].strip()


# ------------------------------------------------------------
# 【第 2 步】试播，检测频道能不能看
# ------------------------------------------------------------

def is_alive(url):
    """打开播放地址，读一小段内容。能正常读到就算这个频道能看。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            if resp.status != 200:
                return False
            head = resp.read(2048)
            # .m3u8 格式的地址，正常的话开头会有 #EXTM3U 字样
            if ".m3u8" in url.lower():
                return b"#EXTM3U" in head
            return len(head) > 0
    except Exception:
        return False


# ------------------------------------------------------------
# 【第 3 步】排序并保存成文件
# ------------------------------------------------------------

def sort_key(item):
    """排序规则：按分组 → 央视（按 CCTV-1、2、3 顺序）→ 卫视 → 其他按名字。"""
    group, info, _ = item
    name = channel_name(info)
    rank = 0 if name.upper().startswith("CCTV") else 1 if "卫视" in name else 2
    num = re.search(r"\d+", name)
    return (list(SOURCES).index(group), rank, int(num.group()) if num and rank == 0 else 0, name)


def write_m3u(path, items):
    """把频道写进 .m3u 播放列表文件。"""
    with open(path, "w", encoding="utf-8") as f:
        f.write("#EXTM3U\n")
        for _, info, url in items:
            f.write(f"{info}\n{url}\n")


# ------------------------------------------------------------
# 【主流程】把上面三步串起来
# ------------------------------------------------------------

def main():
    # 下载所有分组的频道，同一个播放地址只留一个（去重）
    items, seen = [], set()
    for group, urls in SOURCES.items():
        for src in urls:
            try:
                channels = parse_m3u(download(src))
            except Exception as e:
                print(f"下载失败 {src}: {e}", file=sys.stderr)
                continue
            for info, url in channels:
                if url not in seen:
                    seen.add(url)
                    items.append((group, set_group(info, group), url))

    # 保险 1：一个频道都没下载到（多半是网络问题），就不动旧文件，保留上次能用的列表
    if not items:
        sys.exit("一个频道都没抓到，保留上次的结果")

    # 同时试播所有频道
    print(f"共抓到 {len(items)} 个频道，开始检测…")
    with ThreadPoolExecutor(WORKERS) as pool:
        alive = list(pool.map(lambda it: is_alive(it[2]), items))

    zip_alive = list(zip(items, alive))
    alive_items = sorted((it for it, ok in zip_alive if ok), key=sort_key)
    items.sort(key=sort_key)

    # 保险 2：全部频道都测不通（多半是检测时网络出了问题），同样保留上次的结果
    if not alive_items:
        sys.exit("所有频道都检测失败，保留上次的结果")

    # 中国大陆没测通的频道，改到“备用”分组，排在播放列表最后
    backup_items = sorted(
        ((g, set_group(info, BACKUP_GROUP), url) for (g, info, url), ok in zip_alive if not ok and g == "中国大陆"),
        key=sort_key,
    )

    write_m3u("all.m3u", items)  # 全部频道
    write_m3u("haosean.m3u", alive_items + backup_items)  # Hao Sean 的专属列表：能看的频道 + 国内备用

    # 生成统计表：每个分组能看几个、什么时候更新的
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
    lines = [f"更新时间：{now}（北京时间）", "", "| 分组 | 可用 / 总数 |", "| :-- | :-- |"]
    for group in SOURCES:
        total = sum(1 for it in items if it[0] == group)
        ok = sum(1 for it in alive_items if it[0] == group)
        lines.append(f"| {group} | {ok} / {total} |")
    lines.append(f"| {BACKUP_GROUP} | {len(backup_items)}（海外没测通，国内可能能看） |")
    with open("stats.md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
