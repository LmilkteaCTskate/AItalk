import pyaudio
import wave
import keyboard
import os
import time
import tkinter as tk
from tkinter import ttk
import threading
import websocket
import json
import base64
import hashlib
import hmac
from urllib.parse import urlencode
from datetime import datetime
from time import mktime
from wsgiref.handlers import format_date_time
import ssl
import _thread as thread
import requests
import re
import queue

# 全局配置
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
CHUNK = 1024
RECORD_DIR = './upload_audio'
STATUS_FIRST_FRAME = 0
STATUS_CONTINUE_FRAME = 1
STATUS_LAST_FRAME = 2

# 讯飞API配置
XF_APP_ID = '71efdd04'
XF_API_KEY = 'e63cbab297110bc8d29c9ede6565bbe1'
XF_API_SECRET = 'NmUxNTczMzQyMjYxZTcwYTdlOGMyZjUy'

os.makedirs(RECORD_DIR, exist_ok=True)

class ASRWebSocket:
    def __init__(self, audio_file, update_callback):
        self.audio_file = audio_file
        self.update_callback = update_callback
        self.ws_param = WsParam(XF_APP_ID, XF_API_KEY, XF_API_SECRET, audio_file)

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if data["code"] != 0:
                print(f"ASR Error: {data['message']}")
            else:
                result = "".join([w["w"] for item in data["data"]["result"]["ws"] for w in item["cw"]])
                with open('./result.txt', 'a+', encoding='utf-8') as f:
                    f.write(result)
                self.update_callback(result)
        except Exception as e:
            print(f"ASR Message Error: {e}")

    def run(self):
        websocket.enableTrace(False)
        ws = websocket.WebSocketApp(
            self.ws_param.create_url(),
            on_message=self.on_message,
            on_error=lambda ws, error: print(f"ASR Error: {error}"),
            on_close=lambda ws, a, b: print("ASR Closed")
        )
        ws.on_open = self.on_open
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

    def on_open(self, ws):
        def run(*args):
            status = STATUS_FIRST_FRAME
            with open(self.audio_file, "rb") as fp:
                while True:
                    buf = fp.read(8000)
                    if not buf:
                        status = STATUS_LAST_FRAME
                    
                    data = {
                        "common": self.ws_param.CommonArgs,
                        "business": self.ws_param.BusinessArgs,
                        "data": {
                            "status": status,
                            "format": "audio/L16;rate=16000",
                            "audio": base64.b64encode(buf).decode(),
                            "encoding": "raw"
                        }
                    }
                    if status == STATUS_FIRST_FRAME:
                        data["data"]["status"] = 0
                        status = STATUS_CONTINUE_FRAME
                    ws.send(json.dumps(data))
                    
                    if status == STATUS_LAST_FRAME:
                        time.sleep(1)
                        break
                    time.sleep(0.04)
            ws.close()
        thread.start_new_thread(run, ())

class TTSWebSocket:
    def __init__(self, text):
        self.text = text
        self.ws_param = WsParamTTS(XF_APP_ID, XF_API_KEY, XF_API_SECRET, text)
        self.audio_data = bytearray()
        self.websocket_closed = threading.Event()

    def on_message(self, ws, message):
        try:
            data = json.loads(message)
            if data["code"] != 0:
                print(f"TTS Error: {data['message']}")
            else:
                audio = base64.b64decode(data["data"]["audio"])
                self.audio_data.extend(audio)
        except Exception as e:
            print(f"TTS Message Error: {e}")

    def run(self):
        websocket.enableTrace(False)
        ws = websocket.WebSocketApp(
            self.ws_param.create_url(),
            on_message=self.on_message,
            on_error=lambda ws, error: print(f"TTS Error: {error}"),
            on_close=self.on_close
        )
        ws.on_open = lambda ws: self.on_open(ws)
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        self.websocket_closed.wait()  # 等待连接完全关闭
        return bytes(self.audio_data)

    def on_open(self, ws):
        data = {
            "common": self.ws_param.CommonArgs,
            "business": self.ws_param.BusinessArgs,
            "data": self.ws_param.Data
        }
        ws.send(json.dumps(data))

    def on_close(self, ws, close_status_code, close_msg):
        print("TTS Closed")
        self.websocket_closed.set()

