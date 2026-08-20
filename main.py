import asyncio
import logging
import os
import sys
from aiogram import Bot, Dispatcher, html, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# Созламаларни улаймиз
import config

# Логларни ёқиш
logging.basicConfig(level=logging.INFO, stream=sys.stdout)

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

# Админ панел учун ҳолатлар
class AdminStates(StatesGroup):
    add_channel_name = State()
    add_channel_url = State()
    add_channel_id = State()

# Мажбурий обунани текшириш функцияси
async def check_subscriptions(user_id: int) -> bool:
    for channel in config.CHANNELS:
        try:
            member = await bot.get_chat_member(chat_id=channel["id"], user_id=user_id)
            if member.status in ["left", "kicked"]:
                return False
        except Exception:
            # Агар бот каналда админ бўлмаса, текширишни ўтказиб юборади
            continue
    return True

# Фойдаланувчи учун асосий тугмалар
def get_main_keyboard(user_id: int):
    kb = [
        [KeyboardButton(text="🎬 Фильмни таржима қилиш"), KeyboardButton(text="💎 VIP Статус")]
    ]
    if user_id == config.ADMIN_ID:
        kb.append([KeyboardButton(text="⚙️ Админ Панель")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# Каналларга аъзо бўлиш тугмачалари
def get_sub_keyboard():
    buttons = []
    for channel in config.CHANNELS:
        buttons.append([InlineKeyboardButton(text=f"👉 {channel['name']} аъзо бўлиш", url=channel['url'])])
    buttons.append([InlineKeyboardButton(text="✅ Обунани текшириш", callback_data="check_sub")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

@dp.message(CommandStart())
async def command_start_handler(message: Message):
    is_subbed = await check_subscriptions(message.from_user.id)
    if not is_subbed:
        await message.answer(
            f"👋 Салом, {html.bold(message.from_user.full_name)}!\n\n"
            "Ботдан фойдаланиш учун қуйидаги ҳомий каналларимизга аъзо бўлишингиз шарт:",
            reply_markup=get_sub_keyboard()
        )
    else:
        await message.answer(
            f"👋 Салом, {html.bold(message.from_user.full_name)}!\n"
            "ИИ Кино-Таржимон ботига хуш келибсиз. Менга видео ёки линк юборинг.",
            reply_markup=get_main_keyboard(message.from_user.id)
        )

@dp.callback_query(F.data == "check_sub")
async def callback_check_sub(callback: CallbackQuery):
    is_subbed = await check_subscriptions(callback.from_user.id)
    if is_subbed:
        await callback.message.answer("🎉 Раҳмат! Обуна тасдиқланди. Энди видео юборишингиз мумкин.", 
                                      reply_markup=get_main_keyboard(callback.from_user.id))
        await callback.answer()
    else:
        await callback.answer("❌ Сиз ҳали ҳамма каналларга аъзо бўлмадингиз!", show_alert=True)

# Сунъий интеллект ишлаши ва фоизли кутиш чизиғи (Progress Bar)
async def fake_ai_processing(message: Message, chat_id: int, duration_type: str):
    # Видео узунлигига қараб вақт созланади (5 минутлик тез, узун кино секинроқ)
    steps = [
        ("📥 Видео қабул қилинди. Овозлар ажратилмоқда (Demucs)...", 10),
        ("🧠 Whisper ИИ овозларни матнга ўгирмоқда...", 35),
        ("📝 Матн ўзбек тилига таржима қилинмоқда (NLLB)...", 60),
        ("🎭 Овозлар ажратилиб, ҳиссиёт билан дубляж қилинмоқда (XTTS)...", 85),
        ("🎬 Тайёр аудио оригинал видеога бирлаштирилмоқда...", 95),
        ("✅ Фильм тайёр! Юборилмоқда...", 100)
    ]
    
    speed_modifier = 1 if duration_type == "short" else 5
    
    progress_msg = await message.answer("⏳ Жараён бошланди...\n⬛⬛⬛⬛⬛⬛⬛⬛⬛⬛ 0%")
    
    for text, percent in steps:
        await asyncio.sleep(speed_modifier) # Сервердаги ишлаш вақтини белгилайди
        filled_blocks = percent // 10
        empty_blocks = 10 - filled_blocks
        bar = "⬜" * filled_blocks + "⬛" * empty_blocks
        
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=progress_msg.message_id,
                text=f"{text}\n{bar} {percent}%"
            )
        except Exception:
            pass
            
    await bot.send_message(chat_id, "🎬 Мана сизнинг видеоингиз! (Бу ерига тайёр кино файли уланади)")

@dp.message(F.video | F.document)
async def handle_video(message: Message):
    is_subbed = await check_subscriptions(message.from_user.id)
    if not is_subbed:
        await message.answer("❌ Ботни ишлатишдан олдин каналларга аъзо бўлинг!", reply_markup=get_sub_keyboard())
        return

    # Видео ҳажмини аниқлаймиз (Агар 50 МБ дан кичик бўлса - тез ишлайди, катта бўлса - секин)
    file_size = message.video.file_size if message.video else message.document.file_size
    duration_type = "short" if file_size < 50 * 1024 * 1024 else "long"
    
    await message.answer("🚀 Фильмингиз навбатга қўшилди. Телеграмдан чиқиб кетишингиз мумкин. Тайёр бўлгач, хабар юборамиз.")
    
    # Орқа фонда ишлаш тизими (Фойдаланувчи чиқиб кетса ҳам тўхтамайди)
    asyncio.create_task(fake_ai_processing(message, message.chat.id, duration_type))

# VIP Меню
@dp.message(F.text == "💎 VIP Статус")
async def vip_status(message: Message):
    await message.answer("💎 **VIP Тариф**\n\nVIP тариф орқали сиз фильмларни умуман навбатларсиз ва рекламаларсиз 3 баравар тезроқ таржима қилишингиз мумкин!\n\n💳 Нархи: Ойига 15 000 сўм.\nСотиб олиш учун админга ёзинг: @Eldor_Asadov_1993_yil")

# --- АДМИН ПАНЕЛЬ ---
@dp.message(F.text == "⚙️ Админ Панель")
async def admin_panel(message: Message):
    if message.from_user.id != config.ADMIN_ID:
        return
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Канал қўшиш", callback_data="add_channel")],
        [InlineKeyboardButton(text="📜 Каналлар рўйхати", callback_data="list_channels")]
    ])
    await message.answer("🛠 Админ Панелига хуш келибсиз, Хўжайин. Янги ҳомий канал қўшамизми?", reply_markup=admin_kb)

@dp.callback_query(F.data == "list_channels")
async def list_channels(callback: CallbackQuery):
    if callback.from_user.id != config.ADMIN_ID: return
    if not config.CHANNELS:
        await callback.message.answer("Ҳозирча мажбурий обуна каналлари йўқ.")
        return
    
    text = "📋 **Мажбурий обуна каналлари:**\n\n"
    for i, ch in enumerate(config.CHANNELS, 1):
        text += f"{i}. {ch['name']} (ID: {ch['id']})\n🔗 {ch['url']}\n\n"
    await callback.message.answer(text)
    await callback.answer()

@dp.callback_query(F.data == "add_channel")
async def add_channel_start(callback: CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.ADMIN_ID: return
    await callback.message.answer("Канал номини киритинг (Масалан: Кино олами):")
    await state.set_state(AdminStates.add_channel_name)
    await callback.answer()

@dp.message(AdminStates.add_channel_name)
async def process_ch_name(message: Message, state: FSMContext):
    await state.update_data(name=message.text)
    await message.answer("Канал ҳаволасини (линк) юборинг (Масалан: https://t.me...):")
    await state.set_state(AdminStates.add_channel_url)

@dp.message(AdminStates.add_channel_url)
async def process_ch_url(message: Message, state: FSMContext):
    await state.update_data(url=message.text)
    await message.answer("Каналнинг рақамли ID'сини юборинг (Масалан: -1001234567890). Бот каналда админ бўлиши шарт!")
    await state.set_state(AdminStates.add_channel_id)

@dp.message(AdminStates.add_channel_id)
async def process_ch_id(message: Message, state: FSMContext):
    try:
        ch_id = int(message.text)
        data = await state.get_data()
        
        config.CHANNELS.append({
            "name": data["name"],
            "url": data["url"],
            "id": ch_id
        })
        
        await message.answer("✅ Канал муваффақиятли қўшилди ва мажбурий обунага жойланди!")
        await state.clear()
    except ValueError:
        await message.answer("❌ Хато! ID фақат рақамлардан иборат бўлиши ерак. Қайтадан уриниб кўринг:")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
