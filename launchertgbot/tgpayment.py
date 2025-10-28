# ===================== BOT.PY ===================== #
import asyncio
import aiohttp
import requests
import re
import logging
from aiogram import Bot, Dispatcher, Router, types, F

logging.basicConfig(level=logging.INFO)

TOKEN = ""
ADMIN_KEY = "ebubabulus"

# загружаем API base с GitHub
def get_api_base():
    try:
        resp = requests.get("https://raw.githubusercontent.com/kol49/rtkapi/main/url.json")
        if resp.status_code == 200:
            return resp.json().get("url", "")
    except Exception as e:
        print("⚠ Ошибка загрузки API:", e)
    return ""

API_BASE = get_api_base()
print("✅ API_BASE =", API_BASE)

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)
user_state = {}

session = None  # глобальная aiohttp сессия, создаётся в main()

def is_valid(txt):
    return re.fullmatch(r"[A-Za-z0-9]+", txt) is not None

@router.message(F.text == "/start")
async def start(msg: types.Message):
    kb = types.ReplyKeyboardMarkup(
        keyboard=[[types.KeyboardButton(text="Купить аккаунт ($1 ≈ 40₴)")]],
        resize_keyboard=True
    )
    await msg.answer("👋 Привет! Хочешь аккаунт для RTK-лаунчера всего за $1 (≈40₴)?", reply_markup=kb)


@router.message(F.text == "Купить аккаунт ($1 ≈ 40₴)")
async def buy(msg: types.Message):
    user_state[msg.chat.id] = {"step": "set_username"}
    await msg.answer("✍ Введите ник (латиница/цифры):")


