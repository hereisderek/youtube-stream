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
# 1. Dynamic Configuration Dictionary
# ==========================================
STREAM_CONFIGS = {
    "dota2": {
        "title": "Dota 2 2K HEVC Stream",
        "description": "Auto-streaming via RTX 3070.\n#Dota2 #HEVC",
        "category_id": "20",
        "width": 2560,        
        "height": 1440,
        "fps": 60,
        "rate_control": "CBR",
        "bitrate": "10000", 
        "max_bitrate": "18000", 
        "stream_key_title": "AutoKey-Dota2-HEVC",
        "keyframe_sec": 2
    },
    "dota2-vbr": {
        "title": "Dota 2 天梯冲分实况",
        "description": "自动推流测试。\n#Dota2 #Gaming",
        "category_id": "20",
        "width": 2560,        
        "height": 1440,
        "fps": 60,
        "rate_control": "VBR",     # Changed to VBR as requested (CBR is still recommended)
        "bitrate": "13500",        # Target Bitrate
        "max_bitrate": "18000",    # Hard cap for VBR spikes
        "stream_key_title": "AutoKey-Dota2-vbr",
        "keyframe_sec": 2
    },
    "coding": {
        "title": "编程实况: 系统维护与脚本开发",
        "description": "自动推流测试。\n#Coding #Python",
        "category_id": "28", 
        "width": 2560, 
        "height": 1440, 
        "fps": 30, 
        "rate_control": "CBR",     # Coding is mostly static, CBR is perfectly fine here
        "bitrate": "6000",         
        "max_bitrate": "6000",
        "stream_key_title": "AutoKey-Coding",
        "keyframe_sec": 2
    }
}

OBS_WS_HOST = "localhost"
OBS_WS_PORT = 4455
OBS_WS_PASSWORD = "你的WebSocket密码" # ⚠️ Update this password

SCOPES = ['https://www.googleapis.com/auth/youtube']

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
    print(f">>> Checking OBS Status...")
    obs_running = False
    for proc in psutil.process_iter(['name']):
        try:
            if 'obs' in proc.info['name'].lower():
                obs_running = True
                break
        except: pass

    if obs_running:
        try:
            cl = obs.ReqClient(host=OBS_WS_HOST, port=OBS_WS_PORT, password=OBS_WS_PASSWORD)
            if cl.get_stream_status().output_active:
                sys.exit("❌ OBS is currently streaming. Script terminated to prevent conflict.")
            return True
        except Exception as e:
            sys.exit(f"❌ Cannot connect to OBS WebSocket: {e}. Check your password and port.")
    else:
        print("🚀 OBS is not running. Launching process...")
        if obs_cwd:
            subprocess.Popen([obs_path], cwd=obs_cwd)
        else:
            subprocess.Popen([obs_path])
        return False

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
    print(f"Configuring YouTube Broadcast...")
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
                "monitorStream": {
                    "enableMonitorStream": True,
                    "enableAutoStart": True,
                    "enableAutoStop": True
                }
            }
        }
    ).execute()
    broadcast_id = broadcast['id']

    video_response = youtube.videos().list(part="snippet", id=broadcast_id).execute()
    if video_response['items']:
        video = video_response['items'][0]
        video['snippet']['categoryId'] = config['category_id']
        youtube.videos().update(part="snippet", body=video).execute()

    target_key_name = config.get('stream_key_title', 'Auto Stream Key')
    existing_streams = youtube.liveStreams().list(part="snippet,cdn,id", mine=True).execute().get("items", [])
    
    target_stream_id = None
    stream_key = None
    
    for stream in existing_streams:
        if stream['snippet']['title'] == target_key_name:
            target_stream_id = stream['id']
            stream_key = stream['cdn']['ingestionInfo']['streamName']
            break
            
    if not target_stream_id:
        new_stream = youtube.liveStreams().insert(
            part="snippet,cdn",
            body={
                "snippet": {"title": target_key_name},
                "cdn": {"frameRate": "variable", "ingestionType": "rtmp", "resolution": "variable"}
            }
        ).execute()
        target_stream_id = new_stream['id']
        stream_key = new_stream['cdn']['ingestionInfo']['streamName']

    youtube.liveBroadcasts().bind(id=broadcast_id, streamId=target_stream_id, part="id,contentDetails").execute()
    return stream_key

