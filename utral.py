from sparkai.llm.llm import ChatSparkLLM, ChunkPrintHandler
from sparkai.core.messages import ChatMessage
import sys
import pyttsx3

def get_response_text(response):
    """提取星火模型回复的文本内容"""
    try:
        if response.generations:
            first_generation = response.generations[0][0]
            return first_generation.text.strip()
        return "未收到有效回复"
    except Exception as e:
        print(f"解析响应时出错: {e}")
        return "响应解析失败"

def send_to_sparkai(text):
    """调用星火认知大模型"""
    SPARKAI_URL = 'wss://spark-api.xf-yun.com/v4.0/chat'
    SPARKAI_APP_ID = '71efdd04'
    SPARKAI_API_SECRET = 'NmUxNTczMzQyMjYxZTcwYTdlOGMyZjUy'
    SPARKAI_API_KEY = 'e63cbab297110bc8d29c9ede6565bbe1'
    SPARKAI_DOMAIN = '4.0Ultra'

    try:
        spark = ChatSparkLLM(
            spark_api_url=SPARKAI_URL,
            spark_app_id=SPARKAI_APP_ID,
            spark_api_key=SPARKAI_API_KEY,
            spark_api_secret=SPARKAI_API_SECRET,
            spark_llm_domain=SPARKAI_DOMAIN,
            streaming=False,
        )
        
        messages = [ChatMessage(role="user", content=text)]
        result = spark.generate([messages])
        return get_response_text(result)
    
    except Exception as e:
        print(f"调用星火API时出错: {e}")
        return "服务暂时不可用"

def read_input_file():
    """读取输入文本文件"""
    try:
        with open('./result.txt', 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        print("错误：未找到result.txt文件")
        sys.exit(1)
    except Exception as e:
        print(f"读取文件时出错: {e}")
        sys.exit(1)

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

if __name__ == '__main__':
    # 读取输入内容
    input_text = read_input_file()
    print(input_text+"\n")    
    # 获取并打印回复
    result= send_to_sparkai(input_text)
    print(result)
    text_to_speech(result)