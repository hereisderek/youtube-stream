# YouTube Auto-Stream Controller 🚀

这是一个高度自动化的跨平台 YouTube 直播控制脚本集。它通过 YouTube Data API v3 和 OBS WebSocket，实现了基于配置字典（Gaming / Coding 等）的全自动推流。支持动态切换 2K 画布、智能复用推流密钥（HLS / RTMP）、以及全硬件平台（NVENC / Apple VT / x264）的编码器盲注机制。

## 📁 文件结构与用途

* `stream-youtube-gaming.py`: **核心引擎**。负责检查并启动后台 OBS，与 YouTube API 交互创建/修改直播间，动态生成或复用推流密钥，并通过 WebSocket 强行将对应的分辨率、码率、关键帧注入 OBS 配置并开启推流。
* `stop_stream.py`: **一键下播引擎**。负责向 OBS 发送停止推流指令，优雅关闭 OBS 进程，并调用 YouTube API 将当前活跃的直播状态标记为 `complete`（结束并转为录播）。
* `requirements.txt`: Python 依赖清单。包含 `obsws-python`, `google-api-python-client` 等必要模块。
* `start_stream.bat` / `.sh`: **Windows / macOS & Linux 启动入口**。自动创建 `.venv` 虚拟环境，静默安装依赖，并允许传入配置参数（如 `dota2` 或 `coding`）。
* `stop_stream.bat` / `.sh`: **下播快捷入口**。双击即可在终端内秒关直播，无需打开浏览器。
* `credentials.json`: *(需用户自备)* Google Cloud Console 下载的 YouTube API OAuth 2.0 凭证文件。
* `token.json`: *(自动生成)* 脚本首次运行授权后生成的本地 Token 文件，用于后续免密调用 API。

## ⚙️ OBS 初始手动设置 (只需配置一次)

虽然脚本接管了大部分动态参数，但为了保证跨平台兼容性和底层协议的稳定性，请在首次运行脚本前手动在 OBS 中完成以下“基调”设置：

### 1. 锁定推流协议与硬件编码器
1. 打开 OBS，点击 **设置 (Settings)** -> **推流 (Stream)**。
2. **服务 (Service)** 选择：**`YouTube - HLS`**（如果你主要推 2K HEVC）或 **`YouTube - RTMPS`**。
3. 服务器选择：`Primary YouTube ingest server`，并选择 **使用串流密钥 (Use Stream Key)**。
4. 点击 **输出 (Output)**，将 **输出模式 (Output Mode)** 改为 **高级 (Advanced)**。
5. 在 **直播 (Streaming)** 选项卡下，选择你当前设备最强的 **视频编码器 (Video Encoder)**（例如 Windows 选 `NVIDIA NVENC HEVC`，Mac 选 `Apple VT H264/HEVC Hardware`）。
6. **极其重要**：确保 **“重新缩放输出 (Rescale Output)” 是未勾选状态**。

### 2. OBS 后台运行机制
脚本代码中已添加 `--minimize-to-tray` 启动参数。为了让该参数完美生效，建议在 OBS 中开启系统托盘支持：
1. 点击 **设置 (Settings)** -> **通用 (General)**。
2. 找到 **系统托盘 (System Tray)** 区域。
3. 勾选 **启用 (Enable)**。
此后通过脚本拉起 OBS 时，它将默默在右下角托盘运行，不会干扰你的屏幕画面。

## 🚀 使用方法

### 1. 准备工作
确保项目根目录下存在 `credentials.json`。并在 `stream-youtube-gaming.py` 和 `stop_stream.py` 中修改你的 OBS WebSocket 密码：
`OBS_WS_PASSWORD = "你的真实密码"`

### 2. 一键开播
使用终端或直接双击执行脚本，并可附带配置名称（默认为 `dota2`）：
* **Windows:**
    `.\start_stream.bat dota2`
    `.\start_stream.bat coding`
* **macOS / Linux:**
    `./start_stream.sh dota2`
脚本会自动拉起后台 OBS，与 YouTube 握手并验证密钥，数据同步后自动全网开播。

### 3. 一键下播
结束任务后，直接运行下播脚本：
* **Windows:** `.\stop_stream.bat`
* **macOS / Linux:** `./stop_stream.sh`
脚本会切断推流、关闭后台 OBS，并通知 YouTube 结束直播生成录像。

## 📝 自定义直播配置 (`STREAM_CONFIGS`)
你可以随时在 `stream-youtube-gaming.py` 开头的字典中添加新的直播场景：
* `width` / `height`: 自动重载 OBS 的基础与输出画布。
* `rate_control` / `bitrate`: 盲注适配各种底层硬件编码器（支持 CBR / VBR）。
* `protocol`: 决定使用 `hls` 还是 `rtmp` 密钥生成逻辑。