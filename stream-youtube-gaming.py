import os
import sys
import time
import psutil
import argparse
import platform
import subprocess
from datetime import datetime
import obsws_python as obs
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# ==========================================
# 1. 动态配置字典
# ==========================================
STREAM_CONFIGS = {
    "dota2": {
        "title": "Dota 2 实况 (HEVC 2K HLS-VBR)",
        "description": "NVENC HEVC 自动推流。\n#Dota2 #RTX3070",
        "category_id": "20",
        "width": 2560,        
        "height": 1440,
        "fps": 60,
        "rate_control": "VBR",
        "bitrate": "9000",
        "max_bitrate": "13500",
        "stream_key_title": "AutoKey-Dota2-HLS-VBR",
        "keyframe_sec": 2,
        "protocol": "hls",
        "enable_auto_start": True,
        "enable_auto_stop": True
    },
    "dota2-cbr": {
        "title": "Dota 2 实况 (HEVC 2K HLS-CBR)",
        "description": "NVENC HEVC 自动推流。\n#Dota2 #RTX3070",
        "category_id": "20",
        "width": 2560,        
        "height": 1440,
        "fps": 60,
        "rate_control": "CBR",
        "bitrate": "9000",
        "stream_key_title": "AutoKey-Dota2-HLS-CBR",
        "keyframe_sec": 2,
        "protocol": "hls",
        "enable_auto_start": True,
        "enable_auto_stop": True
    },
    "coding": {
        "title": "编程实况: 系统维护与脚本开发",
        "description": "日常代码与 HomeLab 维护。\n#Coding #Python",
        "category_id": "28", 
        "width": 2560, 
        "height": 1440, 
        "fps": 30, 
        "rate_control": "CBR",
        "bitrate": "6000",
        "stream_key_title": "AutoKey-Coding-RTMP",
        "keyframe_sec": 2,
        "protocol": "rtmp"
    }
}

OBS_WS_HOST = "localhost"
OBS_WS_PORT = 4455
OBS_WS_PASSWORD = "你的WebSocket密码" # ⚠️ 记得替换密码
OBS_PROFILE_NAME = "auto-stream"

SCOPES = ['https://www.googleapis.com/auth/youtube']

# --- [ 辅助函数: OBS 路径与状态检查 ] ---

def get_obs_paths(custom_path=None):
    if custom_path and os.path.exists(custom_path):
        return custom_path, os.path.dirname(custom_path)
    system_name = platform.system()
    default_paths = {
        "Windows": { "path": r"C:\Program Files\obs-studio\bin\64bit\obs64.exe", "cwd": r"C:\Program Files\obs-studio\bin\64bit" },
        "Darwin": { "path": "/Applications/OBS.app/Contents/MacOS/OBS", "cwd": "/Applications/OBS.app/Contents/MacOS" },
        "Linux": { "path": "obs", "cwd": None }
    }
    sys_defaults = default_paths.get(system_name, default_paths["Linux"])
    return sys_defaults["path"], sys_defaults["cwd"]

def check_and_prepare_obs(obs_path, obs_cwd):
    print(f">>> 检查 OBS 状态...")
    obs_running = False
    for proc in psutil.process_iter(['name']):
        try:
            if 'obs' in proc.info['name'].lower():
                obs_running = True
                break
        except: pass
    
    if obs_running:
        try:
            # WebSocket 状态检查
            cl = obs.ReqClient(host=OBS_WS_HOST, port=OBS_WS_PORT, password=OBS_WS_PASSWORD)
            status = cl.get_stream_status()
            if status.output_active:
                sys.exit("\n❌ 检测到 OBS 当前正在直播推流中！\n为防止配置冲突，脚本已安全退出。请先停止推流后再运行本脚本。")
            
            print("✅ 检测到 OBS 已运行且处于空闲状态。")
            return True
        except Exception as e:
            sys.exit(f"\n❌ OBS 正在运行，但无法连接 WebSocket。\n请检查 OBS 设置或密码是否正确。报错信息: {e}")
    else:
        print("🚀 OBS 未运行，正在自动启动并最小化到托盘...")
        if obs_cwd:
            subprocess.Popen([obs_path, '--minimize-to-tray'], cwd=obs_cwd)
        else:
            subprocess.Popen([obs_path, '--minimize-to-tray'])
        return False

# --- [ YouTube API 交互 ] ---

