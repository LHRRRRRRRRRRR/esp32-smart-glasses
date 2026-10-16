# Smart Glasses Assistant

ESP32 photo capture → Flask backend upload → AI recognition → Database storage → Web display.

## Tech Stack
- **ESP32**: Arduino, esp_camera, HTTPClient, ArduinoJson
- **Backend**: Python, Flask, SQLAlchemy, SQLite
- **AI**: DeepSeek 官方 API（`deepseek-flash` / DeepSeek-V4.1-Flash，支持图片输入）
- **Frontend**: HTML, CSS, JS (Dark mode, SSE real-time push, OCR copy)

## Features
- **Dark Mode**: Auto-detect system preference, toggle with localStorage persistence
- **Real-time Push**: SSE (Server-Sent Events) for instant updates, polling fallback
- **Photo Management**: Individual photo deletion, copy OCR text to clipboard
- **LED Status**: ESP32 built-in LED indicates WiFi/capture/upload status
- **Model Validation**: Server-side model name validation before applying

## Project Structure
```
smart-glasses/
│
├── esp32/
│   ├── platformio.ini
│   ├── src/
│   │   └── main.cpp
│   └── include/
│       └── config.h
│
├── server/
│   ├── app.py
│   ├── config.py
│   ├── models.py
│   ├── database.py
│   ├── ai_client.py
│   ├── requirements.txt
│   ├── templates/
│   │   └── index.html
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css
│   │   └── js/
│   │       └── main.js
│   └── photos/
│
├── docs/
│   └── README.md
│
└── .gitignore
```

## Quick Start

### Backend
```bash
cd server
pip install -r requirements.txt
```

Configure API Key (priority high to low):
1. Set env var `DEEPSEEK_API_KEY`
2. Enter key in Web UI "API Config" (persisted to `runtime_config.json`, survives restart, in .gitignore)
3. Copy `local_config.example.py` to `local_config.py` with real key (in .gitignore)

Start server:
```bash
python app.py
```
Visit http://localhost:5000

### ESP32
1. Copy `esp32/include/config.h.example` to `config.h`, set WiFi credentials and server IP
2. Build & flash with PlatformIO:
```bash
cd esp32
pio run --target upload
pio device monitor
```

## API Endpoints
| Method | Path | Description |
|---|---|---|
| GET | / | Home page |
| POST | /upload | Upload image (max 2MB) |
| GET | /photos | Photo list |
| GET | /has_new_photo | Check for new photos |
| GET | /photo/<filename> | Get image |
| DELETE | /photo/<filename> | Delete photo & record |
| GET | /stream | SSE real-time updates |
| GET | /get_config | Get config |
| POST | /set_config | Update config (model validated) |
| GET | /reset_config | Reset config |
| GET | /get_prompt | Get prompt |
| POST | /set_prompt | Update prompt |
| GET | /reset_prompt | Reset prompt |

## Data Flow
ESP32 capture → HTTP POST /upload → Save image → Call AI (auto retry 1x) → Write DB → SSE push to web → Web renders

## Error Handling
- AI failures: saved image auto-cleaned to avoid orphan files
- Network/rate-limit errors: auto retry 1x; key errors (401/403) no retry
- Upload > 2MB: JSON error response, not HTML error page
- Path traversal protection on /photo/<filename> endpoints
