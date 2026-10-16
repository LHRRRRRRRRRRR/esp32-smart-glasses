#include "esp_camera.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "config.h"

// ================= CAMERA - Xiao ESP32S3 =================
#define PWDN_GPIO_NUM     -1
#define RESET_GPIO_NUM    -1
#define XCLK_GPIO_NUM     10
#define SIOD_GPIO_NUM     40
#define SIOC_GPIO_NUM     39
#define Y9_GPIO_NUM       48
#define Y8_GPIO_NUM       11
#define Y7_GPIO_NUM       12
#define Y6_GPIO_NUM       14
#define Y5_GPIO_NUM       16
#define Y4_GPIO_NUM       18
#define Y3_GPIO_NUM       17
#define Y2_GPIO_NUM       15
#define VSYNC_GPIO_NUM    38
#define HREF_GPIO_NUM     47
#define PCLK_GPIO_NUM     13

// ================= KEY & LED =================
#define KEY_PIN 0
#define LED_PIN 21  // Xiao ESP32S3 built-in LED (GPIO 21)

bool lastButton = HIGH;
unsigned long lastPressTime = 0;

// LED status patterns
void ledIdle() {
    // Slow pulse when ready
    digitalWrite(LED_PIN, HIGH);
    delay(50);
    digitalWrite(LED_PIN, LOW);
}

void ledWorking() {
    // Solid on during active operation
    digitalWrite(LED_PIN, HIGH);
}

void ledSuccess() {
    // Double blink on success
    for (int i = 0; i < 2; i++) {
        digitalWrite(LED_PIN, HIGH); delay(100);
        digitalWrite(LED_PIN, LOW);  delay(100);
    }
}

void ledError() {
    // Rapid blink on error
    for (int i = 0; i < 5; i++) {
        digitalWrite(LED_PIN, HIGH); delay(150);
        digitalWrite(LED_PIN, LOW);  delay(150);
    }
}

void ledWiFiConnecting() {
    // Fast blink during WiFi connection
    static unsigned long lastBlink = 0;
    if (millis() - lastBlink > 200) {
        lastBlink = millis();
        digitalWrite(LED_PIN, !digitalRead(LED_PIN));
    }
}

// ================= WiFi =================
void connectWiFi()
{
    WiFi.mode(WIFI_STA);
    WiFi.setAutoReconnect(true);
    WiFi.persistent(true);
    // Open network: pass NULL instead of empty string for better compatibility
    if (strlen(WIFI_PASS) == 0) {
        WiFi.begin(WIFI_SSID);
    } else {
        WiFi.begin(WIFI_SSID, WIFI_PASS);
    }
    Serial.print("Connecting to WiFi");

    unsigned long startConnect = millis();
    const unsigned long WIFI_CONNECT_TIMEOUT = 20000;

    while (WiFi.status() != WL_CONNECTED)
    {
        delay(500);
        Serial.print(".");
        ledWiFiConnecting();
        if (millis() - startConnect > WIFI_CONNECT_TIMEOUT)
        {
            Serial.println();
            Serial.println("WiFi timeout - restarting in 3s...");
            ledError();
            delay(3000);
            ESP.restart();
        }
    }
    Serial.println();
    Serial.println("WiFi connected");
    Serial.print("IP: ");
    Serial.println(WiFi.localIP());
}

