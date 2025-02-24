import io
import pyaudio
import wave
import keyboard
import os
import time
import tkinter as tk
from tkinter import ttk, filedialog
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
import pyttsx3
import torch
import torchaudio

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
    """讯飞语音听写WebSocket客户端"""
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

    def on_error(self, ws, error):
        print(f"ASR Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print("ASR Closed")

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

    def run(self):
        websocket.enableTrace(False)
        ws = websocket.WebSocketApp(
            self.ws_param.create_url(),
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        ws.on_open = self.on_open
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})

class TTSWebSocket:
    """讯飞语音合成WebSocket客户端"""
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

    def on_error(self, ws, error):
        print(f"TTS Error: {error}")

    def on_close(self, ws, close_status_code, close_msg):
        print("TTS Closed")
        self.websocket_closed.set()

    def on_open(self, ws):
        data = {
            "common": self.ws_param.CommonArgs,
            "business": self.ws_param.BusinessArgs,
            "data": self.ws_param.Data
        }
        ws.send(json.dumps(data))

    def run(self):
        websocket.enableTrace(False)
        ws = websocket.WebSocketApp(
            self.ws_param.create_url(),
            on_message=self.on_message,
            on_error=self.on_error,
            on_close=self.on_close
        )
        ws.on_open = self.on_open
        ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
        self.websocket_closed.wait()
        return bytes(self.audio_data)

class WsParam:
    """讯飞听写参数生成器"""
    def __init__(self, APPID, APIKey, APISecret, AudioFile):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.AudioFile = AudioFile
        self.CommonArgs = {"app_id": self.APPID}
        self.BusinessArgs = {
            "domain": "iat",
            "language": "zh_cn",
            "accent": "mandarin",
            "vinfo": 1,
            "vad_eos": 10000
        }

    def create_url(self):
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        signature_origin = "host: ws-api.xfyun.cn\ndate: {}\nGET /v2/iat HTTP/1.1".format(date)
        signature_sha = hmac.new(self.APISecret.encode(), signature_origin.encode(), hashlib.sha256).digest()
        signature = base64.b64encode(signature_sha).decode()
        authorization = base64.b64encode(
            f'api_key="{self.APIKey}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'.encode()
        ).decode()
        return f"wss://ws-api.xfyun.cn/v2/iat?{urlencode({'authorization': authorization, 'date': date, 'host': 'ws-api.xfyun.cn'})}"

class WsParamTTS:
    """讯飞语音合成参数生成器"""
    def __init__(self, APPID, APIKey, APISecret, Text):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.Text = Text
        self.CommonArgs = {"app_id": self.APPID}
        self.BusinessArgs = {
            "aue": "raw",
            "auf": "audio/L16;rate=16000",
            "vcn": "aisjiuxu",
            "tte": "utf8"
        }
        self.Data = {
            "status": 2,
            "text": base64.b64encode(self.Text.encode()).decode()
        }

    def create_url(self):
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))
        signature_origin = "host: ws-api.xfyun.cn\ndate: {}\nGET /v2/tts HTTP/1.1".format(date)
        signature_sha = hmac.new(self.APISecret.encode(), signature_origin.encode(), hashlib.sha256).digest()
        signature = base64.b64encode(signature_sha).decode()
        authorization = base64.b64encode(
            f'api_key="{self.APIKey}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature}"'.encode()
        ).decode()
        return f"wss://tts-api.xfyun.cn/v2/tts?{urlencode({'authorization': authorization, 'date': date, 'host': 'ws-api.xfyun.cn'})}"

class LocalASRProcessor:
    """本地语音识别处理器"""
    def __init__(self, model_path):
        self.model = torch.jit.load(model_path)
        self.model.eval()
        self.resample = torchaudio.transforms.Resample(orig_freq=16000, new_freq=16000)
        self.vocab = ["<pad>", "<unk>"] + [chr(i) for i in range(ord('a'), ord('z')+1)] + [" ", "'", "<eos>"]
        
    def process_audio(self, file_path):
        waveform, sample_rate = torchaudio.load(file_path)
        if sample_rate != 16000:
            waveform = torchaudio.transforms.Resample(sample_rate, 16000)(waveform)
        return waveform.unsqueeze(0)
    
    def transcribe(self, waveform):
        with torch.no_grad():
            outputs = self.model(waveform)
        return self.decode_output(outputs[0])
    
    def decode_output(self, outputs):
        tokens = torch.argmax(outputs, dim=-1)
        return "".join([self.vocab[t] for t in tokens.tolist() if t < len(self.vocab)]).replace("<eos>", "")

