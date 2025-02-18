import wave
import pyaudio
import threading
import os
import subprocess
import tkinter as tk
from tkinter import messagebox

# 录音参数
CHUNK = 1024  # 每个缓冲区的帧数
FORMAT = pyaudio.paInt16  # 16位量化
CHANNELS = 1  # 单声道
RATE = 16000  # 采样率
OUTPUT_FILENAME = "./upload_audio/output.wav"  # 输出文件名

# 全局变量
is_recording = False  # 录音状态
frames = []  # 存储录音数据
p = None  # PyAudio 对象
stream = None  # 音频流对象
recording_thread = None  # 录音线程
use_local_model = True  # 默认使用本地模型

# 录音函数
def record_audio():
    global is_recording, frames
    try:
        while is_recording:
            data = stream.read(CHUNK)
            frames.append(data)
    except Exception as e:
        print(f"Error during recording: {e}")

# 开始录音
# 开始录音
def start_recording():
    global is_recording, frames, p, stream, recording_thread
    if is_recording:
        return

    print("Recording started...")
    is_recording = True
    frames = []  # 清空之前的录音数据

    # 初始化 PyAudio 和音频流
    try:
        p = pyaudio.PyAudio()
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)
    except Exception as e:
        print(f"Error initializing audio stream: {e}")
        messagebox.showerror("Error", f"Error initializing audio stream: {e}")
        return

    # 启动录音线程
    recording_thread = threading.Thread(target=record_audio, daemon=True)
    recording_thread.start()

# 停止录音
def stop_recording():
    global is_recording, frames, p, stream, recording_thread, use_local_model
    if not is_recording:
        return

    print("Recording stopped. Saving audio...")
    is_recording = False

    # 等待录音线程结束
    if recording_thread is not None:
        recording_thread.join()

    # 停止录音并关闭流
    if stream is not None:
        stream.stop_stream()
        stream.close()
    if p is not None:
        p.terminate()

    # 保存录音文件（直接覆盖已存在的文件）
    try:
        with wave.open(OUTPUT_FILENAME, 'wb') as wf:
            wf.setnchannels(CHANNELS)
            wf.setsampwidth(p.get_sample_size(FORMAT))
            wf.setframerate(RATE)
            wf.writeframes(b''.join(frames))
        print(f"Audio saved to {OUTPUT_FILENAME}")
    except PermissionError:
        print(f"Error: Permission denied. Please close any program using {OUTPUT_FILENAME} and try again.")
        messagebox.showerror("Error", f"Permission denied. Please close any program using {OUTPUT_FILENAME}.")
    except Exception as e:
        print(f"Error saving audio: {e}")
        messagebox.showerror("Error", f"Error saving audio: {e}")

    # 调用 iat_ws_python3.py，并传递模型选择参数
    try:
        model_type = "local" if use_local_model else "remote"
        subprocess.run(["python", "iat_ws_python3.py", OUTPUT_FILENAME, model_type], check=True)
    except subprocess.CalledProcessError as e:
        print(f"Error calling iat_ws_python3.py: {e}")
        messagebox.showerror("Error", f"Error calling iat_ws_python3.py: {e}")


# 切换模型类型
def toggle_model_type():
    global use_local_model
    use_local_model = not use_local_model
    model_type = "本地模型" if use_local_model else "远程模型"
    model_button.config(text=f"当前模型: {model_type}")
    print(f"切换到 {model_type}")

# GUI 界面
class AudioRecorderApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Audio Recorder")
        self.root.geometry("300x150")

        # 提示标签
        self.label = tk.Label(root, text="按住空格录制,松开空格结束", font=("Arial", 12))
        self.label.pack(pady=10)

        # 模型切换按钮
        global model_button
        model_button = tk.Button(root, text="当前模型: 本地模型", command=toggle_model_type)
        model_button.pack(pady=10)

        # 绑定键盘事件
        self.root.bind("<KeyPress-space>", lambda event: start_recording())
        self.root.bind("<KeyRelease-space>", lambda event: stop_recording())

# 主程序
if __name__ == "__main__":
    root = tk.Tk()
    app = AudioRecorderApp(root)
    root.mainloop()