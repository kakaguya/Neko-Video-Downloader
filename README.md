# 🌸 Neko Video Downloader

基于 **yt-dlp + PyQt5** 的桌面视频下载器，支持 YouTube、Bilibili 及 yt-dlp 支持的其他站点。通过图形界面解析格式、选择画质并下载视频或音频。

## 功能

- 暗色主题，视频与音频格式分栏选择。
- 支持手动组合、智能最佳、最佳单文件和最佳音频四种下载模式。
- 后台解析与下载，显示进度、速度和剩余时间，支持取消任务。
- 按需导入 Cookie，不修改原始 Cookie 文件。
- 内置环境诊断与 yt-dlp 一键更新。

## 快速开始

### Windows

1. 安装 [Python](https://www.python.org/downloads/) **3.10 或更高版本**，安装时勾选 **Add Python to PATH**。
2. 下载并解压本项目，或克隆仓库。
3. 双击 **`run.bat`**。

首次运行会在项目目录创建 `.venv`，并通过 `requirements.txt` 安装依赖，需要联网。后续启动复用该环境；缺少核心依赖时会重新执行安装。无需手动激活虚拟环境，也无需安装 Conda。

如果希望手动安装，在项目目录打开 PowerShell：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\run.bat
```

仅准备环境而不打开窗口，可运行 `run.bat --setup`。原有 `run_windows.bat` 仍可使用。

### macOS / Linux

安装 Python 3.10+ 后，在项目目录执行：

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python run.py
```

### FFmpeg 与 Deno

这两个工具需要单独安装，**不包含在 `requirements.txt` 中**：

| 工具 | 用途 | 安装后检查 |
| --- | --- | --- |
| [FFmpeg](https://ffmpeg.org/download.html)（含 ffprobe） | 合并独立视频与音频、执行后处理 | `ffmpeg -version` / `ffprobe -version` |
| [Deno](https://docs.deno.com/runtime/getting_started/installation/) | 处理 YouTube JavaScript challenge，建议下载 YouTube 时安装 | `deno --version` |

安装后确保工具位于系统 `PATH` 中，并重新打开程序。本项目的 Deno 检测最低版本为 2.3.0；`requirements.txt` 中的 `yt-dlp[default]` 会同时安装 EJS 相关依赖。

没有 FFmpeg 时，可使用“最佳单文件”模式；YouTube 格式还可能受到登录状态或站点策略限制，详见 [YouTube 格式说明](docs/YOUTUBE_FORMATS.md)。

## 使用方法

1. 粘贴视频链接，选择保存目录。
2. 如需登录访问，选择 Netscape 格式的 Cookie 文件；公开内容可先留空。
3. 点击 **解析格式**，选择下载模式。
4. 手动模式下，左栏选择视频、右栏选择音频；选择已含音频的视频后，无需再选音轨。
5. 点击 **开始下载**，完成后打开保存目录查看文件。

解析或下载失败时，可先使用界面的 **更新 yt-dlp**，更新后重启程序。

## 常见问题

- **依赖安装失败**：检查网络，在项目目录重新执行 `.venv\Scripts\python.exe -m pip install -r requirements.txt`。
- **移动项目后无法启动**：重命名或删除旧 `.venv`，再运行 `run.bat` 创建新环境。
- **需要登录或出现 403**：确认浏览器可以访问该内容，更新 yt-dlp，必要时重新导出 Cookie。更多情况见 [故障排查](docs/TROUBLESHOOTING.md)。

## 文档

[故障排查](docs/TROUBLESHOOTING.md) · [YouTube 格式说明](docs/YOUTUBE_FORMATS.md) · [第三方许可](THIRD_PARTY_NOTICES.md)

## 许可与使用说明

本项目采用 [GPL-3.0](LICENSE) 许可证，核心下载能力由 [yt-dlp](https://github.com/yt-dlp/yt-dlp) 提供。
