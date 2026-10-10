<div align="center">

# 📺 Hao Sean 的专属直播源

**央视 · 地方 · 港澳台　|　国内 1080P 起　|　支持回看　|　每天自动更新**

</div>

---

## 🔗 我的链接

复制一个，填进手机 App 的「添加播放列表 → M3U 网址」。

### 🟢 IPv4（大多数网络用这个）

| 网络 | 链接 |
| :-: | :-- |
| 🇨🇳 国内 | `https://cdn.jsdelivr.net/gh/hxq900203/HaoSean-IPTV@main/haosean.m3u` |
| 🌍 VPN | `https://raw.githubusercontent.com/hxq900203/HaoSean-IPTV/main/haosean.m3u` |

### 🔵 IPv6（家里宽带支持 IPv6 时用，回看更多）

| 网络 | 链接 |
| :-: | :-- |
| 🇨🇳 国内 | `https://cdn.jsdelivr.net/gh/hxq900203/HaoSean-IPTV@main/haosean-ipv6.m3u` |
| 🌍 VPN | `https://raw.githubusercontent.com/hxq900203/HaoSean-IPTV/main/haosean-ipv6.m3u` |

> 💡 **不知道用哪个？** 先用 IPv4。手机浏览器打开 [test-ipv6.com](https://test-ipv6.com)，显示支持 IPv6 的话，可以再加一份 IPv6。
>
> 📱 **App 推荐**：安卓用 **TiviMate**，苹果用 **APTV**（两个都支持回看）

---

## 📊 今日频道

👉 每个分组有多少台、多少台能回看、最后更新时间，见 **[stats.md](stats.md)**

| 分组 | 内容 |
| :-- | :-- |
| 📺 **央视频道** | CCTV-1 到 CCTV-17、4K / 8K 等，按台号排好 |
| 📡 **地方频道** | 各省卫视、地方台 |
| 🌏 **港澳台** | 香港、澳门、台湾的公开频道 |
| 🔸 **国内备用** | 海外服务器测不通、但在国内可能能看的台（只在 IPv4 列表里） |

**筛选规则**
- ✅ 国内频道只要 **1080P 及以上**
- ✅ 频道名统一成中文，比如「CCTV-1 综合」「北京卫视」
- ✅ 同名频道只留一个，优先保留画质最好、支持回看的
- ✅ IPv4 和 IPv6 分成两份，互不混合

---

## ⏪ 回看怎么用

1. 第一次添加播放列表后，等 App 自动加载**节目单**（几分钟）
2. 打开一个频道，调出节目单，往前翻，点之前播过的节目就能看
3. 支持回看的频道，在 TiviMate / APTV 里会有一个 ⏪ 小图标

> ⚠️ 能不能回看取决于频道来源。**IPv6 的央视、卫视大多支持**；IPv4 的大多不支持。

---

## ❓ 常见问题

<details>
<summary><b>以后真的不用管了吗？</b></summary>

不用管。每天早上 6 点左右自动更新、自动去掉失效的频道；每次运行都会「保活」，GitHub 不会把它停掉；抓取失败也会保留上一次的列表，不会清空。

唯一要知道的是：这些都是**免费公开源**，个别频道哪天失效是正常的，第二天更新时会自动换掉或去掉。
</details>

<details>
<summary><b>某个频道黑屏 / 一直转圈？</b></summary>

免费源偶尔会失效，换一个台，或者等第二天自动更新后再试。
</details>

<details>
<summary><b>IPv6 的频道为什么没有「备用」分组？</b></summary>

检测是在 GitHub 的海外服务器上做的，那里不支持 IPv6，所以 IPv6 频道没法提前试播，会全部保留，由你在家里的网络下实际试看。
</details>

<details>
<summary><b>列表一直没变化？</b></summary>

在 App 里手动「刷新播放列表」。还不行，去 **Actions** 页面看看最近一次是不是绿色 ✅。
</details>

<details>
<summary><b>想马上更新？</b></summary>

点上方 **Actions** → 左边「更新直播源」→ **Run workflow** → 再点绿色 **Run workflow**，等一两分钟。
</details>

---

<div align="center">

<sub>频道来源：<a href="https://github.com/iptv-org/iptv">iptv-org</a> 等公开免费源 · 程序 <code>fetch.py</code> 每一步都有中文解释</sub>

</div>
