# ============================================================
# Hao Sean 的专属直播源：自动抓取程序
#
# 这个程序做四件事：
#   1. 下载公开免费的国内、港澳台电视频道列表（iptv-org + 网友整理源里的电视台官方地址）
#   2. 整理频道：换成中文名、分成「央视 / 地方 / 港澳台」、只留 1080P 以上的国内频道
#   3. 一个个试播，看哪些现在能看
#   4. 生成播放列表 haosean.m3u（只要 IPv4 的频道）
#   5. 保留「回看」和「节目单」信息：来源支持回看的频道，在 App 里就能看之前播过的节目
#
# 你不需要自己运行它，GitHub 每天会自动运行。
# 只用到 Python 自带的功能，不需要额外安装任何东西。
# ============================================================

import ipaddress
import json
import re
import socket
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

# ------------------------------------------------------------
# 【可以改的设置】
# ------------------------------------------------------------

BASE = "https://iptv-org.github.io/iptv"

# 频道来源：左边是地区，右边是下载地址
SOURCES = {
    "大陆": [f"{BASE}/countries/cn.m3u"],
    "港澳台": [f"{BASE}/countries/hk.m3u", f"{BASE}/countries/mo.m3u", f"{BASE}/countries/tw.m3u"],
}

# 网友整理的源：里面混着各种来路的地址，只收电视台官方的（规则见下面 OFFICIAL_HOSTS）
COMMUNITY_SOURCES = [
    "https://raw.githubusercontent.com/vbskycn/iptv/master/tv/iptv4.m3u",
    "https://raw.githubusercontent.com/Guovin/iptv-api/gd/output/ipv4/result.m3u",
]

# 电视台官方网站：地址是 .cn 结尾，或者是下面这几家（都是省市电视台自己的网站）。
# 一串数字（IP）开头的地址、来路不明的转播网站都不要。
OFFICIAL_HOSTS = ["cztv.com", "cztvcloud.com", "gztv.com", "ynurl.com", "hrbtv.net"]
# 虽然是 .cn 结尾、但属于付费平台的网站，不要
PAID_HOSTS = ["bestv.cn"]

# 网友源里这些分组不要（付费频道、广播、春晚回放、风景直播等）
SKIP_GROUPS = ["付费", "更新时间", "春晚", "直播中国", "音乐", "解说", "广播"]

# iptv-org 的频道资料库，用来把英文频道名换成中文名
CHANNELS_DB = "https://iptv-org.github.io/api/channels.json"

MIN_HEIGHT = 1080  # 国内频道最低分辨率（1080 就是 1080P）
TIMEOUT = 8  # 试播一个频道最多等几秒
WORKERS = 64  # 同时试播多少个频道

# App 里显示的分组名（前面的小图标让列表更好看）
G_CCTV = "📺 央视频道"
G_LOCAL = "📡 地方频道"
G_HMT = "🌏 港澳台"
G_BACKUP = "🔸 国内备用"  # 海外没测通、但国内可能能看的频道
GROUP_ORDER = [G_CCTV, G_LOCAL, G_HMT, G_BACKUP]

# 央视频道的中文名
CCTV_NAMES = {
    "1": "综合", "2": "财经", "3": "综艺", "4": "中文国际", "5": "体育", "5+": "体育赛事",
    "6": "电影", "7": "国防军事", "8": "电视剧", "9": "纪录", "10": "科教", "11": "戏曲",
    "12": "社会与法", "13": "新闻", "14": "少儿", "15": "音乐", "16": "奥林匹克", "17": "农业农村",
    "4K": "超高清", "8K": "超高清",
}

# 只要这些地区自己的电视台（iptv-org 的频道编号结尾就是地区代码，比如 HunanTV.cn）
ALLOWED_COUNTRIES = {"cn", "hk", "mo", "tw"}

# 不要的台：频道名里含有这些字就去掉（主要是境外机构办的、只是面向华语观众播出的台）
EXCLUDE = ["VOA", "美国之音", "BRICS", "Supreme Master", "NTD", "新唐人", "希望之声", "Epoch", "大纪元"]

