import os
import sys
import threading
import subprocess
import logging
import requests
import tkinter as tk
from tkinter import ttk, messagebox
from PIL import Image, ImageTk
import minecraft_launcher_lib
import json
import shutil
import platform
import zipfile
import io

# ---------------- Настройки ----------------

MINECRAFT_VERSION = "1.12.2"
FORGE_BUILD = "14.23.5.2859"  # короткий номер билда
FORGE_VERSION = f"{MINECRAFT_VERSION}-forge-{FORGE_BUILD}"
LAUNCHER_VERSION = "2.2.1"
LAUNCHER_JSON_URL = "https://kol49.github.io/rtkapi/launcher.json"
API_META_URL = "https://kol49.github.io/rtkapi/url.json"

FORGE_INSTALLER_URL = "https://maven.minecraftforge.net/net/minecraftforge/forge/1.12.2-14.23.5.2859/forge-1.12.2-14.23.5.2859-installer.jar"

MINECRAFT_DIR = minecraft_launcher_lib.utils.get_minecraft_directory()

# ---------------- Логирование ----------------
logging.basicConfig(level=logging.CRITICAL)
logging.getLogger().setLevel(logging.CRITICAL)
logging.getLogger("minecraft_launcher_lib").setLevel(logging.CRITICAL)


CONFIG_PATH = os.path.join(MINECRAFT_DIR, "launcher_config.json")
ram_allocation = "2G"  # значение по умолчанию

def save_config():
    global ram_allocation
    config = {
        "ram_allocation": ram_allocation,
        "remember_me": remember_var.get(),
        "saved_user": entry_user.get().strip() if remember_var.get() else "",
        "saved_pass": entry_pass.get().strip() if remember_var.get() else ""
    }
    os.makedirs(MINECRAFT_DIR, exist_ok=True)
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4)
    except Exception as e:
        show_error("Ошибка", f"Не удалось сохранить настройки:\n{e}")


def load_config():
    global ram_allocation
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                config = json.load(f)
                ram_allocation = config.get("ram_allocation", ram_allocation)

                # Загрузка логина/пароля
                if config.get("remember_me"):
                    remember_var.set(True)
                    entry_user.insert(0, config.get("saved_user", ""))
                    entry_pass.insert(0, config.get("saved_pass", ""))
        except Exception as e:
            show_error("Ошибка", f"Не удалось загрузить настройки:\n{e}")

# Загружаем настройки при старте лаунчера


def open_options():
    opts_win = tk.Toplevel(root)
    opts_win.title("Настройки")
    opts_win.geometry("300x150")
    opts_win.resizable(False, False)

    tk.Label(opts_win, text="Выберите объём оперативной памяти:",
             font=("Arial", 11)).pack(pady=10)

    values = ["1G", "2G", "3G", "4G", "6G", "8G", "12G", "16G"]
    combo = ttk.Combobox(opts_win, values=values, state="readonly")
    combo.set(ram_allocation)  # загруженное значение
    combo.pack(pady=5)

    def save_and_close():
        global ram_allocation
        ram_allocation = combo.get()
        save_config()
        opts_win.destroy()

    tk.Button(opts_win, text="Сохранить", command=save_and_close,
              width=15, bg="#28a745", fg="white").pack(pady=10)


# ---------------- Java ----------------


JAVA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jre")
JAVA_BIN = os.path.join(JAVA_DIR, "bin", "java.exe" if os.name == "nt" else "java")

# ссылки на portable JRE 8 (Temurin)
JAVA_URLS = {
    "Windows": "https://github.com/adoptium/temurin8-binaries/releases/download/jdk8u382-b05/OpenJDK8U-jre_x64_windows_hotspot_8u382b05.zip",
    "Linux": "https://github.com/adoptium/temurin8-binaries/releases/download/jdk8u382-b05/OpenJDK8U-jre_x64_linux_hotspot_8u382b05.tar.gz",
    "Darwin": "https://github.com/adoptium/temurin8-binaries/releases/download/jdk8u382-b05/OpenJDK8U-jre_x64_mac_hotspot_8u382b05.tar.gz",
}


