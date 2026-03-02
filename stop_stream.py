import os
import psutil
import obsws_python as obs
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

# 填入你之前的 WebSocket 密码
OBS_WS_HOST = "localhost"
OBS_WS_PORT = 4455
OBS_WS_PASSWORD = "你的WebSocket密码" # ⚠️ 务必替换

SCOPES = ['https://www.googleapis.com/auth/youtube']

def stop_obs():
    print(">>> 第一步：正在断开 OBS 推流...")
    try:
        cl = obs.ReqClient(host=OBS_WS_HOST, port=OBS_WS_PORT, password=OBS_WS_PASSWORD)
        cl.stop_stream()
        print("✅ OBS 推流已成功断开！")
    except Exception as e:
        print(f"⚠️ 无法通过 WebSocket 停止推流 (可能已断开): {e}")

    print(">>> 第二步：正在关闭 OBS 进程...")
    closed = False
    for proc in psutil.process_iter(['name']):
        try:
            if proc.info['name'] and 'obs' in proc.info['name'].lower():
                proc.terminate()  # 优雅结束进程
                closed = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if closed:
        print("✅ OBS 软件已完全关闭！")
    else:
        print("⚠️ 未发现运行中的 OBS 进程。")

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

def stop_youtube_broadcast(youtube):
    print("\n>>> 第三步：正在向 YouTube 发送下播指令...")
    try:
        # 查找当前账号下正在直播 (active) 的房间
        request = youtube.liveBroadcasts().list(
            part="id,snippet",
            broadcastStatus="active",
            broadcastType="all"
        )
        response = request.execute()
        items = response.get("items", [])
        
        if not items:
            print("✅ 当前没有正在进行的 YouTube 直播，或者直播已通过 AutoStop 自动结束。")
            return
            
        for item in items:
            broadcast_id = item["id"]
            title = item["snippet"]["title"]
            print(f"找到活跃直播间: [{title}]，正在强制结束...")
            
            # 将直播状态变更为 complete (已完成/下播)
            youtube.liveBroadcasts().transition(
                broadcastStatus="complete",
                id=broadcast_id,
                part="id"
            ).execute()
            print("🎉 YouTube 直播已成功结束并转为录播！")
            
    except Exception as e:
        print(f"❌ 结束 YouTube 直播失败: {e}")

if __name__ == '__main__':
    print("\n=== 开始执行一键下播工作流 ===")
    stop_obs()
    yt = authenticate_youtube()
    stop_youtube_broadcast(yt)
    print("=== 工作流执行完毕 ===\n")