# 英文省份名 → 中文，用来把 “Hunan TV” 这类英文名换成 “湖南卫视”
PROVINCES = {
    "Anhui": "安徽", "Beijing": "北京", "Chongqing": "重庆", "Dongnan": "东南", "Fujian": "福建",
    "Gansu": "甘肃", "Guangdong": "广东", "Guangxi": "广西", "Guizhou": "贵州", "Hainan": "海南",
    "Hebei": "河北", "Heilongjiang": "黑龙江", "Henan": "河南", "Hubei": "湖北", "Hunan": "湖南",
    "Jiangsu": "江苏", "Jiangxi": "江西", "Jilin": "吉林", "Liaoning": "辽宁", "Neimenggu": "内蒙古",
    "Inner Mongolia": "内蒙古", "Ningxia": "宁夏", "Qinghai": "青海", "Shaanxi": "陕西",
    "Shandong": "山东", "Shanghai": "上海", "Dragon": "东方", "Shanxi": "山西", "Shenzhen": "深圳",
    "Sichuan": "四川", "Tianjin": "天津", "Xinjiang": "新疆", "Xizang": "西藏", "Tibet": "西藏",
    "Yunnan": "云南", "Zhejiang": "浙江",
}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36"


# ------------------------------------------------------------
# 【第 1 步】下载
# ------------------------------------------------------------

def download(url):
    """下载一个网址的内容。失败会自动重试 3 次。"""
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception:
            if attempt == 2:
                raise
            time.sleep(5)


def parse_m3u(text):
    """读懂播放列表：每个频道是「#EXTINF 信息行 + 播放地址」两行，配成一对一对的。"""
    channels, info = [], None
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#EXTINF"):
            info = line
        elif line and not line.startswith("#") and info:
            channels.append((info, line))
            info = None
    return channels


def load_chinese_names():
    """从 iptv-org 频道资料库里，找出每个频道的中文名。下载失败就用英文名。"""
    try:
        db = json.loads(download(CHANNELS_DB))
    except Exception as e:
        print(f"频道资料库下载失败，使用英文名：{e}", file=sys.stderr)
        return {}
    names = {}
    for ch in db:
        for alt in ch.get("alt_names") or []:
            if re.search(r"[一-鿿]", alt):  # 含有汉字的就是中文名
                names[ch["id"]] = alt
                break
    return names


# ------------------------------------------------------------
# 【第 2 步】整理频道
# ------------------------------------------------------------

def attr(info, key):
    """从信息行里取出某一项，比如 tvg-logo（台标）。"""
    m = re.search(rf'{key}="([^"]*)"', info)
    return m.group(1) if m else ""


def name_height(raw_name):
    """从频道名里读出分辨率，比如 “(1080p)” 就是 1080。4K/8K 算 2160。没写就返回 0。"""
    m = re.search(r"\((\d{3,4})p\)", raw_name)
    if m:
        return int(m.group(1))
    if re.search(r"\b[48]K\b", raw_name, re.I):
        return 2160
    return 0


def cctv_key(raw_name):
    """如果是央视频道，返回台号（比如 “1”、“5+”、“4K”），不是就返回 None。"""
    m = re.match(r"\s*CCTV[-\s]?(\d{1,2}\+?|[48]K)(?![\d])", raw_name, re.I)
    return m.group(1).upper() if m else None


def clean_name(raw_name, tvg_id, cn_names):
    """把频道名整理干净、换成中文。"""
    key = cctv_key(raw_name)
    if key:
        return f"CCTV-{key} {CCTV_NAMES.get(key, '')}".strip()
    cn = cn_names.get(tvg_id.split("@")[0])
    if cn:
        return re.sub(r"^CCTV-央视", "央视", cn)
    # 省级卫视的英文名，比如 “Hunan TV”“Beijing Satellite TV HD” → “湖南卫视”“北京卫视”
    m = re.match(r"\s*([A-Za-z ]+?)\s+(?:Satellite\s+)?TV\b(?:\s+HD)?\s*(\(|\[|$)", raw_name)
    if m and m.group(1) in PROVINCES:
        return PROVINCES[m.group(1)] + "卫视"
    # 没有中文名：去掉 (1080p)、[Not 24/7]、HD 这类后缀
    name = re.sub(r"\(\d{3,4}p\)|\[[^\]]*\]|\bHD\b|\bSD\b", "", raw_name)
    return re.sub(r"\s+", " ", name).strip()