class WsParam:
    def __init__(self, APPID, APIKey, APISecret, AudioFile):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.AudioFile = AudioFile
        self.CommonArgs = {"app_id": self.APPID}
        self.BusinessArgs = {"domain": "iat", "language": "zh_cn", "accent": "mandarin", "vinfo": 1, "vad_eos": 10000}

    def create_url(self):
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        signature_origin = f"host: ws-api.xfyun.cn\ndate: {date}\nGET /v2/iat HTTP/1.1"
        signature_sha = hmac.new(self.APISecret.encode(), signature_origin.encode(), hashlib.sha256).digest()
        signature = base64.b64encode(signature_sha).decode()
        authorization = base64.b64encode(
            f'api_key="{self.APIKey}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'.encode()
        ).decode()
        return f"wss://ws-api.xfyun.cn/v2/iat?{urlencode({'authorization': authorization, 'date': date, 'host': 'ws-api.xfyun.cn'})}"

class WsParamTTS:
    def __init__(self, APPID, APIKey, APISecret, Text):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.Text = Text
        self.CommonArgs = {"app_id": self.APPID}
        self.BusinessArgs = {"aue": "raw", "auf": "audio/L16;rate=16000", "vcn": "aisjiuxu", "tte": "utf8"}
        self.Data = {"status": 2, "text": base64.b64encode(self.Text.encode()).decode()}

    def create_url(self):
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        signature_origin = f"host: ws-api.xfyun.cn\ndate: {date}\nGET /v2/tts HTTP/1.1"
        signature_sha = hmac.new(self.APISecret.encode(), signature_origin.encode(), hashlib.sha256).digest()
        signature = base64.b64encode(signature_sha).decode()
        authorization = base64.b64encode(
            f'api_key="{self.APIKey}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'.encode()
        ).decode()
        return f"wss://tts-api.xfyun.cn/v2/tts?{urlencode({'authorization': authorization, 'date': date, 'host': 'ws-api.xfyun.cn'})}"

