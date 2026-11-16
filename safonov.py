import asyncio
import json
import os
from datetime import datetime, timezone, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.filters.callback_data import CallbackData

# ==================== НАСТРОЙКИ ====================
BOT_TOKEN = "9135870925:AAHzYaEomgvs2OxvGgIJxHr6Pd0TkXV7z9Q"
DATA_FILE = "safonov_data.json"
TZ = timezone(timedelta(hours=7))  # МСК+4
# ===================================================

class CB(CallbackData, prefix="saf"):
    action: str
    value: str = ""

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

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

def main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Общий список", callback_data=CB(action="all").pack())],
        [InlineKeyboardButton(text="🛒 Список покупок", callback_data=CB(action="shop").pack()),
         InlineKeyboardButton(text="🔧 Список поломок", callback_data=CB(action="broken").pack())],
        [InlineKeyboardButton(text="➕ Добавить покупку", callback_data=CB(action="add_shop").pack()),
         InlineKeyboardButton(text="➕ Сообщить о поломке", callback_data=CB(action="add_broken").pack())],
    ])

def list_keyboard(kind):
    mark = "✅ Отметить купленное" if kind == "shop" else "✅ Отметить починенное"
    act = "mark_shop" if kind == "shop" else "mark_broken"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=mark, callback_data=CB(action=act).pack())],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data=CB(action="main").pack())],
    ])

def mark_keyboard(kind, items):
    kb, row = [], []
    for it in items:
        row.append(InlineKeyboardButton(text=it["name"], callback_data=CB(action=kind, value=it["name"]).pack()))
        if len(row) == 2:
            kb.append(row); row = []
    if row: kb.append(row)
    kb.append([InlineKeyboardButton(text="⬅️ В главное меню", callback_data=CB(action="main").pack())])
    return InlineKeyboardMarkup(inline_keyboard=kb)

def main_text():
    return "🛠 **Панель закупок и поломок**\nВыберите действие:"

def format_list(kind):
    if kind == "all":
        t = "📋 **Общий список**\n\n🛒 **КУПИТЬ:**\n"
        t += "\n".join(f"{i}. {it['name']}" for i, it in enumerate(data["shopping"], 1)) or "_пусто_"
        t += "\n\n🔧 **ПОЧИНИТЬ:**\n"
        t += "\n".join(f"{i}. {it['name']} (сообщил {it['user']}, {it['time']})" for i, it in enumerate(data["broken"], 1)) or "_пусто_"
        return t
    elif kind == "shop":
        t = "🛒 **Список покупок**\n\n"
        return t + ("\n".join(f"{i}. {it['name']}" for i, it in enumerate(data["shopping"], 1)) if data["shopping"] else "_Список пуст._")
    else:
        t = "🔧 **Список поломок**\n\n"
        return t + ("\n".join(f"{i}. {it['name']} (сообщил {it['user']}, {it['time']})" for i, it in enumerate(data["broken"], 1)) if data["broken"] else "_Список пуст._")

@dp.message(Command("panel"))
@dp.message(Command("start"))
async def cmd_panel(message: Message):
    await message.answer(main_text(), reply_markup=main_keyboard(), parse_mode="Markdown")

@dp.callback_query(CB.filter(F.action == "main"))
async def go_main(call: CallbackQuery):
    try: await call.message.delete()
    except Exception: pass
    await call.message.answer(main_text(), reply_markup=main_keyboard(), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(CB.filter(F.action == "all"))
async def show_all(call: CallbackQuery):
    await call.message.edit_text(format_list("all"), reply_markup=InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Отметить купленное", callback_data=CB(action="mark_shop").pack())],
        [InlineKeyboardButton(text="✅ Отметить починенное", callback_data=CB(action="mark_broken").pack())],
        [InlineKeyboardButton(text="⬅️ В главное меню", callback_data=CB(action="main").pack())],
    ]), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(CB.filter(F.action == "shop"))
