# server/app.py
from flask import Flask, request, jsonify, send_from_directory, render_template, Response, stream_with_context
import os
import time
import queue
import threading
from config import (
    DEFAULT_API_KEY, FILE_API_KEY, DEFAULT_MODEL, AI_URL, DEFAULT_PROMPT,
    UPLOAD_FOLDER, MAX_PHOTOS, AVAILABLE_MODELS,
    THINKING_ENABLED, THINKING_EFFORT, MAX_OUTPUT_TOKENS,
    RUNTIME_CONFIG_PATH, save_runtime_config
)
from ai_client import call_ai
from database import init_db, get_session
from models import Device, Record

app = Flask(__name__)

app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

current_api_key = DEFAULT_API_KEY
current_model = DEFAULT_MODEL
current_prompt = DEFAULT_PROMPT

last_upload_time = 0

sse_clients = []
sse_lock = threading.Lock()

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
init_db()

def _validate_model(model_name):
    valid = [m["name"] for m in AVAILABLE_MODELS]
    return model_name in valid

def _notify_sse_clients(event, data):
    with sse_lock:
        dead = []
        for q in sse_clients:
            try:
                q.put_nowait((event, data))
            except queue.Full:
                dead.append(q)
        for q in dead:
            sse_clients.remove(q)
@app.route("/stream")
def stream():
    def event_stream():
        q = queue.Queue(maxsize=20)
        with sse_lock:
            sse_clients.append(q)
        try:
            yield f"event: connected\ndata: {last_upload_time}\n\n"
            while True:
                try:
                    event, data = q.get(timeout=30)
                    yield f"event: {event}\ndata: {data}\n\n"
                except queue.Empty:
                    yield ": heartbeat\n\n"
        except GeneratorExit:
            pass
        finally:
            with sse_lock:
                if q in sse_clients:
                    sse_clients.remove(q)
    return Response(
        stream_with_context(event_stream()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*"
        }
    )

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload():
    global last_upload_time
    
    print("\n=== Received upload ===")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Client: {request.remote_addr}")
    
    img = request.data
    print(f"Image size: {len(img)} bytes")
    
    if not img:
        print("Error: no image data")
        return jsonify({"mode": "error", "text": "No image"}), 400

    session = get_session()
    filepath = None
    try:
        timestamp = int(time.time() * 1000)
        filename = f"photo_{timestamp}.jpg"
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        with open(filepath, 'wb') as f:
            f.write(img)
        print(f"Saved: {filename}")

        print(f"Calling AI... Model: {current_model}")
        start = time.time()
        text = call_ai(img, current_prompt, current_model, current_api_key, AI_URL,
                       thinking=THINKING_ENABLED, thinking_effort=THINKING_EFFORT,
                       max_tokens=MAX_OUTPUT_TOKENS)
        print(f"AI time: {time.time() - start:.2f}s")

        mode = "scene"
        if text.startswith("OCR:"):
            mode = "ocr"
            text = text[4:].strip()
        elif text.startswith("SCENE:"):
            text = text[6:].strip()

        device_id = "esp32_001"
        device = session.get(Device, device_id)
        if not device:
            device = Device(id=device_id, name="Smart Glasses")
            session.add(device)
        
        from datetime import datetime
        device.last_seen = datetime.now()
        device.status = "online"
        
        record = Record(
            device_id=device_id,
            filename=filename,
            mode=mode,
            text=text[:500]
        )
        session.add(record)
        session.commit()
        
        last_upload_time = timestamp
        _cleanup_old_photos(session)
        _notify_sse_clients("new_photo", str(timestamp))

        print(f"Result - Mode: {mode}, Text: {text}")
        return jsonify({"mode": mode, "text": text})

    except Exception as e:
        session.rollback()
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
                print(f"Cleaned: {os.path.basename(filepath)}")
            except OSError as clean_err:
                print(f"Clean error: {clean_err}")
        print(f"Error: {str(e)}")
        return jsonify({"mode": "error", "text": str(e)}), 500
    finally:
        session.close()

def _cleanup_old_photos(session):
    records = session.query(Record).order_by(Record.created_at.desc()).all()
    if len(records) > MAX_PHOTOS:
        for r in records[MAX_PHOTOS:]:
            old_path = os.path.join(UPLOAD_FOLDER, r.filename)
            if os.path.exists(old_path):
                os.remove(old_path)
            session.delete(r)
        session.commit()