// ================= Camera =================
bool startCamera()
{
    camera_config_t config;
    
    config.ledc_channel = LEDC_CHANNEL_0;
    config.ledc_timer = LEDC_TIMER_0;
    config.pin_d0 = Y2_GPIO_NUM;
    config.pin_d1 = Y3_GPIO_NUM;
    config.pin_d2 = Y4_GPIO_NUM;
    config.pin_d3 = Y5_GPIO_NUM;
    config.pin_d4 = Y6_GPIO_NUM;
    config.pin_d5 = Y7_GPIO_NUM;
    config.pin_d6 = Y8_GPIO_NUM;
    config.pin_d7 = Y9_GPIO_NUM;
    config.pin_xclk = XCLK_GPIO_NUM;
    config.pin_pclk = PCLK_GPIO_NUM;
    config.pin_vsync = VSYNC_GPIO_NUM;
    config.pin_href = HREF_GPIO_NUM;
    config.pin_sscb_sda = SIOD_GPIO_NUM;
    config.pin_sscb_scl = SIOC_GPIO_NUM;
    config.pin_pwdn = PWDN_GPIO_NUM;
    config.pin_reset = RESET_GPIO_NUM;
    config.xclk_freq_hz = 20000000;
    config.pixel_format = PIXFORMAT_JPEG;
    config.frame_size = FRAMESIZE_VGA;
    config.jpeg_quality = 8;
    config.fb_count = 2;
    // 这两项必须显式设置：camera_config_t 是未初始化的栈变量，不写就是未定义行为。
    // 尤其 grab_mode：默认的 CAMERA_GRAB_WHEN_EMPTY 会在缓冲区满后停止采集，
    // 加上本程序只在按键时才取帧，队列里存的会是几秒前甚至开机时的画面。
    // CAMERA_GRAB_LATEST 会让驱动一直保留最新帧，按快门才是"现在"。
    config.fb_location = CAMERA_FB_IN_PSRAM;
    config.grab_mode = CAMERA_GRAB_LATEST;

    Serial.println("Initializing camera...");
    
    esp_err_t err = esp_camera_init(&config);
    if (err != ESP_OK)
    {
        Serial.printf("Camera init failed 0x%x, trying QVGA...\n", err);
        config.frame_size = FRAMESIZE_QVGA;
        config.fb_count = 1;
        err = esp_camera_init(&config);
        if (err != ESP_OK) {
            Serial.printf("Camera init failed again 0x%x\n", err);
            return false;
        }
    }

    sensor_t *s = esp_camera_sensor_get();
    if (s) {
        s->set_brightness(s, 1);
        s->set_contrast(s, 1);
        s->set_saturation(s, 1);
        s->set_special_effect(s, 0);
        s->set_whitebal(s, 1);
        s->set_awb_gain(s, 1);
        s->set_wb_mode(s, 0);
        s->set_exposure_ctrl(s, 1);
        s->set_aec2(s, 1);
        // ---- 暗光调优 ----
        // 自动曝光的目标亮度往亮偏 1 档（范围 -2 ~ 2，0 是中性）
        s->set_ae_level(s, 1);
        // 1000/曝光寄存器：自动曝光模式下由 AEC 算法接管，这行只是给个起点
        s->set_aec_value(s, 400);
        s->set_gain_ctrl(s, 1);
        s->set_agc_gain(s, 10);
        // 关键：原来写的是 (gainceiling_t)2，即 GAINCEILING_8X。
        // 暗光下 AGC 撞到 8 倍上限后自动曝光就再也拉不亮画面，实测拍出来接近全黑。
        // 提到 32X 给 AGC 留足余量；若噪点太夸张可降到 GAINCEILING_16X，
        // 若还是很暗就上 GAINCEILING_64X。枚举顺序：2X/4X/8X/16X/32X/64X/128X
        s->set_gainceiling(s, GAINCEILING_32X);
        s->set_bpc(s, 1);
        s->set_wpc(s, 1);
        s->set_raw_gma(s, 1);
        s->set_lenc(s, 1);
        s->set_hmirror(s, 0);
        s->set_vflip(s, 0);
        s->set_dcw(s, 1);
        s->set_colorbar(s, 0);
    }

    Serial.println("Camera initialized successfully");
    return true;
}

