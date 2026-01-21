import asyncio
import sqlite3
from datetime import datetime, timedelta
import secrets
import os
import random
import logging
import re
import aiohttp
import time
import psutil 

from flyerapi import Flyer
from aiogram.utils.exceptions import MessageCantBeDeleted
from pyrogram import Client
from aiogram.types import ReplyKeyboardRemove
from aiogram.utils.exceptions import MessageCantBeDeleted, MessageToDeleteNotFound, MessageNotModified
from aiogram.dispatcher.filters.state import State, StatesGroup
from html import escape
from aiogram.utils.exceptions import InvalidQueryID
from aiogram.types import ReplyKeyboardRemove
from aiogram.types import PreCheckoutQuery
from aiogram.utils.exceptions import BotBlocked, ChatNotFound, UserDeactivated, BadRequest
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher.filters import Text
from database import *
from settings import *
from texts import TEXTS

import string
import random

bot = Bot(token=TOKEN, parse_mode='HTML', disable_web_page_preview=True)
dp = Dispatcher(bot, storage=MemoryStorage())

flyer = Flyer(FLYER_API_KEY)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

AVAILABLE_LANGS = ['ru']
BOT_VERSION = "7.0.0"

app = Client(
    "ClientStars",
    api_id=API_I,
    api_hash=API_H,
)

required_for_draw = random.randint(25, 200)
channel_ids = get_channels_db()
admins = ADMIN_IDS

def get_inactive_users(days):
    """Получает список пользователей, которые неактивны указанное количество дней."""
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    target_date = (datetime.now() - timedelta(days=days)).isoformat()
    cursor.execute("SELECT id FROM users WHERE last_click_time <= ?", (target_date,))
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users

async def send_reminder(user_id, days_inactive):
    if days_inactive == 1:
        messages = [
            ("Эй! Ты куда пропал? Задания ждут, звёзды тоже. Давай, загляни в бот!", "Ну ладно, посмотрю 🌟"),
            ("Привет! Тут уже кое-кто звёзды собирает, а ты где? Скорее к нам!", "Я в деле 🚀"),
            ("Не хочешь глянуть новые задания? Они как раз под для тебя!", "Давай гляну 👀"),
            ("Кажется, звёзды начали скучать без тебя. Пора это исправить!", "Иду фармить звёзды 🌠"),
            ("У нас тут движ, а тебя нет! Заходи, а то всё самое интересное пропустишь.", "Что за движ? 🤔"),
            ("Ты ведь не забыл, как классно собирать звёзды? Давай повторим!", "Точно, погнали! ✨"),
            ("Хей! Ты же звёздный профи. Пора возвращаться в игру!", "Ну да, точно я 💪")
        ]
    elif days_inactive == 3:
        messages = [
            ("Три дня? Серьёзно? Ты куда так надолго? Давай уже к заданиям!", "Да-да, иду 🌟"),
            ("А звёзды-то тебя ждут! Вернёшься? Они без тебя никуда.", "Скорее к ним 🚀"),
            ("Три дня без звёзд— это преступление! Срочно исправляем!", "Исправляю 😎"),
            ("Звёзды тут уже всем рассказывают, как они скучают. Вернёшься?", "Окей, захожу 💫"),
            ("Ты бы видел, сколько звёзд тут! А тебя всё нет. Давай скорее.", "Ну теперь точно иду ✨"),
            ("Слушай, тут такие задания подъехали — просто огонь! Заценишь?", "Уговорил 🔥"),
            ("Эх, три дня без звёзд… Возвращайся уже, тут тебя все заждались!", "Вот он я 🌟")
        ]
    elif days_inactive == 7:
        messages = [
            ("Неделя без тебя — это просто кошмар! Давай уже в бот, тут полно дел.", "Захожу, что делать? ✨"),
            ("Ты ведь не забыл про звёзды? Они тут все только о тебе и говорят!", "Как тут без меня? 🌟"),
            ("Семь дней без заданий? Ну ты даёшь! Исправим это прямо сейчас?", "Исправляю 🚀"),
            ("Хей! Неделя — это слишком. Возвращайся, пока тут без тебя всё не развалилось!", "Всё под контролем, иду 💪"),
            ("Неделя отдыха — это круто. Но звёзды сами себя не заработают, ты как?", "Ну ладно, пора работать 🌠"),
            ("Ты уже знаешь, что пора вернуться, верно? Давай, тут все свои!", "Ну, раз свои… ✨"),
            ("Звёзды без тебя уже заскучали. Ты где пропадал? Давай скорее сюда!", "Вернулся! Что нового? 🌟")
        ]
    else:
        messages = [("Ты где пропал? Вернись, звезды ждут!", "Не могу больше ждать, заждались!")]

    message, button_text = random.choice(messages)
    keyboard = InlineKeyboardMarkup(row_width=1)
    button = InlineKeyboardButton(text=button_text, url=f"{LINK_BOT}")
    keyboard.add(button)

    try:
        await bot.send_message(user_id, message, reply_markup=keyboard)
        return True
    except Exception as e:
        print(f"Ошибка при отправке сообщения: {e}")
        return False

