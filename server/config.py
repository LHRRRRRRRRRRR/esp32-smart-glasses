# server/config.py
import os

# ================= 路径 =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "photos")
DB_PATH = os.path.join(BASE_DIR, "smart_glasses.db")

# ================= AI配置 =================
# 密钥读取优先级：环境变量 SILICONFLOW_API_KEY > local_config.py > 空
# local_config.py 已在 .gitignore 中忽略，不会被提交，避免密钥进 git 历史
try:
    from local_config import LOCAL_API_KEY  # type: ignore
except ImportError:
    LOCAL_API_KEY = ""

DEFAULT_API_KEY = os.environ.get("SILICONFLOW_API_KEY", LOCAL_API_KEY)
DEFAULT_MODEL = "Qwen/Qwen3-VL-8B-Instruct"
AI_URL = "https://api.siliconflow.cn/v1/chat/completions"

# ================= 提示词 =================
DEFAULT_PROMPT = """你是智能眼镜助手。
规则：
1. 如果图片中有文字，返回格式：OCR:内容
2. 如果没有文字，返回格式：SCENE:一句话描述（不超过20字）
不要解释，直接输出。"""

# ================= 其他 =================
MAX_PHOTOS = 10

AVAILABLE_MODELS = [
    {"name": "Qwen/Qwen3-VL-8B-Instruct", "description": "Qwen3-VL 8B - 推荐"},
    {"name": "Qwen/Qwen-VL-Chat", "description": "Qwen-VL Chat"},
    {"name": "Qwen/Qwen2-VL-7B-Instruct", "description": "Qwen2-VL 7B"},
    {"name": "internlm/internlm-xcomposer2-vl-7b", "description": "InternLM XComposer2"},
]
