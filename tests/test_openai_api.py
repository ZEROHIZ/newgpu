import requests
import json
import time
import sys

# 确保控制台输出编码为 utf-8，避免中文乱码
if sys.stdout.encoding != 'utf-8':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_api_loop(iterations=10):
    url = "http://192.168.110.30:5566/v1/chat/completions"
    model = "gemini-3-flash-preview"
    
    # 目前测试发现使用 'sk-test' 会返回 401 Invalid Token。
    api_key = "sk-VdJ4DV8srDJVKYzbC1eWuokjohrWRfAqu5IQG29jptOoANUj" 
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }
    
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": "你好，这是一次测试，请简短回复。"}
        ],
        "stream": False
    }

    print("🚀 开始测试 API 稳定性")
    print(f"📍 地址: {url}")
    print(f"🤖 模型: {model}")
    print(f"次数: {iterations} 次")
    print("-" * 60)

    success_count = 0
    fail_count = 0

    for i in range(1, iterations + 1):
        start_time = time.time()
        print(f"[{i:02d}/{iterations}] 请求中... ", end="", flush=True)
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            elapsed = time.time() - start_time
            
            if response.status_code == 200:
                data = response.json()
                try:
                    content = data['choices'][0]['message']['content']
                    # 避免在 f-string 中使用反斜杠
                    display_content = content[:30].replace('\n', ' ')
                    print(f"✅ 成功 | 耗时: {elapsed:.2f}s | 响应: {display_content}...")
                except (KeyError, IndexError):
                    print(f"✅ 成功(格式异常) | 耗时: {elapsed:.2f}s | 完整响应: {json.dumps(data)}")
                success_count += 1
            else:
                print(f"❌ 失败 | 状态码: {response.status_code} | 耗时: {elapsed:.2f}s")
                print(f"   详情: {response.text}")
                fail_count += 1
                
        except requests.exceptions.Timeout:
            print(f"⌛ 超时 | 耗时: {time.time() - start_time:.2f}s")
            fail_count += 1
        except Exception as e:
            print(f"⚠️ 异常 | {str(e)}")
            fail_count += 1
        
        time.sleep(0.3)

    print("-" * 60)
    print(f"统计结果: 成功 {success_count}, 失败 {fail_count}")
    if fail_count > 0:
        print("💡 提示: 所有的 401 错误通常表示 API Key (Token) 无效，请检查 headers 中的 Authorization。")
    print("测试任务结束。")

if __name__ == "__main__":
    test_api_loop(10)