@router.message()
async def handle(msg: types.Message):
    global session
    state = user_state.get(msg.chat.id, {})
    step = state.get("step")

    text = msg.text.strip()

    # -------------------- Шаг 1: Ввод ника --------------------
    if step == "set_username":
        if len(text) < 3 or not is_valid(text):
            await msg.answer("❌ Некорректный ник.")
            return

        # Проверяем, существует ли ник
        try:
            r = await session.get(f"{API_BASE}/api/admin/users?admin_key={ADMIN_KEY}")
            data = await r.json()
            existing_users = data.get("users", [])
        except Exception as e:
            await msg.answer(f"⚠ Ошибка проверки ника: {e}")
            return

        if text in existing_users:
            await msg.answer("❌ Этот ник уже существует. Попробуйте другой.")
            return

        state["username"] = text
        state["step"] = "set_password"
        await msg.answer("🔑 Введите пароль (латиница/цифры, минимум 6 символов):")

    # -------------------- Шаг 2: Ввод пароля --------------------
    elif step == "set_password":
        if len(text) < 6 or not is_valid(text):
            await msg.answer("❌ Некорректный пароль.")
            return
        state["password"] = text
        state["step"] = "choose_payment"

        kb = types.ReplyKeyboardMarkup(
            keyboard=[
                [types.KeyboardButton(text="Оплатить через Monobank (40₴)")],
                [types.KeyboardButton(text="Оплатить через YooMoney (100₽)")],
                [types.KeyboardButton(text="Оплатить через USDT (≈$1)")]
            ],
            resize_keyboard=True
        )
        await msg.answer("💰 Выберите способ оплаты:", reply_markup=kb)

    # -------------------- Шаг 3: Выбор Monobank --------------------
    elif step == "choose_payment" and "Monobank" in text:
        state["step"] = "set_card"
        await msg.answer("💳 Введите последние 4 цифры карты:")

    elif step == "set_card":
        if not text.isdigit() or len(text) < 4:
            await msg.answer("❌ Нужно хотя бы 4 цифры.")
            return
        state["payer_card"] = text[-4:]
        state["step"] = "waiting_payment"

        # Создаём заказ
        try:
            r = await session.post(f"{API_BASE}/api/create_order", json={
                "chat_id": msg.chat.id,
                "method": "monobank",
                "username": state["username"],
                "password": state["password"],
                "payer_card": state["payer_card"]
            })
            d = await r.json()
        except Exception as e:
            await msg.answer(f"⚠ Ошибка создания заказа: {e}")
            return

        if not d.get("success"):
            await msg.answer("⚠ Ошибка создания заказа.")
            return

        order_id = d["order_id"]
        state["order_id"] = order_id

        kb = types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="✅ Я оплатил")]],
            resize_keyboard=True
        )
        await msg.answer(
            f"💳 Переведите 40₴ на карту <b>4441111144245713</b>\n"
            f"В комментарии укажите <code>order_id: {order_id}</code>\n\n"
            f"ВАЖНО! В комментарии должен быть полностью указан с припиской, например: order_id: xxxxxxxxxx\n\n"
            f"После оплаты нажмите кнопку ниже 👇",
            reply_markup=kb,
            parse_mode="HTML"
        )

    # -------------------- Шаг 3: Выбор YooMoney --------------------
    elif step == "choose_payment" and "YooMoney" in text:
        state["method"] = "yoomoney"
        state["step"] = "waiting_yoomoney"

        try:
            r = await session.post(f"{API_BASE}/api/create_order", json={
                "chat_id": msg.chat.id,
                "method": "yoomoney",
                "username": state["username"],
                "password": state["password"],
                "payer_card": None
            })
            d = await r.json()
        except Exception as e:
            await msg.answer(f"⚠ Ошибка создания заказа: {e}")
            return

        if not d.get("success"):
            await msg.answer("⚠ Ошибка создания заказа.")
            return

        order_id = d["order_id"]
        state["order_id"] = order_id

        kb = types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="✅ Я оплатил")]],
            resize_keyboard=True
        )
        YOOMONEY_WALLET = "4100119354176020"
        await msg.answer(
            f"💳 Отправьте 100₽ на кошелёк <code>{YOOMONEY_WALLET}</code>\n"
            f"В комментарии укажите <code>order_id: {order_id}</code>\n\n"
            f"ВАЖНО! В комментарии должен быть полностью указан с припиской, например: order_id: xxxxxxxxxx\n\n"
            f"После оплаты нажмите кнопку ниже 👇",
            reply_markup=kb,
            parse_mode="HTML"
        )
        # -------------------- Шаг 3: Выбор USDT --------------------
    elif step == "choose_payment" and "USDT" in text:
        state["method"] = "usdt"
        state["step"] = "waiting_usdt"

        try:
            r = await session.post(f"{API_BASE}/api/create_order", json={
                "chat_id": msg.chat.id,
                "method": "usdt",
                "username": state["username"],
                "password": state["password"],
                "payer_card": None
            })
            d = await r.json()
        except Exception as e:
            await msg.answer(f"⚠ Ошибка создания заказа: {e}")
            return

        if not d.get("success"):
            await msg.answer("⚠ Ошибка создания заказа.")
            return

        order_id = d["order_id"]
        state["order_id"] = order_id

        USDT_WALLET = "TGcFLyXRperjx1GTS1yTw75xYsP7bN8cay"  # 👈 твой TRC20-кошелёк

        kb = types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="✅ Я оплатил")]],
            resize_keyboard=True
        )
        await msg.answer(
            f"💰 Отправьте <b>1 USDT (TRC20)</b> на адрес:\n"
            f"<code>{USDT_WALLET}</code>\n\n"
            f"⚠ В комментарии к переводу (Memo) укажите:\n"
            f"<code>order_id: {order_id}</code>\n\n"
            f"После оплаты нажмите кнопку ниже 👇",
            reply_markup=kb,
            parse_mode="HTML"
        )

    # -------------------- Проверка оплаты Monobank --------------------
    elif step == "waiting_payment" and "оплатил" in text.lower():
        try:
            r = await session.get(f"{API_BASE}/api/check_orders")
            data = await r.json()
        except Exception as e:
            await msg.answer(f"⚠ Ошибка проверки оплаты: {e}")
            return

        found = False
        for o in data.get("orders", []):
            if str(o.get("order_id")) == str(state.get("order_id")) and o.get("status") == "paid":
                resp = await session.post(f"{API_BASE}/api/register", json={
                    "username": state["username"],
                    "password": state["password"],
                    "admin_key": ADMIN_KEY
                })
                d = await resp.json()
                if d.get("success"):
                    await msg.answer(
                        f"✅ Оплата получена! Аккаунт `{state['username']}` активирован.",
                        parse_mode="Markdown"
                    )
                    user_state.pop(msg.chat.id, None)
                    found = True
                else:
                    await msg.answer("⚠ Ошибка регистрации после оплаты.")
                break

        if not found:
            await msg.answer("⏳ Оплата пока не найдена, попробуйте через минуту.")

    # -------------------- Проверка оплаты YooMoney --------------------
    elif step == "waiting_yoomoney" and "оплатил" in text.lower():
        try:
            r = await session.get(f"{API_BASE}/api/check_yoomoney")
            data = await r.json()
        except Exception as e:
            await msg.answer(f"⚠ Ошибка проверки оплаты: {e}")
            return

        found = False
        for o in data.get("orders", []):
            if str(o.get("order_id")) == str(state.get("order_id")) and o.get("status") == "paid":
                resp = await session.post(f"{API_BASE}/api/register", json={
                    "username": state["username"],
                    "password": state["password"],
                    "admin_key": ADMIN_KEY
                })
                d = await resp.json()
                if d.get("success"):
                    await msg.answer(
                        f"✅ Оплата получена! Аккаунт `{state['username']}` активирован.",
                        parse_mode="Markdown"
                    )
                    user_state.pop(msg.chat.id, None)
                    found = True
                else:
                    await msg.answer("⚠ Ошибка регистрации после оплаты.")
                break

        if not found:
            await msg.answer("⏳ Оплата пока не найдена, попробуйте через минуту.")
 # -------------------- Шаг 3: Выбор USDT --------------------
    elif step == "choose_payment" and "USDT" in text:
        state["method"] = "usdt"
        state["step"] = "waiting_usdt"

        try:
            r = await session.post(f"{API_BASE}/api/create_order", json={
                "chat_id": msg.chat.id,
                "method": "usdt",
                "username": state["username"],
                "password": state["password"],
                "payer_card": None
            })
            d = await r.json()
        except Exception as e:
            await msg.answer(f"⚠ Ошибка создания заказа: {e}")
            return

        if not d.get("success"):
            await msg.answer("⚠ Ошибка создания заказа.")
            return

        order_id = d["order_id"]
        state["order_id"] = order_id

        USDT_WALLET = "TDW1mRqz8zwo12345abcdEfghijkLmnoPQ"  # 👈 твой TRC20-кошелёк

        kb = types.ReplyKeyboardMarkup(
            keyboard=[[types.KeyboardButton(text="✅ Я оплатил")]],
            resize_keyboard=True
        )
        await msg.answer(
            f"💰 Отправьте <b>1 USDT (TRC20)</b> на адрес:\n"
            f"<code>{USDT_WALLET}</code>\n\n"
            f"⚠ В комментарии к переводу (Memo) укажите:\n"
            f"<code>order_id: {order_id}</code>\n\n"
            f"После оплаты нажмите кнопку ниже 👇",
            reply_markup=kb,
            parse_mode="HTML"
        )
   # -------------------- Проверка оплаты USDT --------------------
    elif step == "waiting_usdt" and "оплатил" in text.lower():
        try:
            r = await session.get(f"{API_BASE}/api/check_usdt")
            data = await r.json()
        except Exception as e:
            await msg.answer(f"⚠ Ошибка проверки оплаты: {e}")
            return

        found = False
        for o in data.get("orders", []):
            if str(o.get("order_id")) == str(state.get("order_id")) and o.get("status") == "paid":
                resp = await session.post(f"{API_BASE}/api/register", json={
                    "username": state["username"],
                    "password": state["password"],
                    "admin_key": ADMIN_KEY
                })
                d = await resp.json()
                if d.get("success"):
                    await msg.answer(
                        f"✅ Оплата USDT получена! Аккаунт `{state['username']}` активирован.",
                        parse_mode="Markdown"
                    )
                    user_state.pop(msg.chat.id, None)
                    found = True
                else:
                    await msg.answer("⚠ Ошибка регистрации после оплаты.")
                break

        if not found:
            await msg.answer("⏳ Платёж пока не найден, попробуйте через минуту.")


async def main():
    global session
    session = aiohttp.ClientSession()  # создаём сессию внутри async
    try:
        await dp.start_polling(bot)
    finally:
        await session.close()  # закрываем сессию при завершении


if __name__ == "__main__":
    asyncio.run(main())
