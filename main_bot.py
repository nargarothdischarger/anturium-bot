import os
import telebot
from services import SERVICES, CATEGORIES
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

TOKEN = os.getenv("BOT_TOKEN", "8783413296:AAHS8pTPF-2SxJKPUpljdq7KNx3H0IC9zLk")
bot = telebot.TeleBot(TOKEN)

cart_storage = {}  # user_id - список id услуг
MANAGER_CHAT_ID = -1004359178319
booking_draft = {}  # user_id -> {"fio": ..., "phone": ..., "birth": ...}

def main_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row(KeyboardButton("🏥 Услуги"), KeyboardButton("🛒 Корзина"))
    kb.row(KeyboardButton("📝 Записаться"))
    return kb

@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        "🏥 *Больница Антуриум* (г. Барнаул)\n\n"
        "Выберите действие в меню снизу 👇",
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

@bot.message_handler(commands=['services'])
def services(message):
    kb = InlineKeyboardMarkup()
    for key, name in CATEGORIES.items():
        kb.add(InlineKeyboardButton(name, callback_data=f"cat_{key}"))
    bot.send_message(message.chat.id, "Выберите категорию:", reply_markup=kb)

@bot.message_handler(commands=['cart'])
def cart(message):
    uid = message.from_user.id
    if uid not in cart_storage or not cart_storage[uid]:
        bot.send_message(message.chat.id, "Корзина пуста.")
        return

    total = 0
    text = "🛒 *Ваша корзина:*\n"
    for svc_id in cart_storage[uid]:
        svc = next(s for s in SERVICES if s["id"] == svc_id)
        text += f"• {svc['title']} - {svc['price']}₽\n"
        total += svc["price"]
    text += f"\n*Итого: {total}₽*"

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🗑 Очистить корзину", callback_data="cart_clear"))

    bot.send_message(message.chat.id, text, parse_mode="Markdown", reply_markup=kb)

@bot.message_handler(commands=['book'])
def book_start(message):
    uid = message.from_user.id
    if uid not in cart_storage or not cart_storage[uid]:
        bot.send_message(
            message.chat.id,
            "Корзина пуста. Сначала выберите услуги через /services"
        )
        return

    booking_draft[uid] = {}
    bot.send_message(
        message.chat.id,
        "Введите ваше **ФИО**:\n\n_Чтобы отменить, напишите: Отмена_",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(message, get_fio)

def cancel_booking(uid, chat_id):
    if uid in booking_draft:
        del booking_draft[uid]
    bot.send_message(chat_id, "❌ Запись отменена.", reply_markup=main_keyboard())

def get_fio(message):
    uid = message.from_user.id
    if uid not in booking_draft:
        return
    text = message.text.strip().lower()
    if text in ["отмена", "/cancel"]:
        cancel_booking(uid, message.chat.id)
        return

    fio = message.text.strip()
    if len(fio.split()) < 2:
        bot.send_message(
            message.chat.id,
            "Введите ФИО полностью (минимум 2 слова):\n\n_Чтобы отменить, напишите: Отмена_",
            parse_mode="Markdown"
        )
        bot.register_next_step_handler(message, get_fio)
        return

    booking_draft[uid]["fio"] = fio
    bot.send_message(
        message.chat.id,
        "Введите **номер телефона** (например: +7-999-123-45-67):\n\n_Чтобы отменить, напишите: Отмена_",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(message, get_phone)

def get_phone(message):
    uid = message.from_user.id
    if uid not in booking_draft:
        return
    text = message.text.strip().lower()
    if text in ["отмена", "/cancel"]:
        cancel_booking(uid, message.chat.id)
        return

    phone = message.text.strip()
    booking_draft[uid]["phone"] = phone
    bot.send_message(
        message.chat.id,
        "Введите **дату рождения** (например: 15.03.1990):\n\n_Чтобы отменить, напишите: Отмена_",
        parse_mode="Markdown"
    )
    bot.register_next_step_handler(message, get_birth)

def get_birth(message):
    uid = message.from_user.id
    if uid not in booking_draft:
        return
    text = message.text.strip().lower()
    if text in ["отмена", "/cancel"]:
        cancel_booking(uid, message.chat.id)
        return

    birth = message.text.strip()
    booking_draft[uid]["birth"] = birth

    svc_list = ""
    total = 0
    for svc_id in cart_storage[uid]:
        svc = next(s for s in SERVICES if s["id"] == svc_id)
        svc_list += f"• {svc['title']} - {svc['price']}₽\n"
        total += svc["price"]

    draft = booking_draft[uid]
    msg_to_manager = (
        f"📩 *Новая заявка!*\n\n"
        f"*Услуги:*\n{svc_list}"
        f"*Сумма:* {total}₽\n\n"
        f"*ФИО:* {draft['fio']}\n"
        f"*Телефон:* {draft['phone']}\n"
        f"*Дата рождения:* {draft['birth']}"
    )

    try:
        bot.send_message(MANAGER_CHAT_ID, msg_to_manager, parse_mode="Markdown")
    except Exception as e:
        print(f"Ошибка отправки менеджеру: {e}")

    bot.send_message(
        message.chat.id,
        "✅ *Заявка принята!*\n\n"
        "Скоро с вами свяжется консультант, ожидайте звонка в течение 5 минут.",
        parse_mode="Markdown"
    )

    cart_storage[uid] = []
    del booking_draft[uid]

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    data = call.data

    if data == "cart_clear":
        uid = call.from_user.id
        cart_storage[uid] = []
        bot.answer_callback_query(call.id, "Корзина очищена")
        bot.edit_message_text("Корзина пуста.", call.message.chat.id, call.message.id)

    elif data.startswith("cat_"):
        cat_key = data[4:]
        kb = InlineKeyboardMarkup()
        for s in SERVICES:
            if s["cat"] == cat_key:
                btn_text = f"{s['title']} - {s['price']}₽"
                kb.add(InlineKeyboardButton(btn_text, callback_data=f"svc_{s['id']}"))
        kb.add(InlineKeyboardButton("<< Назад", callback_data="back_services"))
        bot.edit_message_text(
            CATEGORIES[cat_key],
            call.message.chat.id,
            call.message.id,
            reply_markup=kb
        )

    elif data.startswith("svc_"):
        svc_id = int(data[4:])
        uid = call.from_user.id

        if uid not in cart_storage:
            cart_storage[uid] = []

        if svc_id in cart_storage[uid]:
            cart_storage[uid].remove(svc_id)
            bot.answer_callback_query(call.id, "Удалено из корзины")
        else:
            cart_storage[uid].append(svc_id)
            bot.answer_callback_query(call.id, "Добавлено в корзину")

    elif data == "back_services":
        kb = InlineKeyboardMarkup()
        for key, name in CATEGORIES.items():
            kb.add(InlineKeyboardButton(name, callback_data=f"cat_{key}"))
        bot.edit_message_text(
            "Выберите категорию:",
            call.message.chat.id,
            call.message.id,
            reply_markup=kb
        )
@bot.message_handler(func=lambda m: m.text in ["🏥 Услуги", "🛒 Корзина", "📝 Записаться"])
def menu_buttons(message):
    if message.text == "🏥 Услуги":
        services(message)
    elif message.text == "🛒 Корзина":
        cart(message)
    elif message.text == "📝 Записаться":
        book_start(message)

bot.polling(non_stop=True)