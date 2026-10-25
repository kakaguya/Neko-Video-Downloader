# YouTube 格式完整性：Deno、EJS、PO Token 与无浏览器模式

> 本文对应 Neko Video Downloader 1.0.0。YouTube 与 yt-dlp 会持续变化；遇到解析问题时应先更新 yt-dlp。

## 1. Deno 解决的是 JavaScript Challenge

现代 yt-dlp 的 YouTube 解析需要外部 JavaScript Runtime。项目优先检测 Deno，并执行 `deno --version`；当前项目按 yt-dlp 的要求把最低支持版本设为 **2.3.0**。

检测成功后，Neko 会把 Deno 的绝对路径传给 yt-dlp：

```python
"js_runtimes": {
    "deno": {"path": r"C:\\path\\to\\deno.exe"}
}
```

这避免 Windows + Conda + 双击启动时出现“终端能找到 Deno，但 GUI 进程找不到”的 PATH 差异。

上游文档：<https://github.com/yt-dlp/yt-dlp/wiki/EJS>

## 2. 还需要 `yt-dlp-ejs`

Deno 是执行器；YouTube challenge solver scripts 来自 `yt-dlp-ejs`。本项目依赖：

```text
yt-dlp[default]
```

所以“一键更新 yt-dlp”会同步升级 `yt-dlp-ejs`。项目同时允许：

```python
"remote_components": {"ejs:github"}
```

作为本地 EJS 缺失或过旧时的回退。

## 3. Deno/EJS 与 PO Token 是两套机制

Deno/EJS 正常并不代表 YouTube 一定返回所有 formats。某些 YouTube client 的 GVS/字幕/播放请求还会要求 PO Token。

因此下面这种状态是可能的：

```text
Deno           ✓
yt-dlp-ejs      ✓
JS challenge   ✓
PO Token       未提供
=> 某些 HTTPS / DASH / HLS / 独立音视频格式被跳过
```

上游说明：<https://github.com/yt-dlp/yt-dlp/wiki/PO-Token-Guide>

## 4. v1.0.0 为什么不会再启动 Chrome/Chromium

第三方 PO Token Provider 中存在通过浏览器生成 Token 的实现。如果这种 Provider 已安装，yt-dlp 在需要 PO Token 时可能调用它。

为了满足桌面程序“不在获取 format 或下载时弹出浏览器”的要求，Neko v1.0.0 明确设置：

```python
"extractor_args": {
    "youtube": {
        "fetch_pot": ["never"]
    }
}
```

yt-dlp 将 `fetch_pot=never` 定义为：**永远不从 Provider 获取 PO Token**。

因此：

- Deno 仍用于 JavaScript challenge；
- `yt-dlp-ejs` 仍正常使用；
- 已安装的浏览器型 PO Token Provider 不会被 Neko 主动调用；
- 不会为了获取 PO Token 自动启动 Chrome/Chromium；
- 代价是需要 PO Token 的格式可能不会出现在列表中，或被 yt-dlp 跳过。

这是一项明确的产品取舍，而不是把 Deno 错当成 PO Token 替代品。

## 5. 格式界面如何分类

v1.0.0 将媒体格式拆成左右两栏：

```text
视频格式（左）                    音频格式（右）
────────────────────             ────────────────────
纯视频                            纯音频
音视频单文件
```

手动模式下：

- 纯视频 + 纯音频 → `VIDEO_ID+AUDIO_ID`，FFmpeg 自动合并；
- 音视频单文件 → 直接下载，右侧音频栏自动禁用；
- 只选纯视频 → 下载视频轨；
- 只选纯音频 → 下载音频轨。

格式类型判断优先使用 `audio_ext/video_ext=none` 等明确字段，再结合 codec、分辨率、码率和声道信息，避免 `acodec=unknown` 一类 manifest 信息把纯视频错误标成“音视频”。

## 6. 格式仍不完整时怎么判断

在启动 Neko 的**同一个 Conda/venv 环境**中可以执行：

```bash
python -m yt_dlp -v -F "你的 YouTube URL"
```

重点看：

```text
JS runtimes: ... deno-...
Optional libraries: ... yt_dlp_ejs-...
[youtube] [jsc] ...
[youtube] [pot] ...
```

需要注意：命令行 yt-dlp 会按你的全局插件环境和参数工作，而 Neko v1.0.0 会固定 `fetch_pot=never`。如果命令行因为已安装 PO Token Provider 而能得到更多格式，而 Neko 少一些，这是“无浏览器模式”的预期差异。

## 7. “全部格式”的边界

Neko 展示的是当前 yt-dlp 实际返回并认为可用的媒体 formats。项目不会通过 `allow_unplayable_formats` 等调试选项强行显示已知不可播放、DRM 或大概率 403 的格式。
