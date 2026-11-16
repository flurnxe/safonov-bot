import asyncio
import json
import os
import logging
from datetime import datetime, timezone, timedelta

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "9135870925:AAF2l37IPIux38HJbSZxgmwwX_rxNQkASM4"

DATA_FILE = "safonov_data.json"
TZ = timezone(timedelta(hours=7))  # МСК+4
# ===================================================

logging.basicConfig(level=logging.INFO)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(disable_notification=True)
)
dp = Dispatcher()

# ---------- Хранилище ----------
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"shopping": [], "broken": [], "bought": [], "fixed": []}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

data = load_data()
pending = {}

# ---------- Клавиатуры ----------
def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Общий список", callback_data="all")],
        [InlineKeyboardButton(text="🛒 Добавить покупку", callback_data="add_shop")],
        [InlineKeyboardButton(text="🔧 Сообщить о поломке", callback_data="add_broken")],
    ])

def list_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Куплено", callback_data="mark_shop"),
         InlineKeyboardButton(text="✅ Починено", callback_data="mark_broken")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main")],
    ])

def mark_keyboard(kind, items):
    kb, row = [], []
    for it in items:
        row.append(InlineKeyboardButton(text=f"• {it['name']}", callback_data=f"{kind}:{it['name']}"))
        if len(row) == 2:
            kb.append(row); row = []
    if row: kb.append(row)
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="main")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def cancel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="cancel_add")],
    ])

def main_text():
    return "🛠 **Сафонов** — закупки и поломки\n\nВыберите действие:"

def format_all():
    t = "📋 **ОБЩИЙ СПИСОК**\n━━━━━━━━━━━━━━━\n\n"
    t += "🛒 **КУПИТЬ:**\n"
    t += "\n".join(f"{i}. {it['name']}" for i, it in enumerate(data["shopping"], 1)) or "_пусто_"
    t += "\n\n🔧 **ПОЧИНИТЬ:**\n"
    t += "\n".join(f"{i}. {it['name']} (сообщил {it['user']}, {it['time']})" for i, it in enumerate(data["broken"], 1)) or "_пусто_"
    return t

# ---------- Хэндлеры ----------
@dp.message(Command("panel"))
@dp.message(Command("start"))
async def cmd_panel(message: Message):
    await message.answer(main_text(), reply_markup=main_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "main")
async def go_main(call: CallbackQuery):
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer(main_text(), reply_markup=main_keyboard(), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "all")
async def show_all(call: CallbackQuery):
    await call.message.edit_text(format_all(), reply_markup=list_keyboard(), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data == "add_shop")
async def ask_add_shop(call: CallbackQuery):
    msg = await call.message.answer(
        "✍️ **Напишите название** одним сообщением:\n_например: салфетки_",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown"
    )
    pending[call.from_user.id] = {"type": "shop", "prompt_msg_id": msg.message_id, "chat_id": call.message.chat.id, "panel_msg_id": call.message.message_id}
    await call.answer()

@dp.callback_query(F.data == "add_broken")
async def ask_add_broken(call: CallbackQuery):
    msg = await call.message.answer(
        "✍️ **Напишите, что сломалось** одним сообщением:\n_например: колонка_",
        reply_markup=cancel_keyboard(),
        parse_mode="Markdown"
    )
    pending[call.from_user.id] = {"type": "broken", "prompt_msg_id": msg.message_id, "chat_id": call.message.chat.id, "panel_msg_id": call.message.message_id}
    await call.answer()

@dp.callback_query(F.data == "cancel_add")
async def cancel_add(call: CallbackQuery):
    p = pending.pop(call.from_user.id, None)
    if p:
        try:
            await bot.delete_message(p["chat_id"], p["prompt_msg_id"])
        except Exception:
            pass
        try:
            await bot.delete_message(p["chat_id"], p["panel_msg_id"])
        except Exception:
            pass
    await call.message.answer(main_text(), reply_markup=main_keyboard(), parse_mode="Markdown")
    await call.answer()

@dp.message(F.text)
async def save_input(message: Message):
    p = pending.pop(message.from_user.id, None)
    if not p:
        return
    try:
        await bot.delete_message(p["chat_id"], p["prompt_msg_id"])
    except Exception:
        pass
    try:
        await message.delete()
    except Exception:
        pass
    try:
        await bot.delete_message(p["chat_id"], p["panel_msg_id"])
    except Exception:
        pass

    user = message.from_user
    user_name = f"@{user.username}" if user.username else user.full_name
    now = datetime.now(TZ).strftime("%d.%m.%y")
    text = message.text.strip()
    if not text:
        return

    if p["type"] == "shop":
        data["shopping"].append({"name": text, "user": user_name, "time": now})
        confirm_text = f"✅ «{text}» добавлено в список покупок"
    else:
        data["broken"].append({"name": text, "user": user_name, "time": now})
        confirm_text = f"✅ «{text}» добавлено в список поломок"
    save_data(data)

    confirm = await message.answer(confirm_text)
    await message.answer(main_text(), reply_markup=main_keyboard(), parse_mode="Markdown")
    await asyncio.sleep(3)
    try:
        await confirm.delete()
    except Exception:
        pass

@dp.callback_query(F.data == "mark_shop")
async def ask_mark_shop(call: CallbackQuery):
    if not data["shopping"]:
        await call.answer("Список покупок пуст.", show_alert=True)
        return
    await call.message.edit_text("✅ **Что куплено?**", reply_markup=mark_keyboard("buy", data["shopping"]), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data.startswith("buy:"))
async def mark_bought(call: CallbackQuery):
    name = call.data.split(":", 1)[1]
    found = next((it for it in data["shopping"] if it["name"] == name), None)
    if not found:
        await call.answer("Позиция не найдена.", show_alert=True)
        return
    data["shopping"].remove(found)
    found["bought_by"] = f"@{call.from_user.username}" if call.from_user.username else call.from_user.full_name
    found["bought_at"] = datetime.now(TZ).strftime("%d.%m.%y %H:%M")
    data["bought"].append(found)
    save_data(data)
    await call.answer(f"«{name}» отмечено как купленное")
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer(main_text(), reply_markup=main_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "mark_broken")
async def ask_mark_broken(call: CallbackQuery):
    if not data["broken"]:
        await call.answer("Список поломок пуст.", show_alert=True)
        return
    await call.message.edit_text("✅ **Что починено?**", reply_markup=mark_keyboard("fix", data["broken"]), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(F.data.startswith("fix:"))
async def mark_fixed(call: CallbackQuery):
    name = call.data.split(":", 1)[1]
    found = next((it for it in data["broken"] if it["name"] == name), None)
    if not found:
        await call.answer("Позиция не найдена.", show_alert=True)
        return
    data["broken"].remove(found)
    found["fixed_by"] = f"@{call.from_user.username}" if call.from_user.username else call.from_user.full_name
    found["fixed_at"] = datetime.now(TZ).strftime("%d.%m.%y %H:%M")
    data["fixed"].append(found)
    save_data(data)
    await call.answer(f"«{name}» отмечено как починенное")
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer(main_text(), reply_markup=main_keyboard(), parse_mode="Markdown")

# ---------- Запуск ----------
async def main():
    print("Бот «Сафонов» запущен.")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    asyncio.run(main())