def authenticate_youtube():
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('youtube', 'v3', credentials=creds)

def prepare_youtube_stream(youtube, config):
    protocol = config.get('protocol', 'rtmp').lower()
    print(f">>> 正在配置 YouTube {protocol.upper()} 直播间...")
    
    # determine auto start/stop from config, defaulting to True when not provided
    auto_start = config.get('enable_auto_start', True)
    auto_stop = config.get('enable_auto_stop', True)
    broadcast = youtube.liveBroadcasts().insert(
        part="snippet,status,contentDetails",
        body={
            "snippet": {
                "title": f"{config['title']} - {datetime.now().strftime('%Y-%m-%d')}",
                "description": config['description'],
                "scheduledStartTime": datetime.utcnow().isoformat() + "Z"
            },
            "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
            "contentDetails": {
                "monitorStream": {"enableMonitorStream": True},
                "enableAutoStart": auto_start,
                "enableAutoStop": auto_stop
            }
        }
    ).execute()
    broadcast_id = broadcast['id']

    video_response = youtube.videos().list(part="snippet", id=broadcast_id).execute()
    if video_response['items']:
        video = video_response['items'][0]
        video['snippet']['categoryId'] = config['category_id']
        youtube.videos().update(part="snippet", body=video).execute()

    target_key_name = config.get('stream_key_title')
    existing_streams = youtube.liveStreams().list(part="snippet,cdn,id", mine=True).execute().get("items", [])
    
    target_stream_id = None
    stream_key = None
    
    for stream in existing_streams:
        if stream['snippet']['title'] == target_key_name and stream['cdn'].get('ingestionType') == protocol:
            target_stream_id = stream['id']
            stream_key = stream['cdn']['ingestionInfo']['streamName']
            print(f"♻️ 找到匹配的 {protocol.upper()} 密钥，正在复用...")
            break
            
    if not target_stream_id:
        print(f"✨ 正在创建全新的 {protocol.upper()} 推流密钥...")
        new_stream = youtube.liveStreams().insert(
            part="snippet,cdn",
            body={
                "snippet": {"title": target_key_name},
                "cdn": {"frameRate": "variable", "ingestionType": protocol, "resolution": "variable"}
            }
        ).execute()
        target_stream_id = new_stream['id']
        stream_key = new_stream['cdn']['ingestionInfo']['streamName']

    youtube.liveBroadcasts().bind(id=broadcast_id, streamId=target_stream_id, part="id,contentDetails").execute()
    return stream_key, target_stream_id

# --- [ 健康度监控 ] ---

def monitor_stream_health(youtube, stream_id):
    print("\n--- YouTube 流健康度诊断 ---")
    for i in range(3):
        time.sleep(10)
        res = youtube.liveStreams().list(part="status", id=stream_id).execute()
        status = res['items'][0]['status']
        health = status.get('healthStatus', {})
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] 状态: {status['streamStatus']} | 健康度: {health.get('status', 'Waiting...')}")
        
        if 'configurationIssues' in health:
            for issue in health['configurationIssues']:
                print(f"⚠️ 警告: {issue['type']} - {issue['description']}")
        
        if health.get('status') in ['good', 'excellent']:
            print("✅ YouTube 报告流状态极佳，自动开播应该已触发！")
            break

# --- [ OBS 配置注入 ] ---