class VoiceAssistant:
    """主应用程序类"""
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        
        # 状态变量
        self.selected_model = tk.StringVar(value='localhost')
        self.selected_tts = tk.StringVar(value='xfyun')
        self.selected_asr = tk.StringVar(value='xfyun')
        self.local_asr_model_path = tk.StringVar()
        self.is_recording = False
        self.recording_lock = threading.Lock()
        self.start_time = None
        
        # 音频设备
        self.audio_player = pyaudio.PyAudio()
        self.task_queue = queue.Queue()
        
        # 文本显示
        self.asr_text = tk.StringVar()
        self.response_text = tk.StringVar()
        
        # 本地引擎
        self.engine = pyttsx3.init()
        self.check_queue()
        
        # 配置选项
        self.model_options = {
            "localhost": "本地模型", 
            "utral": "星火模型"
        }
        self.tts_options = {
            "local": "本地语音合成",
            "xfyun": "讯飞语音"
        }
        self.asr_options = {
            "xfyun": "讯飞听写",
            "local": "本地ASR模型"
        }

    # GUI相关方法
    def create_gui(self):
        self.root.deiconify()
        self.root.title('智能语音助手 v2.0')
        self.root.geometry('900x600')
        
        # 控制面板
        control_frame = ttk.Frame(self.root, padding=10)
        control_frame.pack(fill=tk.X)
        
        # 模型选择
        model_frame = self.create_select_frame(control_frame, "AI模型", self.model_options, self.selected_model)
        model_frame.pack(side=tk.LEFT, padx=5)
        
        # ASR选择
        asr_frame = ttk.LabelFrame(control_frame, text="语音识别")
        asr_frame.pack(side=tk.LEFT, padx=5)
        self.create_asr_controls(asr_frame)
        
        # TTS选择
        tts_frame = self.create_select_frame(control_frame, "语音合成", self.tts_options, self.selected_tts)
        tts_frame.pack(side=tk.LEFT, padx=5)
        
        # 结果显示
        result_frame = ttk.Frame(self.root)
        result_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        self.create_result_panels(result_frame)
        
        # 状态栏
        status_frame = ttk.Frame(self.root)
        status_frame.pack(fill=tk.X, padx=10, pady=5)
        self.status_label = ttk.Label(status_frame, text="按住空格键开始录音")
        self.status_label.pack()
        
        self.root.after(100, self.update_status)
        self.root.mainloop()

    def create_select_frame(self, parent, title, options, variable):
        frame = ttk.LabelFrame(parent, text=title)
        combobox = ttk.Combobox(
            frame, 
            textvariable=variable,
            values=list(options.values()),
            state="readonly",
            width=12
        )
        combobox.current(0)
        combobox.pack()
        combobox.bind("<<ComboboxSelected>>", lambda e: self.on_combo_select(e, options))
        return frame

    def create_asr_controls(self, parent):
        self.asr_combobox = ttk.Combobox(
            parent,
            textvariable=self.selected_asr,
            values=list(self.asr_options.values()),
            state="readonly",
            width=12
        )
        self.asr_combobox.current(0)
        self.asr_combobox.pack(side=tk.LEFT)
        self.asr_combobox.bind("<<ComboboxSelected>>", self.on_asr_select)
        
        ttk.Button(parent, text="选择模型", command=self.select_asr_model).pack(side=tk.LEFT, padx=5)
        ttk.Label(parent, textvariable=self.local_asr_model_path, width=30).pack(side=tk.LEFT)

    def create_result_panels(self, parent):
        # 语音识别结果
        asr_result_frame = ttk.LabelFrame(parent, text="识别结果")
        asr_result_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(asr_result_frame, textvariable=self.asr_text, wraplength=800).pack(padx=10, pady=5)
        
        # 模型回复
        response_frame = ttk.LabelFrame(parent, text="AI回复")
        response_frame.pack(fill=tk.BOTH, expand=True)
        ttk.Label(response_frame, textvariable=self.response_text, wraplength=800).pack(padx=10, pady=5)

    # 事件处理
    def on_combo_select(self, event, options):
        widget = event.widget
        selected_text = widget.get()
        for key, value in options.items():
            if value == selected_text:
                getattr(self, f'selected_{widget.master["text"].lower().replace(" ", "_")}').set(key)
                break

    def on_asr_select(self, event):
        selected_text = self.asr_combobox.get()
        for key, value in self.asr_options.items():
            if value == selected_text:
                self.selected_asr.set(key)
                break

    def select_asr_model(self):
        if self.selected_asr.get() == 'local':
            path = filedialog.askopenfilename(filetypes=[("模型文件", "*.pt *.pth")])
            if path:
                self.local_asr_model_path.set(path)

    # 核心功能
    def record_audio(self):
        while True:
            filename = os.path.join(RECORD_DIR, "output.wav")
            p = pyaudio.PyAudio()
            stream = p.open(
                format=FORMAT,
                channels=CHANNELS,
                rate=RATE,
                input=True,
                frames_per_buffer=CHUNK
            )
            
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
        self.task_queue.put(lambda: self.asr_text.set(""))
        
        if self.selected_asr.get() == 'xfyun':
            asr_ws = ASRWebSocket(audio_file, self.update_asr_callback)
            asr_ws.run()
        else:
            threading.Thread(
                target=self.run_local_asr,
                args=(audio_file,),
                daemon=True
            ).start()

    def run_local_asr(self, audio_file):
        try:
            if not os.path.exists(self.local_asr_model_path.get()):
                raise FileNotFoundError("ASR模型文件不存在")
            
            processor = LocalASRProcessor(self.local_asr_model_path.get())
            waveform = processor.process_audio(audio_file)
            text = processor.transcribe(waveform)
            
            self.task_queue.put(lambda: self.asr_text.set(text))
            self.task_queue.put(lambda: self.process_response(text))
            
        except Exception as e:
            self.task_queue.put(
                lambda: self.asr_text.set(f"ASR错误: {str(e)}")
            )

    def update_asr_callback(self, text):
        current = self.asr_text.get()
        self.task_queue.put(lambda: self.asr_text.set(current + text))
        
        if text.endswith(('。', '！', '？')):
            self.task_queue.put(lambda: self.process_response(current + text))

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
        if self.selected_tts.get() == 'xfyun':
            self.use_xfyun_tts(text)
        else:
            self.use_local_tts(text)

    def use_xfyun_tts(self, text):
        def tts_task():
            try:
                tts_ws = TTSWebSocket(text)
                audio_data = tts_ws.run()
                self.task_queue.put(lambda: self.finalize_response(text, audio_data))
            except Exception as e:
                print(f"讯飞语音合成失败: {e}")
        threading.Thread(target=tts_task, daemon=True).start()

    def use_local_tts(self, text):
        def tts_task():
            try:
                temp_file = os.path.join(RECORD_DIR, "temp_tts.wav")
                self.engine.setProperty('rate', 200)
                self.engine.setProperty('volume', 1.0)
                self.engine.save_to_file(text, temp_file)
                self.engine.runAndWait()
                
                with open(temp_file, 'rb') as f:
                    audio_data = f.read()
                
                self.task_queue.put(lambda: self.finalize_response(text, audio_data))
                
            except Exception as e:
                print(f"本地语音合成失败: {e}")
                self.task_queue.put(lambda: self.response_text.set(f"语音合成失败: {str(e)}"))
        
        threading.Thread(target=tts_task, daemon=True).start()

    def finalize_response(self, text, audio_data):
        self.response_text.set(text)
        if self.selected_tts.get() == 'local':
            self.play_local_audio(audio_data)
        else:
            self.play_xfyun_audio(audio_data)

    def play_local_audio(self, audio_data):
        def play_thread():
            try:
                with wave.open(io.BytesIO(audio_data)) as wf:
                    stream = self.audio_player.open(
                        format=self.audio_player.get_format_from_width(wf.getsampwidth()),
                        channels=wf.getnchannels(),
                        rate=wf.getframerate(),
                        output=True
                    )
                    data = wf.readframes(1024)
                    while data:
                        stream.write(data)
                        data = wf.readframes(1024)
                    stream.stop_stream()
                    stream.close()
            except Exception as e:
                print(f"本地音频播放失败: {e}")
        
        threading.Thread(target=play_thread, daemon=True).start()

    def play_xfyun_audio(self, audio_data):
        def play_thread():
            try:
                stream = self.audio_player.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,
                    output=True
                )
                chunk_size = 1024
                for i in range(0, len(audio_data), chunk_size):
                    stream.write(audio_data[i:i+chunk_size])
                stream.stop_stream()
                stream.close()
            except Exception as e:
                print(f"讯飞音频播放失败: {e}")
        
        threading.Thread(target=play_thread, daemon=True).start()

    # 辅助方法
    def check_queue(self):
        try:
            while True:
                task = self.task_queue.get_nowait()
                task()
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.check_queue)

    def update_status(self):
        if self.is_recording:
            duration = int(time.time() - self.start_time)
            self.status_label.config(text=f"录音中... 时长: {duration}秒")
        else:
            self.status_label.config(text="按住空格键开始录音")
        self.root.after(100, self.update_status)

if __name__ == "__main__":
    assistant = VoiceAssistant()
    threading.Thread(target=assistant.record_audio, daemon=True).start()
    assistant.create_gui()