class VoiceAssistant:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.selected_model = tk.StringVar(value='localhost')
        self.is_recording = False
        self.recording_lock = threading.Lock()
        self.start_time = None
        self.audio_player = pyaudio.PyAudio()
        self.task_queue = queue.Queue()
        
        self.asr_text = tk.StringVar()
        self.response_text = tk.StringVar()
        
        self.check_queue()

    def check_queue(self):
        try:
            while True:
                task = self.task_queue.get_nowait()
                task()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.check_queue)

    def record_audio(self):
        while True:
            filename = os.path.join(RECORD_DIR, "output.wav")
            p = pyaudio.PyAudio()
            stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
            
            try:
                frames = []
                recording = False
                
                while True:
                    if keyboard.is_pressed('space'):
                        if not recording:
                            recording = True
                            with self.recording_lock:
                                self.is_recording = True
                            self.start_time = time.time()
                        frames.append(stream.read(CHUNK))
                    elif recording:
                        recording = False
                        with self.recording_lock:
                            self.is_recording = False
                        break
                    time.sleep(0.01)
                    
                if frames:
                    with wave.open(filename, 'wb') as wf:
                        wf.setnchannels(CHANNELS)
                        wf.setsampwidth(p.get_sample_size(FORMAT))
                        wf.setframerate(RATE)
                        wf.writeframes(b''.join(frames))
                    self.run_asr(filename)
                    
            except Exception as e:
                print(f"录音错误: {e}")
            finally:
                stream.stop_stream()
                stream.close()
                p.terminate()
                time.sleep(1)

    def run_asr(self, audio_file):
    # 开始新识别时清空显示
        self.task_queue.put(lambda: self.asr_text.set(""))
        with open('./result.txt', 'w') as f:
            f.truncate()
        
        asr_ws = ASRWebSocket(audio_file, lambda text: self.task_queue.put(lambda: self.update_asr_display(text)))
        asr_ws.run()
        
        with open('./result.txt', 'r', encoding='utf-8') as f:
            text = f.read().strip()
        
        if text:
            self.task_queue.put(lambda: self.process_response(text))

    def update_asr_display(self, text):
        current = self.asr_text.get()
        self.asr_text.set(current + text)

    def process_response(self, text):
        model = self.selected_model.get()
        try:
            if model == 'localhost':
                raw_response = self.local_model(text)
            elif model == 'utral':
                raw_response = self.spark_model(text)
            
            filtered = self.clean_response(raw_response)
            
            if filtered:
                self.start_tts(filtered)
        except Exception as e:
            print(f"处理响应失败: {e}")

    def clean_response(self, text):
        # 多重过滤确保去除所有标签
        text = re.sub(r'<script.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<.*?>', '', text)
        return text.strip()

    def local_model(self, text):
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={"model": "deepseek-r1:1.5b", "prompt": text, "stream": False},
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get("response", "")
            return "请求本地模型失败"
        except Exception as e:
            return f"本地模型错误: {str(e)}"

    def spark_model(self, text):
        try:
            messages = [{"role": "user", "content": text}]
            response = requests.post(
                "https://spark-api.xf-yun.com/v4.0/chat",
                json={
                    "header": {"app_id": XF_APP_ID},
                    "parameter": {"chat": {"domain": "4.0Ultra"}},
                    "payload": {"message": {"text": messages}}
                },
                headers={"Authorization": f"Bearer {XF_API_KEY}"},
                timeout=30
            )
            if response.status_code == 200:
                return response.json()["payload"]["choices"]["text"]["content"]
            return "请求星火模型失败"
        except Exception as e:
            return f"星火模型错误: {str(e)}"

    def start_tts(self, text):
        def tts_task():
            try:
                tts_ws = TTSWebSocket(text)
                audio_data = tts_ws.run()
                self.task_queue.put(lambda: self.finalize_response(text, audio_data))
            except Exception as e:
                print(f"语音合成失败: {e}")
        
        threading.Thread(target=tts_task, daemon=True).start()

    def finalize_response(self, text, audio_data):
        """同时更新界面和播放语音"""
        self.response_text.set(text)
        self.play_audio(audio_data)

    def play_audio(self, audio_data):
        def play_thread():
            try:
                stream = self.audio_player.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,
                    output=True
                )
                stream.write(audio_data)
                stream.stop_stream()
                stream.close()
            except Exception as e:
                print(f"播放失败: {e}")
    
        # 在独立线程中播放音频
        threading.Thread(target=play_thread, daemon=True).start()

    def create_gui(self):
        self.root.deiconify()
        self.root.title('智能语音助手')
        self.root.geometry('500x300')
        
        main_frame = ttk.Frame(self.root, padding=10)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        model_frame = ttk.LabelFrame(main_frame, text="模型选择")
        model_frame.pack(fill=tk.X, pady=5)
        for model in ["localhost", "utral"]:
            ttk.Radiobutton(model_frame, text=model, variable=self.selected_model, value=model).pack(side=tk.LEFT, padx=10)
        
        asr_frame = ttk.LabelFrame(main_frame, text="语音识别结果")
        asr_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        ttk.Label(asr_frame, textvariable=self.asr_text, wraplength=450).pack(padx=10, pady=5, fill=tk.BOTH)
        
        response_frame = ttk.LabelFrame(main_frame, text="模型回复")
        response_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        ttk.Label(response_frame, textvariable=self.response_text, wraplength=450).pack(padx=10, pady=5, fill=tk.BOTH)
        
        status_frame = ttk.Frame(main_frame)
        status_frame.pack(fill=tk.X, pady=5)
        self.status_label = ttk.Label(status_frame, text="按住空格键开始录音")
        self.status_label.pack(side=tk.LEFT)
        
        self.update_status()
        self.root.mainloop()

    def update_status(self):
        if self.root.winfo_exists():
            if self.is_recording:
                duration = int(time.time() - self.start_time)
                status = f"录音中... 时长: {duration}秒"
            else:
                status = "按住空格键开始录音"
            
            self.status_label.config(text=status)
            self.root.after(100, self.update_status)

if __name__ == "__main__":
    assistant = VoiceAssistant()
    threading.Thread(target=assistant.record_audio, daemon=True).start()
    assistant.create_gui()