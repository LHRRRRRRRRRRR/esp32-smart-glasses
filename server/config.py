# server/config.py
import json
import os

# ================= 路径 =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "photos")
DB_PATH = os.path.join(BASE_DIR, "smart_glasses.db")
# 网页 API Config 里保存的设置存这里（已在 .gitignore 中忽略）
RUNTIME_CONFIG_PATH = os.path.join(BASE_DIR, "runtime_config.json")

# ================= 模型列表 =================
# 只有支持视觉(VLM)的模型能列在这里：本项目是把照片发给模型识别
# deepseek-flash 支持图片输入；deepseek-v4-pro 官方明确不支持视觉，选了会报错
AVAILABLE_MODELS = [
    {"name": "deepseek-flash", "description": "DeepSeek-V4.1-Flash - 支持看图，推荐"},
]
FALLBACK_MODEL = AVAILABLE_MODELS[0]["name"]


# ================= 网页端保存的设置 =================
def load_runtime_config():
    """读取网页 API Config 保存的设置；文件不存在或损坏时返回空字典。"""
    try:
        with open(RUNTIME_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def save_runtime_config(data):
    """原子写入，避免写到一半导致文件损坏。"""
    tmp = RUNTIME_CONFIG_PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, RUNTIME_CONFIG_PATH)


RUNTIME_CONFIG = load_runtime_config()

# ================= AI配置（DeepSeek 官方 API） =================
# 密钥读取优先级（高到低）：
#   1. 环境变量 DEEPSEEK_API_KEY
#   2. 网页 API Config 里填的（runtime_config.json，重启后依然有效）
#   3. local_config.py
# 后两个文件都在 .gitignore 中忽略，不会被提交，避免密钥进 git 历史
try:
    from local_config import LOCAL_API_KEY  # type: ignore
except ImportError:
    LOCAL_API_KEY = ""

# 不含网页设置的"文件级"默认值，Reset 按钮会回退到它
FILE_API_KEY = os.environ.get("DEEPSEEK_API_KEY") or LOCAL_API_KEY or ""
DEFAULT_API_KEY = RUNTIME_CONFIG.get("api_key") or FILE_API_KEY

# 注意：DeepSeek-V4.1-Flash 的 API 模型名是 deepseek-flash
# （deepseek-v4-flash / deepseek-v4-flash-vision-exp 是已退役旧名，仍兼容）
_saved_model = RUNTIME_CONFIG.get("model")
_available_names = [m["name"] for m in AVAILABLE_MODELS]
DEFAULT_MODEL = _saved_model if _saved_model in _available_names else FALLBACK_MODEL

AI_URL = "https://api.deepseek.com/chat/completions"

# 思考模式：开启后等价于 "DeepSeek-V4.1-Flash High"，识别更稳，但每张图多等几秒
# 强度可选 low / high / max（官方默认 high）；不想要延迟就改成 False
THINKING_ENABLED = True
THINKING_EFFORT = "high"

# 单次识别的最大输出 token 数。
# 重要：思考模式下"推理内容"也占用这个额度，原本的 150 会被推理吃光，
# 导致最终答案被截断甚至返回空字符串。实测完整回答约需 180 token，这里给足余量。
MAX_OUTPUT_TOKENS = 1024

# ================= 提示词 =================
DEFAULT_PROMPT = """你是智能眼镜助手。
规则：
1. 如果图片中有文字，返回格式：OCR:内容
2. 如果没有文字，返回格式：SCENE:一句话描述（不超过20字）
不要解释，直接输出。"""

# ================= 其他 =================
MAX_PHOTOS = 10
