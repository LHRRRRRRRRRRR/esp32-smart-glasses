# server/ai_client.py
import requests
import base64
import time

session = requests.Session()

# 不重试的状态码：密钥/参数类问题，重试没有意义
FATAL_STATUS = {400, 401, 403, 404}


def call_ai(image_bytes, prompt, model, api_key, ai_url, retries=1):
    """调用AI API，返回识别文字。
    网络错误/限流(429)/服务端错误(5xx)自动重试 retries 次；
    密钥或参数类错误直接抛出，不浪费重试。
    """
    img64 = base64.b64encode(image_bytes).decode()
    
    payload = {
        "model": model,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img64}"}}
            ]
        }],
        "temperature": 0.1,
        "max_tokens": 150
    }
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    last_error = None
    for attempt in range(retries + 1):
        try:
            resp = session.post(ai_url, headers=headers, json=payload, timeout=30)

            # 先把HTTP层错误转成可读消息
            if resp.status_code == 401:
                raise RuntimeError("AI密钥无效(401)，请检查 API Key")
            if resp.status_code == 403:
                raise RuntimeError("AI访问被拒绝(403)，可能欠费或无该模型权限")
            if resp.status_code == 429:
                raise RuntimeError("AI请求限流(429)，请稍后再试")
            if resp.status_code in FATAL_STATUS:
                raise RuntimeError(f"AI请求参数错误(HTTP {resp.status_code}): {resp.text[:200]}")
            if resp.status_code >= 500:
                raise RuntimeError(f"AI服务器错误(HTTP {resp.status_code})")
            resp.raise_for_status()

            result = resp.json()
            try:
                return result["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError, TypeError):
                # 返回体结构不符合预期时，把服务端原始错误带出来，方便排查
                err_msg = result.get("error", {}).get("message", "") if isinstance(result, dict) else ""
                raise RuntimeError(f"AI返回格式异常: {err_msg or str(result)[:200]}")

        except RuntimeError as e:
            # 业务错误：401/403/400 这类重试无意义，直接抛
            last_error = e
            msg = str(e)
            fatal = any(k in msg for k in ("密钥", "拒绝", "参数错误", "返回格式异常"))
            if fatal or attempt == retries:
                raise
        except requests.RequestException as e:
            # 网络层错误（超时、断网、DNS）：可重试
            last_error = RuntimeError(f"连接AI服务失败: {e}")
            if attempt == retries:
                raise

        # 还能重试：简单退避后继续
        if attempt < retries:
            print(f"AI第{attempt + 1}次调用失败({last_error})，2秒后重试...")
            time.sleep(2)

    raise last_error
