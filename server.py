import sys
import os
import socket
import time
import logging
import io
import threading
import webbrowser
import uuid
import subprocess
from flask import Flask, request, render_template, send_file, jsonify
import qrcode
import shutil

def hide_console():
    if os.name == 'nt':
        return subprocess.STARTUPINFO(dwFlags=subprocess.STARTF_USESHOWWINDOW, wShowWindow=0)
    return None

def resource_path(relative_path):
    if hasattr(sys, '_MEIPASS'):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.abspath("."), relative_path)

app = Flask(__name__, 
            static_folder=resource_path('static'),
            template_folder=resource_path(os.path.join('static', 'html')))

PORT = 3600
RECEIVE_DIR = os.path.join(os.path.expanduser("~"), "Desktop", "receive")
SEND_TO_PHONE_DIR = os.path.join(RECEIVE_DIR, "to_phone")

def clear_all_on_start():
    try:
        for base_dir in [RECEIVE_DIR, SEND_TO_PHONE_DIR]:
            if os.path.exists(base_dir):
                for f in os.listdir(base_dir):
                    path = os.path.join(base_dir, f)
                    if os.path.isfile(path):
                        os.remove(path)
    except Exception as e:
        logging.error(f"{e}")

os.makedirs(RECEIVE_DIR, exist_ok=True)
os.makedirs(SEND_TO_PHONE_DIR, exist_ok=True)

if os.name == 'nt':
    try:
        subprocess.run(['attrib', '+h', SEND_TO_PHONE_DIR], check=True, startupinfo=hide_console())
    except Exception as e:
        logging.error(f"{e}")

clear_all_on_start()

QR_TOKEN = uuid.uuid4().hex
UPLOAD_TOKEN = uuid.uuid4().hex

last_heartbeat = time.time()

def check_heartbeat():
    global last_heartbeat
    while True:
        if time.time() - last_heartbeat > 8:
            try:
                if os.path.exists(SEND_TO_PHONE_DIR):
                    for f in os.listdir(SEND_TO_PHONE_DIR):
                        path = os.path.join(SEND_TO_PHONE_DIR, f)
                        if os.path.isfile(path):
                            os.remove(path)
            except Exception as e:
                logging.error(f"{e}")
            os._exit(0)
        time.sleep(1)

threading.Thread(target=check_heartbeat, daemon=True).start()

logging.basicConfig(
    filename="logs.txt",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8"
)

logging.getLogger('werkzeug').setLevel(logging.ERROR)

def get_local_ips():
    ips = []
    try:
        hostname = socket.gethostname()
        for addr in socket.getaddrinfo(hostname, None):
            ip = addr[4][0]
            if "." in ip and ip != "127.0.0.1": 
                if ip not in ips:
                    ips.append(ip)
        
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        primary_ip = s.getsockname()[0]
        s.close()
        if primary_ip not in ips:
            ips.insert(0, primary_ip)
    except:
        pass
    if not ips:
        ips = ["127.0.0.1"]
    return ips

def get_save_path(filename):
    return os.path.join(RECEIVE_DIR, filename)

@app.route("/qr/<token>")
def qr_page(token):
    if token != QR_TOKEN:
        return "发生了一点问题，请重新启动程序喵~", 403
    return render_template("qr.html", token=QR_TOKEN, upload_token=UPLOAD_TOKEN, ips=get_local_ips(), port=PORT)

@app.route("/api/files/<token>")
def list_files(token):
    if token != QR_TOKEN:
        return "无效访问", 403
    files = []
    if os.path.exists(RECEIVE_DIR):
        files = sorted(
            [f for f in os.listdir(RECEIVE_DIR) if os.path.isfile(os.path.join(RECEIVE_DIR, f))],
            key=lambda f: os.path.getmtime(os.path.join(RECEIVE_DIR, f)),
            reverse=True
        )
    return jsonify({"files": files, "texts": msg_store["to_pc"]})

msg_store = {"to_pc": [], "to_phone": []}

