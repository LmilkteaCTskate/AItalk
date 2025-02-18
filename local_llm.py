# LLM.py
import requests
import argparse
import re
import subprocess
import pyttsx3

def send_to_ollama(text, model_name="deepseek-r1:1.5b", api_url="http://localhost:11434/api/generate"):
    """
    发送文本到本地部署的Ollama服务
    """
    headers = {"Content-Type": "application/json"}
    data = {
        "model": model_name,  # 使用的模型名称
        "prompt": text,        # 输入的文本
        "stream": False        # 是否流式输出
    }

    try:
        #测试查看请求和响应参数请取消此模块注释
        
        # print(f"请求URL: {api_url}")
        # print(f"请求参数: {data}")
        response = requests.post(api_url, headers=headers, json=data)
        # print(f"响应状态码: {response.status_code}")
        # print(f"响应内容: {response.text}")

        if response.status_code == 200:
            result = response.json()
            # 过滤掉 <think> 和 </think> 标签
            response_text = result.get("response", "未收到有效响应")
            cleaned_text = re.sub(r"<think>.*?</think>", "", response_text, flags=re.DOTALL).strip()
            return cleaned_text
        else:
            return f"请求失败，状态码: {response.status_code}, 错误信息: {response.text}"
    except Exception as e:
        return f"请求异常: {str(e)}"

def main():
    # 解析命令行参数
    parser = argparse.ArgumentParser(description="调用本地Ollama服务处理文本")
    parser.add_argument("--model", type=str, default="deepseek-r1:1.5b", help="Ollama模型名称（默认：deepseek-r1:1.5b）")
    parser.add_argument("--api_url", type=str, default="http://localhost:11434/api/generate", help="Ollama API地址（默认：http://localhost:11434/api/generate）")
    args = parser.parse_args()

    # 读取result.txt文件中的文本内容
    with open('./result.txt', 'r', encoding='utf-8') as f:
        text = f.read().strip()

    if not text:
        print("没有识别到文本内容")
        return
    print(text)
    #print("识别的文本内容:", text)

    # 调用本地Ollama服务
    #print(f"调用Ollama模型: {args.model}...")
    result = send_to_ollama(text, args.model, args.api_url)

    print(result)
    # 保存模型处理结果到 result.txt
    with open('./result.txt', 'w', encoding='utf-8') as f:
        f.write(result)
    #读取处理结果并使用tts播放
    text_to_speech(result)
def text_to_speech(result):
    """
    将文本转换为语音并朗读
    """
    # 初始化 TTS 引擎
    engine = pyttsx3.init()

    # 设置语速（可选）
    engine.setProperty('rate', 200)  # 默认是 200，值越小语速越慢

    # 设置音量（可选）
    engine.setProperty('volume', 1.0)  # 范围是 0.0 到 1.0

    # 设置语音（可选）
    voices = engine.getProperty('voices')
    engine.setProperty('voice', voices[0].id)  # 0 是男性声音，1 是女性声音（如果有）

    # 朗读文本
    engine.say(result)
    engine.runAndWait()
    #print("模型处理结果:", result)

if __name__ == "__main__":
    main()