@app.route("/photos")
def get_photos():
    session = get_session()
    try:
        records = session.query(Record).order_by(Record.created_at.desc()).limit(MAX_PHOTOS).all()
        photos = [{
            "timestamp": int(r.created_at.timestamp() * 1000),
            "time": r.created_at.strftime("%Y-%m-%d %H:%M:%S"),
            "filename": r.filename,
            "mode": r.mode,
            "text": r.text
        } for r in records]
        return jsonify({"photos": photos, "last_upload": last_upload_time})
    finally:
        session.close()

@app.route("/has_new_photo")
def has_new_photo():
    client_time = request.args.get('time', 0, type=int)
    return jsonify({
        "has_new": client_time < last_upload_time,
        "last_upload": last_upload_time
    })

@app.route("/photo/<filename>")
def get_photo(filename):
    if ".." in filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "Invalid filename"}), 400
    return send_from_directory(UPLOAD_FOLDER, filename)

@app.route("/photo/<filename>", methods=["DELETE"])
def delete_photo(filename):
    if ".." in filename or "/" in filename or "\\" in filename:
        return jsonify({"error": "Invalid filename"}), 400
    session = get_session()
    try:
        record = session.query(Record).filter_by(filename=filename).first()
        if not record:
            return jsonify({"success": False, "error": "Record not found"}), 404
        
        filepath = os.path.join(UPLOAD_FOLDER, filename)
        if os.path.exists(filepath):
            os.remove(filepath)
        session.delete(record)
        session.commit()
        _notify_sse_clients("photo_deleted", filename)
        print(f"Deleted: {filename}")
        return jsonify({"success": True})
    except Exception as e:
        session.rollback()
        return jsonify({"success": False, "error": str(e)}), 500
    finally:
        session.close()

@app.route("/get_config")
def get_config():
    return jsonify({
        "api_key_set": bool(current_api_key),
        "model": current_model,
        "available_models": AVAILABLE_MODELS
    })

@app.route("/set_config", methods=["POST"])
def set_config():
    global current_api_key, current_model
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "error": "Missing body"}), 400
    
    if "api_key" in data and data["api_key"].strip():
        current_api_key = data["api_key"].strip()
        print("API Key updated")
    
    if "model" in data:
        model_name = data["model"]
        if not _validate_model(model_name):
            return jsonify({
                "success": False,
                "error": f"Unsupported model: {model_name}",
                "available_models": [m["name"] for m in AVAILABLE_MODELS]
            }), 400
        current_model = model_name
        print(f"Model updated: {current_model}")
    
    # 落到 runtime_config.json（已在 .gitignore），重启后不用重新填
    try:
        save_runtime_config({"api_key": current_api_key, "model": current_model})
        print("Config saved to runtime_config.json")
    except OSError as e:
        print(f"Config persist failed: {e}")
        return jsonify({"success": False, "error": f"Save failed: {e}"}), 500
    
    return jsonify({"success": True, "model": current_model})

@app.route("/reset_config")
def reset_config():
    global current_api_key, current_model
    current_api_key = FILE_API_KEY
    current_model = DEFAULT_MODEL
    # 同时删掉网页端保存的设置，否则重启后又被读回来
    try:
        os.remove(RUNTIME_CONFIG_PATH)
        print("runtime_config.json removed")
    except OSError:
        pass
    return jsonify({"success": True, "model": current_model})

@app.route("/get_prompt")
def get_prompt():
    return jsonify({"prompt": current_prompt.strip()})

@app.route("/set_prompt", methods=["POST"])
def set_prompt():
    global current_prompt
    data = request.get_json()
    if data and "prompt" in data:
        current_prompt = data["prompt"]
        print(f"Prompt updated: {current_prompt[:50]}...")
        return jsonify({"success": True, "prompt": current_prompt.strip()})
    return jsonify({"success": False, "error": "Missing prompt"}), 400

@app.route("/reset_prompt")
def reset_prompt():
    global current_prompt
    current_prompt = DEFAULT_PROMPT
    return jsonify({"success": True, "prompt": current_prompt.strip()})

@app.errorhandler(413)
def request_entity_too_large(e):
    return jsonify({"mode": "error", "text": "Image exceeds 2MB limit"}), 413

if __name__ == "__main__":
    print("=== Smart Glasses Server ===")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    if not DEFAULT_API_KEY:
        print("WARNING: No API Key configured")
    print("URL: http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, threaded=True, debug=False)
