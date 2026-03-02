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
        "protocol": "hls"
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
            # 核心修复：重新加入 WebSocket 状态检查
            cl = obs.ReqClient(host=OBS_WS_HOST, port=OBS_WS_PORT, password=OBS_WS_PASSWORD)
            status = cl.get_stream_status()
            if status.output_active:
                sys.exit("\n❌ 严重错误：检测到 OBS 当前正在直播推流中！\n为防止配置冲突，脚本已安全退出。请先停止推流后再运行本脚本。")
            
            print("✅ 检测到 OBS 已运行且处于空闲状态。")
            return True
        except Exception as e:
            sys.exit(f"\n❌ 严重错误：OBS 正在运行，但无法连接 WebSocket。\n请检查 OBS 设置或密码是否正确。报错信息: {e}")
    else:
        print("🚀 OBS 未运行，正在自动启动...")
        subprocess.Popen([obs_path], cwd=obs_cwd)
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
                "enableAutoStart": True,
                "enableAutoStop": True
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
    print(f">>> 正在应用 OBS 设置 ({protocol.upper()} 模式)...")
    try:
        cl = obs.ReqClient(host=OBS_WS_HOST, port=OBS_WS_PORT, password=OBS_WS_PASSWORD)
        
        profile_name = "auto-stream"
        profiles = cl.get_profile_list().profiles
        temp_profile = "Untitled" if "Untitled" in profiles else profiles[0]

        if profile_name not in profiles:
            cl.create_profile(profile_name)

        cl.set_current_profile(profile_name)
        
        cl.set_profile_parameter("Video", "BaseCX", str(config['width']))
        cl.set_profile_parameter("Video", "BaseCY", str(config['height']))
        cl.set_profile_parameter("Video", "OutputCX", str(config['width']))
        cl.set_profile_parameter("Video", "OutputCY", str(config['height']))
        cl.set_profile_parameter("Video", "FPSCommon", str(config['fps']))
        
        cl.set_profile_parameter("Output", "Mode", "Advanced")
        cl.set_profile_parameter("AdvOut", "NVENC.Bitrate", str(config['bitrate']))
        cl.set_profile_parameter("AdvOut", "NVENC.MaxBitrate", str(config.get('max_bitrate', config['bitrate'])))
        cl.set_profile_parameter("AdvOut", "NVENC.KeyframeIntervalSec", str(config.get('keyframe_sec', 2)))
        cl.set_profile_parameter("AdvOut", "NVENC.RateControl", config['rate_control'])
        cl.set_profile_parameter("AdvOut", "Track1Bitrate", "128")

        try:
            current_service = cl.get_stream_service_settings()
            service_type = current_service.stream_service_type
            settings = current_service.stream_service_settings
            settings['key'] = stream_key
            cl.set_stream_service_settings(service_type, settings)
            print(f"✅ 成功将 {protocol.upper()} 密钥注入 OBS！")
        except Exception as se:
            print(f"⚠️ 推流服务密钥注入异常: {se}")

        if temp_profile != profile_name:
            cl.set_current_profile(temp_profile)
            time.sleep(1.5)
            cl.set_current_profile(profile_name)
            time.sleep(2.0)
        
        cl.start_stream()
        print(f"🚀 OBS 推流已启动！(通过 {protocol.upper()} 协议)")
        
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
    
    # 这里是防撞机制发挥作用的地方
    obs_ready = check_and_prepare_obs(obs_path, obs_cwd)
    
    yt_service = authenticate_youtube()
    key, stream_id = prepare_youtube_stream(yt_service, cfg)
    
    if not obs_ready: 
        print("等待 OBS 初始化 (8秒)...")
        time.sleep(8)
        
    apply_obs_settings(key, cfg)
    monitor_stream_health(yt_service, stream_id)