def auto_install_java():
    """Скачивает и распаковывает Java 8 portable в папку jre"""
    os.makedirs(JAVA_DIR, exist_ok=True)
    system = platform.system()
    url = JAVA_URLS.get(system)

    if not url:
        show_error("Ошибка", f"Автоустановка Java не поддерживается на {system}")
        return None

    try:
        loading = tk.Toplevel(root)
        loading.title("Установка Java 8")
        loading.geometry("400x150")
        tk.Label(loading, text="Скачиваем Java 8...", font=("Arial", 12)).pack(pady=15)
        pb = ttk.Progressbar(loading, mode="indeterminate")
        pb.pack(fill="x", padx=20, pady=10)
        pb.start(10)

        def download_and_extract():
            try:
                resp = requests.get(url, stream=True, timeout=60)
                resp.raise_for_status()

                if url.endswith(".zip"):
                    with zipfile.ZipFile(io.BytesIO(resp.content)) as z:
                        z.extractall(JAVA_DIR)
                else:
                    import tarfile
                    with tarfile.open(fileobj=io.BytesIO(resp.content), mode="r:gz") as tar:
                        tar.extractall(JAVA_DIR)

                # переносим содержимое если внутри лишняя папка
                for item in os.listdir(JAVA_DIR):
                    p = os.path.join(JAVA_DIR, item)
                    if os.path.isdir(p) and "bin" in os.listdir(p):
                        for sub in os.listdir(p):
                            s, d = os.path.join(p, sub), os.path.join(JAVA_DIR, sub)
                            if not os.path.exists(d):
                                shutil.move(s, d)
                        shutil.rmtree(p, ignore_errors=True)
                        break

                pb.stop()
                loading.destroy()
                show_info("Java установлена", "✅ Java 8 успешно установлена!")
            except Exception as e:
                pb.stop()
                loading.destroy()
                show_error("Ошибка установки Java", str(e))

        threading.Thread(target=download_and_extract, daemon=True).start()
    except Exception as e:
        show_error("Ошибка", f"Не удалось установить Java:\n{e}")
        return None


def get_java_executable() -> str | None:
    """Возвращает путь к java.exe или скачивает portable"""
    # 1️⃣ Проверяем JAVA_HOME
    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        java_path = os.path.join(java_home, "bin", "java.exe" if os.name == "nt" else "java")
        if os.path.exists(java_path):
            return java_path

    # 2️⃣ Проверяем java в PATH
    java_path = shutil.which("java")
    if java_path:
        return java_path

    # 3️⃣ Проверяем локальную portable Java
    if os.path.exists(JAVA_BIN):
        return JAVA_BIN

    # 4️⃣ Если нет — пробуем установить
    auto_install_java()
    return JAVA_BIN if os.path.exists(JAVA_BIN) else None


def check_java() -> bool:
    """Проверка Java, скачивает при необходимости"""
    java = get_java_executable()
    if not java or not os.path.exists(java):
        show_error("Java не найдена", "❌ Не удалось найти или установить Java 8.\nПроверьте интернет.")
        return False

    try:
        result = subprocess.run([java, "-version"], capture_output=True, text=True)
        print(result.stderr.strip())
        return result.returncode == 0
    except Exception as e:
        show_error("Ошибка Java", f"❌ Не удалось запустить Java:\n{e}")
        return False
# ---------------- Вспомогательные функции ----------------
def show_error(title: str, message: str):
    error_win = tk.Toplevel(root)
    error_win.title(title)
    error_win.geometry("400x150")
    error_win.resizable(False, False)

    tk.Label(error_win, text=title, fg="red", font=("Arial", 12, "bold")).pack(pady=5)
    tk.Label(error_win, text=message, wraplength=380, justify="center").pack(pady=5)
    tk.Button(error_win, text="OK", command=error_win.destroy,
              bg="#ff5555", fg="white", width=15).pack(pady=10)


def show_info(title: str, message: str):
    messagebox.showinfo(title, message)


def get_api_url(endpoint: str) -> str | None:
    try:
        meta = requests.get(API_META_URL, timeout=5).json()
        if url := meta.get("url"):
            return url + endpoint
        show_error("Ошибка", "❌ Сервер не вернул ngrok-адрес")
    except requests.exceptions.RequestException:
        show_error("Ошибка соединения", "Не удалось подключиться к серверу.\nПроверьте интернет.")
    return None


def check_java() -> bool:
    try:
        result = subprocess.run(["java", "-version"], capture_output=True, text=True)
        if result.returncode == 0:
            return True
    except FileNotFoundError:
        pass
    show_error("Java не найдена", "❌ Установите Java 8 или 17 и добавьте в PATH.")
    return False


# ---------------- Обновление лаунчера ----------------
import zipfile
import io

