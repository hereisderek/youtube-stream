# YouTube Auto-Stream Controller 🚀

This is a highly automated, cross-platform streaming controller for YouTube. Utilizing the YouTube Data API v3 and OBS WebSocket, it enables fully automated live streaming based on configuration dictionaries (e.g., Gaming, Coding). It features dynamic 2K canvas switching, intelligent stream key reuse (HLS/RTMP), and an encoder blind-injection mechanism compatible with all hardware platforms (NVENC / Apple VT / x264).

## 📁 File Structure & Purpose

* `stream-youtube-gaming.py`: **Core Engine**. Responsible for checking and launching OBS in the background, communicating with the YouTube API to create/modify broadcasts, dynamically generating or reusing stream keys, and injecting resolutions, bitrates, and keyframes into OBS via WebSocket before starting the stream.
* `stop_stream.py`: **One-Click Stop Engine**. Sends a stop-streaming command to OBS, gracefully terminates the OBS process, and calls the YouTube API to transition the active broadcast status to `complete` (saving it as a VOD).
* `requirements.txt`: Python dependencies list. Includes essential modules like `obsws-python` and `google-api-python-client`.
* `start_stream.bat` / `.sh`: **Windows / macOS & Linux Launchers**. Automatically creates a virtual environment (default `.venv`), silently installs dependencies, and accepts configuration arguments (e.g., `dota2` or `coding`). You can also supply a custom venv directory as the second parameter or set the `CUSTOM_VENV_DIR` environment variable.
* `stop_stream.bat` / `.sh`: **Quick Stop Launchers**. Double-click to instantly terminate the stream directly from the terminal without opening a browser.
* `credentials.json`: *(User provided)* The YouTube API OAuth 2.0 credentials file downloaded from the Google Cloud Console.
* `token.json`: *(Auto-generated)* A local token file generated after the first authorized run, used for subsequent passwordless API calls.

## ⚙️ Initial OBS Manual Setup (One-time only)

Although the script handles most dynamic parameters, to ensure cross-platform compatibility and underlying protocol stability, please manually configure the following "baseline" settings in OBS before running the script for the first time:

### 1. Lock Streaming Protocol and Hardware Encoder
1. Open OBS, click **Settings** -> **Stream**.
2. **Service**: Select **`YouTube - HLS`** (if primarily streaming 2K HEVC) or **`YouTube - RTMPS`**.
3. **Server**: Select `Primary YouTube ingest server` and choose **Use Stream Key**.
4. Click **Output** and change the **Output Mode** to **Advanced**.
5. Under the **Streaming** tab, select the most powerful **Video Encoder** for your current device (e.g., `NVIDIA NVENC HEVC` for Windows, `Apple VT H264/HEVC Hardware` for Mac).
6. **CRITICAL**: Ensure **"Rescale Output" is UNCHECKED**.

### 2. OBS Background Execution
The `--minimize-to-tray` launch argument has been added to the script. For this parameter to work perfectly, it is recommended to enable System Tray support in OBS:
1. Click **Settings** -> **General**.
2. Locate the **System Tray** section.
3. Check **Enable**.
When the script launches OBS, it will run silently in the system tray without interfering with your screen.

## 🚀 Usage

### 1. Preparation
Ensure `credentials.json` is located in the project root directory. Update your OBS WebSocket password in both `stream-youtube-gaming.py` and `stop_stream.py`:
`OBS_WS_PASSWORD = "your_real_password"`

### 2. One-Click Start
Use the terminal or double-click to execute the script. You can append the configuration name (defaults to `dota2`):
* **Windows:**
    `.\start_stream.bat dota2`
    `.\start_stream.bat coding`
* **macOS / Linux:**
    `./start_stream.sh dota2`
The script will automatically launch OBS in the background, handshake with YouTube, verify the key, and go live automatically once data is synced.

### 3. One-Click Stop
When you are done, simply run the stop script:
* **Windows:** `.\stop_stream.bat`
* **macOS / Linux:** `./stop_stream.sh`
The script will stop the stream, close OBS, and notify YouTube to end the broadcast.

## 📝 Custom Stream Configurations (`STREAM_CONFIGS`)
You can add new streaming scenarios to the dictionary at the top of `stream-youtube-gaming.py` at any time:
* `width` / `height`: Automatically reloads the OBS base and output canvas.
* `rate_control` / `bitrate`: Blindly injects values to adapt to various hardware encoders (supports CBR / VBR).
* `protocol`: Determines whether to use `hls` or `rtmp` stream key generation logic.