def is_official(url):
    """网友源里的地址，是不是电视台官方网站的。"""
    host = (urllib.parse.urlsplit(url).hostname or "").lower()
    try:
        ipaddress.ip_address(host)
        return False  # 一串数字开头的地址，不要
    except ValueError:
        pass
    def match(h):
        return host == h or host.endswith("." + h)
    if any(match(h) for h in PAID_HOSTS):
        return False
    return host.endswith(".cn") or any(match(h) for h in OFFICIAL_HOSTS)


def is_ipv6(url):
    """判断播放地址是不是 IPv6：地址里直接写着 IPv6 号码，或者这个网站只有 IPv6。"""
    host = urllib.parse.urlsplit(url).hostname or ""
    try:
        return ipaddress.ip_address(host).version == 6
    except ValueError:
        pass
    try:
        socket.getaddrinfo(host, None, socket.AF_INET)
        return False  # 有 IPv4 地址
    except OSError:
        try:
            socket.getaddrinfo(host, None, socket.AF_INET6)
            return True  # 只有 IPv6 地址
        except OSError:
            return False


# ------------------------------------------------------------
# 【第 3 步】试播
# ------------------------------------------------------------

def probe(url):
    """打开播放地址试一下。返回（能不能看，实际分辨率）。读不出分辨率时分辨率为 0。"""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            if resp.status != 200:
                return False, 0
            head = resp.read(16384)
    except Exception:
        return False, 0
    if ".m3u8" in url.lower() and b"#EXTM3U" not in head:
        return False, 0
    heights = [int(h) for h in re.findall(rb"RESOLUTION=\d+x(\d+)", head)]
    return len(head) > 0, max(heights, default=0)


# ------------------------------------------------------------
# 【第 4 步】排序、保存
# ------------------------------------------------------------

def sort_key(ch):
    """排序：按分组 → 央视按台号 1、2、3… → 其他按名字。"""
    m = re.match(r"CCTV-(\d+)", ch["name"])
    num = int(m.group(1)) if m else 999
    return (GROUP_ORDER.index(ch["group"]), num, ch["name"])


def dedupe(channels):
    """同一个分组里同名的频道只留一个（分辨率高的优先，一样高就优先留支持回看的）。"""
    best = {}
    for ch in sorted(channels, key=lambda c: (-c["height"], not c["catchup"])):
        best.setdefault((ch["group"], ch["name"]), ch)
    return sorted(best.values(), key=sort_key)


# 回看相关的设置项：来源里有就原样保留
CATCHUP_KEYS = ("catchup", "catchup-source", "catchup-days")


def write_m3u(path, channels, epg_urls):
    with open(path, "w", encoding="utf-8") as f:
        # 文件开头写上节目单地址，App 会自动加载节目单（回看要靠它选节目）
        epg = f' x-tvg-url="{",".join(epg_urls)}"' if epg_urls else ""
        f.write(f"#EXTM3U{epg}\n")
        for ch in channels:
            logo = f' tvg-logo="{ch["logo"]}"' if ch["logo"] else ""
            tid = f' tvg-id="{ch["tvg_id"]}"' if ch["tvg_id"] else ""
            catchup = "".join(f' {k}="{v}"' for k, v in ch["catchup"].items())
            # 节目单按 “CCTV1” 这种写法对频道，所以央视的 tvg-name 用这种写法，显示的名字不变
            m = re.match(r"CCTV-(\S+)", ch["name"])
            tvg_name = f"CCTV{m.group(1)}" if m else ch["name"]
            f.write(f'#EXTINF:-1{tid} tvg-name="{tvg_name}"{logo}{catchup} group-title="{ch["group"]}",{ch["name"]}\n')
            f.write(f'{ch["url"]}\n')


# ------------------------------------------------------------
# 【主流程】
# ------------------------------------------------------------