def update_launcher():
    try:
        resp = requests.get(LAUNCHER_JSON_URL, timeout=5).json()
        latest = resp.get("version")
        url = resp.get("url")  # теперь здесь должна быть ссылка на ZIP архив со всей сборкой

        if not latest or not url:
            show_error("Обновление", "❌ Не удалось получить информацию о лаунчере")
            return

        if latest == LAUNCHER_VERSION:
            show_info("Обновление", "Лаунчер уже последней версии")
            return

        if not messagebox.askyesno(
            "Обновление",
            f"Доступна новая версия {latest}.\nСкачать и установить всю сборку?"
        ):
            return

        loading = tk.Toplevel(root)
        loading.title("Обновление лаунчера")
        loading.geometry("400x150")
        tk.Label(loading, text="Скачивание и установка сборки...", font=("Arial", 12)).pack(pady=10)
        pb = ttk.Progressbar(loading, mode="indeterminate")
        pb.pack(fill="x", padx=20, pady=10)
        pb.start(10)

        def download():
            try:
                r = requests.get(url, stream=True)
                r.raise_for_status()

                # 📦 Распаковываем zip прямо в папку лаунчера
                launcher_dir = os.path.dirname(os.path.realpath(sys.argv[0]))

                with zipfile.ZipFile(io.BytesIO(r.content)) as zip_ref:
                    zip_ref.extractall(launcher_dir)

                pb.stop()
                loading.destroy()

                show_info("Обновление", f"✅ Сборка успешно обновлена до версии {latest}.\nПерезапустите лаунчер.")
                root.quit()

            except Exception as e:
                pb.stop()
                loading.destroy()
                show_error("Ошибка обновления", str(e))

        threading.Thread(target=download, daemon=True).start()

    except Exception as e:
        show_error("Ошибка", f"Проблема при проверке обновлений:\n{e}")



# ---------------- Установка Minecraft + Forge ----------------
def ensure_forge() -> str | None:
    mc_dir = MINECRAFT_DIR
    forge_path = os.path.join(mc_dir, "versions", FORGE_VERSION)
    forge_json = os.path.join(forge_path, f"{FORGE_VERSION}.json")

    # Если Forge уже установлен
    if os.path.exists(forge_json):
        return FORGE_VERSION

    # Ставим ванильную 1.12.2
    try:
        minecraft_launcher_lib.install.install_minecraft_version(MINECRAFT_VERSION, mc_dir)
    except Exception as e:
        print(f"[ERROR] Не удалось поставить ваниль: {e}")
        return None

    # Ставим Forge
    try:
        minecraft_launcher_lib.forge.install_forge_version(f"{MINECRAFT_VERSION}-{FORGE_BUILD}", mc_dir)
    except Exception as e:
        print(f"[ERROR] Forge установка провалилась: {e}")
        return None

    if os.path.exists(forge_json):
        return FORGE_VERSION
    return None

# ---------------- Запуск игры ----------------
def start_game(username: str, uuid: str, token: str):
    if not check_java():
        return

    os.makedirs(MINECRAFT_DIR, exist_ok=True)

    loading = tk.Toplevel(root)
    loading.title("Запуск")
    loading.geometry("400x150")
    tk.Label(loading, text="Подготовка Minecraft...", font=("Arial", 12)).pack(pady=20)
    pb = ttk.Progressbar(loading, mode="indeterminate")
    pb.pack(fill="x", padx=20, pady=10)
    pb.start(10)

    def run():
        try:
            forge = ensure_forge()
            if not forge:
                loading.destroy()
                return

            launcher_root = os.path.dirname(os.path.abspath(sys.argv[0]))

            # ⚡ Передаём токен через environment для клиентского мода
            env = os.environ.copy()
            env["RTK_TOKEN"] = token  # клиентский мод должен читать этот токен

            opts = {
                "username": username[:16],
                "uuid": uuid,
                "accessToken": "fake",  # Minecraft не проверяет, токен нужен только мод
                "jvmArguments": [f"-Xmx{ram_allocation}", f"-Xms{ram_allocation}"],
                "nativesDirectory": os.path.join(MINECRAFT_DIR, "versions", MINECRAFT_VERSION, "natives"),
                "gameDirectory": launcher_root,
                "server": "147.185.221.211",
                "port": "11880"
            }

            root.withdraw()
            loading.destroy()

            cmd = minecraft_launcher_lib.command.get_minecraft_command(
                version=forge,
                minecraft_directory=MINECRAFT_DIR,
                options=opts
            )

            log_win = tk.Toplevel(root)
            log_win.title("Minecraft лог")
            log_win.geometry("700x400")
            text = tk.Text(log_win, wrap="word", bg="black", fg="lime", insertbackground="white")
            text.pack(fill="both", expand=True)

            def append_log(data):
                text.insert("end", data)
                text.see("end")

            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    text=True, bufsize=1, universal_newlines=True, env=env)

            def reader():
                for line in proc.stdout:
                    append_log(line)
                proc.wait()
                append_log("\n=== Minecraft завершился ===\n")

            threading.Thread(target=reader, daemon=True).start()

        except Exception as e:
            loading.destroy()
            show_error("Ошибка запуска", str(e))

    threading.Thread(target=run, daemon=True).start()
