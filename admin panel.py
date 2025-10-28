import requests

ADMIN_KEY = ""
BASE_API = "http://127.0.0.1:5000"  # локальный Flask-сервер


def get_ngrok_url():
    """Пытается получить актуальный ngrok-URL. Если не удаётся — возвращает BASE_API."""
    try:
        r = requests.get(f"{BASE_API}/api/get_url", timeout=3)
        if r.status_code == 200:
            data = r.json()
            url = data.get("url")
            if url and url.startswith("https://"):
                print(f"🌐 Используется ngrok: {url}")
                return url
        print("ℹ️ Ngrok не найден, используется локальный сервер.")
    except requests.RequestException:
        print("⚠️ Не удалось подключиться к ngrok. Работаем локально.")
    return BASE_API


def register_user():
    username = input("Введите логин для нового игрока: ").strip()
    password = input("Введите пароль для нового игрока: ")

    api_url = get_ngrok_url() + "/api/register"
    try:
        r = requests.post(api_url, json={
            "username": username,
            "password": password,
            "admin_key": ADMIN_KEY
        })
        data = r.json()
        print(f"{r.status_code} {data}")
    except Exception as e:
        print("❌ Ошибка запроса:", e)


def list_users():
    api_url = get_ngrok_url() + f"/api/admin/users?admin_key={ADMIN_KEY}"
    try:
        r = requests.get(api_url)
        data = r.json()
        if r.status_code == 200:
            print("👥 Список пользователей:", data.get("users", []))
        else:
            print(f"❌ Ошибка ({r.status_code}):", data)
    except Exception as e:
        print("❌ Ошибка запроса:", e)


def change_password():
    username = input("Введите логин пользователя: ").strip()
    new_password = input("Введите новый пароль: ")

    api_url = get_ngrok_url() + "/api/admin/change_password"
    try:
        r = requests.post(api_url, json={
            "username": username,
            "new_password": new_password,
            "admin_key": ADMIN_KEY
        })
        data = r.json()
        print(f"{r.status_code} {data}")
    except Exception as e:
        print("❌ Ошибка запроса:", e)


def delete_user():
    username = input("Введите логин пользователя для удаления: ").strip()

    api_url = get_ngrok_url() + "/api/admin/delete_user"
    try:
        r = requests.post(api_url, json={
            "username": username,
            "admin_key": ADMIN_KEY
        })
        data = r.json()
        print(f"{r.status_code} {data}")
    except Exception as e:
        print("❌ Ошибка запроса:", e)


# -------------------- Главное меню --------------------
def main():
    while True:
        print("\n=== Меню администратора ===")
        print("1. Зарегистрировать нового игрока")
        print("2. Посмотреть всех пользователей")
        print("3. Изменить пароль пользователя")
        print("4. Удалить пользователя")
        print("0. Выйти")

        choice = input("Выберите действие: ").strip()
        if choice == "1":
            register_user()
        elif choice == "2":
            list_users()
        elif choice == "3":
            change_password()
        elif choice == "4":
            delete_user()
        elif choice == "0":
            break
        else:
            print("❌ Некорректный выбор")


if __name__ == "__main__":
    main()
