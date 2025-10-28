
from flask import Flask, request, jsonify
import hashlib
import uuid
import time
import json
import os
import requests
import base64

app = Flask(__name__)

USERS_FILE = "users.json"
sessions = {}
ADMIN_KEY = ""
NGROK_API = ""  # локальный API ngrok

# 🔹 GitHub настройки
GITHUB_TOKEN = ""   # твой GitHub PAT
GITHUB_REPO = ""     # репозиторий
GITHUB_FILE_PATH = "url.json"    # путь до файла
GITHUB_BRANCH = "main"           # ветка


def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4)

users = load_users()

@app.route("/api/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username", "").strip()
    password = data.get("password", "")
    admin_key = data.get("admin_key", "")

    if admin_key != ADMIN_KEY:
        return jsonify({"success": False, "error": "Not allowed"}), 403

    if not username or not password:
        return jsonify({"success": False, "error": "Username and password required"}), 400

    if username in users:
        return jsonify({"success": False, "error": "User already exists"}), 409

    if len(password) < 6:
        return jsonify({"success": False, "error": "Password must be at least 6 characters"}), 400

    users[username] = hashlib.sha256(password.encode()).hexdigest()
    save_users(users)

    return jsonify({"success": True, "message": f"User {username} registered"}), 201

@app.route("/api/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if username not in users:
        return jsonify({"success": False, "error": "User not found"}), 401

    if users[username] != hashlib.sha256(password.encode()).hexdigest():
        return jsonify({"success": False, "error": "Wrong password"}), 401

    token = str(uuid.uuid4())
    sessions[username] = {"token": token, "time": time.time()}

    return jsonify({
        "success": True,
        "token": token,
        "uuid": str(uuid.uuid5(uuid.NAMESPACE_DNS, username)),
        "username": username
    })

@app.route("/api/verify", methods=["POST"])
def verify():
    data = request.get_json()
    token = data.get("token")

    for username, sess in sessions.items():
        if sess["token"] == token and time.time() - sess["time"] < 3600:
            return jsonify({"success": True, "username": username})

    return jsonify({"success": False}), 401

@app.route("/api/get_url", methods=["GET"])
def get_url():
    try:
        tunnels = requests.get(NGROK_API).json()["tunnels"]
        for t in tunnels:
            if t["proto"] == "https":
                return jsonify({"url": t["public_url"]})
        return jsonify({"error": "No https tunnel found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ------------------ Админ-меню ------------------

@app.route("/api/admin/users", methods=["GET"])
def admin_list_users():
    """Вернуть список всех пользователей (только для админа)"""
    admin_key = request.args.get("admin_key", "")
    if admin_key != ADMIN_KEY:
        return jsonify({"success": False, "error": "Not allowed"}), 403

    return jsonify({"success": True, "users": list(users.keys())})


@app.route("/api/admin/change_password", methods=["POST"])
def admin_change_password():
    """Сменить пароль пользователя (только для админа)"""
    data = request.get_json()
    admin_key = data.get("admin_key", "")
    username = data.get("username", "").strip()
    new_password = data.get("new_password", "")

    if admin_key != ADMIN_KEY:
        return jsonify({"success": False, "error": "Not allowed"}), 403

    if username not in users:
        return jsonify({"success": False, "error": "User not found"}), 404

    if len(new_password) < 6:
        return jsonify({"success": False, "error": "Password must be at least 6 characters"}), 400

    users[username] = hashlib.sha256(new_password.encode()).hexdigest()
    save_users(users)
    return jsonify({"success": True, "message": f"Password for {username} updated"})
# ------------------ MONOBANK ------------------

MONO_TOKEN = ""  # 🔹 токен из кабинета Monobank Business
MONO_ACCOUNT = None  # 🔹 можно оставить None — API вернёт все счета
MONO_API = "https://api.monobank.ua/personal/statement"

@app.route("/api/check_orders", methods=["GET"])
def check_orders():
    """
    Проверка поступлений на Monobank.
    Ожидается, что пользователь указывает order_id в комментарии перевода.
    Возвращает список оплаченных заказов.
    """
    try:
        now = int(time.time())
        frm = now - 24 * 3600  # за последние 24 часа
        url = f"{MONO_API}/0/{frm}/{now}"

        headers = {"X-Token": MONO_TOKEN}
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return jsonify({"error": "Monobank API error", "details": r.text}), 500

        txs = r.json()
        paid_orders = []

        for tx in txs:
            comment = tx.get("comment", "") or ""
            if "order_id" in comment.lower():
                order_id = comment.split(":")[-1].strip()
                paid_orders.append({
                    "order_id": order_id,
                    "amount": tx.get("amount", 0) / 100,
                    "currency": tx.get("currencyCode", "UAH"),
                    "status": "paid",
                    "time": tx.get("time")
                })

        return jsonify({"orders": paid_orders})

    except Exception as e:
        return jsonify({"error": str(e)}), 500



# 🔹 Функция для обновления url.json на GitHub
def update_github_url():
    try:
        tunnels = requests.get(NGROK_API).json()["tunnels"]
        ngrok_url = next((t["public_url"] for t in tunnels if t["proto"] == "https"), None)
        if not ngrok_url:
            print("❌ Не найден https-туннель ngrok")
            return

        api_url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{GITHUB_FILE_PATH}"
        headers = {"Authorization": f"token {GITHUB_TOKEN}"}

        # Получаем текущее содержимое файла
        current = requests.get(api_url, headers=headers).json()
        sha = current.get("sha")

        if "content" in current:
            try:
                existing_content = base64.b64decode(current["content"]).decode()
                existing_json = json.loads(existing_content)
                if existing_json.get("url") == ngrok_url:
                    print("ℹ️ Ngrok URL не изменился, коммит не нужен")
                    return
            except Exception as e:
                print("⚠️ Не удалось распарсить существующий файл:", e)

        # Формируем новые данные
        new_content = json.dumps({"url": ngrok_url}, indent=2)
        data = {
            "message": "Update ngrok URL",
            "content": base64.b64encode(new_content.encode()).decode(),
            "branch": GITHUB_BRANCH,
            "committer": {  # 🔹 коммит будет от "бота", не от твоего профиля
                "name": "bot",
                "email": "bot@example.com"
            },
            "author": {
                "name": "bot",
                "email": "bot@example.com"
            }
        }
        if sha:
            data["sha"] = sha

        r = requests.put(api_url, headers=headers, json=data)
        if r.status_code in (200, 201):
            print(f"✅ Ngrok URL обновлён: {ngrok_url}")
        else:
            print("❌ Ошибка GitHub:", r.json())

    except Exception as e:
        print("❌ Ошибка update_github_url:", e)

# =================== /api/create_order ===================

ORDERS_FILE = "orders.json"

# вспомогательные функции
def load_orders():
    if os.path.exists(ORDERS_FILE):
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_orders(data):
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

orders = load_orders()

@app.route("/api/create_order", methods=["POST"])
def create_order():
    """Создание нового заказа от Telegram-бота"""
    try:
        data = request.get_json(force=True)
        username = data.get("username")
        password = data.get("password")
        payer_card = data.get("payer_card")
        method = data.get("method", "monobank")
        chat_id = data.get("chat_id")

        if not username or not password or not chat_id:
            return jsonify({"success": False, "error": "missing fields"}), 400

        order_id = str(int(time.time())) + str(uuid.uuid4().hex[:4])
        order = {
            "order_id": order_id,
            "chat_id": chat_id,
            "username": username,
            "password": password,
            "payer_card": payer_card,
            "method": method,
            "status": "pending",
            "created": int(time.time())
        }

        orders.append(order)
        save_orders(orders)
        print(f"✅ Новый заказ создан: {order_id} для @{username}")

        return jsonify({"success": True, "order_id": order_id})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500
# ------------------ YOOMONEY ------------------

YOOMONEY_WALLET = ""  # твой номер кошелька
YOOMONEY_TOKEN = ""  # OAuth токен
YOOMONEY_API = "https://yoomoney.ru/api/operation-history"


@app.route("/api/check_yoomoney", methods=["GET"])
def check_yoomoney():
    """
    Проверка поступлений на YooMoney.
    Пользователь указывает order_id в комментарии.
    """
    try:
        headers = {
            "Authorization": f"Bearer {YOOMONEY_TOKEN}"
        }
        params = {
            "records": 50,  # последние 50 операций
            "type": "deposition"
        }
        r = requests.post(YOOMONEY_API, headers=headers, data=params, timeout=10)
        if r.status_code != 200:
            return jsonify({"error": "YooMoney API error", "details": r.text}), 500

        data = r.json()
        txs = data.get("operations", [])
        paid_orders = []

        for tx in txs:
            comment = tx.get("message", "") or ""
            if "order_id" in comment.lower():
                order_id = comment.split(":")[-1].strip()
                paid_orders.append({
                    "order_id": order_id,
                    "amount": float(tx.get("amount", 0)),
                    "currency": "RUB",
                    "status": "paid",
                    "time": tx.get("datetime")
                })

        return jsonify({"orders": paid_orders})
    except Exception as e:
        return jsonify({"error": str(e)}), 500
# ------------------ USDT (TRC20) ------------------
USDT_WALLET = "TGcFLyXRperjx1GTS1yTw75xYsP7bN8cay"  # 👈 твой TRC20 адрес
USDT_API = "https://apilist.tronscanapi.com/api/transaction"  # API Tronscan

@app.route("/api/check_usdt", methods=["GET"])
def check_usdt():
    """
    Проверка поступлений USDT (TRC20) по адресу.
    Пользователь указывает order_id в memo/comment.
    """
    try:
        params = {
            "address": USDT_WALLET,
            "limit": 50
        }
        r = requests.get(USDT_API, params=params, timeout=10)
        if r.status_code != 200:
            return jsonify({"error": "USDT API error", "details": r.text}), 500

        txs = r.json().get("token_transfers", [])
        paid_orders = []

        for tx in txs:
            comment = tx.get("memo", "") or tx.get("data", "") or ""
            if "order_id" in comment.lower():
                order_id = comment.split(":")[-1].strip()
                paid_orders.append({
                    "order_id": order_id,
                    "amount": float(tx.get("amount", 0)),
                    "currency": "USDT",
                    "status": "paid",
                    "time": tx.get("block_timestamp")
                })

        return jsonify({"orders": paid_orders})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ------------------ Удаление пользователя ------------------
@app.route("/api/admin/delete_user", methods=["POST"])
def admin_delete_user():
    """Удаление пользователя (только для админа)"""
    data = request.get_json()
    admin_key = data.get("admin_key", "")
    username = data.get("username", "").strip()

    if admin_key != ADMIN_KEY:
        return jsonify({"success": False, "error": "Not allowed"}), 403

    if username not in users:
        return jsonify({"success": False, "error": "User not found"}), 404

    users.pop(username)
    save_users(users)
    return jsonify({"success": True, "message": f"User {username} deleted"})



# =================== Запуск сервера ===================
if __name__ == "__main__":
    update_github_url()   # <-- при старте обновляем url.json
    app.run(host="0.0.0.0", port=5000, debug=True)