# ---------------- Авторизация ----------------
def login():
    user = entry_user.get().strip()
    pwd = entry_pass.get().strip()

    if not user or not pwd:
        show_error("Ошибка входа", "Введите логин и пароль")
        return

    if not (url := get_api_url("/api/login")):
        return

    try:
        resp = requests.post(url, json={"username": user, "password": pwd}, timeout=5)
        data = resp.json()
    except Exception:
        show_error("Ошибка", "Не удалось подключиться к серверу")
        return

    if resp.status_code != 200 or not data.get("success"):
        show_error("Ошибка входа", data.get("error", "Некорректный ответ сервера"))
        return

    show_info("Успех", f"Добро пожаловать, {data['username']}!")
    save_config()  # сохраняем данные при входе
    start_game(data["username"], data["uuid"], data["token"])



# ---------------- Окно Options ----------------
def open_options():
    def save_and_close():
        global ram_allocation
        ram_allocation = combo.get()
        save_config()
        opts_win.destroy()

    opts_win = tk.Toplevel(root)
    opts_win.title("Настройки")
    opts_win.geometry("300x150")
    opts_win.resizable(False, False)

    tk.Label(opts_win, text="Выберите объём оперативной памяти:",
             font=("Arial", 11)).pack(pady=10)

    values = ["1G", "2G", "3G", "4G", "6G", "8G", "12G", "16G"]
    combo = ttk.Combobox(opts_win, values=values, state="readonly")
    combo.set(ram_allocation)  # текущее значение
    combo.pack(pady=5)

    tk.Button(opts_win, text="Сохранить", command=save_and_close,
              width=15, bg="#28a745", fg="white").pack(pady=10)



    # ---------------- Окно Options ----------------
    def open_options():
        def save_and_close():
            global ram_allocation
            ram_allocation = combo.get()
            save_config()
            opts_win.destroy()

        opts_win = tk.Toplevel(root)
        opts_win.title("Настройки")
        opts_win.geometry("300x150")
        opts_win.resizable(False, False)

        tk.Label(opts_win, text="Выберите объём оперативной памяти:",
                 font=("Arial", 11)).pack(pady=10)

        values = ["1G", "2G", "3G", "4G", "6G", "8G", "12G", "16G"]
        combo = ttk.Combobox(opts_win, values=values, state="readonly")
        combo.set(ram_allocation)  # текущее значение
        combo.pack(pady=5)

        tk.Button(opts_win, text="Сохранить", command=save_and_close,
                  width=15, bg="#28a745", fg="white").pack(pady=10)



# ---------------- GUI ----------------
root = tk.Tk()
root.title("RTK Launcher")
root.geometry("900x500")



try:
    root.iconbitmap("icon.ico")
except Exception:
    pass

# --- Фон ---
bg_photo = None
background_label = tk.Label(root)
background_label.place(x=0, y=0, relwidth=1, relheight=1)

def update_bg(event=None):
    global bg_photo
    try:
        bg = Image.open("background.png").resize((root.winfo_width(), root.winfo_height()))
        bg_photo = ImageTk.PhotoImage(bg)
        background_label.config(image=bg_photo)
    except FileNotFoundError:
        root.configure(bg="black")

root.bind("<Configure>", update_bg)  # обновляем фон при изменении размера
update_bg()  # первый вызов при старте

# --- Центральный блок логина ---
frame = tk.Frame(root, bg="black", bd=10)  # увеличена толщина рамки
frame.place(relx=0.5, rely=0.5, anchor="center")

tk.Label(frame, text="Логин:", font=("Arial", 13), bg="black", fg="white").pack(pady=(10,5))
entry_user = tk.Entry(frame, font=("Arial", 12), width=30)  # увеличена ширина
entry_user.pack(pady=(0,10))

tk.Label(frame, text="Пароль:", font=("Arial", 13), bg="black", fg="white").pack(pady=(5,5))
entry_pass = tk.Entry(frame, show="*", font=("Arial", 12), width=30)  # увеличена ширина
entry_pass.pack(pady=(0,15))
remember_var = tk.BooleanVar(value=False)
tk.Checkbutton(
    frame,
    text="Запомнить меня",
    variable=remember_var,
    bg="black",
    fg="white",
    selectcolor="black"
).pack(pady=(0, 15))

# ВАЖНО: вызываем после того, как элементы созданы
load_config()

tk.Button(frame, text="Войти", command=login,
          width=25, height=2, bg="#1e90ff", fg="white").pack(pady=(0,20))

# --- Кнопки в правом нижнем углу ---
btn_update = tk.Button(root, text="Обновить лаунчер", command=update_launcher,
                       width=20, bg="#28a745", fg="white")
btn_update.place(relx=1.0, rely=1.0, x=-10, y=-45, anchor="se")

btn_options = tk.Button(root, text="Опции", command=open_options,
                        width=20, bg="#ffa500", fg="white")
btn_options.place(relx=1.0, rely=1.0, x=-10, y=-10, anchor="se")

root.mainloop()