def apply_obs_settings(stream_key, config):
    protocol = config.get('protocol', 'rtmp').lower()
    print(f">>> 正在应用跨平台 OBS 设置 ({protocol.upper()} 模式)...")
    try:
        cl = obs.ReqClient(host=OBS_WS_HOST, port=OBS_WS_PORT, password=OBS_WS_PASSWORD)
        
        profile_name = OBS_PROFILE_NAME
        profiles = cl.get_profile_list().profiles
        temp_profile = "Untitled" if "Untitled" in profiles else profiles[0]

        if profile_name not in profiles:
            cl.create_profile(profile_name)

        cl.set_current_profile(profile_name)
        
        # 1. 覆盖通用画面分辨率与帧率 (全平台通用)
        cl.set_profile_parameter("Video", "BaseCX", str(config['width']))
        cl.set_profile_parameter("Video", "BaseCY", str(config['height']))
        cl.set_profile_parameter("Video", "OutputCX", str(config['width']))
        cl.set_profile_parameter("Video", "OutputCY", str(config['height']))
        cl.set_profile_parameter("Video", "FPSCommon", str(config['fps']))
        
        # 2. 覆盖码率与关键帧 (全硬件平台盲注策略)
        # 不修改 Output Mode，完全尊重并复用你在 OBS 软件里手动选择的编码器！
        rc = config['rate_control']
        bit = str(config['bitrate'])
        max_bit = str(config.get('max_bitrate', config['bitrate']))
        kf = str(config.get('keyframe_sec', 2))

        cl.set_profile_parameter("AdvOut", "Track1Bitrate", "128") # 音频底线

        # ---> NVIDIA GPU (NVENC 新旧版)
        cl.set_profile_parameter("AdvOut", "NVENC.Bitrate", bit)
        cl.set_profile_parameter("AdvOut", "NVENC.MaxBitrate", max_bit)
        cl.set_profile_parameter("AdvOut", "NVENC.KeyframeIntervalSec", kf)
        cl.set_profile_parameter("AdvOut", "NVENC.RateControl", rc)
        cl.set_profile_parameter("AdvOut", "NVENCBitrate", bit)         # 兼容旧版本插件
        cl.set_profile_parameter("AdvOut", "NVENCRateControl", rc)

        # ---> Apple macOS (VideoToolbox)
        cl.set_profile_parameter("AdvOut", "VTBitrate", bit)
        cl.set_profile_parameter("AdvOut", "VTMaxBitrate", max_bit)
        cl.set_profile_parameter("AdvOut", "VTKeyframeIntervalSec", kf)
        cl.set_profile_parameter("AdvOut", "VTERateControl", rc)

        # ---> CPU 通用编码 (x264)
        cl.set_profile_parameter("AdvOut", "x264Bitrate", bit)
        cl.set_profile_parameter("AdvOut", "x264RateControl", rc)
        cl.set_profile_parameter("AdvOut", "x264KeyintSec", kf)

        # ---> AMD GPU (AMF)
        cl.set_profile_parameter("AdvOut", "VCEBitrate", bit)
        cl.set_profile_parameter("AdvOut", "VCERateControl", rc)

        # ---> 兼容处于“简单 (Simple)”输出模式的情况
        cl.set_profile_parameter("SimpleOutput", "VBitrate", bit)

        # 3. 安全注入推流密钥，绝不破坏现有 HLS/RTMP 协议框架
        try:
            current_service = cl.get_stream_service_settings()
            service_type = current_service.stream_service_type
            settings = current_service.stream_service_settings
            settings['key'] = stream_key
            cl.set_stream_service_settings(service_type, settings)
            print(f"✅ 成功将 {protocol.upper()} 密钥注入 OBS！")
        except Exception as se:
            print(f"⚠️ 推流服务密钥注入异常: {se}")

        # 4. 重载配置，强制显卡加载 2K 画布
        if temp_profile != profile_name:
            cl.set_current_profile(temp_profile)
            time.sleep(1.5)
            cl.set_current_profile(profile_name)
            time.sleep(2.0)
        
        cl.start_stream()
        print(f"🚀 OBS 推流已启动！(协议: {protocol.upper()} | 已复用当前设备硬件加速)")
        
    except Exception as e:
        print(f"❌ OBS 错误: {e}")
        
if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--type', default='dota2')
    parser.add_argument('--obs-path', default=None)
    args = parser.parse_args()
    
    cfg = STREAM_CONFIGS.get(args.type)
    if not cfg:
        sys.exit(f"❌ 找不到配置: {args.type}")
        
    obs_path, obs_cwd = get_obs_paths(args.obs_path)
    
    obs_ready = check_and_prepare_obs(obs_path, obs_cwd)
    yt_service = authenticate_youtube()
    key, stream_id = prepare_youtube_stream(yt_service, cfg)
    
    if not obs_ready:
        # poll every 5 seconds for a limited number of checks
        max_checks = 3  # adjust or make configurable
        for attempt in range(1, max_checks + 1):
            print(f"等待 OBS 初始化 ({attempt}/{max_checks})...")
            time.sleep(5)
            try:
                obs_ready = check_and_prepare_obs(obs_path, obs_cwd)
            except Exception:
                obs_ready = False
            if obs_ready:
                print("OBS 已准备就绪。")
                break
        if not obs_ready:
            print("⚠️ OBS 在给定时间内仍未准备就绪，继续执行可能会失败。")
    apply_obs_settings(key, cfg)
    monitor_stream_health(yt_service, stream_id)