def apply_obs_settings(stream_key, config):
    print(f"Applying OBS Parameters: {config['width']}x{config['height']} @ {config['fps']}FPS")
    try:
        cl = obs.ReqClient(host=OBS_WS_HOST, port=OBS_WS_PORT, password=OBS_WS_PASSWORD)
        
        # 1. Profile Management
        profiles = cl.get_profile_list().profiles
        profile_name = "auto-stream"
        temp_profile = "Untitled" if "Untitled" in profiles else profiles[0]

        if profile_name not in profiles:
            cl.create_profile(profile_name)

        # Force switch to target profile to write settings
        cl.set_current_profile(profile_name)

        # 2. Hard-lock Resolutions (The 2K Fix)
        res_w = str(config['width'])
        res_h = str(config['height'])
        fps_val = str(config['fps'])

        # We set both Base (Canvas) and Output (Scaled) to 2K
        cl.set_profile_parameter("Video", "BaseCX", res_w)
        cl.set_profile_parameter("Video", "BaseCY", res_h)
        cl.set_profile_parameter("Video", "OutputCX", res_w)
        cl.set_profile_parameter("Video", "OutputCY", res_h)
        cl.set_profile_parameter("Video", "FPSCommon", fps_val)
        
        # 3. Rate Control & Bitrate
        rc = str(config['rate_control'])
        bitrate = str(config['bitrate'])
        max_bitrate = str(config['max_bitrate'])
        keyframe_val = str(config.get('keyframe_sec', 2))

        cl.set_profile_parameter("Output", "Mode", "Advanced")
        cl.set_profile_parameter("AdvOut", "Track1Bitrate", "128")
        
        # Universal encoder param injection
        for prefix in ["x264", "NVENC", "QSV", "VCE", "VT"]:
            cl.set_profile_parameter("AdvOut", f"{prefix}RateControl", rc)
            cl.set_profile_parameter("AdvOut", f"{prefix}Bitrate", bitrate)
            if rc == "VBR":
                cl.set_profile_parameter("AdvOut", f"{prefix}MaxBitrate", max_bitrate)
            # Keyframes
            kf_field = "KeyintSec" if prefix == "x264" else "KeyframeSecs"
            if prefix == "VT": kf_field = "KeyframeIntervalSec"
            cl.set_profile_parameter("AdvOut", f"{prefix}{kf_field}", keyframe_val)

        # 4. THE CRITICAL RESTART: Force OBS to 're-read' the 2K config from disk
        print("Re-initializing Video Engine for 1440p...")
        cl.set_current_profile(temp_profile)
        time.sleep(1.5)  # Wait for engine to unload
        cl.set_current_profile(profile_name)
        time.sleep(2.0)  # Wait for engine to load 2K textures

        # 5. Set Key & Go
        cl.set_stream_service_settings("rtmp_custom", {
            "server": "rtmp://a.rtmp.youtube.com/live2",
            "key": stream_key
        })
        
        cl.start_stream()
        print(f"🎉 Success! Stream is now LIVE at {res_w}x{res_h}.")
        
    except Exception as e:
        print(f"❌ OBS Error: {e}")

if __name__ == '__main__':
    print("\n>>> Starting YouTube Auto-Stream Workflow <<<")
    parser = argparse.ArgumentParser()
    parser.add_argument('-t', '--type', default='dota2')
    parser.add_argument('--obs-path', default=None)
    args = parser.parse_args()
    
    cfg = STREAM_CONFIGS.get(args.type, STREAM_CONFIGS['dota2'])
    obs_path, obs_cwd = get_obs_paths(args.obs_path)
    
    obs_ready = check_and_prepare_obs(obs_path, obs_cwd)
    yt_service = authenticate_youtube()
    key = prepare_youtube_stream(yt_service, cfg)
    
    if not obs_ready:
        print("Waiting for OBS to initialize and load WebSocket (8 seconds)...")
        time.sleep(8)
        
    apply_obs_settings(key, cfg)