def main():
    cn_names = load_chinese_names()

    # 下载并整理所有频道
    channels, seen, epg_urls = [], set(), []
    all_sources = [(region, src) for region, urls in SOURCES.items() for src in urls]
    all_sources += [("大陆", src) for src in COMMUNITY_SOURCES]
    for region, src in all_sources:
        try:
            text = download(src)
            items = parse_m3u(text)
        except Exception as e:
            print(f"下载失败 {src}: {e}", file=sys.stderr)
            continue
        # 记下来源自带的节目单地址，以及写在文件开头、对整个文件生效的回看设置
        header = text.lstrip().split("\n", 1)[0]
        file_catchup = {k: attr(header, k) for k in CATCHUP_KEYS if attr(header, k)}
        for epg in re.findall(r'(?:x-tvg-url|url-tvg)="([^"]+)"', header):
            for u in epg.split(","):
                if u.strip() and u.strip() not in epg_urls:
                    epg_urls.append(u.strip())
        community = src in COMMUNITY_SOURCES
        for info, url in items:
            if url in seen:
                continue
            # 网友源：只收电视台官方地址，跳过不要的分组
            if community and (not is_official(url) or any(w in attr(info, "group-title") for w in SKIP_GROUPS)):
                continue
            # 去掉外地电视台（编号结尾不是 .cn .hk .mo .tw 的）
            cc = attr(info, "tvg-id").split("@")[0].rsplit(".", 1)
            if len(cc) == 2 and cc[1].lower() not in ALLOWED_COUNTRIES:
                continue
            seen.add(url)
            raw_name = info.rsplit(",", 1)[-1].strip()
            # 只看频道名和编号，不看台标网址（网址里的乱码可能碰巧含有这些字母）
            if any(w.lower() in (raw_name + attr(info, "tvg-id")).lower() for w in EXCLUDE):
                continue
            is_cctv = region == "大陆" and re.match(r"\s*(CCTV|CGTN|CETV|中国教育)", raw_name, re.I)
            channels.append({
                "name": clean_name(raw_name, attr(info, "tvg-id"), cn_names),
                "group": G_HMT if region == "港澳台" else G_CCTV if is_cctv else G_LOCAL,
                "logo": attr(info, "tvg-logo"),
                "tvg_id": attr(info, "tvg-id"),
                "catchup": {k: attr(info, k) for k in CATCHUP_KEYS if attr(info, k)} or file_catchup,
                "url": url,
                "height": name_height(raw_name),
                "v6": is_ipv6(url),
            })

    # 保险 1：一个频道都没下载到（多半是网络问题），保留上次的结果
    if not channels:
        sys.exit("一个频道都没抓到，保留上次的结果")

    # 只要 IPv4 的频道
    v4 = [c for c in channels if not c["v6"]]

    print(f"共 {len(v4)} 个频道，开始检测…")
    with ThreadPoolExecutor(WORKERS) as pool:
        results = list(pool.map(lambda c: probe(c["url"]), v4))
    for ch, (ok, height) in zip(v4, results):
        ch["ok"] = ok
        ch["height"] = ch["height"] or height  # 频道名里没写分辨率，就用试播读到的

    def hd_enough(ch):
        """国内频道只要 1080P 以上；港澳台不限。"""
        return ch["group"] == G_HMT or ch["height"] >= MIN_HEIGHT

    # IPv4：能看的 + 国内没测通的放进「国内备用」
    alive = dedupe([c for c in v4 if c["ok"] and hd_enough(c)])
    alive_names = {c["name"] for c in alive}
    backup = [dict(c, group=G_BACKUP) for c in v4
              if not c["ok"] and c["group"] != G_HMT and hd_enough(c) and c["name"] not in alive_names]
    list_v4 = alive + dedupe(backup)

    # 保险 2：IPv4 一个能看的都没有（多半是检测时网络出问题），保留上次的结果
    if not alive:
        sys.exit("IPv4 频道全部检测失败，保留上次的结果")

    write_m3u("haosean.m3u", list_v4, epg_urls)

    # 生成统计表
    now = datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M")
    rows = [f"更新时间：**{now}**（北京时间）", "", "| 分组 | 频道数 |", "| :-- | :-: |"]
    for g in GROUP_ORDER:
        rows.append(f"| {g} | {sum(1 for c in list_v4 if c['group'] == g)} |")
    rows.append(f"| **合计** | **{len(list_v4)}** |")
    with open("stats.md", "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")
    print("\n".join(rows))


if __name__ == "__main__":
    main()
