# AItalk
ai对话demo
audio.py用于录制音频
iat_ws_python3.py为科大讯飞语音听写
local_llm将处理结果提交给本地模型进行回复

#教程
在终端输入pip install -r requirements.txt 安装所需库后
在iat_ws_python3.py中写入科大讯飞的语音听写API(目前只支持这个)

随后在local_llm.py中填入本地Ollama部署的模型名称

然后在根目录中输入powershell后运行python.exe ./audio.py

