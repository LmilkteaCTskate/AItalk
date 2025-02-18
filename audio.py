import pyaudio
import wave
import keyboard
import os
import time
import tkinter as tk
import threading
import subprocess

# 设置录音参数
FORMAT = pyaudio.paInt16  # 16位深度
CHANNELS = 1              # 单声道
RATE = 16000              # 采样率
CHUNK = 1024              # 每次读取的音频块大小
RECORD_DIR = './upload_audio'  # 音频保存路径

# 创建保存目录（如果不存在）
if not os.path.exists(RECORD_DIR):
    os.makedirs(RECORD_DIR)

# 全局变量用于状态跟踪
is_recording = False
recording_lock = threading.Lock()

def record_audio():
    """录制音频并保存为 output.wav，每次录音都会覆盖该文件"""
    global is_recording
    filename = os.path.join(RECORD_DIR, "output.wav")

    p = None
    stream = None
    try:
        p = pyaudio.PyAudio()
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK)

        print("准备就绪，按住空格键开始录音...")

        frames = []
        recording = False  # 用于标记是否正在录音

        while True:
            if keyboard.is_pressed('space'):
                if not recording:  # 开始录音
                    recording = True
                    with recording_lock:
                        is_recording = True
                    print("录音开始...")
                data = stream.read(CHUNK)
                frames.append(data)
            elif recording:
                # 松开空格键时停止录音
                recording = False
                with recording_lock:
                    is_recording = False
                print("录音结束...")
                break  # 结束录音并保存

            time.sleep(0.01)  # 避免过度消耗CPU
    except Exception as e:
        print(f"录音过程中发生错误: {e}")
    finally:
        # 确保资源正确释放
        if stream is not None:
            stream.stop_stream()
            stream.close()
        if p is not None:
            p.terminate()
        # 保存录音数据
        if 'frames' in locals() and frames:
            print("保存录音文件...")
            try:
                with wave.open(filename, 'wb') as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(p.get_sample_size(FORMAT))
                    wf.setframerate(RATE)
                    wf.writeframes(b''.join(frames))
                print(f"录音已保存为 {filename}")
                #录音完成后调用转文本
                subprocess.run(['python','ASR.py'])

            except Exception as e:
                print(f"保存录音时发生错误: {e}")
        else:
            print("没有录音数据，文件未保存")

def tkinter_audio():
    """创建 Tkinter 窗口并更新录音状态"""
    window = tk.Tk()
    window.title('语音转文本')
    window.geometry('400x300')
    
    # 用于存储模型选项
    models = ["本地模型", "星火模型", "其他模型"]
    selected_model = tk.StringVar()  # 用于存储选择的模型
    
    def on_model_select():
        """确认按钮的回调函数"""
        model = selected_model.get()
        if model == "本地模型":
            model = 'localhost'
            #将选择模型写入model文件中
            with open('./model/model.txt', 'w') as f:
                f.write(model)
                print("选择模型: " + model)
        elif model == "星火模型":
            model = 'utral'
            #将选择模型写入model文件中
            with open('./model/model.txt', 'w') as f:
                f.write(model)
                print("选择模型: " + model)
        else:
            print("没有选择任何模型")
        return model
    
    # 创建单选按钮，只能选择一个
    for model in models:
        radio_btn = tk.Radiobutton(window, text=model, variable=selected_model, value=model)
        radio_btn.pack(anchor='w')
    
    # 设置默认值为第一个模型
    selected_model.set(models[0])

    # 确认按钮
    button = tk.Button(window, text="确认模型", command=on_model_select)
    button.pack(pady=10)

    status_label = tk.Label(window, font=("Arial", 12))
    status_label.pack(pady=50)

    def update_status():
        """更新界面录音状态"""
        with recording_lock:
            current_status = "录音中..." if is_recording else "按住空格键开始录音"
        status_label.config(text=current_status)
        window.after(100, update_status)  # 每100ms更新一次

    update_status()  # 初始化状态更新
    window.mainloop()

def start_recording():
    """持续监听录音的循环"""
    while True:
        record_audio()

def start_recording_thread():
    """启动录音线程"""
    recording_thread = threading.Thread(target=start_recording)
    recording_thread.daemon = True  # 随主线程退出而终止
    recording_thread.start()

if __name__ == "__main__":
    start_recording_thread()  # 启动录音线程
    tkinter_audio()           # 启动GUI界面
    