async def show_shop(call: CallbackQuery):
    await call.message.edit_text(format_list("shop"), reply_markup=list_keyboard("shop"), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(CB.filter(F.action == "broken"))
async def show_broken(call: CallbackQuery):
    await call.message.edit_text(format_list("broken"), reply_markup=list_keyboard("broken"), parse_mode="Markdown")
    await call.answer()

@dp.callback_query(CB.filter(F.action == "add_shop"))
async def ask_add_shop(call: CallbackQuery):
    msg = await call.message.answer("✍️ Напишите, что нужно купить, одним сообщением:")
    pending[call.from_user.id] = {"type": "shop", "prompt_msg_id": msg.message_id, "chat_id": call.message.chat.id, "panel_msg_id": call.message.message_id}
    await call.answer()

@dp.callback_query(CB.filter(F.action == "add_broken"))
async def ask_add_broken(call: CallbackQuery):
    msg = await call.message.answer("✍️ Напишите, что сломалось, одним сообщением:")
    pending[call.from_user.id] = {"type": "broken", "prompt_msg_id": msg.message_id, "chat_id": call.message.chat.id, "panel_msg_id": call.message.message_id}
    await call.answer()

@dp.message(F.text)
async def save_input(message: Message):
    p = pending.pop(message.from_user.id, None)
    if not p: return
    try: await bot.delete_message(p["chat_id"], p["prompt_msg_id"])
    except Exception: pass
    try: await message.delete()
    except Exception: pass
    try: await bot.delete_message(p["chat_id"], p["panel_msg_id"])
    except Exception: pass

    user = message.from_user
    user_name = f"@{user.username}" if user.username else user.full_name
    now = datetime.now(TZ).strftime("%d.%m.%y")
    text = message.text.strip()
    if not text: return

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
    try: await confirm.delete()
    except Exception: pass

@dp.callback_query(CB.filter(F.action == "mark_shop"))
async def ask_mark_shop(call: CallbackQuery):
    if not data["shopping"]:
        await call.answer("Список покупок пуст.", show_alert=True); return
    await call.message.edit_text("Выберите, что куплено:", reply_markup=mark_keyboard("buy", data["shopping"]))
    await call.answer()

@dp.callback_query(CB.filter(F.action == "buy"))
async def mark_bought(call: CallbackQuery, callback_data: CB):
    name = callback_data.value
    found = next((it for it in data["shopping"] if it["name"] == name), None)
    if not found:
        await call.answer("Позиция не найдена.", show_alert=True); return
    data["shopping"].remove(found)
    found["bought_by"] = f"@{call.from_user.username}" if call.from_user.username else call.from_user.full_name
    found["bought_at"] = datetime.now(TZ).strftime("%d.%m.%y %H:%M")
    data["bought"].append(found); save_data(data)
    await call.answer(f"«{name}» отмечено как купленное")
    try: await call.message.delete()
    except Exception: pass
    await call.message.answer(main_text(), reply_markup=main_keyboard(), parse_mode="Markdown")

@dp.callback_query(CB.filter(F.action == "mark_broken"))
async def ask_mark_broken(call: CallbackQuery):
    if not data["broken"]:
        await call.answer("Список поломок пуст.", show_alert=True); return
    await call.message.edit_text("Выберите, что починено:", reply_markup=mark_keyboard("fix", data["broken"]))
    await call.answer()

@dp.callback_query(CB.filter(F.action == "fix"))
async def mark_fixed(call: CallbackQuery, callback_data: CB):
    name = callback_data.value
    found = next((it for it in data["broken"] if it["name"] == name), None)
    if not found:
        await call.answer("Позиция не найдена.", show_alert=True); return
    data["broken"].remove(found)
    found["fixed_by"] = f"@{call.from_user.username}" if call.from_user.username else call.from_user.full_name
    found["fixed_at"] = datetime.now(TZ).strftime("%d.%m.%y %H:%M")
    data["fixed"].append(found); save_data(data)
    await call.answer(f"«{name}» отмечено как починенное")
    try: await call.message.delete()
    except Exception: pass
    await call.message.answer(main_text(), reply_markup=main_keyboard(), parse_mode="Markdown")

async def main():
    print("Бот «Сафонов» запущен.")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query"])

if __name__ == "__main__":
    asyncio.run(main())