@app.route("/api/send_text/<token>", methods=["POST"])
def send_text(token):
    if token != UPLOAD_TOKEN:
        return "无效访问", 403
    data = request.json
    text = data.get("text")
    if text:
        msg_store["to_pc"].insert(0, {"id": uuid.uuid4().hex, "content": text, "time": time.time()})
        msg_store["to_pc"] = msg_store["to_pc"][:20]
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@app.route("/api/pc_send_text/<token>", methods=["POST"])
def pc_send_text(token):
    if token != QR_TOKEN:
        return "无效访问", 403
    data = request.json
    text = data.get("text")
    if text:
        msg_store["to_phone"].insert(0, {"id": uuid.uuid4().hex, "content": text, "time": time.time()})
        msg_store["to_phone"] = msg_store["to_phone"][:20]
        return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 400

@app.route("/api/pc_upload/<token>", methods=["POST"])
def pc_upload(token):
    if token != QR_TOKEN:
        return "无效访问", 403
    files = request.files.getlist("files")
    saved = []
    for f in files:
        if f and f.filename:
            path = os.path.join(SEND_TO_PHONE_DIR, f.filename)
            with open(path, 'wb') as dest:
                shutil.copyfileobj(f.stream, dest, length=1024*1024)
            saved.append(f.filename)
    return jsonify({"status": "success", "files": saved})

@app.route("/api/phone_files/<token>")
def list_phone_files(token):
    if token != UPLOAD_TOKEN:
        return "无效访问", 403
    files = []
    if os.path.exists(SEND_TO_PHONE_DIR):
        files = sorted(os.listdir(SEND_TO_PHONE_DIR), key=lambda f: os.path.getmtime(os.path.join(SEND_TO_PHONE_DIR, f)), reverse=True)
    return jsonify({"files": files, "texts": msg_store["to_phone"]})

@app.route("/download/<token>/<filename>")
def download_file(token, filename):
    if token != UPLOAD_TOKEN:
        return "无效访问", 403
    path = os.path.join(SEND_TO_PHONE_DIR, filename)
    if os.path.exists(path):
        def delayed_delete(file_path):
            time.sleep(2) 
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logging.error(f"{e}")

        if filename.startswith("文字_") and filename.endswith(".txt"):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
            threading.Thread(target=delayed_delete, args=(path,)).start()
            return content
        
        return send_file(path, as_attachment=True)
    return "文件不存在", 404

@app.route("/open_file", methods=["POST"])
def open_file_location():
    filename = request.json.get("filename")
    if filename:
        path = os.path.join(RECEIVE_DIR, filename)
        if os.path.exists(path):
            if os.name == 'nt':
                subprocess.Popen(f'explorer /select,"{path}"')
                return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404

@app.route("/open_folder", methods=["POST"])
def open_folder():
    if os.path.exists(RECEIVE_DIR):
        if os.name == 'nt': 
            subprocess.Popen(f'explorer "{RECEIVE_DIR}"')
            return jsonify({"status": "success"})
    return jsonify({"status": "error"}), 404

@app.route("/api/qr")
def qr_img():
    data = request.args.get("data", "")
    if not data:
        return "Missing data", 400
    img = qrcode.make(data)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return send_file(buf, mimetype="image/png")

@app.route("/api/heartbeat/<token>")
def heartbeat(token):
    if token == QR_TOKEN:
        global last_heartbeat
        last_heartbeat = time.time()
        return jsonify({"status": "ok"})
    return jsonify({"status": "error", "message": "token mismatch"}), 403

@app.route("/upload/<token>")
def upload_page(token):
    if token != UPLOAD_TOKEN:
        return "请重新扫描电脑浏览器二维码喵", 403
    return render_template("upload.html", token=token)

@app.route("/upload/<token>", methods=["POST"])
def upload_action(token):
    if token != UPLOAD_TOKEN:
        return "无效访问", 403
    files = request.files.getlist("files")
    saved = []
    for f in files:
        if f and f.filename:
            name = str(int(time.time()*1000)) + "_" + f.filename
            path = get_save_path(name)
            try:
                with open(path, 'wb') as dest:
                    shutil.copyfileobj(f.stream, dest, length=1024*1024)
                saved.append(f.filename)
            except Exception as e:
                logging.error(f"{str(e)}")
    return jsonify({"status": "success", "files": saved})

if __name__ == "__main__":
    def get_primary_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
            
    ip = get_primary_ip()
    qr_page_url = f"http://{ip}:{PORT}/qr/{QR_TOKEN}"
    print("\n电脑端页面 (PC)：", qr_page_url)
    def open_browser():
        time.sleep(1)
        webbrowser.open(qr_page_url)
    threading.Thread(target=open_browser).start()
    app.run(host="0.0.0.0", port=PORT, debug=False)