async def check_last_click_time():
    for admin in admins:
        """Проверяет активность пользователей и отправляет уведомления только тем, кто неактивен 1, 3 или 7 дней."""
        inactive_days = [7, 3, 1]
        checked_users = set()
        
        inactive_users = {days: get_inactive_users(days) for days in inactive_days}
        total_users = sum(len(users) for users in inactive_users.values())
        
        progress_message = await bot.send_message(admin, "<b>🔍 Проверка активности...</b>", parse_mode="HTML")
        last_message_id = progress_message.message_id
        
        index = 0
        for days in inactive_days:
            for user_id in inactive_users[days]:
                if user_id in checked_users:
                    continue
                
                if await send_reminder(user_id, days):
                    checked_users.add(user_id)
                    index += 1
                
                if index % 285 == 0:
                    percentage = int(index / total_users * 100) if total_users else 100
                    progress_bar = "🟩" * (percentage // 10) + "⬜" * (10 - percentage // 10)
                    new_text = f"<b>📊 Прогресс:</b> {progress_bar} {percentage}%\n👤 Проверено: {index}/{total_users}"
                    
                    try:
                        await bot.delete_message(admin, last_message_id)
                    except:
                        pass
                    
                    progress_message = await bot.send_message(admin, new_text, parse_mode="HTML")
                    last_message_id = progress_message.message_id

                await asyncio.sleep(0.035)
        
        summary = (f"<b>✅ Проверка завершена!</b>\n\n"
                f"👤 Всего пользователей: {total_users}\n"
                f"📅 1 день: {len(inactive_users[1])} потенциальных уведомлений\n"
                f"📅 3 дня: {len(inactive_users[3])} потенциальных уведомлений\n"
                f"📅 7 дней: {len(inactive_users[7])} потенциальных уведомлений")
        
        await bot.send_message(admin, summary, parse_mode="HTML")

async def periodic_check():
    """Запускает проверку активности каждые 12 часов."""
    while True:
        await check_last_click_time()
        await asyncio.sleep(12 * 60 * 60)

async def on_start():
    asyncio.create_task(periodic_check())

@dp.message_handler(commands=['ac'])
async def manual_check(message: types.Message):
    if message.from_user.id in ADMIN_IDS:
        await check_last_click_time()
        await message.answer("Проверка активности пользователей выполнена.")
    else:
        await message.answer("У вас нет прав для выполнения этой команды.")

@dp.callback_query_handler(lambda call: call.data == "taskslist")
async def donate_main_handler(callback: types.CallbackQuery):
    tasks = get_tasks()

    if not tasks:
        await callback.answer("Нет активных задач.")
        return

    task_list = []
    for task in tasks:
        task_id = task[0]
        channel_id = task[1]
        reward = task[2]
        completed = task[3]
        max_completions = task[4]
        keyboard = InlineKeyboardMarkup()
        keyboard.add(InlineKeyboardButton(text="👑 Вернуться в админ-меню", callback_data="adminpanel"))
        try:
            chat = await bot.get_chat(channel_id)
            if chat.username:
                channel_link = f'<a href="https://t.me/{chat.username}">{chat.title}</a>'
            else:
                channel_link = chat.title
        except Exception as e:
            channel_link = f"Канал {channel_id} (неизвестное имя)"
            print(f"Ошибка получения данных о канале {channel_id}: {e}")

        task_list.append(f"{channel_link} - {reward:.2f} 🌟 ({completed} | {max_completions})")

    response = "\n".join(task_list)
    await callback.message.edit_text(
        f"<b>Список задач:</b>\n{response}",
        reply_markup=keyboard,
        disable_web_page_preview=True
    )

@dp.callback_query_handler(lambda call: call.data == "donate")
async def donate_main_handler(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton(text="🌟 Stars", callback_data="donate_stars")
    )
    keyboard.add(
        InlineKeyboardButton("В главное меню", callback_data="back_main")
    )

    image = "image/donate.jpg"
    await callback.message.delete()
    with open(image, "rb") as photo:
            await callback.message.answer_photo(photo=photo, caption="""
💛 <b>Выберите способ поддержки:</b>


1️⃣ ЮMoney — оплатить ЮMoney/Карта.
2️⃣ Stars — оплатить Telegram Stars.

Выберите подходящий вариант ниже.""",
        parse_mode="HTML",
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda call: call.data == "donate_stars")
async def check_subs(call: types.CallbackQuery):
    try:
        await call.message.delete()
    except (MessageCantBeDeleted, MessageToDeleteNotFound):
        pass

    one = types.LabeledPrice(label='Поддержать', amount=DONATE_PAY)

    await bot.send_invoice(
        call.from_user.id,
        title="Донат 💛",
        description=f"✨ Поддержи проект и получи бонусы! \n\n🌟 Множитель x2.5 к кликам на {DONATE_TIME} дней. \n🤝 Множитель x2 за рефералов на {DONATE_TIME} дней. \n\n❓ Для возврата в меню пропиши /start.",
        provider_token="YOUR_PROVIDER_TOKEN",
        currency="XTR",
        photo_url="<ссылка_на_картинку>",
        photo_width=3600,
        photo_height=2338,
        photo_size=262000,
        is_flexible=False,
        prices=[one],
        start_parameter="one-more",
        payload="one-more"
    )

@dp.pre_checkout_query_handler()
async def checkout_handler(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message_handler(content_types=types.ContentType.SUCCESSFUL_PAYMENT)
async def hide_keyboard(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    min_click_reward = 0.25
    max_click_reward = 0.25
    min_ref_reward = 2
    max_ref_reward = 2

    set_custom_reward_in_db(user_id, min_click_reward, max_click_reward)
    set_ref_reward(user_id, min_ref_reward, max_ref_reward)

    for admin in admins:
        await bot.send_message(
            admin,
            text=(
                f"💛 <b>Получен донат!</b>\n\n"
                f"👤 Отправитель: @{username} | ID: <code>{user_id}</code>\n\n"
                f"💳 <b>ID транзакции:</b> <code>{message.successful_payment.telegram_payment_charge_id}</code>\n\n"
            ),
        )

    await message.answer(
        f"<b>Спасибо за поддержку проекта 💛</b>\n\n"
        f"✨ Твои бусты успешно подключены:\n"
        f"🌟 <b>Клики:</b> x2.5 на 15 дней (0.25/клик).\n"
        f"🤝 <b>Рефералы:</b> x2 на 15 дней (2.0/реферал).\n\n"
        f"Продолжай наслаждаться игрой! 🥳"
    )

def get_tasks_for_user(user_id):
    tasks = get_tasks()
    result = []
    
    for task in tasks:
        try:
            if len(task) == 7:
                task_id, ch_id, rew, completed_count, max_completions, requires_subscription, task_type = task
            elif len(task) == 5:
                task_id, ch_id, rew, completed_count, max_completions = task
                
                if isinstance(ch_id, int) and ch_id < 0:  
                    requires_subscription, task_type = 1, 'sub'
                else:
                    requires_subscription, task_type = 0, 'nosub'
            else:
                print(f"Ошибка: неправильное количество данных в задаче: {task}")
                continue
        except ValueError:
            print(f"Ошибка при распаковке задачи: {task}")
            continue

        if not user_completed_task(user_id, task_id):
            result.append((task_id, ch_id, rew, completed_count, max_completions, requires_subscription, task_type))
    
    return result


class GiveStars(StatesGroup):
    amount = State()

class AdminSearchIdlState(StatesGroup):
    waiting_for_message = State()

class PromoCodeState(StatesGroup):
    waiting_for_promocode = State()

class BroadcastState(StatesGroup):
    waiting_for_message = State()
    waiting_for_button_text = State()
    waiting_for_button_url = State()
    waiting_for_more_buttons = State()
    waiting_for_confirmation = State()

class AdminAddChannelState(StatesGroup):
    waiting_for_channel_id = State()
    waiting_for_delete_time = State()

class AdminDeleteChannelState(StatesGroup):
    waiting_for_channel_id = State()

class AdminAddTaskState(StatesGroup):
    waiting_for_task_type = State()
    waiting_for_channel_id = State()
    waiting_for_reward = State()
    waiting_for_max_completions = State()

class AdminRemoveTaskState(StatesGroup):
    waiting_for_channel_id = State()

class AdminAddStarsState(StatesGroup):
    waiting_for_data = State()

class AdminAddPromoCodeState(StatesGroup):
    waiting_for_data = State()

class AdminDeletePromoCodeState(StatesGroup):
    waiting_for_promocode = State()

class UserIDState(StatesGroup):
    waiting_for_user_id = State()
    waiting_for_star_amount = State()
    waiting_for_ref_reward = State()
    waiting_for_click_reward = State()

def t(user_id, key):
    lang = get_user_lang(user_id)
    if lang not in TEXTS:
        lang = 'ru'
    return TEXTS[lang].get(key, key)

def get_language_markup():
    markup = InlineKeyboardMarkup()
    for lang in AVAILABLE_LANGS:
        button = InlineKeyboardButton(text=TEXTS[lang]['lang_'+lang], callback_data=f"set_lang:{lang}")
        markup.add(button)
    return markup

async def request_op(user_id, chat_id, gender=None, age=None):
    registration_time_str = get_user_registration_time(user_id)
    if not registration_time_str:
        return "ok"

    registration_time = datetime.strptime(registration_time_str, "%Y-%m-%d %H:%M:%S")

    current_time = datetime.now()
    delay_seconds = (REQUEST_OP_DELAY_HOURS * 3600) + (REQUEST_OP_DELAY_MINUTES * 60)

    if (current_time - registration_time).total_seconds() < delay_seconds:
        return "ok"

    headers = {
        'Content-Type': 'application/json',
        'Auth': REQUEST_API_KEY,
        'Accept': 'application/json',
    }
    data = {'UserId': user_id, 'ChatId': chat_id}
    if gender:
        data['Gender'] = gender
    if age:
        data['Age'] = age

    async with aiohttp.ClientSession() as session:
        async with session.post('https://api.subgram.ru/request-op/', headers=headers, json=data) as response:
            if not response.ok:
                return "ok"

            response_json = await response.json()
            if response.status != 200:
                pass

            status = response_json.get("status")
            if status == 'warning':
                links = response_json.get("links", [])
                markup = InlineKeyboardMarkup(row_width=2)
                unique_links = list(set(links))

                buttons = [InlineKeyboardButton(f'Спонсор №{idx}', url=url) for idx, url in enumerate(unique_links, start=1)]
                markup.add(*buttons)

                check_button = InlineKeyboardButton('✅ Я подписан', callback_data='check_subs')
                markup.add(check_button)

                subscribe_text = "💜 Чтобы продолжить пользоваться ботом, пожалуйста, подпишись на следующие ресурсы:"
                image = "image/check.jpg"

                with open(image, "rb") as photo:
                    await bot.send_photo(user_id, photo=photo, caption=subscribe_text, reply_markup=markup)
                return False

            return status

async def show_advert(user_id: int):
    log = logging.getLogger('adverts')
    async with aiohttp.ClientSession() as session:
        async with session.post(
            'https://api.gramads.net/ad/SendPost',
            headers={
                'Authorization': 'Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIzMDU5MCIsImp0aSI6Ijc3ZmMyNzQ4LTkzNjItNDk5Mi05NzI3LTkwZTA2NTI1MTJjNSIsIm5hbWUiOiJHSUZUIFRHIHwg0JHQtdGB0L_Qu9Cw0YLQvdGL0LUg0L_QvtC00LDRgNC60LgiLCJib3RpZCI6IjEzODQ5IiwiaHR0cDovL3NjaGVtYXMueG1sc29hcC5vcmcvd3MvMjAwNS8wNS9pZGVudGl0eS9jbGFpbXMvbmFtZWlkZW50aWZpZXIiOiIzMDU5MCIsIm5iZiI6MTc0MDkwNDMyNSwiZXhwIjoxNzQxMTEzMTI1LCJpc3MiOiJTdHVnbm92IiwiYXVkIjoiVXNlcnMifQ.XxETQbY4YAv1OTaWAOJ2144OngPbBSmQY0G9ypzy8S0',
                'Content-Type': 'application/json',
            },
            json={'SendToChatId': user_id},
        ) as response:
            content_type = response.headers.get('Content-Type', '')
            if 'application/json' in content_type:
                response_data = await response.json()
            else:
                response_data = await response.text()
            if not response.ok:
                log.error('Gramads: %s' % str(response_data))

async def check_subscription(user_id, chat_id, channel_ids):
    response = await request_op(user_id, chat_id)
    if response != 'ok':
        return False
    if user_id in ADMIN_IDS:
        return True
    message = {
        'text': '<b>Пожалуйста, подпишитесь!</b> для доступа',
        'button_bot': 'Запустить',
        'button_channel': 'Подписаться',
        'button_url': 'Перейти',
        'button_boost': 'Забустить',
    }
    try:
        flyer_check = await flyer.check(user_id, language_code="ru", message=message)
        if not flyer_check:
            return
    except Exception as e:
        return False
    if not channel_ids:
        return True
    await show_advert(user_id)
    markup = InlineKeyboardMarkup()
    subscribed = True
    channels_list_text = ""
    sponsor_buttons = get_sponsor_buttons()
    for channel_id in channel_ids:
        try:
            chat_member = await bot.get_chat_member(channel_id, user_id)
            if chat_member.status not in ['member', 'administrator', 'creator']:
                chat = await bot.get_chat(channel_id)
                invite_link = (await bot.create_chat_invite_link(channel_id, member_limit=1)).invite_link
                subscribe_button = InlineKeyboardButton(chat.title, url=invite_link)
                markup.add(subscribe_button)
                subscribed = False
                channels_list_text += f"• {chat.title}: {invite_link}\\n"
        except:
            try:
                chat = await bot.get_chat(channel_id)
                invite_link = (await bot.create_chat_invite_link(channel_id, member_limit=1)).invite_link
                subscribe_button = InlineKeyboardButton(chat.title, url=invite_link)
                markup.add(subscribe_button)
                subscribed = False
                channels_list_text += f"• {chat.title}: {invite_link}\\n"
            except:
                pass

    for name, url in sponsor_buttons:
        extra_button = InlineKeyboardButton(name, url=url)
        markup.add(extra_button)

    if not subscribed:
        await show_advert(user_id)
        check_button = InlineKeyboardButton(t(user_id, 'check_subscribe'), callback_data="check_subs")
        markup.add(check_button)
        subscribe_text = t(user_id, 'start_subscribe').replace("{channels_list}", channels_list_text.strip())
        image = "image/check.jpg"
        with open(image, "rb") as photo:
            await bot.send_photo(user_id, photo=photo, caption=subscribe_text, reply_markup=markup)
            return False
    return True

@dp.callback_query_handler(lambda c: c.data == 'op')
async def dell_noop_callback(callback_query: types.CallbackQuery):
    markup = InlineKeyboardMarkup(row_width=1)
    add_noop_button = InlineKeyboardButton("➕ Добавить ОП без проверки", callback_data="add_noop")
    dell_noop_button = InlineKeyboardButton("❌ Удалить ОП без проверки", callback_data="dell_noop")
    view_noop_button = InlineKeyboardButton("👁️ Все ОП без проверки", callback_data="view_noop")
    markup.add(add_noop_button, dell_noop_button, view_noop_button)
    await callback_query.message.edit_text("Выберите действие:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == 'view_noop')
async def view_noop_callback(callback_query: types.CallbackQuery):
    chat_id = callback_query.message.chat.id

    buttons = get_sponsor_buttons()

    if not buttons:
        await callback_query.message.answer("Нет добавленных кнопок 'оп без проверки'.")
        await bot.answer_callback_query(callback_query.id)
        return

    buttons_list = "\n".join([f"• <code>{name}:{url}</code>" for name, url in buttons])

    await callback_query.message.answer(f"Все кнопки 'оп без проверки':\n{buttons_list}", parse_mode="HTML")
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query_handler(lambda c: c.data == 'add_noop')
async def add_noop_callback(callback_query: types.CallbackQuery):
    await callback_query.message.answer("Введите название кнопки и URL через двоеточие (например, 'Спонсор 1:url')")
    await ButtonState.adding.set()
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query_handler(lambda c: c.data == 'dell_noop')
async def dell_noop_callback(callback_query: types.CallbackQuery):
    await callback_query.message.answer("Введите название кнопки и URL через двоеточие (например, 'Спонсор 1:url')")
    await ButtonState.removing.set()
    await bot.answer_callback_query(callback_query.id)

class ButtonState(StatesGroup):
    adding = State()
    removing = State()

@dp.message_handler(state=ButtonState.adding)
async def handle_add_button(message: types.Message, state: FSMContext):
    if ':' not in message.text:
        await message.answer("Неверный формат. Используйте: name_button:url")
        return

    name, url = message.text.split(":", 1)

    add_sponsor_button(message.chat.id, name, url)
    await message.answer(f"✅ Кнопка '{name}' успешно добавлена.")

    await state.finish()

@dp.message_handler(state=ButtonState.removing)
async def handle_remove_button(message: types.Message, state: FSMContext):
    if ':' not in message.text:
        await message.answer("Неверный формат. Используйте: name_button:url")
        return

    name, url = message.text.split(":", 1)

    remove_sponsor_button(message.chat.id, name, url)
    await message.answer(f"✅ Кнопка '{name}' успешно удалена.")

    await state.finish()

def get_total_combined_strings():
    total_combined = get_total_combined()
    return f"{total_combined:.2f}"

async def show_main_menu(message, user_id, edit=False):
    total_stars = get_total_combined_strings()
    withdrawn_amount = get_total_withdrawn()
    withdrawn_formatted = f"{withdrawn_amount:.2f}"
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
    menu_text = t(user_id, 'welcome_msg').format(
        ref_link=ref_link,
        total_stars=total_stars,
        withdrawn_formatted=withdrawn_formatted
    )
    markup = get_main_menu_markup(user_id)

    image = "image/menu.jpg"

    if edit:
        try:
            await message.delete()
            with open(image, "rb") as photo:
                await message.answer_photo(
                    photo=photo,
                    caption=menu_text,
                    reply_markup=markup
                )
        except FileNotFoundError:
            await message.answer("Ошибка: файл изображения 'menu.jpg' не найден.")
        except Exception as e:
            await message.answer(f"Ошибка при обновлении меню: {str(e)}")
    else:
        try:
            with open(image, "rb") as photo:
                await message.answer_photo(
                    photo=photo,
                    caption=menu_text,
                    reply_markup=markup
                )
        except FileNotFoundError:
            await message.answer("Ошибка: файл изображения 'menu.jpg' не найден.")


def get_main_menu_markup(user_id):
    markup = InlineKeyboardMarkup()

    earn_text = t(user_id, 'btn_earn_stars_text')
    withdraw_text = t(user_id, 'btn_withdraw_stars_text')
    balance_text = t(user_id, 'btn_my_balance_text')
    tasks_text = t(user_id, 'btn_tasks_text')
    spons_text = t(user_id, "btn_spons_text")
    game_text = t(user_id, "btn_game_text")
    faq_text = t(user_id, "btn_faq_text")
    top_ref_text = t(user_id, "btn_top_ref_text")
    farm_text = t(user_id, "btn_farm_text")

    reklama = InlineKeyboardButton("💌 Отзывы", url=LINK_5)
    farm_button = InlineKeyboardButton(farm_text, callback_data="click_star")
    spons = InlineKeyboardButton(spons_text, callback_data="donate_stars")
    earn = InlineKeyboardButton(earn_text, callback_data="earn_stars")
    balance = InlineKeyboardButton(balance_text, callback_data="my_balance")
    tasks = InlineKeyboardButton(tasks_text, callback_data="tasks")
    exchange = InlineKeyboardButton(withdraw_text, callback_data="withdraw_stars_menu")
    faq = InlineKeyboardButton(faq_text, callback_data="faq")
    top_ref = InlineKeyboardButton(top_ref_text, callback_data="top_5")

    markup.add(farm_button)
    markup.add(earn)
    markup.add(balance, exchange)
    markup.add(tasks, faq)
    markup.add(spons)

    if SHOW_MINI_GAMES_BUTTON:
        game = InlineKeyboardButton(game_text, callback_data="mini_games")
        markup.add(game)

    markup.add(top_ref, reklama)
    return markup

import random
import asyncio
import logging
from aiogram import Bot, types
from aiogram.types import ReplyKeyboardRemove
from database import get_user, get_referral_reward_range, increment_stars, update_user_ref_rewarded, update_verified_signups

@dp.message_handler(commands=['start'])
async def handle_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username or f"{user_id}"
    full_name = message.from_user.full_name or ""
    chat_id = message.chat.id

    if re.search(r'[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]', full_name):
        return

    ref_full_name = "-"
    ref_username = "-"
    referral_id = None
    stars_balance = 0.0
    special_ref = None

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0] + 1
    conn.close()

    full_name = re.sub(r'[<>/]', '', full_name)
    telegram_link = f"<a href='tg://user?id={user_id}'>{full_name}</a>"

    inline_button = InlineKeyboardButton(text="Посмотреть профиль", url=f"tg://user?id={user_id}")
    inline_kb = InlineKeyboardMarkup().add(inline_button)

    args = message.text.split()
    
    if len(args) > 1:
        print(f"Аргументы: {args}")
        
        if args[1].isdigit():
            ref_id = int(args[1])
            if user_exists(ref_id) and ref_id != user_id:
                referral_id = ref_id

        elif args[1].startswith("ref_"):
            special_ref = args[1]
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT user_id FROM special_links WHERE special_code = ?", (special_ref,))
            ref_owner = cursor.fetchone()
            
            if ref_owner:
                ref_owner_id = ref_owner[0]
                cursor.execute("UPDATE special_links SET total_visits = total_visits + 1 WHERE special_code = ?", (special_ref,))
                cursor.execute("SELECT COUNT(*) FROM special_link_visits WHERE user_id = ? AND special_code = ?", (user_id, special_ref))
                already_visited = cursor.fetchone()[0]
                
                if already_visited == 0:
                    cursor.execute("INSERT INTO special_link_visits (user_id, special_code) VALUES (?, ?)", (user_id, special_ref))
                    cursor.execute("UPDATE special_links SET unique_visits = unique_visits + 1 WHERE special_code = ?", (special_ref,))
                conn.commit()
            conn.close()

    if referral_id:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT stars, username FROM users WHERE id = ?", (referral_id,))
        referral_data = cursor.fetchone()
        conn.close()

        if referral_data:
            stars_balance = referral_data[0] or 0.0
            ref_username = referral_data[1] or "-"
            ref_full_name = f"<a href='tg://user?id={referral_id}'>Посмотреть профиль</a>"

    if not user_exists(user_id):
        print(f"Записываю в БД: special_ref={special_ref}")
        add_user(user_id, username, referral_id=referral_id, lang='ru', special_ref=special_ref)

        referrals_weekly = get_referrals_count_week(referral_id)

        await bot.send_message(LOG_CH_USER, text=f"""
🚨 <b>Новый пользователь в боте!</b>

👤 <b>Имя:</b> {telegram_link}
🆔 <b>ID пользователя:</b> <code>{user_id}</code>
📛 <b>Username:</b> @{username if username else '-'}

👥 <b>Реферал:</b> {ref_full_name}
🔗 <b>ID:</b> <code>{referral_id if referral_id else 'Нет'}</code>
📛 <b>Username:</b> @{ref_username}
💰 <b>Баланс:</b> <code>{stars_balance:.2f} ✨</code>
👥 <b>Рефералы за неделю:</b> <code>{referrals_weekly}</code>

🏅 <b>Пользователь №:</b><code>{user_count}</code>
""", reply_markup=inline_kb, parse_mode="HTML")

    subscribed = await check_subscription(user_id, chat_id, channel_ids)

    if subscribed:
        await show_main_menu(message, user_id, edit=False)

async def award_referral(user_id, bot: Bot):
    try:
        user_data = get_user(user_id)
        if user_data is None:
            print(f"Ошибка: Пользователь с ID {user_id} не найден.")
            return

        referral_id = user_data[4]
        ref_rewarded = user_data[7]
        special_code = user_data[8]

        if not referral_id or ref_rewarded:
            return

        min_reward, max_reward = get_referral_reward_range(referral_id)
        reward = round(random.uniform(min_reward, max_reward), 2)
        increment_stars(referral_id, reward)

        update_user_ref_rewarded(user_id, True)

        ref_link = f"https://t.me/{(await bot.get_me()).username}?start={referral_id}"
        
        mark_onboarding_completed(user_id)

        if special_code:
            update_verified_signups(special_code)

        try:
            await bot.send_message(
                referral_id,
                f"🎉 <b>Новый реферал!</b>\n\n"
                f"👤 Пользователь <code>{user_id}</code> присоединился по вашей ссылке!\n"
                f"💰 Вы получили <b>+{reward}⭐</b> за приглашение.\n\n"
                f"🔗 <b>Поделитесь ссылкой ещё раз:</b>\n<code>{ref_link}</code>",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"Ошибка при отправке сообщения рефереру {referral_id}: {e}")

        print(f"Награда за реферала ({reward}⭐) выдана пользователю {referral_id} за приглашение {user_id}.")
    except Exception as e:
        print(f"Ошибка при выдаче награды за реферала: {e}")


def get_luck_game_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=3)
    stakes = [0.5, 1, 2, 3, 4, 5]
    for stake in stakes:
        keyboard.insert(
            InlineKeyboardButton(f"Ставка: {stake} ⭐", callback_data=f"play_game_with_bet:{stake}")
        )

    keyboard.insert(
        InlineKeyboardButton("⬅️ Назад в меню мини-игр", callback_data="mini_games")
    )

    return keyboard

@dp.message_handler(commands=['set_win_chance'])
async def set_win_chance(message: types.Message):
    try:
        if message.from_user.id not in admins:
            await message.answer("❌ У тебя нет прав для изменения шанса выигрыша.")
            return

        try:
            new_chance = float(message.text.split()[1])
            if not (0 < new_chance <= 100):
                await message.answer("❌ Введите корректное значение шанса от 0 до 100.")
                return
        except (IndexError, ValueError):
            await message.answer("❌ Укажите правильное значение шанса (например, /set_win_chance 50).")
            return

        global WIN_CHANCE
        WIN_CHANCE = new_chance

        await message.answer(f"✅ Новый шанс выигрыша установлен: {WIN_CHANCE}%!", parse_mode="HTML")
    except Exception as e:
        await message.answer(f"Произошла ошибка: {str(e)}")

@dp.callback_query_handler(lambda callback_query: callback_query.data == "check_subs")
async def handle_check_subscription(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id

    subscribed = await check_subscription(user_id, chat_id, channel_ids)

    if subscribed:
        await callback_query.answer(t(user_id, 'subscribed_successfully'), show_alert=True)
        await show_main_menu(callback_query.message, user_id, edit=True)
        await mark_onboarding_completed(user_id)
        await award_referral(user_id, bot)
    else:
        await callback_query.answer(t(user_id, 'not_subscribed'), show_alert=True)


@dp.callback_query_handler(lambda call: call.data == "play_game")
async def play_game_callback(call: types.CallbackQuery):
    user_data = get_user(call.from_user.id)
    if not user_data:
        await call.answer("Пользователь не найден. Зарегистрируйтесь в боте.", show_alert=True)
        return

    stars = user_data[2]
    await call.message.edit_caption(caption=
        f"💰 <b>У тебя на счету:</b> {stars:.2f} ⭐️\n\n"
        f"🔔 Ты выбрал игру 'Испытать удачу'. Выбери ставку и попытайся победить! 🍀"
        f"\n\n📊 Онлайн статистика выигрышей: {LINK_4}",
        reply_markup=get_luck_game_keyboard(),
        parse_mode="HTML"
    )


def get_mini_games_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.insert(InlineKeyboardButton("Все или ничего 🎲", callback_data="play_game"))
    keyboard.insert(InlineKeyboardButton("Я вор! 🏃‍♂️", callback_data="play_robbery"))
    keyboard.insert(InlineKeyboardButton("В главное меню", callback_data="back_main"))
    return keyboard

@dp.callback_query_handler(lambda c: c.data == "play_robbery")
async def robbery_game(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    last_robbery_time = await get_last_robbery_time(user_id)
    if last_robbery_time:
        current_time = datetime.now()
        time_difference = current_time - last_robbery_time
        if time_difference.total_seconds() < 3600:
            remaining_time = 3600 - time_difference.total_seconds()
            message = f"<b>Ты можешь ограбить только через {remaining_time // 60:.0f} минут.</b>"
            main_menu_markup = InlineKeyboardMarkup(row_width=2)
            back_button = InlineKeyboardButton("В главное меню 🏠", callback_data="back_main")
            main_menu_markup.add(back_button)
            await callback_query.message.edit_caption(caption=message, reply_markup=main_menu_markup, parse_mode='HTML')
            return

    robbery_markup = InlineKeyboardMarkup(row_width=2)
    rob_button = InlineKeyboardButton("Ограбить 🏃‍♂️", callback_data="robbery_attempt")
    back_button = InlineKeyboardButton("Назад в меню ⬅️", callback_data="back_main")
    robbery_markup.add(rob_button, back_button)

    await callback_query.message.edit_caption(caption=(
        "<b>🔓 У тебя есть шанс украсть <code>2%</code> звезд у случайного пользователя!</b>\n\n"
        "Но будь осторожен, если тебя поймают — ты потеряешь все свои звезды! 💥\n\n"
        "<i>Готов рискнуть?</i>"
    ), reply_markup=robbery_markup, parse_mode='HTML')

@dp.callback_query_handler(lambda c: c.data == "robbery_attempt")
async def attempt_robbery(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id

    user_balance = get_users_balance(user_id)

    if user_balance < 5:
        message = "<b>У тебя недостаточно звезд для ограбления. Требуется минимум 5 звезд на балансе.</b>"
        main_menu_markup = InlineKeyboardMarkup(row_width=2)
        back_button = InlineKeyboardButton("В главное меню 🏠", callback_data="back_main")
        main_menu_markup.add(back_button)

        await callback_query.message.edit_caption(caption=message, reply_markup=main_menu_markup, parse_mode='HTML')
        return

    random_user = await get_random_user()
    if random_user is None:
        await callback_query.message.edit_caption(caption="<b>Не удалось найти случайного пользователя для ограбления. Попробуй позже.</b>", parse_mode='HTML')
        return

    random_user_id, random_user_stars = random_user

    if user_id == random_user_id:
        message = "<b>Ты не можешь ограбить сам себя!</b>"
        main_menu_markup = InlineKeyboardMarkup(row_width=2)
        back_button = InlineKeyboardButton("В главное меню 🏠", callback_data="back_main")
        main_menu_markup.add(back_button)

        await callback_query.message.edit_caption(caption=message, reply_markup=main_menu_markup, parse_mode='HTML')
        return

    last_robbery_time = await get_last_robbery_time(user_id)
    if last_robbery_time:
        time_diff = datetime.now() - last_robbery_time
        if time_diff < timedelta(hours=12):
            remaining_time = timedelta(hours=12) - time_diff
            message = f"<b>Ты должен подождать {remaining_time} до следующего ограбления.</b>"
            main_menu_markup = InlineKeyboardMarkup(row_width=2)
            back_button = InlineKeyboardButton("В главное меню 🏠", callback_data="back_main")
            main_menu_markup.add(back_button)

            await callback_query.message.edit_caption(caption=message, reply_markup=main_menu_markup, parse_mode='HTML')
            return

    stolen_stars = random_user_stars * 0.02
    new_balance = get_users_balance(user_id) + stolen_stars
    await update_user_balance(user_id, new_balance)

    message = f"<b>Ты успешно украл {stolen_stars:.2f}⭐️ у пользователя {random_user_id}!</b>"

    victim_message = f"🥷 <b>У тебя украли {stolen_stars:.2f}⭐️.</b>"

    await bot.send_message(random_user_id, victim_message, parse_mode='HTML')

    await update_last_robbery_time(user_id, random_user_id)

    main_menu_markup = InlineKeyboardMarkup(row_width=2)
    back_button = InlineKeyboardButton("В главное меню 🏠", callback_data="back_main")
    main_menu_markup.add(back_button)

    await callback_query.message.edit_caption(caption=message, reply_markup=main_menu_markup, parse_mode='HTML')

async def get_last_robbery_time(user_id: int):
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    result = cursor.execute('SELECT robbery_time FROM robberies WHERE user_id = ? ORDER BY robbery_time DESC LIMIT 1', (user_id,)).fetchone()
    conn.close()
    
    if result and result[0]:
        try:
            print(datetime)
            last_robbery_time = datetime.strptime(result[0], "%Y-%m-%d %H:%M:%S")
            return last_robbery_time
        except ValueError:
            print(f"Ошибка при парсинге времени: {result[0]}")
            return None
    return None

async def update_last_robbery_time(user_id: int, target_user_id: int):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('INSERT OR REPLACE INTO robberies (user_id, target_user_id, robbery_time) VALUES (?, ?, ?)',
                   (user_id, target_user_id, current_time))
    conn.commit()
    conn.close()

@dp.callback_query_handler(lambda call: call.data == "mini_games")
async def mini_games_callback(call: types.CallbackQuery):
    image = "image/minegame.jpg"
    try:
        await call.message.delete()
    except (MessageCantBeDeleted, MessageToDeleteNotFound):
        pass
    with open(image, "rb") as photo:
        await call.message.answer_photo(photo=photo,caption=
        f"🎮 <b>Добро пожаловать в мини-игры!</b> Выбери игру, чтобы начать:\n\n"
        f"1️⃣ <b>Испытать удачу</b> — попробуй победить с разными ставками!\n",
        reply_markup=get_mini_games_keyboard(),
        parse_mode="HTML"
    )

@dp.callback_query_handler(lambda call: call.data.startswith("play_game_with_bet:"))
async def play_game_with_bet(call: types.CallbackQuery):
    try:
        bet_amount = float(call.data.split(":")[1])
        user_id = call.from_user.id
        user_data = get_user(user_id)

        if not user_data:
            await call.answer("Пользователь не найден. Зарегистрируйтесь в боте.", show_alert=True)
            return

        stars = user_data[2]

        if stars < bet_amount:
            await call.answer("😞 У тебя недостаточно звёзд для этой ставки.", show_alert=True)
            return

        win_coefficient = round(random.uniform(1.8, 2.5), 2)

        win = random.randint(1, 100) <= WIN_CHANCE
        if win:
            win_messages = [
                "<b>🎉 Потрясающий выигрыш!</b> 🏆✨",
                "<b>🥳 Невероятная удача!</b> 🌟💥",
                "<b>🎊 Ты сегодня на высоте!</b> 🏅🎉",
                "<b>🔥 Великолепный результат!</b> 🎯✨",
                "<b>🚀 Просто потрясающий выигрыш!</b> 🏆🌟"
            ]
            random_win_message = random.choice(win_messages)
            win_amount = bet_amount * win_coefficient
            new_stars = stars + win_amount - bet_amount
            result_message = (
                f"🎉 Ты выиграл! {win_amount:.2f} ⭐️(коэффициент: {win_coefficient})"
            )
            await bot.send_message(
                WIN_CHANEL_ID,
                f"<b>🎉 Поздравляем!</b> 🏆\n\n"
                f"Пользователь <b>{call.from_user.full_name}</b> (ID: <code>{call.from_user.id}</code>)\n"
                f"<i>выиграл</i> <b>{win_amount:.2f} ⭐️</b> на ставке <b>{bet_amount} ⭐️</b> 🎲\n\n"
                f"<b>Коэффициент:</b> <i>{win_coefficient}</i> ✨\n\n"
                f"{random_win_message} 🎉\n\n"
                f"🎯 <i>Не упусти свой шанс!</i>  <a href='https://t.me/{USER_BOT}'>Испытать удачу!</a>🍀"
            )
        else:
            new_stars = stars - bet_amount
            result_message = "😞 Ты проиграл свою ставку. Попробуй снова!"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET stars = ? WHERE id = ?", (new_stars, user_id))
        conn.commit()
        conn.close()

        await call.answer(result_message, show_alert=True)

        await call.message.edit_text(
            f"💰 <b>У тебя на счету:</b> {new_stars:.2f} ⭐️\n\n"
            "🔔 Эта игра ведётся на виртуальную валюту — баланс бота. Помни, что это рискованно: "
            "ты можешь как всё проиграть, так и значительно увеличить свой баланс! Выбирай ставку и попробуй удачу. 🍀\n\n📊 Онлайн статистика выигрышей: t.me/StarsBitGame",
            reply_markup=get_luck_game_keyboard(),
            parse_mode="HTML"
        )
    except Exception as e:
        await call.answer(f"Произошла ошибка: {str(e)}", show_alert=True)

@dp.message_handler(state=AdminAddTaskState.waiting_for_channel_id)
async def process_channel_id(message: types.Message, state: FSMContext):
    data = await state.get_data()
    task_type = data["task_type"]
    if task_type == "nosub":
        channel_id = message.text.strip()
    else:
        try:
            channel_id = int(message.text.strip())
        except ValueError:
            await message.reply("Введите корректный ID канала.")
            return
    await state.update_data(channel_id=channel_id)
    print(f"Тип задания: {task_type}, Канал: {channel_id}")
    await message.answer("💰 Введи награду за выполнение задания:")
    await AdminAddTaskState.waiting_for_reward.set()

@dp.message_handler(state=AdminAddTaskState.waiting_for_reward)
async def process_reward_and_add_task(message: types.Message, state: FSMContext):
    try:
        reward = float(message.text.strip()) 
        if reward <= 0:
            await message.reply("Сумма должна быть больше нуля.")
            return
    except ValueError:
        await message.reply("Введите корректное значение для награды (например, 1.0).")
        return

    await state.update_data(reward=reward)
    await message.reply("Введите лимит выполнения задания (количество участников):")
    await AdminAddTaskState.waiting_for_max_completions.set()

@dp.message_handler(state=AdminAddTaskState.waiting_for_max_completions)
async def process_max_completions(message: types.Message, state: FSMContext):
    try:
        max_completions = int(message.text.strip())
        if max_completions <= 0:
            await message.reply("Лимит должен быть больше нуля.")
            return
    except ValueError:
        await message.reply("Введите корректное число для лимита.")
        return

    data = await state.get_data()
    task_type = data["task_type"]
    channel_id = data["channel_id"]
    reward = data["reward"]

    print(f"Тип задания: {task_type}, Канал: {channel_id}, Награда: {reward}, Лимит: {max_completions}")

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute(
        'INSERT INTO tasks (channel_id, reward, active, completed_count, max_completions, requires_subscription, task_type) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (channel_id, reward, 1, 0, max_completions, 1 if task_type == "sub" else 0, task_type)
    )
    conn.commit()
    conn.close()

    await message.reply(f"Задание с типом {task_type} добавлено с наградой {reward} ⭐️ и лимитом {max_completions}!")
    
    await state.finish()


@dp.message_handler(state=AdminAddTaskState.waiting_for_max_completions)
async def process_add_task_max_completions(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in admins:
        await state.finish()
        return

    try:
        max_completions = int(message.text)

        data = await state.get_data()
        channel_id = data.get('channel_id')
        reward = data.get('reward')

        print(f"channel_id: {channel_id}, reward: {reward}, max_completions: {max_completions}")

        if channel_id is None or reward is None or max_completions is None:
            await message.answer("Ошибка. Один из параметров не был передан корректно.")
            await state.finish()
            return

        add_task(channel_id, reward, max_completions)

        await message.answer("Задача добавлена успешно!")
        await state.finish()

    except ValueError:
        await message.answer("Пожалуйста, введите корректное количество завершений.")

@dp.callback_query_handler(lambda callback_query: callback_query.data.startswith("check_subs:"))
async def handle_check_subscription(callback_query: types.CallbackQuery):
    data = callback_query.data.split(":")
    referral_id = int(data[1]) if len(data) > 1 and data[1].isdigit() else None
    user_id = callback_query.from_user.id
    chat_id = callback_query.message.chat.id
    
    subscribed = await check_subscription(user_id, chat_id, channel_ids)

    if subscribed:
        await callback_query.answer(t(user_id, 'subscribed_successfully'), show_alert=True)
        await award_referral(referral_id)
        await mark_onboarding_completed(referral_id)
        await show_main_menu(callback_query.message, user_id, edit=True)
    else:
        await callback_query.answer(t(user_id, 'not_subscribed'), show_alert=True)

@dp.callback_query_handler(lambda c: c.data == "set_ref_reward")
async def process_set_referral_reward(callback_query: types.CallbackQuery):
    try:
        await bot.send_message(callback_query.from_user.id, "Введите ID пользователя и диапазон награды в формате: user_id min:max")

        await UserIDState.waiting_for_ref_reward.set()

    except Exception as e:
        await bot.send_message(callback_query.from_user.id, f"❌ Произошла ошибка: {e}")

@dp.message_handler(state=UserIDState.waiting_for_ref_reward)
async def handle_ref_reward_input(message: types.Message, state: FSMContext):
    keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("👑 Вернуться в админ-меню", callback_data="adminpanel"))
    try:
        if message.from_user.id not in admins:
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            await state.finish()
            return

        args = message.text.split()
        if len(args) != 2:
            await message.answer("❌ Неверный формат. Используйте: user_id min:max", reply_markup=keyboard)
            await state.finish()
            return

        try:
            user_id = int(args[0])
            min_f_reward, max_f_reward = map(float, args[1].split(":"))
        except ValueError:
            await message.answer("❌ Неверный формат. Убедитесь, что используете: user_id min:max.", reply_markup=keyboard)
            await state.finish()
            return

        if min_f_reward < 0 or max_f_reward < 0 or min_f_reward > max_f_reward:
            await message.answer("❌ Укажите корректные значения наград.", reply_markup=keyboard)
            await state.finish()
            return

        set_ref_reward(user_id, min_f_reward, max_f_reward)
        await message.answer(f"✅ Награда за рефералов для пользователя {user_id} установлена: от {min_f_reward}⭐ до {max_f_reward}⭐.", reply_markup=keyboard)
        await state.finish()

    except Exception as e:
        await message.answer(f"❌ Произошла ошибка: {e}")


@dp.callback_query_handler(lambda c: c.data == "set_click_reward")
async def process_set_click_reward(callback_query: types.CallbackQuery):
    try:
        await bot.send_message(callback_query.from_user.id, "Введите ID пользователя и диапазон награды в формате: user_id min:max")

        await UserIDState.waiting_for_click_reward.set()

    except Exception as e:
        await bot.send_message(callback_query.from_user.id, f"❌ Произошла ошибка: {e}")

@dp.message_handler(state=UserIDState.waiting_for_click_reward)
async def handle_click_reward_input(message: types.Message, state: FSMContext):
    try:
        keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("👑 Вернуться в админ-меню", callback_data="adminpanel"))
        if message.from_user.id not in admins:
            await message.answer("❌ У вас нет прав для выполнения этой команды.")
            await state.finish()
            return

        args = message.text.split()
        if len(args) != 2:
            await message.answer("❌ Неверный формат. Используйте: user_id min:max")
            await state.finish()
            return

        try:
            user_id = int(args[0])
            min_reward, max_reward = map(float, args[1].split(":"))
        except ValueError:
            await message.answer("❌ Неверный формат. Убедитесь, что используете: user_id min:max.")
            await state.finish()
            return

        if min_reward < 0 or max_reward < 0 or min_reward > max_reward:
            await message.answer("❌ Укажите корректные значения наград.")
            await state.finish()
            return

        set_custom_reward_in_db(user_id, min_reward, max_reward)
        await message.answer(f"✅ Награда за клик для пользователя {user_id} установлена: от {min_reward}⭐ до {max_reward}⭐.", reply_markup=keyboard)
        await state.finish()

    except Exception as e:
        await message.answer(f"❌ Произошла ошибка: {e}")


@dp.callback_query_handler(lambda c: c.data == "click_star")
async def handle_click(call: types.CallbackQuery):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    channel_ids = get_channels_db() 

    if not await check_subscription(user_id, chat_id, channel_ids):
        try:
            await call.message.delete()
        except (MessageCantBeDeleted, MessageToDeleteNotFound):
            pass
        await call.answer(t(user_id, "not_subscribed"), show_alert=True)
        return

    current_username = call.from_user.username
    stored_username = get_user_username(user_id)

    if stored_username != current_username and current_username:
        update_user_username(user_id, current_username)

    last_click_time = get_last_click_time(user_id)
    current_time = datetime.utcnow()

    if last_click_time:
        last_click_time = datetime.fromisoformat(last_click_time)
        time_diff = current_time - last_click_time
        time_left_seconds = TIME_CLICK_KD - time_diff.total_seconds()

        if time_left_seconds > 0:
            minutes_left = int(time_left_seconds // 60)
            seconds_left = int(time_left_seconds % 60)

            await call.answer(f"⏳ Подождите еще {minutes_left}мин {seconds_left}сек перед следующим кликом.", show_alert=True)
            return

    min_reward, max_reward = get_custom_reward_from_db(user_id)

    if is_lucky_time_now():
        min_reward, max_reward = (CLICK_MIN_REWARD_X2, CLICK_MAX_REWARD_X2)

    random_stars = random.uniform(min_reward, max_reward)
    formatted_stars = f"{random_stars:.2f}"

    add_stars(user_id, random_stars)
    increment_click_count(user_id)
    update_last_click_time(user_id)

    await call.answer(f"🎉 Ты получил {formatted_stars}⭐", show_alert=True)
    await show_advert(user_id)

@dp.callback_query_handler(lambda c: c.data == "giftday")
async def handle_click(call: types.CallbackQuery):
    admin_contact_button = InlineKeyboardButton(
            "Связаться с администратором", url=f"https://t.me/{SUP_LOGIN}"
        )
    keyboard = InlineKeyboardMarkup(row_width=1).add(admin_contact_button)
    if is_user_blocked(call.from_user.id):
        await call.message.edit_text(
            "❌ <b>Вы заблокированы</b> и не можете выполнить это действие.\n\n"
            "Если у вас есть вопросы или вы хотите обсудить ситуацию, "
            "пожалуйста, свяжитесь с администратором через кнопку ниже.",
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        return
    else:
        user_id = call.from_user.id
        user_name = call.from_user.first_name
        last_gift_time = get_last_gift(user_id)

        current_time = datetime.utcnow()

        if last_gift_time:
            last_gift_time = datetime.fromisoformat(last_gift_time)
            time_diff = current_time - last_gift_time
            hours_left = 24 - time_diff.days * 24 - time_diff.seconds // 3600
            minutes_left = 60 - (time_diff.seconds // 60) % 60
            seconds_left = 60 - time_diff.seconds % 60

            if time_diff.days < 1:
                await call.answer(
                    f"⏳ Подождите еще {hours_left} часов, {minutes_left} минут(ы), {seconds_left} секунд(ы) перед следующим подарком.",
                    show_alert=True
                )
                return

        random_stars = round(random.uniform(MIN_GIFT, MAX_GIFT), 2)
        if is_lucky_time_now():
            random_stars = round(random.uniform(MIN_GIFT_L, MAX_GIFT_L), 2)
        add_stars(user_id, random_stars)
        increment_gift_count(user_id)
        update_last_gift(user_id)

        await call.answer(f"🎉 Ты получил {random_stars}⭐", show_alert=True)

@dp.callback_query_handler(lambda c: c.data.startswith("show_link_stats"))
async def show_link_stats(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    params = callback_query.data.split(":")
    page = int(params[1]) if len(params) > 1 else 1
    per_page = 5  # Количество ссылок на одной странице

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT special_code, total_visits, unique_visits, completed_onboarding FROM special_links WHERE user_id = ?", (user_id,))
    links = cursor.fetchall()
    conn.close()

    if not links:
        await callback_query.message.edit_text("ℹ️ У вас нет созданных специальных ссылок.")
        return

    total_pages = (len(links) + per_page - 1) // per_page  # Всего страниц
    start = (page - 1) * per_page
    end = start + per_page
    current_links = links[start:end]

    text = f"📊 <b>Статистика ваших спецссылок (стр. {page}/{total_pages}):</b>\n\n"
    text += "<b>🔗 Ссылка | 🔄 Запуски | 👥 Уник. | ✅ ОП</b>\n"
    text += "━━━━━━━━━━━━━━━━━━━━━\n"

    for link, total, unique, onboarding in current_links:
        text += f"<code>{link}</code> | {total} | {unique} | {onboarding}\n"

    # Кнопки пагинации
    buttons = []
    if page > 1:
        buttons.append(InlineKeyboardButton("◀ Назад", callback_data=f"show_link_stats:{page-1}"))
    if page < total_pages:
        buttons.append(InlineKeyboardButton("Вперёд ▶", callback_data=f"show_link_stats:{page+1}"))

    keyboard = InlineKeyboardMarkup(row_width=2)
    if buttons:
        keyboard.add(*buttons)

    await callback_query.message.edit_text(text, parse_mode="HTML", reply_markup=keyboard)


@dp.callback_query_handler(lambda c: c.data == "gen_link")
async def ask_for_user_id(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    special_code = f"ref_{secrets.token_hex(8)}"
    special_link = f"https://t.me/{USER_BOT}?start={special_code}"
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO special_links (user_id, special_code) VALUES (?, ?)", (user_id, special_code))
    conn.commit()
    conn.close()

    await bot.send_message(user_id, f"Ваша специальная ссылка: <code>{special_link}</code>", parse_mode="HTML")


def mask_id(user_id):
    return str(user_id)[:-3] + "***"

def mask_username(username):
    if username:
        return username[:-3] + "***" if len(username) > 4 else username
    return "Без username"

def generate_referrals_text(referrals, page=1, per_page=5):
    total_pages = (len(referrals) + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    referrals_page = referrals[start_idx:end_idx]
    referrals_text = "\n".join(
        f"<i>{i+1}. <code>@{mask_username(username)}</code> | <code>{mask_id(user_id)}</code> | {balance:.2f}⭐️</i>"
        for i, (user_id, username, balance) in enumerate(referrals_page)
    )

    return referrals_text, total_pages

def create_back_button(user_id):
    return InlineKeyboardButton(t(user_id, "btn_back"), callback_data="back_main")

def generate_pagination_buttons(page, total_pages, user_id):
    giftday_text = t(user_id, "btn_giftday_text")
    promo_text = t(user_id, "btn_promo_text")

    buttons = []
    if page < total_pages:
        buttons.append(
            InlineKeyboardButton(f"➡️ След. стр. {page + 1}", callback_data=f"referrals_page:{page+1}")
        )
    if page > 1:
        buttons.append(
            InlineKeyboardButton(f"⬅️ Назад. стр. {page - 1}", callback_data=f"referrals_page:{page-1}")
        )
    promocode_button = InlineKeyboardButton(promo_text, callback_data="enter_promocode")
    giftday_button = InlineKeyboardButton(giftday_text, callback_data="giftday")
    back_button = create_back_button(user_id)

    markup = InlineKeyboardMarkup(row_width=2)
    if buttons:
        markup.row(*buttons)
    markup.row(promocode_button, giftday_button)
    markup.add(back_button)

    return markup

def sanitize_username(username):
    """Удаляет или экранирует опасные символы из имени пользователя."""
    if not username:
        return "unknown"
    sanitized = username.replace("<", "").replace(">", "").replace("/", "")
    return escape(sanitized)

def mask_id(user_id):
    """Маскирует последние 3 цифры ID."""
    return str(user_id)[:-3] + "***"

def mask_username(username):
    """Маскирует последние 3 символа имени пользователя."""
    if username:
        return username[:-3] + "***" if len(username) > 4 else username
    return "Без username"

def generate_referrals_text(referrals, page=1, per_page=5):
    total_pages = (len(referrals) + per_page - 1) // per_page
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page

    referrals_page = referrals[start_idx:end_idx]
    referrals_text = "\n".join(
        f"<b>{idx + start_idx + 1}.</b> <i><code>@{sanitize_username(mask_username(username))}</code> | <code>{mask_id(user_id)}</code> | {balance:.2f}⭐️</i>"
        for idx, (user_id, username, balance) in enumerate(referrals_page)
    )

    return referrals_text, total_pages

async def get_user_info(user_id):
    try:
        user = await bot.get_chat_member(chat_id=user_id, user_id=user_id)
        full_name = user.user.full_name if user.user.full_name else "Без имени"
        username = user.user.username if user.user.username else "Без username"
        return full_name, username
    except Exception as e:
        print(f"Error retrieving user info: {e}")
        return None, None

@dp.callback_query_handler(lambda c: c.data == 'top_5')
async def process_top_5(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    top_referrals = get_referral_top_by_period('day')

    top_referral_str = "<b>🏆 Топ-5 рефералов за день:</b>\n\n"
    medals = ['🥇', '🥈', '🥉']
    valid_referrals = []
    user_position = None
    user_referral_count = 0

    for rank, (referral_id, count) in enumerate(top_referrals[:5], 1):
        try:
            full_name, username = await get_user_info(referral_id)
            if full_name is None or username is None:
                continue
            valid_referrals.append((referral_id, count, full_name, username))

            if referral_id == user_id:
                user_position = rank
                user_referral_count = count
        except Exception as e:
            logging.error(f"Ошибка при обработке пользователя {referral_id}: {e}")
            continue

    for rank, (referral_id, count, full_name, username) in enumerate(valid_referrals, 1):
        medal = medals[rank - 1] if rank <= 3 else "✨"
        user_link = f'<a href="tg://user?id={referral_id}">{full_name}</a>'
        top_referral_str += f"{medal} <b>{user_link}</b> | Рефералов: <code>{count}</code>\n"

    if user_position is None:
        position_in_full_top = None
        for rank, (referral_id, count) in enumerate(top_referrals, 1):
            if referral_id == user_id:
                position_in_full_top = rank
                user_referral_count = count
                break

        if position_in_full_top:
            top_referral_str += f"\n<b>🏅 Ты на {position_in_full_top} месте</b>"
        else:
            top_referral_str += f"\n🚫 Ты не в Топ-5 за 24 часа!"

        top_referral_str += f" | <code>{user_referral_count}</code> рефералов."

    markup = InlineKeyboardMarkup(row_width=2)
    week_button = InlineKeyboardButton("📅 Топ за неделю", callback_data="top_referrals_week")
    month_button = InlineKeyboardButton("📅 Топ за месяц", callback_data="top_referrals_month")
    back_button = InlineKeyboardButton("⬅️ В главное меню", callback_data="back_main")
    markup.add(week_button, month_button)
    markup.add(back_button)

    image = "image/tops.jpg"
    await callback_query.message.delete()
    with open(image, "rb") as photo:
        await callback_query.message.answer_photo(photo=photo,caption=top_referral_str, parse_mode='HTML', reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data in ['top_5', 'top_referrals_week', 'top_referrals_month'])
async def process_top_referrals_periods(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    period_map = {
        'top_5': ('day', 'Топ-5 рефералов за последние 24 часа'),
        'top_referrals_week': ('week', 'Топ-5 рефералов за неделю'),
        'top_referrals_month': ('month', 'Топ-5 рефералов за месяц')
    }
    period = period_map[callback_query.data][0]
    period_title = period_map[callback_query.data][1]

    top_referrals = get_referral_top_by_period(period)

    top_referral_str = f"<b>{period_title}:</b>\n\n"
    medals = ['🥇', '🥈', '🥉']
    valid_referrals = []
    user_position = None
    user_referral_count = 0

    for rank, (referral_id, count) in enumerate(top_referrals[:5], 1):
        try:
            full_name, username = await get_user_info(referral_id)
            if full_name is None or username is None:
                continue
            valid_referrals.append((referral_id, count, full_name, username))

            if referral_id == user_id:
                user_position = rank
                user_referral_count = count
        except Exception as e:
            logging.error(f"Ошибка при обработке пользователя {referral_id}: {e}")
            continue

    for rank, (referral_id, count, full_name, username) in enumerate(valid_referrals, 1):
        medal = medals[rank - 1] if rank <= 3 else "✨"
        user_link = f'<a href="tg://user?id={referral_id}">{full_name}</a>'
        top_referral_str += f"{medal} <b>{user_link}</b> | Рефералов: <code>{count}</code>\n"

    if user_position is None:
        position_in_full_top = None
        for rank, (referral_id, count) in enumerate(top_referrals, 1):
            if referral_id == user_id:
                position_in_full_top = rank
                user_referral_count = count
                break

        if position_in_full_top:
            top_referral_str += f"\n<b>🏅 Ты на {position_in_full_top} месте</b>"
        else:
            top_referral_str += f"\n🚫 Ты не в Топ-5 за {period_title.lower()}!"

        top_referral_str += f" | <code>{user_referral_count}</code> рефералов."

    markup = InlineKeyboardMarkup(row_width=2)
    day_button = InlineKeyboardButton("📅 Топ за 24 часа", callback_data="top_5")
    other_period_button = InlineKeyboardButton(f"📅 Топ за {'месяц' if period == 'week' else 'неделю'}",
                                               callback_data=f"top_referrals_{'month' if period == 'week' else 'week'}")
    back_button = InlineKeyboardButton("⬅️ В главное меню", callback_data="back_main")
    markup.add(day_button, other_period_button)
    markup.add(back_button)

    await callback_query.message.edit_caption(caption=top_referral_str, parse_mode='HTML', reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == 'top_clicks')
async def process_top_clicks(callback_query: types.CallbackQuery):
    top_clicks = get_click_top()
    user_id = callback_query.from_user.id

    top_click_str = "<b>Топ 10 по кликам:</b>\n\n"

    medals = ['🥇', '🥈', '🥉']

    for rank, (user_id, click_count) in enumerate(top_clicks, 1):
        full_name, username = await get_user_info(user_id)

        if full_name is None or username is None or full_name == "Неизвестный пользователь" or username == "Неизвестно":
            continue

        medal = medals[rank - 1] if rank <= 3 else ""

        user_link = f'{full_name}'

        top_click_str += f"{medal} <b>{user_link}</b> | Клики: <code>{click_count}</code>\n"

    if top_click_str == "<b>Топ 10 по кликам:</b>\n\n":
        top_click_str = "Топ кликов пуст!"

    markup = InlineKeyboardMarkup(row_width=2)
    back_to_referrals = InlineKeyboardButton(t(user_id, 'Топ-10 | По рефералам'), callback_data="top_referrals")
    back = InlineKeyboardButton(t(user_id, 'btn_back'), callback_data="back_main")
    markup.add(back_to_referrals)
    markup.add(back)

    await callback_query.message.edit_text(top_click_str, parse_mode='HTML', reply_markup=markup)

@dp.callback_query_handler(lambda call: call.data == "my_balance")
async def show_referrals(call: types.CallbackQuery):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    channel_ids = get_channels_db()


    if not await check_subscription(user_id, chat_id, channel_ids):
        try:
            await call.message.delete()
        except (MessageCantBeDeleted, MessageToDeleteNotFound):
            pass
        await call.answer(t(user_id, "not_subscribed"), show_alert=True)
        return

    user_data = get_user(call.from_user.id)
    full_name = escape(call.from_user.full_name)
    referrals = get_referrals(user_id)
    weekly_referrals = get_referrals_count_week(user_id)
    page = 1
    referrals_text, total_pages = generate_referrals_text(referrals, page)
    stars = user_data[2]

    exchange_status = "✅ <b>Доступен</b>" if weekly_referrals >= REF_VIVOD_MIN else "❌ <b>Не доступен</b>"

    admin_contact_button = InlineKeyboardButton(
        "Связаться с администратором", url=f"https://t.me/{SUP_LOGIN}"
    )
    keyboard = InlineKeyboardMarkup(row_width=1).add(admin_contact_button)

    if is_user_blocked(call.from_user.id):
        await call.message.edit_text(
            "❌ <b>Вы заблокированы</b> и не можете выполнить это действие.\n\n"
            "Если у вас есть вопросы или вы хотите обсудить ситуацию, "
            "пожалуйста, свяжитесь с администратором через кнопку ниже.",
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        return
    else:
        main_text = (
            f"✨ <b>Профиль</b>\n"
            f"──────────────\n"
            f"👤 <b>Имя:</b> {full_name}\n"
            f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
            f"──────────────\n"
            f"💰 <b>Баланс:</b> {stars:.2f}⭐️\n"
            f"👥 <b>Всего рефералов:</b> {len(referrals)}\n"
            f"📆 <b>За неделю:</b> {weekly_referrals}\n"
            f"──────────────\n"
            f"📜 <b>Реферальный список:</b>\n"
            f"{referrals_text}\n"
            f"──────────────\n"
            f"🔄 <b>Обмен звезд:</b> {exchange_status}\n"
            f"──────────────\n"
            f"<i>⬇️ Используй кнопки ниже для действий.</i>"
        )

        buttons = generate_pagination_buttons(page, total_pages, user_id)
        buttons.add()

        if not hasattr(call.message, 'is_edit'):
            image = "image/profile.jpg"
            with open(image, "rb") as photo:
                try:
                    await call.message.delete()
                except (MessageCantBeDeleted, MessageToDeleteNotFound):
                    pass

                await call.message.answer_photo(
                    photo=photo,
                    caption=main_text,
                    reply_markup=buttons,
                    parse_mode="HTML"
                )
        else:
            await call.message.edit_caption(
                caption=main_text,
                reply_markup=buttons,
                parse_mode="HTML"
            )


@dp.callback_query_handler(lambda call: call.data == "faq")
async def show_referrals(call: types.CallbackQuery):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    channel_ids = get_channels_db()

    if not await check_subscription(user_id, chat_id, channel_ids):
        try:
            await call.message.delete()
        except (MessageCantBeDeleted, MessageToDeleteNotFound):
            pass
        await call.answer(t(user_id, "not_subscribed"), show_alert=True)
        return

    user_data = get_user(call.from_user.id)
    user_id = call.from_user.id
    full_name = escape(call.from_user.full_name)
    referrals = get_referrals(user_id)
    page = 1
    referrals_text, total_pages = generate_referrals_text(referrals, page)
    stars = user_data[2]

    admin_contact_button = InlineKeyboardButton(
            "Связаться с администратором", url=f"https://t.me/{SUP_LOGIN}"
        )
    keyboard = InlineKeyboardMarkup(row_width=1).add(admin_contact_button)
    if is_user_blocked(call.from_user.id):
        await call.message.edit_text(
            "❌ <b>Вы заблокированы</b> и не можете выполнить это действие.\n\n"
            "Если у вас есть вопросы или вы хотите обсудить ситуацию, "
            "пожалуйста, свяжитесь с администратором через кнопку ниже.",
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        return
    else:
        main_text = (
            f"""
<b>❓ Часто задаваемые вопросы (FAQ):</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<blockquote>🔸 <b>Как пользоваться ботом и зарабатывать звезды?</b>
👉 Ознакомься с подробным руководством по <a href='{TELEGRAPH1}'>этой ссылке</a>.

🔸 <b>Как вывести звезды?</b>
👉 Инструкцию по выводу звёзд ты найдёшь на <a href='{TELEGRAPH2}'>этой странице</a>.</blockquote>

❗ <b>Обратите внимание:</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<blockquote>Заявка может быть отклонена, если вы не подписаны на какой-либо канал или чат проекта.
📩 В таком случае свяжитесь с <a href='t.me/{SUP_LOGIN}'>Администрацией</a>, указав:
— Ссылку на пост с выплатой
— Ваш ID из бота (указан в '👤 Профиль')</blockquote>
""")
        markup = InlineKeyboardMarkup(row_width=2)
        back = InlineKeyboardButton(t(user_id, 'btn_back'), callback_data="back_main")
        markup.add(back)
        image = "image/faq.jpg"
        try:
            await call.message.delete()
        except (MessageCantBeDeleted, MessageToDeleteNotFound):
            pass
        with open(image, "rb") as photo:
            await call.message.answer_photo(photo=photo,caption=main_text, reply_markup=markup)

@dp.callback_query_handler(lambda call: call.data == "enter_promocode")
async def prompt_for_promocode(call: types.CallbackQuery):
    image = "image/promo.jpg"
    try:
        await call.message.delete()
    except (MessageCantBeDeleted, MessageToDeleteNotFound):
        pass

    with open(image, "rb") as photo:
        await call.message.answer_photo(photo=photo, caption=
        f"✨ Для получения звезд на ваш баланс введите промокод:\n"
        f"<i>*Найти промокоды можно в <a href='{LINK_1}'>канале</a> и <a href='{LINK_2}'>чате</a></i>")

    await PromoCodeState.waiting_for_promocode.set()

@dp.message_handler(state=PromoCodeState.waiting_for_promocode)
async def process_promocode_entry(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    promocode = message.text.strip()
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("""
        SELECT reward, max_uses, min_referrals 
        FROM promocodes 
        WHERE promocode = ?
    """, (promocode,))
    promo_data = cursor.fetchone()
    conn.close()
    if promo_data is None:
        await message.answer("❌ <b>Неверный промокод</b> или он уже недоступен.", parse_mode="HTML")
        await show_main_menu(message, user_id, edit=False)
        await state.finish()
        return
    reward, max_uses, min_referrals = promo_data
    referrals = get_referrals(user_id)
    if len(referrals) < min_referrals:
        await message.answer(
            f"❌ Для активации этого промокода требуется минимум <b>{min_referrals}</b> рефералов.", 
            parse_mode="HTML"
        )
        await show_main_menu(message, user_id, edit=False)
        await state.finish()
        return
    if check_promocode_usage(user_id, promocode):
        await message.answer("❌ <b>Вы уже активировали этот промокод.</b>", parse_mode="HTML")
        await show_main_menu(message, user_id, edit=False)
        await state.finish()
        return
    if max_uses <= 0:
        await message.answer("❌ <b>Этот промокод больше недоступен.</b>", parse_mode="HTML")
        await show_main_menu(message, user_id, edit=False)
        await state.finish()
        return
    add_promocode_usage(user_id, promocode)
    decrement_promocode_uses(promocode)
    add_user_stars(user_id, reward)
    await message.answer(
        f"✅ <b>Промокод успешно активирован!</b>\n🎉 Вы получили <b>{reward}⭐️</b>.", 
        parse_mode="HTML"
    )
    await show_main_menu(message, user_id, edit=False)
    await state.finish()

@dp.message_handler(state=PromoCodeState.waiting_for_promocode)
async def handle_promocode(message: types.Message, state: FSMContext):
    promocode = message.text.strip()
    user_id = message.from_user.id

    if check_promocode_usage(user_id, promocode):
        await message.answer(
        f"<b>❌ Ой! Этот промокод уже был использован</b>")
        await show_main_menu(message, user_id, edit=False)
    else:
        reward = get_promocode_reward(promocode)

        if reward is not None:
            add_stars(user_id, reward)
            add_promocode_usage(user_id, promocode)

            await message.answer(
                f"<b>🎉 Поздравляем! Промокод успешно активирован!</b> \n"
                f"<b>Вам начислено</b> {reward}⭐️.\n"
            )
            await show_main_menu(message, user_id, edit=False)
        else:
            await message.answer(
                f"<b>❌ Упс! Промокод не найден или он неверен</b>\n")
            await show_main_menu(message, user_id, edit=False)
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith("referrals_page:"))
async def paginate_referrals(callback_query: types.CallbackQuery):
    user_data = get_user(callback_query.from_user.id)
    user_id = callback_query.from_user.id
    full_name = callback_query.from_user.full_name
    referrals = get_referrals(user_id)
    stars = user_data[2]
    page = int(callback_query.data.split(":")[1])
    referrals_text, total_pages = generate_referrals_text(referrals, page)

    main_text = (
        f"✨ <b>Профиль</b>\n"
        f"──────────────\n"
        f"👤 <b>Имя:</b> {full_name}\n"
        f"🆔 <b>ID:</b> <code>{user_id}</code>\n"
        f"──────────────\n"
        f"💰 <b>Баланс:</b> {stars:.2f}⭐️\n"
        f"👥 <b>Рефералов:</b> {len(referrals)}\n"
        f"──────────────\n"
        f"📜 <b>Реферальный список:</b>\n"
        f"{referrals_text}\n"
        f"──────────────\n"
        f"<i>⬇️ Используй кнопки ниже для действий.</i>"
    )

    buttons = generate_pagination_buttons(page, total_pages, user_id)
    await callback_query.message.edit_caption(caption=main_text, reply_markup=buttons)


@dp.callback_query_handler(lambda c: c.data in ["earn_stars", "withdraw_stars_menu", "tasks"])
async def handle_main_menu_actions(call: types.CallbackQuery):
    user_id = call.from_user.id
    chat_id = call.message.chat.id 
    channel_ids = get_channels_db()

    if not await check_subscription(user_id, chat_id, channel_ids):
        try:
            await call.message.delete()
        except (MessageCantBeDeleted, MessageToDeleteNotFound):
            pass
        await call.answer(t(user_id, "not_subscribed"), show_alert=True)
        return
    
    admin_contact_button = InlineKeyboardButton(
            "Связаться с администратором", url=f"https://t.me/{SUP_LOGIN}"
        )
    keyboard = InlineKeyboardMarkup(row_width=1).add(admin_contact_button)
    if is_user_blocked(call.from_user.id):
        await call.message.edit_text(
            "❌ <b>Вы заблокированы</b> и не можете выполнить это действие.\n\n"
            "Если у вас есть вопросы или вы хотите обсудить ситуацию, "
            "пожалуйста, свяжитесь с администратором через кнопку ниже.",
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        return
    else:
        user_id = call.from_user.id
        user_data = get_user(user_id)

        admin_contact_button = InlineKeyboardButton(
                "Связаться с администратором", url=f"https://t.me/{SUP_LOGIN}"
            )
        keyboard = InlineKeyboardMarkup(row_width=1).add(admin_contact_button)
        if is_user_blocked(call.from_user.id):
            await call.message.edit_text(
                "❌ <b>Вы заблокированы</b> и не можете выполнить это действие.\n\n"
                "Если у вас есть вопросы или вы хотите обсудить ситуацию, "
                "пожалуйста, свяжитесь с администратором через кнопку ниже.",
                reply_markup=keyboard,
                parse_mode='HTML'
            )
            return
        else:
            if not user_data:
                await call.message.edit_text(t(user_id, 'no_registration'))
                return

            ref_link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
            back_button = InlineKeyboardButton(t(user_id, 'btn_back'), callback_data="back_main")

            if call.data == "earn_stars":
                user_id = call.from_user.id
                chat_id = call.message.chat.id
                channel_ids = get_channels_db()

                if not await check_subscription(user_id, chat_id, channel_ids):
                    try:
                        await call.message.delete()
                    except (MessageCantBeDeleted, MessageToDeleteNotFound):
                        pass
                    await call.answer(t(user_id, "not_subscribed"), show_alert=True)
                    return
                share = InlineKeyboardButton(text='👉 Отправить приглашение', switch_inline_query =f'https://t.me/{USER_BOT}?start={user_id}')
                
                markup = InlineKeyboardMarkup().add(share).add(back_button)
                image = "image/referalka.jpg"
                try:
                    await call.message.delete()
                except (MessageCantBeDeleted, MessageToDeleteNotFound):
                    pass
                with open(image, "rb") as photo:
                    await call.message.answer_photo(
                        photo=photo,
                        caption=t(call.from_user.id, 'earn_stars_text').format(ref_link=ref_link),
                        reply_markup=markup
                    )

            elif call.data == "withdraw_stars_menu":
                user_id = call.from_user.id
                chat_id = call.message.chat.id
                channel_ids = get_channels_db()

                if not await check_subscription(user_id, chat_id, channel_ids):
                    try:
                        await call.message.delete()
                    except (MessageCantBeDeleted, MessageToDeleteNotFound):
                        pass
                    await call.answer(t(user_id, "not_subscribed"), show_alert=True)
                    return

                stars = user_data[2]
                markup = InlineKeyboardMarkup(row_width=2)

                amounts = [
                    (15, "🧸", 5170233102089322756),
                    (15, "💝", 5170145012310081615),
                    (25, "🌹", 5168103777563050263),
                    (25, "🎁", 5170250947678437525),
                    (50, "🍾", 6028601630662853006),
                    (50, "🚀", 5170564780938756245),
                    (50, "💐", 5170314324215857265),
                    (50, "🎂", 5170144170496491616),
                    (100, "🏆", 5168043875654172773),
                    (100, "💍", 5170690322832818290),
                    (100, "💎", 5170521118301225164),
                    (1700, "📱", None)
                ]

                for i in range(0, len(amounts), 2):
                    row = []
                    if i < len(amounts):
                        amt, emoji, star_gift_id = amounts[i]
                        if amt == 1700:
                            pass
                        else:
                            row.append(InlineKeyboardButton(text=f"{amt} ⭐️ ({emoji})", callback_data=f"withdraw:{amt}:{star_gift_id}"))

                    if i + 1 < len(amounts):
                        amt, emoji, star_gift_id = amounts[i + 1]
                        if amt == 1700:
                            pass
                        else:
                            row.append(InlineKeyboardButton(text=f"{amt} ⭐️ ({emoji})", callback_data=f"withdraw:{amt}:{star_gift_id}"))
                    
                    markup.row(*row)

                markup.add(InlineKeyboardButton(text=f"Telegram Premium 6мес. (1700⭐️)", callback_data="withdraw:premium"))
                markup.add(back_button)
                image2 = "image/obmen.jpg"
                try:
                    await call.message.delete()
                except (MessageCantBeDeleted, MessageToDeleteNotFound):
                    pass

                with open(image2, "rb") as photo:
                    await call.message.answer_photo(
                        photo=photo,
                        caption=f"""
<b>🔸 У тебя на счету:</b> <code>{stars:.2f}</code>⭐️

<b>‼️ Для обмена звёзд требуется {REF_VIVOD_MIN} рефералов за неделю</b>
<blockquote>*Ваше кол-во посмотреть можно в профиле</blockquote>

<b>Выбери подарок для обмена звёзд из доступных вариантов ниже:</b>
            """,
            reply_markup=markup
        )
            elif call.data == "tasks":
                user_id = call.from_user.id
                chat_id = call.message.chat.id
                channel_ids = get_channels_db()

                tasks = get_tasks_for_user(user_id)
                if not tasks:
                    markup = InlineKeyboardMarkup().add(back_button)
                    image = "image/task.jpg"
                    try:
                        await call.message.delete()
                    except (MessageCantBeDeleted, MessageToDeleteNotFound):
                        pass
                    with open(image, "rb") as photo:
                        await call.message.answer_photo(photo=photo, caption=t(user_id, 'no_tasks'), reply_markup=markup)
                else:
                    try:
                        task_id, ch_id, rew, completed_count, max_completions, requires_subscription, task_type = tasks[0]
                    except ValueError:
                        task_id, ch_id, rew = tasks[0]
                        completed_count, max_completions, requires_subscription, task_type = 0, 10, 1, 'sub'

                    print(f"Задание: {task_id}, Канал: {ch_id}, Награда: {rew}, Тип задания: {task_type}, требуется подписка: {requires_subscription}")

                    if task_type == "nosub":
                        print("Тип задания: nosub")
                        invite_link = ch_id
                        subscribe_btn = InlineKeyboardButton("🔗 Выполнить задание", url=f"{ch_id}")
                        check_btn = InlineKeyboardButton("✅ Выполнил задание", callback_data=f"task_check:{task_id}")
                        chat_title = 'Ссылка на канал/видео'
                    else:
                        print(f"Тип задания: {task_type}, Канал: {ch_id}")  

                        try:
                            chat = await bot.get_chat(ch_id)
                            chat_title = chat.title
                        except Exception as e:
                            chat_title = "Неизвестный канал"
                            print(f"Ошибка получения информации о чате {ch_id}: {e}")

                        invite_link = await create_temp_invite_link(ch_id)

                        subscribe_btn = InlineKeyboardButton("✅ Подписаться на канал", url=invite_link)
                        check_btn = InlineKeyboardButton("🔎 Проверить подписку", callback_data=f"task_check:{task_id}")

                        if isinstance(ch_id, int):
                            invite_link = await create_temp_invite_link(ch_id)
                        else:
                            invite_link = ch_id

                        subscribe_btn = InlineKeyboardButton("✅ Подписаться на канал", url=invite_link)
                        check_btn = InlineKeyboardButton("🔎 Проверить подписку", callback_data=f"task_check:{task_id}")

                    markup = InlineKeyboardMarkup()
                    markup.add(subscribe_btn)
                    markup.add(check_btn)
                    markup.add(back_button)
                    image = "image/task.jpg"
                    try:
                        await call.message.delete()
                    except (MessageCantBeDeleted, MessageToDeleteNotFound):
                        pass
                    with open(image, "rb") as photo:
                        if task_type == "nosub":
                            print(f"Отправляем сообщение с типом задания 'nosub', Ссылка: {invite_link}, Награда: {rew}")
                            await call.message.answer_photo(photo=photo, caption=
                                f"✨ <b>Новое задание!</b> ✨\n\n"
                                f"🔗 <b>Ссылка на задание:</b> {invite_link}\n"
                                f"💎 <b>Награда:</b> {rew} ⭐\n\n"
                                f"📌 Для получения награды выполните задание, нажав на кнопку ниже.",
                                reply_markup=markup,
                                parse_mode="HTML"
                            )
                            print({invite_link})
                        else:
                            print(f"Отправляем сообщение с типом задания 'sub', Канал: {chat_title}, Ссылка: {invite_link}, Награда: {rew}")
                            await call.message.answer_photo(photo=photo, caption=
                                f"✨ <b>Новое задание!</b> ✨\n\n"
                                f" <b>Канал/группа:</b> <a href='{invite_link}'>{chat_title}</a>\n"
                                f"🔗 <b>Ссылка если не работает кнопка:</b> {invite_link}\n"
                                f"💎 <b>Награда:</b> {rew} ⭐\n\n"
                                f"📌 Для получения награды выполните задание, нажав на кнопку ниже.",
                                reply_markup=markup,
                                parse_mode="HTML"
                            )
                            print({invite_link})


async def create_temp_invite_link(channel_id):
    try:
        invite_link = (await bot.create_chat_invite_link(channel_id, member_limit=1)).invite_link
        return invite_link
    except:
        return f"https://t.me/c/{abs(channel_id)}"
    
from datetime import datetime, timedelta
import sqlite3



@dp.callback_query_handler(lambda c: c.data.startswith("task_check:"))
async def handle_task_check(call: types.CallbackQuery):
    user_id = call.from_user.id
    task_id = int(call.data.split(":")[1])

    print(f"Получена команда для проверки задания ID: {task_id} от пользователя {user_id}")

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    task = cursor.execute(
        'SELECT channel_id, reward, completed_count, max_completions, requires_subscription, task_type FROM tasks WHERE id=? AND active=1',
        (task_id,)
    ).fetchone()

    conn.close()

    if not task:
        print(f"Задание с ID {task_id} не найдено или не активно.")
        await call.answer("Задание не найдено или не активно", show_alert=True)
        return

    if user_completed_task(user_id, task_id):
        print(f"Пользователь {user_id} уже выполнил задание ID {task_id}.")
        await call.answer("Вы уже выполнили это задание!", show_alert=True)
        return

    channel_id, reward, completed_count, max_completions, requires_subscription, task_type = task

    print(f"Задание ID {task_id}: Тип = {task_type}, Канал = {channel_id}, Награда = {reward}, Выполнено = {completed_count}/{max_completions}, Требуется подписка = {requires_subscription}")

    if completed_count >= max_completions:
        print(f"Задание ID {task_id} больше не доступно, так как достигнуто максимальное количество выполнений.")
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('DELETE FROM tasks WHERE id=?', (task_id,))
        conn.commit()
        conn.close()
        await call.answer("Это задание больше не доступно!", show_alert=True)
        return

    if task_type == "nosub":
        print(f"Задание ID {task_id} типа 'nosub'. Немедленно засчитываем выполнение без проверки подписки.")
        final_reward = 1.0 if is_lucky_time_now() else reward
        increment_stars(user_id, final_reward)
        mark_task_completed(user_id, task_id)

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE tasks SET completed_count = completed_count + 1 WHERE id=?',
            (task_id,)
        )
        if completed_count + 1 >= max_completions:
            cursor.execute('DELETE FROM tasks WHERE id=?', (task_id,))
        conn.commit()
        conn.close()

        print(f"Задание ID {task_id} типа 'nosub' успешно выполнено. Пользователь {user_id} получил {final_reward} ⭐!")
        await call.answer(f"✅ Вы получили {final_reward} ⭐!", show_alert=True)

    elif task_type == "sub":
        print(f"Задание ID {task_id} типа 'sub'. Проверяем подписку.")
        if requires_subscription:
            try:
                chat_member = await bot.get_chat_member(channel_id, user_id)
                if chat_member.status not in ['member', 'administrator', 'creator']:
                    print(f"Пользователь {user_id} не подписан на канал {channel_id}.")
                    await call.answer("❌ Вы не подписаны!", show_alert=True)
                    return
            except:
                print(f"Ошибка при проверке подписки пользователя {user_id} на канал {channel_id}.")
                await call.answer("Ошибка проверки подписки", show_alert=True)
                return

        final_reward = 1.0 if is_lucky_time_now() else reward
        increment_stars(user_id, final_reward)
        mark_task_completed(user_id, task_id)

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute(
            'UPDATE tasks SET completed_count = completed_count + 1 WHERE id=?',
            (task_id,)
        )
        if completed_count + 1 >= max_completions:
            cursor.execute('DELETE FROM tasks WHERE id=?', (task_id,))
        conn.commit()
        conn.close()

        print(f"Задание ID {task_id} типа 'sub' успешно выполнено. Пользователь {user_id} получил {final_reward} ⭐!")
        await call.answer(f"✅ Вы получили {final_reward} ⭐!", show_alert=True)

    try:
        await call.message.delete()
    except (MessageCantBeDeleted, MessageToDeleteNotFound):
        pass

    await show_main_menu(call.message, user_id, edit=False)


@dp.callback_query_handler(lambda c: c.data.startswith("withdraw:"))
async def handle_withdraw(call: types.CallbackQuery):
    user_id = call.from_user.id
    chat_id = call.message.chat.id  
    channel_ids = get_channels_db()  
    count_refss = get_referrals_count_week(user_id)

    amounts = [
        (15, "🧸", 5170233102089322756),
        (15, "💝", 5170145012310081615),
        (25, "🌹", 5168103777563050263),
        (25, "🎁", 5170250947678437525),
        (50, "🍾", 6028601630662853006),
        (50, "🚀", 5170564780938756245),
        (50, "💐", 5170314324215857265),
        (50, "🎂", 5170144170496491616),
        (100, "🏆", 5168043875654172773),
        (100, "💍", 5170690322832818290),
        (100, "💎", 5170521118301225164),
        (1700, "📱", None)
    ]

    emoji = None
    amt = None
    star_gift_id = None

    try:
        amt_data = call.data.split(":")
        amt = int(amt_data[1])
        star_gift_id = int(amt_data[2]) if len(amt_data) > 2 else None

        for amount, item_emoji, gift_id in amounts:
            if amt == amount and (gift_id == star_gift_id or gift_id is None):
                emoji = item_emoji
                break

    except (ValueError, IndexError):
        await call.answer("Ошибка: неверный формат данных.", show_alert=True)
        return

    if count_refss < REF_VIVOD_MIN:
        await call.answer(f"❌ Для вывода надо минимум {REF_VIVOD_MIN} рефералов за текущую неделю! У тебя {count_refss}", show_alert=True)
        return

    if not await check_subscription(user_id, chat_id, channel_ids):
        try:
            await call.message.delete()
        except (MessageCantBeDeleted, MessageToDeleteNotFound):
            pass
        await call.answer(t(user_id, "not_subscribed"), show_alert=True)
        return

    user_data = get_user(user_id)
    if not user_data:
        await call.answer(t(user_id, 'no_registration'), show_alert=True)
        return

    (id, username, stars, count_refs, referral_id, withdrawn, lang, ref_rewarded,
        second_level_rewards, last_click_time, last_gift_time, click_count, gift_count, registration_time, *extra) = user_data

    if amt > stars:
        await call.answer(t(user_id, 'not_enough_stars'), show_alert=True)
        return

    try:
        withdraw_stars(user_id, amt)

        await call.answer(t(user_id, 'withdraw_success'), show_alert=True)

        request_id = get_next_withdraw_request_id()

        def format_datetime(dt):
            if dt:
                try:
                    dt_obj = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
                    return dt_obj.strftime("%d/%m/%y %H:%M")
                except ValueError:
                    return "Неверный формат"
            return "—"

        formatted_registration_time = format_datetime(registration_time)

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute(""" 
            SELECT id, username, registration_time FROM users 
            WHERE referral_id = ? 
            ORDER BY registration_time DESC 
            LIMIT 15
        """, (user_id,))
        last_refs = cursor.fetchall()
        conn.close()

        refs_text = "\n".join([f"• @{ref[1]} | <code>{ref[0]}</code> | <code>{format_datetime(ref[2])}</code>"
            if ref[1] else f"• <code>{ref[0]}</code> | <code>{format_datetime(ref[2])}</code>"
            for ref in last_refs
        ]) or "Нет рефералов"

        inline_keyboard = InlineKeyboardMarkup(row_width=2)
        inline_keyboard.row(
            InlineKeyboardButton("✅ Отправить", callback_data=f"paid:{user_id}:{amt}:{emoji}:{request_id}"),
            InlineKeyboardButton("🚫 Отказать", callback_data=f"denied:{call.message.message_id}")
        )
        inline_keyboard.add(
            InlineKeyboardButton("👤 Профиль пользователя", url=f"tg://user?id={user_id}")
        )
        try:
            await asyncio.sleep(0.035)
            await bot.send_message(
                CHANEL_ID,
                f"<b>✅ Запрос на обмен №{request_id}</b>\n\n"
                f"👤 Пользователь: @{username or '—'} | ID: {user_id}\n"
                f"💫 Количество: <code>{amt}</code>⭐️ [{emoji}]\n\n"
                f"🔄 Статус: <b>Ожидает обработки ⚙️</b>\n\n",
                reply_markup=inline_keyboard
            )
            print("DEBUG: Успешно отправлено в канал")
        except Exception as e:
            print(f"Ошибка при отправке в канал: {e}")
        await asyncio.sleep(0.035)
        await bot.send_message(
            LOG_VIVOD_CHANEL,
            f"<b>✅ Запрос на вывод №{request_id}</b>\n\n"
            f"👤 Пользователь: @{username or '—'} | ID: <code>{user_id}</code>\n"
            f"💫 Количество: <code>{amt}</code>⭐️ {emoji}\n\n"
            f"📊 Статистика:\n"
            f"👥 Рефералы: <b>{count_refss}</b>\n"
            f"💰 Выведено: <b>{withdrawn + amt}⭐️</b>\n"
            f"🖱 Клики: <b>{click_count}</b>\n"
            f"🎁 Получено подарков: <b>{gift_count}</b>\n"
            f"📅 Дата регистрации: <code>{formatted_registration_time}</code>\n\n"
            f"👤 Последние 5 рефералов:\n{refs_text}\n\n",
            parse_mode="HTML"
        )

        await asyncio.sleep(0.035)
        await show_main_menu(call.message, user_id)
        
        await asyncio.sleep(0.035)
        await bot.send_message(
            user_id,
            f"✅ <b>Твой запрос на вывод №{request_id}</b> успешно добавлен в очередь.\n"
            f"🔍 Следи за статусом в канале: "
            f"<a href='{LINK_3}'><b>Выплаты 🎁</b></a>\n\n"
            f"<blockquote>‼️ Чтобы выплата прошла, быстрее и автоматически напиши любое сообщение ему: @{SUP_LOGIN}</blockquote>",
            parse_mode="HTML", disable_web_page_preview=True
        )

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute(''' 
        INSERT INTO withdraw_requests (user_id, amount, status)
        VALUES (?, ?, ?)''', (user_id, amt, 'pending'))
        conn.commit()
        conn.close()
        print("DEBUG: Запрос на вывод успешно записан в БД")

    except Exception as e:
        await call.answer(f"Произошла ошибка: {e}", show_alert=True)
        return

@dp.callback_query_handler(lambda c: c.data.startswith("paid:"))
async def handle_paid_status(call: types.CallbackQuery):
    data_parts = call.data.split(":")
    
    if len(data_parts) < 5:
        await call.answer("Ошибка: некорректные данные callback.", show_alert=True)
        print(f"Callback data received: {call.data}")
        return
    
    user_id = int(data_parts[1])
    amt = int(data_parts[2])
    emoji = data_parts[3]
    request_id = data_parts[4]
    print(f"Callback data received: {call.data}")
    
    chat_member = await bot.get_chat_member(call.message.chat.id, call.from_user.id)
    
    if chat_member.status not in ["administrator", "creator"]:
        await call.answer("🚫 У вас нет прав для выполнения этого действия.", show_alert=True)
        return
    
    star_gift_ids = {
        (15, "🧸"): 5170233102089322756,  
        (15, "💝"): 5170145012310081615,  
        (25, "🌹"): 5168103777563050263,  
        (25, "🎁"): 5170250947678437525,  
        (50, "🍾"): 6028601630662853006,  
        (50, "🚀"): 5170564780938756245,  
        (50, "💐"): 5170314324215857265,  
        (50, "🎂"): 5170144170496491616,  
        (100, "🏆"): 5168043875654172773,  
        (100, "💍"): 5170690322832818290,  
        (100, "💎"): 5170521118301225164,
        (1700, "📱"): None
    }

    star_gift_id = star_gift_ids.get((amt, emoji))
    
    if not star_gift_id:
        await call.answer(f"Ошибка: Невозможно отправить подарок для суммы {amt}⭐️ и эмодзи {emoji}.", show_alert=True)
        return

    try:
        await send_gift_with_retry(app, user_id, star_gift_id)
        print(app, user_id, star_gift_id)
        
        await call.message.edit_text(
            call.message.text.replace("Ожидает обработки ⚙️", f"<b>Подарок отправлен 🎁\n\n<a href='{LINK_1}'>Основной канал</a> | <a href='{LINK_2}'>Чат</a> | <a href='{LINK_BOT}'> Бот</a> </b>"),
            parse_mode="HTML"
        )
        
        await record_spent_stars(amt)

        await bot.send_message(
            user_id,
            f"🎉 <b>Вывод №{request_id} успешно выполнен!</b>\n"
            f"💸 Сумма: <code>{amt}</code>⭐️ подарок отправлен от <a href='https://t.me/{SUP_LOGIN}'>Бот [Выплаты]</a> \n"
            f"🙏 Будем благодарны, если оставишь отзыв: <a href='{LINK_5}'>(жми)</a>",
            parse_mode="HTML",
            disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup().add(
                InlineKeyboardButton("🌟 Оставить отзыв", url=LINK_5)
            )
        )
        
        await call.answer("Статус обновлен на Подарок отправлен 🎁", show_alert=True)

    except Exception as e:
        for admin in admins:
            if "BALANCE_TOO_LOW" in str(e):
                await bot.send_message(admin,
                    f"🚨 Ошибка при отправке выплаты пользователю {user_id}.\n"
                    f"Причина: Недостаточно звезд на аккаунте!",
                )

async def send_gift_with_retry(app, user_id, star_gift_id, retries=0, max_retries=1):
    try:
        if not user_id:
            raise ValueError("Ошибка: user_id не может быть None.")
        if not star_gift_id:
            raise ValueError("Ошибка: star_gift_id не может быть None.")
        
        if isinstance(star_gift_id, str):
            star_gift_id = star_gift_id.encode()

        await app.send_gift(
            chat_id=user_id, 
            gift_id=star_gift_id
            )
        print(f"Выплата отправлена пользователю {user_id} с ID выплаты {star_gift_id}")
    except Exception as e:
        if retries < max_retries:
            print(f"Ошибка при отправке выплаты пользователю {user_id}: {e}. Повторная попытка через 5 секунд... (Попытка {retries + 1}/{max_retries})")
            await asyncio.sleep(5)
            await send_gift_with_retry(app, user_id, star_gift_id, retries + 1, max_retries)
        else:
            print(f"Ошибка при отправке выплаты пользователю {user_id}: {e}. Все попытки исчерпаны.")
            raise e

@dp.callback_query_handler(lambda c: c.data.startswith("denied:"))
async def handle_denied_status(call: types.CallbackQuery):
    message_id = int(call.data.split(":")[1])
    chat_member = await bot.get_chat_member(call.message.chat.id, call.from_user.id)
    if chat_member.status not in ["administrator", "creator"]:
        await call.answer("❌ У вас нет прав для выполнения этого действия.", show_alert=True)
        return

    try:
        await call.message.edit_text(
            call.message.text.replace(
                f"Ожидает обработки ⚙️", f"<b>Отказано 🚫\n\n<a href='{LINK_1}'>Основной канал</a> | <a href='{LINK_2}'>Чат</a> | <a href='{LINK_BOT}'> Бот</a> </b>"
                ),
            parse_mode="HTML"
        )
        await call.answer("Статус обновлен на Отказано 🚫", show_alert=True)
    except Exception as e:
        await call.answer("Ошибка при обновлении статуса.", show_alert=True)

@dp.message_handler(commands=['why'])
async def handle_why(message: types.Message):
    user_id = message.from_user.id
    ref_link = f"https://t.me/{(await bot.get_me()).username}?start={user_id}"
    if user_exists(user_id):
        await message.answer(t(user_id, 'why_stars').format(
            ref_link=ref_link,
            MAX_REF_REWARD_X2=MAX_REF_REWARD_X2,
            MIN_REF_REWARD=MIN_REF_REWARD,
            CLICK_MAX_REWARD_X2=CLICK_MAX_REWARD_X2,
            SUP_LOGIN=SUP_LOGIN
        ))
    else:
        await message.answer(t(user_id, 'no_registration'))

@dp.callback_query_handler(lambda c: c.data == "back_main")
async def back_to_main(call: types.CallbackQuery):
    user_id = call.from_user.id
    await show_main_menu(call.message, user_id, edit=True)

class AdminSetBalanceState(StatesGroup):
    waiting_for_balance = State()

from aiohttp.client_exceptions import ContentTypeError

async def get_subbalance():
    headers = {'Auth': REQUEST_API_KEY}
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post("https://api.subgram.ru/get-balance/", headers=headers) as response:
                try:
                    data = await response.json()
                except ContentTypeError:
                    return "Тех. работы, попробуйте позже."
                
                if data["status"] == "ok":
                    balance = data.get("balance", 0)
                    return balance
                else:
                    return None
    except Exception as e:
        return f"Ошибка при подключении: {str(e)}"

@dp.message_handler(commands=['adminpanel'])
async def adminpanel(message: types.Message):
    user_id = message.from_user.id
    if user_id in admins:
        subbalance = await get_subbalance()
        balances = await app.get_stars_balance()
        boosters_count = get_unique_users_count()

        user_stats = get_user_counts()
        total_users = user_stats["total"]
        daily_users = user_stats["daily"]
        monthly_users = user_stats["monthly"]
        day_spent = get_spent_stars_for_day()
        week_spent = get_spent_stars_for_week()
        month_spent = get_spent_stars_for_month()
        total_withdrawn = get_total_withdrawn()
        total_tasks = get_total_tasks()
        active_tasks = get_active_tasks()
        completed_tasks = get_completed_tasks()
        total_promocodes = get_total_promocodes()
        active_promocodes = get_active_promocodes()
        total_channels = get_total_channels()
        active_channels = get_active_channels()

        admin_markup = InlineKeyboardMarkup(row_width=2)
        search_id = InlineKeyboardButton(text="🔎 Информация о пользователе", callback_data="get_user_id")
        obnylenie = InlineKeyboardButton(text="🗑 Обнулить балансы всех юзеров", callback_data="obnylenie")
        dobavlenie  = InlineKeyboardButton(text="🎁 Выдать звезды всем юзерам", callback_data="dobavlenie")

        admin_promo = InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_promocode_added")
        show_promocodes = InlineKeyboardButton(text="📊 Список промокодов", callback_data="show_promocodes")
        admin_promo2 = InlineKeyboardButton(text="➖ Удалить промокод", callback_data="admin_promocode_delete")

        lucky_time_btn = InlineKeyboardButton(text="⏰ Счастливое время", callback_data='admin_lucky_time')
        mailing_btn = InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_mailing")
        add_channel_btn = InlineKeyboardButton(text="➕ Добавить канал", callback_data="admin_add_channel")
        list_channel_btn = InlineKeyboardButton(text="📚 Список каналов", callback_data="admin_get_channels")
        remove_channel_btn = InlineKeyboardButton(text="➖ Удалить канал", callback_data='admin_delete_channel')
        list_tasks_btn = InlineKeyboardButton(text="📋 Список заданий", callback_data="show_tasks")
        add_task_btn = InlineKeyboardButton(text="➕ Добавить задание", callback_data='admin_add_task')
        remove_task_btn = InlineKeyboardButton(text="➖ Удалить задание", callback_data='admin_remove_task')
        op_stat_btn = InlineKeyboardButton(text="📊 Показать статистику ОП", callback_data="show_stat_op")
        add_noop_btn = InlineKeyboardButton(text="⚠️ ОП без проверки", callback_data='op')
        taskslist_btn = InlineKeyboardButton(text="📊 Стата заданий", callback_data='taskslist')
        statlink_btn = InlineKeyboardButton("📊 Стата спецссылок", callback_data="show_link_stats")
        admin_db_btn =  InlineKeyboardButton(text="📦 База данных", callback_data='admin_db')
        spec_ref_btn = InlineKeyboardButton(text="🔗 Создать спецссылку", callback_data='gen_link')
        
        admin_markup.row(mailing_btn)
        admin_markup.row(search_id)
        admin_markup.row(obnylenie)
        admin_markup.row(dobavlenie)
        admin_markup.row(spec_ref_btn)
        admin_markup.row(admin_promo, show_promocodes, admin_promo2)
        admin_markup.row(add_channel_btn, list_channel_btn, remove_channel_btn)
        admin_markup.row(add_task_btn, list_tasks_btn, remove_task_btn)
        admin_markup.row(taskslist_btn, statlink_btn)
        admin_markup.row(admin_db_btn)
        admin_markup.row(add_noop_btn)
        admin_markup.row(op_stat_btn)
        admin_markup.row(lucky_time_btn)

        stats_message = (
    f"""
📊 <b>Админ-панель</b>

<b>🏦 Балансы</b>
<blockquote><b>⭐️ Звезд в юзерботе:</b> <code>{balances}</code>
<b>💶 Денег в subgram'e:</b> <code>{subbalance}</code></blockquote>

<b>💸 Выплачено:</b> <code>{total_withdrawn}⭐️</code>

<b>📊 Статистика потраченных звезд:</b>
<blockquote><b>🔹 За cегодня:</b> <code>{day_spent}⭐️</code>
<b>🔹 На этой неделе:</b> <code>{week_spent}⭐️</code>
<b>🔹 За месяц:</b> <code>{month_spent}⭐️</code></blockquote>

<b>👥 Пользователей:</b> 
<blockquote>За все время <code>{total_users}</code>
<b>📅 Новых за день:</b> <code>{daily_users}</code>
<b>📆 Новых за месяц:</b> <code>{monthly_users}</code></blockquote>

<b>🚀 Количество бустеров: <code>{boosters_count}</code></b>

<blockquote><b>📋 Задания:</b> <code>{total_tasks}</code>
<b>📚 Промокоды:</b> <code>{total_promocodes}</code>
<b>📡 ОП Каналы:</b> <code>{total_channels}</code></blockquote>
"""
)
        await message.answer(stats_message, reply_markup=admin_markup)

@dp.callback_query_handler(lambda c: c.data == "obnylenie")
async def process_reset_balances(callback_query: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(
        InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_reset"),
        InlineKeyboardButton("❌ Отмена", callback_data="cancel_reset")
    )

    await bot.send_message(callback_query.from_user.id, "Вы уверены, что хотите обнулить балансы?", reply_markup=keyboard)
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query_handler(lambda c: c.data == "confirm_reset")
async def confirm_reset_balances(callback_query: types.CallbackQuery):
    reset_user_balances()
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "✅ Балансы всех пользователей обнулены.")

@dp.callback_query_handler(lambda c: c.data == "cancel_reset")
async def cancel_reset_balances(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "❌ Обнуление балансов отменено.")

@dp.callback_query_handler(lambda c: c.data == "dobavlenie")
async def process_give_stars(callback_query: types.CallbackQuery):
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(callback_query.from_user.id, "Введите количество звёзд для выдачи:")
    await GiveStars.amount.set()

@dp.message_handler(state=GiveStars.amount)
async def process_stars_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        logging.info(f"Введено количество звёзд: {amount}")
        give_stars_to_all(amount)
        await message.answer(f"✅ Всем пользователям добавлено {amount} звёзд.")
        await state.finish()
    except ValueError:
        logging.error(f"Ошибка ввода: {message.text} не является числом.")
        await message.answer("❌ Введите корректное число.")

@dp.callback_query_handler(lambda c: c.data == "adminpanel")
async def show_admin_panel(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    if user_id in admins:
        user_count = get_user_count()
        total_withdrawn = get_total_withdrawn()

        admin_markup = InlineKeyboardMarkup(row_width=2)
        search_id = InlineKeyboardButton(text="🔎 Информация о пользователе", callback_data="get_user_id")
        obnylenie = InlineKeyboardButton(text="🗑 Обнулить балансы всех юзеров", callback_data="obnylenie")
        dobavlenie  = InlineKeyboardButton(text="🎁 Выдать звезды всем юзерам", callback_data="dobavlenie")

        admin_promo = InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_promocode_added")
        show_promocodes = InlineKeyboardButton(text="📊 Список промокодов", callback_data="show_promocodes")
        admin_promo2 = InlineKeyboardButton(text="➖ Удалить промокод", callback_data="admin_promocode_delete")

        lucky_time_btn = InlineKeyboardButton(text="⏰ Счастливое время", callback_data='admin_lucky_time')
        mailing_btn = InlineKeyboardButton(text="📨 Рассылка", callback_data="admin_mailing")
        add_channel_btn = InlineKeyboardButton(text="➕ Добавить канал", callback_data="admin_add_channel")
        list_channel_btn = InlineKeyboardButton(text="📚 Список каналов", callback_data="admin_get_channels")
        remove_channel_btn = InlineKeyboardButton(text="➖ Удалить канал", callback_data='admin_delete_channel')
        list_tasks_btn = InlineKeyboardButton(text="📋 Список заданий", callback_data="show_tasks")
        add_task_btn = InlineKeyboardButton(text="➕ Добавить задание", callback_data='admin_add_task')
        remove_task_btn = InlineKeyboardButton(text="➖ Удалить задание", callback_data='admin_remove_task')
        op_stat_btn = InlineKeyboardButton(text="📊 Показать статистику ОП", callback_data="show_stat_op")
        add_noop_btn = InlineKeyboardButton(text="⚠️ ОП без проверки", callback_data='op')
        taskslist_btn = InlineKeyboardButton(text="📊 Стата заданий", callback_data='taskslist')
        statlink_btn = InlineKeyboardButton("📊 Стата спецссылок", callback_data="show_link_stats")
        admin_db_btn =  InlineKeyboardButton(text="📦 База данных", callback_data='admin_db')
        spec_ref_btn = InlineKeyboardButton(text="🔗 Создать спецссылку", callback_data='gen_link')
        
        admin_markup.row(mailing_btn)
        admin_markup.row(search_id)
        admin_markup.row(obnylenie)
        admin_markup.row(dobavlenie)
        admin_markup.row(spec_ref_btn)
        admin_markup.row(admin_promo, show_promocodes, admin_promo2)
        admin_markup.row(add_channel_btn, list_channel_btn, remove_channel_btn)
        admin_markup.row(add_task_btn, list_tasks_btn, remove_task_btn)
        admin_markup.row(taskslist_btn, statlink_btn)
        admin_markup.row(admin_db_btn)
        admin_markup.row(add_noop_btn)
        admin_markup.row(op_stat_btn)
        admin_markup.row(lucky_time_btn)

        await callback_query.message.edit_text(
            t(user_id, 'admin_panel').format(user_count=user_count, total_withdrawn=total_withdrawn),
            reply_markup=admin_markup
        )
    else:
        await callback_query.answer("У вас нет доступа к панели администратора.")

@dp.callback_query_handler(lambda c: c.data == "show_tasks", state="*")
async def show_tasks(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if user_id not in admins:
        return

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id, channel_id, reward, active, task_type FROM tasks')
    tasks = cursor.fetchall()
    conn.close()

    keyboard = InlineKeyboardMarkup(row_width=1)

    if tasks:
        response_text = "<b>Выберите задание для удаления:</b>\n\n"

        for task in tasks:
            task_id, channel_id, reward, active, task_type = task
            status = "Активно" if active else "Не активно"
            task_type_str = "Без подписки" if task_type == "nosub" else "С подпиской"

            try:
                chat = await bot.get_chat(channel_id)
                channel_name = chat.title
            except Exception as e:
                channel_name = "Задание"

            button_text = f"{channel_name} | {reward}⭐️ | {status} | {task_type_str}"
            delete_button = InlineKeyboardButton(text=button_text, callback_data=f"delete_task_{task_id}")
            keyboard.add(delete_button)

    else:
        response_text = "<i>Задания не найдены.</i>"

    keyboard.add(InlineKeyboardButton(text="👑 Вернуться в админ-меню", callback_data="adminpanel"))

    await call.message.edit_text(response_text, reply_markup=keyboard, parse_mode="HTML")
    await call.answer()


@dp.callback_query_handler(lambda c: c.data.startswith("delete_task_"), state="*")
async def delete_task(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if user_id not in admins:
        await call.answer("❌ У вас нет прав для этого действия.")
        return

    task_id = int(call.data[len("delete_task_"):])

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT channel_id, task_type FROM tasks WHERE id = ?', (task_id,))
    task = cursor.fetchone()

    if task:
        channel_id, task_type = task
        print(f"Задание с ID {task_id} типа {task_type} удаляется. Канал: {channel_id}")

        cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
        conn.close()

        await call.answer(f"✅ Задание с ID {task_id} успешно удалено!")
    else:
        await call.answer("❌ Задание не найдено.")

    await show_tasks(call, state)


@dp.callback_query_handler(lambda c: c.data == "get_user_id")
async def ask_for_user_id(callback_query: CallbackQuery):
    await bot.send_message(callback_query.from_user.id, "Введите ID пользователя (только цифры):")
    await UserIDState.waiting_for_user_id.set()

@dp.message_handler(state=UserIDState.waiting_for_user_id)
async def process_user_id(message: types.Message, state: FSMContext):
    user_id = message.text.strip()

    if message.from_user.id not in admins:
        await message.answer("⛔ У вас нет доступа к этой команде.")
        await state.finish()
        return

    if not user_id.isdigit():
        await message.answer("❌ Пожалуйста, введите корректный числовой ID пользователя.")
        return

    user_id = int(user_id)

    try:
        user_info = await bot.get_chat(user_id) 
        current_username = user_info.username 
    except Exception as e:
        current_username = None

    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()

    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    user_data = cursor.fetchone()

    if user_data:
        (id, saved_username, stars, count_refs, referral_id, withdrawn, lang, ref_rewarded,
        second_level_rewards, last_click_time, last_gift_time, click_count, gift_count, registration_time, 
        *extra) = user_data

        if saved_username != current_username:
            cursor.execute("UPDATE users SET username = ? WHERE id = ?", (current_username, user_id))
            conn.commit()

        def format_datetime(dt):
            if dt:
                try:
                    try:
                        dt_obj = datetime.strptime(dt, "%Y-%m-%dT%H:%M:%S.%f")
                    except ValueError:
                        dt_obj = datetime.strptime(dt, "%Y-%m-%d %H:%M:%S")
                    return dt_obj.strftime("%d/%m/%y %H:%M")
                except ValueError:
                    return "Неверный формат"
            return "—"

        formatted_registration_time = format_datetime(registration_time)
        formatted_click_time = format_datetime(last_click_time)
        formatted_gift_time = format_datetime(last_gift_time)

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('SELECT is_blocked FROM block_status WHERE user_id = ?', (id,))
        block_status = cursor.fetchone()
        conn.close()

        if block_status and block_status[0] == 1:
            block_status_str = "🔴 Заблокирован"
        else:
            block_status_str = "🟢 Не заблокирован"

        profile_url = f"tg://user?id={user_id}"

        keyboard = InlineKeyboardMarkup()

        block_btn = InlineKeyboardButton(text="🔒 Заблокировать", callback_data=f"block_{id}")
        unblock_btn = InlineKeyboardButton(text="🔓 Разблокировать", callback_data=f"unblock_{id}")
        profile_btn = InlineKeyboardButton(text="👤 Перейти в профиль", url=profile_url)

        add_stars_btn = InlineKeyboardButton(text="➕ Добавить звезды", callback_data=f"add_stars_{id}")
        subtract_stars_btn = InlineKeyboardButton(text="➖ Списать звезды", callback_data=f"subtract_stars_{id}")

        clickup_btn = InlineKeyboardButton(text="🖱️ Настроить награду за клик", callback_data=f"set_click_reward")
        ref_reward_btn = InlineKeyboardButton(text="🔗 Настроить награду за рефералов", callback_data=f"set_ref_reward")

        keyboard.add(block_btn, unblock_btn)
        keyboard.add(add_stars_btn, subtract_stars_btn)
        keyboard.add(profile_btn)
        keyboard.add(clickup_btn)
        keyboard.add(ref_reward_btn)
        keyboard.add(InlineKeyboardButton(text="👑 Админ-меню", callback_data="adminpanel"))

        referrals = get_referrals_count(id)

        response = (
            f"🧾 <b>Информация о пользователе</b>:\n\n"
            f"👤 <b>ID пользователя:</b> <code>{id}</code>\n"
            f"📛 <b>Имя пользователя:</b> @{saved_username or '—'}\n"
            f"⭐️ <b>Звезды:</b> {stars:.2f}\n"
            f"💎 <b>Награды второго уровня:</b> {second_level_rewards}"
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👥 <b>Количество рефералов:</b> {referrals}\n"
            f"🔗 <b>ID реферера:</b> {referral_id or '—'}"
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>Выведено:</b> {withdrawn} 💵\n"
            f"🌍 <b>Язык:</b> {lang}"
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⏰ <b>Последний клик:</b> {formatted_click_time}\n"
            f"🎉 <b>Последний подарок:</b> {formatted_gift_time}"
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📅 <b>Дата регистрации:</b> {formatted_registration_time}\n"
            f"🖱️ <b>Количество кликов:</b> {click_count}\n"
            f"🎁 <b>Количество подарков:</b> {gift_count}"
            f"\n━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>Статус:</b> {block_status_str}\n\n"
            f"📊 <i>Информация актуальна на момент запроса.</i>"
        )

        try:
            await state.update_data(user_id=id)
            await message.answer(response, reply_markup=keyboard)
            await state.finish()
        except BadRequest as e:
            if "Button_user_privacy_restricted" in str(e):
                await message.answer("Пользователь ограничил доступ для ботов.")
                await state.finish()
            else:
                await message.answer(f"Произошла ошибка: {e}")
                await state.finish()
    else:
        keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("👑 Вернуться в админ-меню", callback_data="adminpanel"))
        response = "❌ Пользователь с таким ID не найден."
        await message.answer(response, reply_markup=keyboard)
        await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith("add_stars_") or c.data.startswith("subtract_stars_"))
async def action_select(callback_query: CallbackQuery, state: FSMContext):
    user_id = int(callback_query.data.split("_")[2])
    action = 'add' if callback_query.data.startswith("add_stars_") else 'subtract'

    await state.update_data(user_id=user_id, action=action)

    await UserIDState.waiting_for_star_amount.set()

    await bot.send_message(callback_query.from_user.id, "✨ Введи количество звезд, которое хочешь добавить или списать:")

@dp.message_handler(state=UserIDState.waiting_for_star_amount)
async def process_star_amount(message: types.Message, state: FSMContext):
    user_data = await state.get_data()

    if 'user_id' not in user_data:
        await message.answer("❗ Ошибка: не удалось получить ID пользователя. Пожалуйста, повторите действие.")
        return

    user_id = user_data['user_id']
    action = user_data['action']

    try:
        stars = float(message.text)
    except ValueError:
        await message.answer("❌ Ошибка: введено неверное количество звезд. Пожалуйста, введите число.")
        return

    if action == 'add':
        add_stars(user_id, stars)
        await bot.send_message(user_id, f"✨ <b>Администрация добавила тебе звезды!</b>\n"
                                       f"Ты получил <b>+{stars}</b>⭐️")
        await message.answer(f"Звезды успешно добавлены пользователю с ID {user_id}.")
    elif action == 'subtract':
        subtract_stars(user_id, stars)
        await bot.send_message(user_id, f"🔻 <b>Администрация списала звезды!</b>\n"
                                       f"Ты потерял <b>-{stars}</b>⭐️")
        await message.answer(f"Звезды успешно списаны с пользователя с ID {user_id}.")

    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith("block_"))
async def block_user(callback_query: types.CallbackQuery):
    if callback_query.from_user.id not in admins:
        await callback_query.reply("⛔ У вас нет доступа к этой команде.")
        return
    user_id = int(callback_query.data.split("_")[1])

    print(f"Начинаем блокировать пользователя {user_id}")

    if not block_user_in_db(user_id):
        await callback_query.answer("Пользователь уже заблокирован или произошла ошибка.")
        return

    await callback_query.answer("Пользователь заблокирован.")
    await callback_query.message.answer(f"Пользователь {user_id} заблокирован.")

@dp.callback_query_handler(lambda c: c.data.startswith("unblock_"))
async def unblock_user(callback_query: types.CallbackQuery):
    if callback_query.from_user.id not in admins:
        await callback_query.reply("⛔ У вас нет доступа к этой команде.")
        return
    user_id = int(callback_query.data.split("_")[1])

    print(f"Начинаем разблокировку пользователя {user_id}")

    if not unblock_user_in_db(user_id):
        await callback_query.answer("Пользователь уже не заблокирован или произошла ошибка.")
        return

    await callback_query.answer("Пользователь разблокирован.")
    await callback_query.message.answer(f"Пользователь {user_id} разблокирован.")

@dp.callback_query_handler(lambda call: call.data == "top_stars")
async def top_stars_handler(callback: CallbackQuery):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id
    channel_ids = get_channels_db()

    if not await check_subscription(user_id, chat_id, channel_ids):
        await callback.message.delete()
        await callback.answer(t(user_id, "not_subscribed"), show_alert=True)
        return
    
    admin_contact_button = InlineKeyboardButton(
            "Связаться с администратором", url=f"https://t.me/{SUP_LOGIN}"
        )
    keyboard = InlineKeyboardMarkup(row_width=1).add(admin_contact_button)
    if is_user_blocked(callback.from_user.id):
        await callback.message.edit_text(
            "❌ <b>Вы заблокированы</b> и не можете выполнить это действие.\n\n"
            "Если у вас есть вопросы или вы хотите обсудить ситуацию, "
            "пожалуйста, свяжитесь с администратором через кнопку ниже.",
            reply_markup=keyboard,
            parse_mode='HTML'
        )
        return
    else:
        data = get_top_users()
        if data:
            top_list = "\n".join(
                [f"✨ <b>{i + 1}.</b> <u>{username}</u> — <b>{value}</b> ⭐" for i, (username, value) in enumerate(data)]
            )
            keyboard = InlineKeyboardMarkup().add(create_back_button(callback.from_user.id))
            await callback.message.edit_text(
                f"🏆 <b>Топ-10 пользователей по звёздам:</b>\n\n{top_list}",
                parse_mode="HTML",
                reply_markup=keyboard
            )
        else:
            await callback.message.edit_text(
                "❌ <b>Данных для отображения пока нет.</b>",
                parse_mode="HTML"
            )

@dp.callback_query_handler(lambda c: c.data in ["admin_add_stars", "admin_remove_task", "admin_add_task", "admin_lucky_time", "admin_set_balance", 'admin_promocode_added', 'admin_info_id', 'admin_promocode_delete'])
async def admin_actions(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if user_id not in admins:
        await call.answer("Нет доступа", show_alert=True)
        return

    if call.data == "admin_add_stars":
        await call.message.edit_text(t(user_id, 'enter_user_id_stars'))
        await AdminAddStarsState.waiting_for_data.set()
    elif call.data == "admin_info_id":
        await call.message.edit_text(t(user_id, '✏️ Введи ID пользователя:'))
        await AdminSearchIdlState.waiting_for_message.set()
    elif call.data == "admin_add_task":
        markup = InlineKeyboardMarkup()
        markup.add(InlineKeyboardButton("✅ С проверкой подписки", callback_data="task_type:sub"))
        markup.add(InlineKeyboardButton("🔗 Без проверки подписки", callback_data="task_type:nosub"))
        await call.message.edit_text("Выбери тип задания:", reply_markup=markup)
        await AdminAddTaskState.waiting_for_task_type.set()
    elif call.data == "admin_remove_task":
        await call.message.edit_text("✏️ Введи ID канала/группы для удаления задания:")
        await AdminRemoveTaskState.waiting_for_channel_id.set()
    elif call.data == "admin_promocode_added":
        await call.message.edit_text("✏️ Введи <code>промокод</code>:<code>сумма</code>:<code>макс_использований</code>:<code>мин_рефералов</code>")
        await AdminAddPromoCodeState.waiting_for_data.set()
    elif call.data == "admin_promocode_delete":
        await call.message.edit_text("✏️ Введи промокод:")
        await AdminDeletePromoCodeState.waiting_for_promocode.set()
    elif call.data == "admin_lucky_time":
        start = datetime.utcnow()
        formatted_time = start.strftime("%d.%m %H:%M")
        set_lucky_time(start, 60)
        try:
            await bot.send_message(
                ADMIN_IDD,
f"""
🚨 <b>Счастливый час был успешно запущен!</b>
    
🕒 <b>Начало:</b> {formatted_time} МСК
⏳ <b>Продолжительность:</b> 1 час
""",
                parse_mode='HTML'
            )
        except Exception as e:
            print(f"Не удалось отправить сообщение админу: {e}")

@dp.callback_query_handler(lambda c: c.data == "show_promocodes", state="*")
async def show_promocodes(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if user_id not in admins:
        return

    promocodes = get_all_promocodes()

    response_text = "<b>📜 Доступные промокоды:</b>\n\n"

    keyboard = InlineKeyboardMarkup(row_width=1)

    if promocodes:
        for promocode, reward in promocodes:
            button = InlineKeyboardButton(text=f"{promocode} (❌ удалить)", callback_data=f"delete_{promocode}")
            keyboard.add(button)

        response_text += "<i>Нажмите на промокод, чтобы удалить его.</i>\n\n"
    else:
        response_text += "<i>Нет доступных промокодов.</i>"

    await call.message.edit_text(response_text, reply_markup=keyboard, parse_mode="HTML")


@dp.callback_query_handler(lambda c: c.data.startswith("delete_"), state="*")
async def delete_promocode(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if user_id not in admins:
        return

    promocode_to_delete = call.data[len("delete_"):]

    try:
        delete_promo(promocode_to_delete)

        promocodes = get_all_promocodes()

        response_text = "<b>📜 Доступные промокоды:</b>\n\n"

        keyboard = InlineKeyboardMarkup(row_width=1)

        if promocodes:
            for promocode, reward in promocodes:
                button = InlineKeyboardButton(text=f"{promocode} (❌ удалить)", callback_data=f"delete_{promocode}")
                keyboard.add(button)

            response_text += "<i>Нажмите на промокод, чтобы удалить его.</i>\n\n"
        else:
            response_text += "<i>Нет доступных промокодов.</i>"

        await call.message.edit_text(response_text, reply_markup=keyboard, parse_mode="HTML")

        await call.answer(f"✅ <b>Промокод {promocode_to_delete}</b> успешно удален!", show_alert=True)

    except Exception as e:
        await call.answer(f"❌ <b>Ошибка", show_alert=True)

@dp.callback_query_handler(lambda c: c.data.startswith("task_type:"), state=AdminAddTaskState.waiting_for_task_type)
async def process_task_type(call: types.CallbackQuery, state: FSMContext):
    task_type = call.data.split(":")[1]
    print(f"Тип задания: {task_type}")
    await state.update_data(task_type=task_type)
    data = await state.get_data()
    print(f"Сохраненные данные состояния: {data}")
    message_text = "✏️ Введи ID канала/чата (или ссылку, если без проверки подписки):"
    if call.message.text != message_text:
        await call.message.edit_text(message_text)
    await AdminAddTaskState.waiting_for_channel_id.set()


@dp.callback_query_handler(lambda call: call.data == "cancell_adm", state="*")
async def cancell_adm(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in admins:
        return
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text="👑 Админ-меню", callback_data="adminpanel"))
    try:
        await call.message.delete()
    except (MessageCantBeDeleted, MessageToDeleteNotFound):
        pass
    await state.finish()
    await call.message.answer("Отмена действия", reply_markup=keyboard)

@dp.callback_query_handler(lambda call: call.data == "cancell_ras", state="*")
async def cancel_broadcast(call: CallbackQuery, state: FSMContext):
    if call.from_user.id not in admins:
        return
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text="👑 Админ-меню", callback_data="adminpanel"))
    try:
        await call.message.delete()
    except (MessageCantBeDeleted, MessageToDeleteNotFound):
        pass
    await state.finish()
    await call.message.answer("Рассылка отменена.", reply_markup=keyboard)

@dp.callback_query_handler(lambda call: call.data == "admin_mailing")
async def admin_mailing_start(call: CallbackQuery):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("❌ Отменить рассылку", callback_data="cancell_ras"))
    await call.message.edit_text(t(call.from_user.id, 'enter_mailing_text'), reply_markup=keyboard)
    await BroadcastState.waiting_for_message.set()

@dp.message_handler(state=BroadcastState.waiting_for_message, content_types=['text', 'photo'])
async def broadcast_message_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in admins:
        await state.finish()
        return

    if message.content_type == 'photo':
        await state.update_data(photo=message.photo[-1].file_id, text=message.caption or "")
    else:
        await state.update_data(photo=None, text=message.html_text)

    await message.answer(t(user_id, 'Введи текст Inline кнопки') + "\n\nНапишите 'skip', чтобы пропустить добавление кнопки.")
    await BroadcastState.waiting_for_button_text.set()

@dp.message_handler(state=BroadcastState.waiting_for_button_text, content_types=['text'])
async def broadcast_button_text_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in admins:
        await state.finish()
        return

    button_text = message.text

    if button_text.lower() == 'skip':
        await state.update_data(button_text=None, button_url=None)
        await finalize_broadcast(message, state)
        return

    buttons = await state.get_data()
    if 'buttons' not in buttons:
        buttons['buttons'] = []

    buttons['buttons'].append({'text': button_text})

    await state.update_data(buttons=buttons['buttons'])
    await message.answer(t(user_id, 'Введи ссылку для этой Inline кнопки') + "\n\nНапишите 'skip', чтобы пропустить добавление URL.")
    await BroadcastState.waiting_for_button_url.set()

@dp.message_handler(state=BroadcastState.waiting_for_button_url, content_types=['text'])
async def broadcast_button_url_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in admins:
        await state.finish()
        return

    button_url = message.text

    if button_url.lower() == 'skip':
        await state.update_data(button_url=None)
    else:
        data = await state.get_data()
        buttons = data.get('buttons', [])
        if buttons:
            buttons[-1]['url'] = button_url
            await state.update_data(buttons=buttons)

    await message.answer(t(user_id, 'Хотите добавить еще одну кнопку? (Да/Нет)'))
    await BroadcastState.waiting_for_more_buttons.set()

@dp.message_handler(state=BroadcastState.waiting_for_more_buttons, content_types=['text'])
async def broadcast_add_more_buttons_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in admins:
        await state.finish()
        return

    if message.text.lower() == 'да':
        await message.answer(t(user_id, 'Введи текст Inline кнопки') + "\n\nНапишите 'skip', чтобы пропустить добавление кнопки.")
        await BroadcastState.waiting_for_button_text.set()
    else:
        await preview_broadcast(message, state)

async def preview_broadcast(message: types.Message, state: FSMContext):
    user_id = message.from_user.id

    data = await state.get_data()
    text = data['text']
    photo = data.get('photo')
    buttons = data.get('buttons', [])

    keyboard = InlineKeyboardMarkup()
    for button in buttons:
        if button.get('url') and button.get('text'):
            keyboard.add(InlineKeyboardButton(button['text'], url=button['url']))
    keyboard.add(InlineKeyboardButton("❌ Скрыть", callback_data=f"hide_preview"))
    keyboard.add(InlineKeyboardButton("❌ Отменить рассылку", callback_data="cancell_ras"))

    if photo:
        await bot.send_photo(user_id, photo, caption=text, parse_mode='HTML', reply_markup=keyboard)
    else:
        await bot.send_message(user_id, text, parse_mode='HTML', reply_markup=keyboard)

    confirm_keyboard = InlineKeyboardMarkup()
    confirm_keyboard.add(InlineKeyboardButton("✅ Отправить", callback_data="confirm_broadcast"))
    confirm_keyboard.add(InlineKeyboardButton("✏️ Изменить", callback_data="edit_broadcast"))
    await message.answer(
        "Это предпросмотр вашего сообщения. Вы хотите отправить его всем пользователям?",
        reply_markup=confirm_keyboard
    )
    await BroadcastState.waiting_for_confirmation.set()

@dp.callback_query_handler(lambda call: call.data in ["confirm_broadcast", "edit_broadcast"], state=BroadcastState.waiting_for_confirmation)
async def handle_broadcast_confirmation(call: CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if user_id not in admins:
        await state.finish()
        return

    if call.data == "confirm_broadcast":
        await call.message.answer("Рассылка начата.")
        await finalize_broadcast(call.message, state)
    elif call.data == "edit_broadcast":
        await call.message.answer("Вы можете повторно ввести данные для рассылки.")
        await state.finish()

async def send_message(uid, text, photo, buttons):
    keyboard = InlineKeyboardMarkup()
    for button in buttons:
        if button.get('url') and button.get('text'):
            keyboard.add(InlineKeyboardButton(button['text'], url=button['url']))
    keyboard.add(InlineKeyboardButton("❌ Скрыть", callback_data=f"hide_message_{uid}"))

    try:
        if photo:
            await bot.send_photo(uid, photo, caption=text, parse_mode="HTML", reply_markup=keyboard)
        else:
            await bot.send_message(uid, text, parse_mode="HTML", reply_markup=keyboard)
        return "success"
    except Exception as e:
        if 'bot was blocked by the user' in str(e) or 'Forbidden' in str(e):
            return "blocked"
        elif 'user not found' in str(e):
            return "deleted"
        else:
            return "failed"

async def finalize_broadcast(message: types.Message, state: FSMContext):
    global is_broadcasting
    is_broadcasting = True

    user_id = message.from_user.id
    data = await state.get_data()
    text = data['text']
    photo = data.get('photo')
    buttons = data.get('buttons', [])
    users = get_users()

    await message.answer("<b>🚀 Рассылка началась!</b>")
    await state.finish()

    total = len(users)
    counter = blocked = deleted = failed = 0
    last_update_time = time.time()
    start_time = time.time()

    keyboards = InlineKeyboardMarkup()
    keyboards.add(InlineKeyboardButton("❌ Остановить рассылку", callback_data="stop_broadcast"))
    progress_message = await message.answer(f"<b>Прогресс рассылки:</b>\n⬜⬜⬜⬜⬜⬜⬜⬜⬜⬜ 0%\n0/{total}", reply_markup=keyboards)

    for index, uid in enumerate(users):
        if not is_broadcasting:
            await message.answer("⚠️ Рассылка была остановлена администратором.")
            break

        result = await send_message(uid[0], text, photo, buttons)
        
        if result == "success":
            counter += 1
        elif result == "blocked":
            blocked += 1
        elif result == "deleted":
            deleted += 1
        else:
            failed += 1

        total_processed = counter + blocked + deleted + failed
        percentage = int((total_processed / total) * 100)
        progress_bars = "🟩" * (percentage // 10) + "⬜" * (10 - percentage // 10)

        current_time = time.time()
        if current_time - last_update_time >= 15 or index + 1 >= total:
            elapsed_time = int(current_time - start_time)
            speed = round(total_processed / elapsed_time, 2) if elapsed_time > 0 else 0
            
            try:
                await progress_message.edit_text(
                    f"<b>Прогресс рассылки:</b>\n{progress_bars} <b>{percentage}%</b>\n<b>{total_processed}/{total}</b>\n\n"
                    f"✅ <b>Успешно</b>: <code>{counter}</code>\n"
                    f"🚫 <b>Заблокировано</b>: <code>{blocked}</code>\n\n"
                    f"⚡ <b>Скорость:</b> <code>{speed} сообщений/сек</code>",
                    reply_markup=keyboards
                )
            except Exception:
                pass  

            last_update_time = current_time

        await asyncio.sleep(0.25)

    end_time = time.time()
    total_time = int(end_time - start_time)
    final_speed = round(total / total_time, 2) if total_time > 0 else 0

    await message.answer(
        f"<b>🎉 Рассылка завершена!</b>\n"
        f"✅ <b>Успешно:</b> {counter}\n"
        f"🚫 <b>Заблокировано:</b> {blocked}\n\n"
        f"⏳ <b>Время:</b> {total_time} сек\n"
        f"⚡ <b>Средняя скорость:</b> {final_speed} сообщений/сек",
        parse_mode="HTML"
    )

@dp.callback_query_handler(lambda call: call.data == "stop_broadcast", state="*")
async def stop_broadcast(call: CallbackQuery, state: FSMContext):
    global is_broadcasting
    is_broadcasting = False
    try:
        await call.message.delete()
    except (MessageCantBeDeleted, MessageToDeleteNotFound):
        pass
    await call.answer("Рассылка остановлена.")
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(text="👑 Админ-меню", callback_data="adminpanel"))
    await call.message.answer("Выберите действие:", reply_markup=keyboard)

@dp.callback_query_handler(Text(startswith="hide_message_"))
async def hide_message_callback(call: CallbackQuery):
    try:
        uid = call.data.split("_")[2]

        try:
            await call.message.delete()
        except (MessageCantBeDeleted, MessageToDeleteNotFound):
            pass

        await call.answer("Сообщение скрыто.", show_alert=False)

    except Exception as e:
        print(f"Ошибка при скрытии сообщения для {uid}: {e}")

        await call.answer("Не удалось скрыть сообщение.", show_alert=True)


@dp.callback_query_handler(lambda call: call.data == "admin_add_channel")
async def admin_add_channel(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if user_id not in admins:
        return
    await AdminAddChannelState.waiting_for_channel_id.set()
    await call.message.edit_text("Пожалуйста, отправьте ID канала для добавления.")

@dp.callback_query_handler(lambda call: call.data == "admin_delete_channel")
async def admin_delete_channel(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if user_id not in admins:
        return
    await AdminDeleteChannelState.waiting_for_channel_id.set()
    await call.message.edit_text("Пожалуйста, отправьте ID канала для удаления.")

@dp.message_handler(state=AdminAddChannelState.waiting_for_channel_id)
async def process_add_channel(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in admins:
        await state.finish()
        return
    try:
        channel_id = int(message.text)
        await AdminAddChannelState.waiting_for_delete_time.set()
        await message.answer("Теперь отправьте количество часов, через которое канал должен быть удалён из базы данных.")
        await state.update_data(channel_id=channel_id)
    except:
        await message.answer(t(user_id, 'invalid_channel_id'))

@dp.message_handler(state=AdminAddChannelState.waiting_for_delete_time)
async def process_delete_time(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in admins:
        await state.finish()
        return

    try:
        delete_time = int(message.text)
        if delete_time <= 0:
            raise ValueError("Время должно быть больше 0")

        data = await state.get_data()
        channel_id = data.get('channel_id')

        if channel_id is None:
            await message.answer("⚠ Ошибка! ID канала не найден. Попробуйте снова.")
            await state.finish()
            return
        
        print(f"[DEBUG] Добавление канала {channel_id} с временем удаления {delete_time} часов.")
        
        add_channel_db(channel_id, delete_time)

        global channel_ids
        channel_ids = get_channels_db()

        keyboard = InlineKeyboardMarkup()
        admin_panel_btn = InlineKeyboardButton(text="👑 Админ-меню", callback_data="adminpanel")
        keyboard.add(admin_panel_btn)

        await message.answer(f"✅ Канал {channel_id} успешно добавлен и будет удалён через {delete_time} часов.", reply_markup=keyboard)

    except ValueError:
        await message.answer("⚠ Ошибка! Введите число (количество часов).")
    except Exception as e:
        print(f"[ERROR] Ошибка при добавлении канала: {e}")
        await message.answer("⚠ Произошла ошибка, попробуйте снова.")
    
    await state.finish()


@dp.message_handler(state=AdminDeleteChannelState.waiting_for_channel_id)
async def process_delete_channel(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in admins:
        await state.finish()
        return
    try:
        channel_id = int(message.text)
        delete_channel_db(channel_id)
        global channel_ids
        channel_ids = get_channels_db()
        keyboard = InlineKeyboardMarkup()
        admin_panel_btn = InlineKeyboardButton(text="👑 Админ-меню", callback_data="adminpanel")
        keyboard.add(admin_panel_btn)
        await message.answer(t(user_id, 'channel_deleted'), reply_markup=keyboard)
    except:
        await message.answer(t(user_id, 'invalid_channel_id'))
    await state.finish()

@dp.callback_query_handler(lambda call: call.data == "admin_get_channels")
async def admin_get_channels(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if user_id not in admins:
        return

    channel_ids = get_channels_db()

    if not channel_ids:
        await call.message.answer("В базе данных нет каналов.")
        return

    keyboard = InlineKeyboardMarkup(row_width=1)
    for channel_id in channel_ids:
        try:
            channel = await bot.get_chat(channel_id)
            channel_name = channel.title

            channel_btn = InlineKeyboardButton(
                text=channel_name,
                callback_data=f"channel_{channel_id}"
            )
            keyboard.add(channel_btn)
        except Exception as e:
            print(f"Ошибка при получении информации о канале {channel_id}: {e}")

    admin_panel_btn = InlineKeyboardButton(text="👑 Админ-меню", callback_data="adminpanel")
    keyboard.add(admin_panel_btn)

    await call.message.edit_text("Выберите канал:", reply_markup=keyboard)

@dp.callback_query_handler(lambda call: call.data.startswith("channel_"))
async def delete_channel_callback(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if user_id not in admins:
        return

    channel_id = int(call.data.split("_")[1])

    delete_channel_db(channel_id)

    channel_ids = get_channels_db()

    keyboard = InlineKeyboardMarkup(row_width=1)
    for channel_id in channel_ids:
        try:
            channel = await bot.get_chat(channel_id)
            channel_name = channel.title

            channel_btn = InlineKeyboardButton(
                text=channel_name,
                callback_data=f"channel_{channel_id}"
            )
            keyboard.add(channel_btn)
        except Exception as e:
            print(f"Ошибка при получении информации о канале {channel_id}: {e}")

    admin_panel_btn = InlineKeyboardButton(text="👑 Админ-меню", callback_data="adminpanel")
    keyboard.add(admin_panel_btn)

    try:
        await call.message.edit_text("Выберите канал для удаления:", reply_markup=keyboard)
    except Exception as e:
        print(f"Ошибка при редактировании сообщения: {e}")
        await call.message.answer("Выберите канал для удаления:", reply_markup=keyboard)

    await call.answer(f"Канал с ID {channel_id} был удален.")

@dp.callback_query_handler(lambda call: call.data == "admin_promocode_added")
async def admin_add_promocode_callback(call: types.CallbackQuery):
    await call.message.edit_text("Введите промокод и его сумму в формате: промокод:сумма (например, STAR900:2).")
    await AdminAddPromoCodeState.waiting_for_data.set()

@dp.callback_query_handler(lambda c: c.data == "admin_promocode_delete", state="*")
async def admin_promocode_delete(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id
    if user_id not in admins:
        return

    await call.message.edit_text("Введите промокод, который хотите удалить:")
    await AdminDeletePromoCodeState.waiting_for_promocode.set()

@dp.message_handler(state=AdminDeletePromoCodeState.waiting_for_promocode)
async def process_delete_promocode(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in admins:
        await state.finish()
        return

    promocode_to_delete = message.text.strip()

    delete_promo(promocode_to_delete)

    keyboard = InlineKeyboardMarkup()
    admin_panel_btn = InlineKeyboardButton(text="👑 Админ-меню", callback_data="adminpanel")
    keyboard.add(admin_panel_btn)

    await message.answer(f"✅ Промокод {promocode_to_delete} успешно удалён!", reply_markup=keyboard)

    await state.finish()


@dp.message_handler(state=AdminAddPromoCodeState.waiting_for_data)
async def process_add_promocode(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in admins:
        await state.finish()
        return

    try:
        parts = message.text.split(':')
        if len(parts) < 2:
            raise ValueError

        promocode = parts[0]
        reward = float(parts[1])
        max_uses = int(parts[2]) if len(parts) > 2 else 1
        min_referrals = int(parts[3]) if len(parts) > 3 else 0

        add_promocode(promocode, reward, max_uses, min_referrals)
        keyboard = InlineKeyboardMarkup()
        admin_panel_btn = InlineKeyboardButton(text="👑 Админ-меню", callback_data="adminpanel")
        keyboard.add(admin_panel_btn)
        await message.answer(
            f"✅ Промокод {promocode} с наградой {reward}⭐️, макс. {max_uses} использований и мин. {min_referrals} рефералов успешно добавлен!",
            reply_markup=keyboard
        )

    except ValueError:
        keyboard = InlineKeyboardMarkup().add(InlineKeyboardButton("👑 Вернуться в админ-меню", callback_data="adminpanel"))
        await message.answer("❌ Неверный формат. Используйте: промокод:сумма[:макс_использований][:мин_рефералов]", reply_markup=keyboard)

    await state.finish()

@dp.message_handler(state=AdminAddStarsState.waiting_for_data)
async def process_add_stars(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in admins:
        await state.finish()
        return
    try:
        u_id, stars = map(int, message.text.split(':'))
        increment_stars(u_id, stars)
        await message.answer(t(user_id, 'stars_added').format(stars=stars, user_id=u_id))
        await bot.send_message(u_id, t(u_id, 'admin_added_stars').format(stars=stars))
    except:
        await message.answer(t(user_id, 'invalid_format'))
    await state.finish()

@dp.message_handler(state=AdminRemoveTaskState.waiting_for_channel_id)
async def process_remove_task_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    if user_id not in admins:
        await state.finish()
        return
    try:
        channel_id = int(message.text)
        if remove_task(channel_id):
            await message.answer("Задание успешно удалено!")
        else:
            await message.answer("Задание с таким ID не найдено.")
    except ValueError:
        await message.answer("Ошибка. Убедитесь, что ввели корректный ID.")
    except Exception as e:
        await message.answer(f"Произошла ошибка: {e}")
    await state.finish()

@dp.message_handler(commands=['deleteuser'])
async def delete_user_command(message: types.Message):
    if message.from_user.id in admins:
        try:
            args = message.text.split()
            if len(args) < 2:
                await message.answer("Пожалуйста, укажите ID пользователя, которого нужно удалить.")
                return
            user_id_to_delete = int(args[1])
            delete_user(user_id_to_delete)
            await message.answer(f"Пользователь с ID {user_id_to_delete} успешно удален.")
        except ValueError:
            await message.answer("Пожалуйста, укажите корректный ID пользователя.")
    else:
        await message.answer("У вас нет прав для выполнения этой команды.")

class SlotState(StatesGroup):
    waiting_for_bet = State()

def create_slot_button():
    keyboard = InlineKeyboardMarkup()
    button = InlineKeyboardButton("🎰 Крутить", callback_data="play_slots")
    keyboard.add(button)
    return keyboard

def create_bet_inline_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=3)
    keyboard.row(
        InlineKeyboardButton("1 ⭐️", callback_data="bets_1"),
        InlineKeyboardButton("2 ⭐️", callback_data="bets_2"),
        InlineKeyboardButton("3 ⭐️", callback_data="bets_3")
    )
    keyboard.row(
        InlineKeyboardButton("4 ⭐️", callback_data="bets_4"),
        InlineKeyboardButton("5 ⭐️", callback_data="bets_5"),
        InlineKeyboardButton("6 ⭐️", callback_data="bets_6")
    )
    keyboard.add(InlineKeyboardButton("⬅️ Назад в меню мини-игр", callback_data="mini_games"))
    return keyboard

@dp.callback_query_handler(lambda c: c.data == "play_slots")
async def ask_for_bet(callback_query: types.CallbackQuery):
    user_data = get_user(callback_query.from_user.id)
    if not user_data:
        await callback_query.answer("Пользователь не найден. Зарегистрируйтесь в боте.", show_alert=True)
        return

    stars = user_data[2]
    await SlotState.waiting_for_bet.set()
    await callback_query.message.delete()
    await bot.send_message(
        callback_query.from_user.id,
        f"💰 Твой текущий баланс: {stars:.2f} ⭐️\n🖌 Выбери сумму ставки",
        reply_markup=create_bet_inline_keyboard()
    )

@dp.callback_query_handler(lambda c: c.data.startswith("bets_"), state=SlotState.waiting_for_bet)
async def handle_bet_selection(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = get_user(callback_query.from_user.id)
    stars = user_data[2]

    try:
        bet_amount = float(callback_query.data.split("_")[1])
    except ValueError:
        await callback_query.answer("Некорректная сумма. Попробуй снова.", show_alert=True)
        return

    if stars < bet_amount:
        await callback_query.answer(
            f"❌ Недостаточно звёзд для ставки. Твой баланс: {stars:.2f} ⭐️",
            show_alert=True
        )
        return

    await process_bet(callback_query.message.chat.id, callback_query.from_user.id, bet_amount, state)
    await callback_query.message.delete()

async def process_bet(chat_id, user_id, bet_amount, state):
    user_data = get_user(user_id)
    stars = user_data[2]
    new_stars = stars - bet_amount

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET stars = ? WHERE id = ?", (new_stars, user_id))
    conn.commit()
    conn.close()

    data = await bot.send_dice(chat_id, emoji="🎰")
    dice_value = data.dice.value

    if dice_value in [64, 43, 1, 22]:
        win_coefficient = random.uniform(1.2, 2)
        win_amount = bet_amount * win_coefficient
        new_stars += win_amount
        result_message = (
            f"🎉 Поздравляем! Ты выиграл {win_amount:.2f} ⭐️! "
            f"Коэффициент: {win_coefficient:.2f}\n💰 Твой новый баланс: {new_stars:.2f} ⭐️."
        )
    else:
        result_message = (
            f"😞 Увы, ты проиграл. Попробуй ещё раз!\n"
            f"💰 Твой текущий баланс: {new_stars:.2f} ⭐️."
        )

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET stars = ? WHERE id = ?", (new_stars, user_id))
    conn.commit()
    conn.close()

    await asyncio.sleep(2)

    keyboard = create_slot_button()
    await bot.send_message(chat_id, result_message, reply_markup=keyboard)
    await state.finish()

async def schedule_channel_deletion(channel_id, delete_time):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Ожидание удаления канала {channel_id} через {delete_time} часов...")
    await asyncio.sleep(delete_time * 3600)
    delete_channel_db(channel_id)

async def check_channels_for_deletion():
    while True:
        current_time = int(time.time())
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Запуск проверки каналов на удаление...")

        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()

        cursor.execute("SELECT channel_id, delete_time FROM channels")
        channels_to_delete = cursor.fetchall()

        total_channels = len(channels_to_delete)
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Всего каналов: {total_channels}")

        if channels_to_delete:
            for channel_id, delete_time in channels_to_delete:
                if delete_time is not None:
                    time_remaining = delete_time - current_time
                    hours_remaining = time_remaining // 3600
                    minutes_remaining = (time_remaining % 3600) // 60
                    seconds_remaining = time_remaining % 60

                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Канал {channel_id} будет удален через {hours_remaining} ч {minutes_remaining} мин {seconds_remaining} сек.")

                    if time_remaining <= 0:
                        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Канал {channel_id} подлежит немедленному удалению!")
                        asyncio.create_task(schedule_channel_deletion(channel_id, 0))
                    else:
                        asyncio.create_task(schedule_channel_deletion(channel_id, hours_remaining))
                else:
                    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Для канала {channel_id} не указано время удаления.")
        else:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Каналов для удаления нет.")

        conn.close()
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Проверка завершена. Следующая проверка через 1 час.\n")
        await asyncio.sleep(600)

async def add_channel_on_startup():
    add_channel_db(NEWS_CHANEL_ID, delete_time=999999)
    print(f"Канал {NEWS_CHANEL_ID} был добален в ОП автоматически для корректной работы SubGram, при первом запуске ПЕРЕЗАПУСТИТЕ скрипт!")

def get_server_uptime():
    """Получает время работы сервера из /proc/uptime"""
    try:
        with open("/proc/uptime", "r") as f:
            uptime_seconds = float(f.readline().split()[0])
            server_start_time = datetime.now() - timedelta(seconds=uptime_seconds)
            return server_start_time
    except Exception as e:
        print(f"Ошибка получения аптайма сервера: {e}")
        return datetime.now()

async def on_startup(_):
    await add_channel_on_startup()
    asyncio.create_task(check_channels_for_deletion())  
    print("Запуск Pyrogram клиента...")
    await app.start()
    print("Pyrogram клиент запущен!")
    boot_time = datetime.fromtimestamp(psutil.boot_time())
    uptime = datetime.now() - boot_time
    ram_usage = psutil.virtual_memory().percent
    cpu_usage = psutil.cpu_percent()
    subbalance = await get_subbalance()
    balances = await app.get_stars_balance()
    user = await app.get_me()
    user_name = user.username if user.username else "Не задано"
    user_id = user.id
    user_full_name = user.first_name + (" " + user.last_name if user.last_name else "")
    server_start_time = get_server_uptime()
    uptime = datetime.now() - server_start_time
    current_time = datetime.now().strftime("%d.%m | %H:%M")
    server_start_time_str = server_start_time.strftime("%d.%m | %H:%M")
    message = (
        f"""<b>✅ Бот успешно запущен!</b>

<blockquote><b>⭐️ Звезд в юзерботе:</b> <code>{balances}</code>
<b>💶 Денег в subgrame:</b> <code>{subbalance}</code></blockquote>

<blockquote>🆙 <b>Версия бота:</b> <code>{BOT_VERSION}</code></blockquote>

<blockquote>💻 <b>Информация о Pyrogram клиенте:</b>
  👤 <b>Имя клиента:</b> <code>{user_full_name}</code>
  🆔 <b>ID клиента:</b> <code>{user_id}</code>
  🏷 <b>Username:</b> <code>@{user_name}</code></blockquote>

<blockquote>📅 <b>Время запуска бота:</b> <code>{current_time}</code>
🖥 <b>Время запуска сервера:</b> <code>{server_start_time_str}</code>
🕒 <b>Аптайм сервера:</b> <code>{str(timedelta(seconds=uptime.total_seconds()))}</code>
💾 <b>Использование RAM:</b> <code>{ram_usage}%</code>
🔥 <b>CPU:</b> <code>{cpu_usage}%</code>
</blockquote>"""
    )

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("👨‍💻 Автор кода", url="https://lolz.live/telegramstars/"))

    for admin in admins:
        try:
            await bot.send_message(admin, message, reply_markup=keyboard, parse_mode="HTML")
        except Exception as e:
            print(f"Ошибка отправки сообщения админу {admin}: {e}")

def create_inline_menu():
    keyboard = InlineKeyboardMarkup()
    button1 = InlineKeyboardButton("🗃 Полную базу данных", callback_data="full_db")
    button2 = InlineKeyboardButton("📁 Только username", callback_data="usernames_list")
    button3 = InlineKeyboardButton("📁 Только id", callback_data="ids_list")
    button4 = InlineKeyboardButton("👑 Вернуться в админ-меню", callback_data="adminpanel")
    keyboard.add(button1)
    keyboard.add(button2, button3)
    keyboard.add(button4)
    return keyboard

@dp.callback_query_handler(lambda call: call.data == "admin_db")
async def admin_add_promocode_callback(call: types.CallbackQuery):
    keyboard = create_inline_menu()
    await call.message.edit_text("Выберите, что хотите запросить:", reply_markup=keyboard)

def generate_filename(prefix):
    current_time = datetime.now().strftime("%d_%m_%Y_%H_%M")
    return f"{prefix}_{current_time}.txt"

@dp.callback_query_handler(lambda c: c.data == "show_stat_op")
async def show_statistics(callback_query: types.CallbackQuery):
    async with aiohttp.ClientSession() as session:
        async with session.post("https://api.subgram.ru/get-statistic/", headers={"Auth": REQUEST_API_KEY}) as response:
            data = await response.json()

    if data.get("status") == "ok":
        stats = data.get("data", [])

        if stats:
            text = "📊 <b>Статистика ОП</b>:\n\n"
            text += "<b>📅 Дата      | 📦 Заказы | 💰 Заработано</b>\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━━\n"

            total_amount = 0
            total_orders = 0 
            count_days = len(stats)

            for item in stats[:10]:
                date = item["date"]
                orders = item["count"]
                amount = item["amount"]

                total_amount += amount
                total_orders += orders

                text += f"<b>🗓 {date} | 📦 {orders:^6} | 💰 {amount:^8}</b>\n"

            avg_earnings = total_amount / count_days if count_days > 0 else 0

            text += "━━━━━━━━━━━━━━━━━━━━━━━\n"
            text += f"📊 <b>Средний заработок: {avg_earnings:.2f} руб./день</b>\n"
        else:
            text = "ℹ️ <b>Нет данных по статистике.</b>"

    else:
        text = f"❌ <b>Ошибка:</b> {data.get('message', 'Не удалось получить статистику')}"

    await bot.send_message(callback_query.from_user.id, text, parse_mode="HTML")
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query_handler(lambda c: c.data in ["full_db", "usernames_list", "ids_list"])
async def process_callback(callback_query: types.CallbackQuery):
    action = callback_query.data
    
    if action == "full_db":
        db_file_path = 'database.db'
        if os.path.exists(db_file_path):
            with open(db_file_path, 'rb') as db_file:
                await bot.send_document(callback_query.from_user.id, db_file, caption="Вот ваша полная база данных (database.db)")
        else:
            await bot.send_message(callback_query.from_user.id, "Ошибка: Файл базы данных не найден.")
    
    elif action == "usernames_list":
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users")
        rows = cursor.fetchall()
        filename = generate_filename("users")
        with open(filename, 'w', newline='') as temp_file:
            for row in rows:
                temp_file.write(f"{row[0]}\n")
        with open(filename, 'rb') as file:
            await bot.send_document(callback_query.from_user.id, file, caption="Список всех пользователей (username)")
        os.remove(filename)

    elif action == "ids_list":
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users")
        rows = cursor.fetchall()
        filename = generate_filename("id")

        with open(filename, 'w', newline='') as temp_file:
            for row in rows:
                temp_file.write(f"{row[0]}\n")

        with open(filename, 'rb') as file:
            await bot.send_document(callback_query.from_user.id, file, caption="Список всех пользователей (id)")

        os.remove(filename)

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)