// ================= Upload =================
void sendImage(camera_fb_t *fb)
{
    if (!fb) {
        Serial.println("Frame buffer empty");
        return;
    }

    HTTPClient http;
    Serial.printf("Uploading image, size: %u bytes\n", fb->len);
    
    if (WiFi.status() != WL_CONNECTED) {
        Serial.println("WiFi not connected");
        ledError();
        return;
    }

    if (!http.begin(SERVER_URL)) {
        Serial.println("HTTP begin failed");
        ledError();
        return;
    }

    http.addHeader("Content-Type", "image/jpeg");
    http.setTimeout(30000);

    unsigned long t = millis();
    int code = http.POST(fb->buf, fb->len);
    unsigned long elapsed = millis() - t;
    Serial.printf("HTTP elapsed: %lu ms, status: %d\n", elapsed, code);

    if (code == HTTP_CODE_OK)
    {
        String payload = http.getString();
        Serial.println("Server response: " + payload);

        DynamicJsonDocument doc(2048);
        DeserializationError err = deserializeJson(doc, payload);
        if (!err)
        {
            String mode = doc["mode"] | "unknown";
            String text = doc["text"] | "No result";
            Serial.println("====================");
            Serial.print("Mode: ");
            Serial.println(mode);
            Serial.print("Result: ");
            Serial.println(text);
            Serial.println("====================");
            ledSuccess();
        }
        else
        {
            Serial.println("JSON parse failed");
            ledError();
        }
    }
    else
    {
        Serial.printf("HTTP error: %d\n", code);
        if (code == 0) {
            Serial.println("Connection timeout or server unreachable");
        }
        ledError();
    }
    http.end();
}

void captureAndSend()
{
    Serial.println("\n=== Capturing ===");
    
    ledWorking();
    unsigned long start = millis();

    // 先丢掉队列里的陈旧帧，确保拿到的是按下按钮这一刻的画面。
    // 摄像头降级到 QVGA 时 fb_count=1，CAMERA_GRAB_LATEST 不生效（要求 fb_count>1），
    // 这个清队列循环就是唯一的保障。
    for (int i = 0; i < 2; i++) {
        camera_fb_t *stale = esp_camera_fb_get();
        if (stale) {
            esp_camera_fb_return(stale);
        }
    }

    camera_fb_t *fb = esp_camera_fb_get();
    
    if (!fb)
    {
        Serial.println("Capture failed - no frame buffer");
        ledError();
        return;
    }

    Serial.printf("Photo size: %u KB\n", fb->len / 1024);
    sendImage(fb);
    esp_camera_fb_return(fb);

    unsigned long total = millis() - start;
    Serial.printf("Total time: %lu ms\n", total);
}

// ================= Setup & Loop =================
void setup()
{
    Serial.begin(115200);
    delay(100);
    
    Serial.println("\n=== Xiao ESP32S3 Smart Glasses ===");
    
    pinMode(KEY_PIN, INPUT_PULLUP);
    pinMode(LED_PIN, OUTPUT);
    digitalWrite(LED_PIN, LOW);
    Serial.println("Pins configured");

    connectWiFi();

    if (!startCamera())
    {
        Serial.println("Camera init failed, halting...");
        while (1)
        {
            ledError();
            delay(2000);
            Serial.println("Waiting for camera...");
        }
    }

    Serial.println("System ready - Press BOOT to capture");
    ledSuccess();
}

void loop()
{
    if (WiFi.status() != WL_CONNECTED)
    {
        Serial.println("WiFi reconnecting...");
        ledWiFiConnecting();
        WiFi.reconnect();
        delay(2000);
        return;
    }

    bool button = digitalRead(KEY_PIN);
    
    if (lastButton == LOW && button == HIGH)  // Trigger on button RELEASE
    {
        if (millis() - lastPressTime > 1000)
        {
            lastPressTime = millis();
            captureAndSend();
        }
    }
    lastButton = button;
    
    // Idle LED heartbeat
    static unsigned long lastIdleBlink = 0;
    if (millis() - lastIdleBlink > 2000) {
        lastIdleBlink = millis();
        ledIdle();
    }
    
    delay(10);
}
