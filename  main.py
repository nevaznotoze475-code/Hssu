import asyncio
import random
import time
import logging
import re
import html
import aiohttp

from typing import List, Tuple
from typing import Optional, Callable, Dict, Any, Awaitable
from aiogram import Bot, Dispatcher, Router, types, F, BaseMiddleware
from aiogram.filters import CommandStart, StateFilter
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputFile, LabeledPrice, PreCheckoutQuery, BufferedInputFile
from aiogram.types.input_file import FSInputFile
from aiogram.exceptions import (
    TelegramAPIError, TelegramBadRequest, TelegramNotFound, TelegramForbiddenError,
    TelegramConflictError, TelegramUnauthorizedError, TelegramRetryAfter, TelegramMigrateToChat
)
from typing import Callable, Dict, Any, Awaitable
from datetime import datetime, timedelta
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from apscheduler.schedulers.asyncio import AsyncIOScheduler

try:
    from database import *
    from settings import *
except ImportError as e:
    print(f"Ошибка импорта: {e}. Пожалуйста, убедитесь, что файлы database.py и settings.py существуют и находятся в правильном месте.")
    exit()

logging.basicConfig(level=logging.ERROR)

router = Router()
admin_msg = {}
message_ids = {}

class AntiFloodMiddleware(BaseMiddleware):
    def __init__(self, limit: int = 1):
        self.limit = limit
        self.last_time: Dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[types.Message | types.CallbackQuery, Dict[str, Any]], Awaitable[Any]],
        event: types.Message | types.CallbackQuery,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, types.Message):
            if event.text and event.text.startswith('/start'):
                return await handler(event, data)

            user_id = event.from_user.id
            current_time = time.time()

            if user_id in self.last_time:
                last_time = self.last_time[user_id]
                if (current_time - last_time) < self.limit:
                    await event.answer("⚠️ Пожалуйста, не флудите! Ожидайте {:.0f} сек.".format(self.limit))
                    return

            self.last_time[user_id] = current_time
            return await handler(event, data)

        elif isinstance(event, types.CallbackQuery):
            user_id = event.from_user.id
            current_time = time.time()

            if user_id in self.last_time:
                last_time = self.last_time[user_id]
                if (current_time - last_time) < self.limit:
                    await event.answer("⚠️ Пожалуйста, не флудите! Ожидайте {:.0f} сек.".format(self.limit), show_alert=True)
                    return

            self.last_time[user_id] = current_time
            return await handler(event, data)

class KNBGame(StatesGroup):
    waiting_username = State()
    # waiting_username_chat = State()
    # waiting_stake_chat = State()
    # waiting_choice_chat_first = State()
    # waiting_choice_chat_second = State()
    waiting_stake = State()

class LotteryState(StatesGroup):
    ticket_cash = State()

class CaptchaState(StatesGroup):
    waiting_for_answer = State()

class CaptchaClick(StatesGroup):
    waiting_click_captcha = State()

class AdminState(StatesGroup):
    USERS_CHECK = State()
    ADD_STARS = State()
    REMOVE_STARS = State()
    MAILING = State()
    ADD_PROMO_CODE = State()
    REMOVE_PROMO_CODE = State()
    ADD_CHANNEL = State()
    REMOVE_CHANNEL = State()
    # TOP_BALANCE = State()
    ADD_MAX_USES = State()
    ADD_TASK = State()
    REMOVE_TASK = State()
    PROMOCODE_INPUT = State()
    ADD_TASK_REWARD = State()
    ADD_TASK_CHANNEL = State()
    ADD_TASK_PRIVATE = State()
    CHECK_TASK_BOT = State()
    DELETE_TASK_INPUT = State()
    DELETE_CHANNEL_INPUT = State()
    DELETE_PROMO_INPUT = State()
    GIVE_BOOST = State()


async def request_op(user_id, chat_id, first_name, language_code, bot: Bot, ref_id=None, gender=None, is_premium=None, age=None):
    headers = {
        'Content-Type': 'application/json',
        'Auth': f'{SUBGRAM_TOKEN}',
        'Accept': 'application/json',
    }
    data = {'UserId': user_id, 'ChatId': chat_id, 'first_name': first_name, 'language_code': language_code}
    if gender:
        data['Gender'] = gender
    if is_premium:
        data['Premium'] = is_premium
    if age:
        data['Age'] = age

    async with aiohttp.ClientSession() as session:
        async with session.post('https://api.subgram.ru/request-op-tokenless/', headers=headers, json=data) as response:
            if not response.ok or response.status != 200:
                logging.error("Ошибка при запросе SubGram. Если такая видишь такую ошибку - ставь другие настройки Subgram или проверь свой API KEY. Вот ошибка: %s" % str(await response.text()))
                return 'ok'
            response_json = await response.json()

            if response_json.get('status') == 'warning':
                if ref_id:
                    await show_op(chat_id,response_json.get("links",[]), bot, ref_id=ref_id)
                else:
                    await show_op(chat_id,response_json.get("links",[]), bot)
            return response_json.get("status")

async def show_op(chat_id,links, bot: Bot, ref_id=None):
    markup = InlineKeyboardBuilder()
    temp_row = []
    sponsor_count = 0
    for url in links:
        sponsor_count += 1
        name = f'Cпонсор №{sponsor_count}'
        button = types.InlineKeyboardButton(text=name, url=url)
        temp_row.append(button) 

        if sponsor_count % 2 == 0:
            markup.row(*temp_row)
            temp_row = []

    if temp_row:
        markup.row(*temp_row)
    if ref_id != "None":
        item1 = types.InlineKeyboardButton(text='✅ Я подписан',callback_data=f'subgram-op:{ref_id}')
    else:
        item1 = types.InlineKeyboardButton(text='✅ Я подписан',callback_data='subgram-op')
    markup.row(item1)
    photo = FSInputFile("photos/check_subs.jpg")
    await bot.send_photo(chat_id, photo, caption="<b>Для продолжения использования бота подпишись на следующие каналы наших спонсоров</b>\n\n<blockquote><b>💜Спасибо за то что вы выбрали НАС</b></blockquote>", parse_mode='HTML', reply_markup=markup.as_markup())

async def send_hi_views(
        user_id: int,
        message_id: int,
        user_first_name: str,
        language_code: str,
        startplace: bool
    ):
    async with aiohttp.ClientSession() as session:
        async with session.post(
            'https://hiviews.net/sendMessage',
            headers={
                'Authorization': HIVIEWS_TOKEN,
                'Content-Type': 'application/json',
            },
            json={
                'UserId': user_id,
                'MessageId': message_id,
                'UserFirstName': user_first_name,
                'LanguageCode': language_code,
                'StartPlace': startplace
            },
        ) as response:
            print('[HiViews]', await response.text('utf-8'))

def get_random_value():
    return round(random.uniform(0.1, 0.12), 2)

async def check_subscription(user_id, channel_ids, bot: Bot, refferal_id=None):
    if not channel_ids:
        return True

    builder = InlineKeyboardBuilder()
    for channel_id in channel_ids:
        try:
            chat_member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
            if chat_member.status not in ['member', 'administrator', 'creator']:
                invite_link = (await bot.create_chat_invite_link(chat_id=channel_id, member_limit=1)).invite_link
                subscribe_button = InlineKeyboardButton(text="Подписаться", url=invite_link)
                builder.add(subscribe_button)
        except Exception as e:
            print(f"Ошибка при проверке подписки: {e}")
            await bot.send_message(user_id, "Ошибка при проверке подписки. Пожалуйста, попробуйте позже.")
            return False

    if builder.export():
        markup = builder.as_markup()
        if refferal_id is not None:
            check_button = InlineKeyboardButton(text="✅ Проверить подписку", callback_data=f"check_subs:{refferal_id}")
            markup.inline_keyboard.append([check_button])
            await bot.send_message(user_id, "<b>👋🏻 Добро пожаловать\n\nПодпишитесь на каналы, чтобы продолжить!</b>", parse_mode='HTML', reply_markup=markup)
            return False
        else:
            check_button = InlineKeyboardButton(text="✅ Проверить подписку", callback_data=f"check_subs")
            markup.inline_keyboard.append([check_button])
            await bot.send_message(user_id, "<b>👋🏻 Добро пожаловать\n\nПодпишитесь на каналы, чтобы продолжить!</b>", parse_mode='HTML', reply_markup=markup)
            return False

    return True

def generate_captcha():
    num1 = random.randint(0, 9)
    num2 = random.randint(0, 9)
    operator = random.choice(['+', '-', '*'])
    question = f"<b>{num1} {operator} {num2} =</b>"
    answer = eval(f"{num1} {operator} {num2}")
    return question, answer

def create_captcha_keyboard(correct_answer, ref_id):
    answers = [correct_answer - 1, correct_answer, correct_answer + 1]
    random.shuffle(answers)
    builder = InlineKeyboardBuilder()
    for answer in answers:
        builder.button(text=str(answer), callback_data=f"captcha_{answer}_{ref_id}")
    builder.adjust(3)
    return builder.as_markup()

@router.message(CommandStart())
async def start_command(message: Message, bot: Bot, state: FSMContext):
    user = message.from_user
    user_id = user.id
    args = message.text.split()

    try:
        all_stars = str(sum_all_stars())
        withdrawed = str(sum_all_withdrawn())
    except Exception as e:
        logging.error(f"Ошибка при получении статистики: {e}")
        all_stars, withdrawed = "Ошибка", "Ошибка"

    builder_start = InlineKeyboardBuilder()
    buttons = [
        ('✨ Фармить звёзды', 'click_star'),
        ('🎮 Мини-игры', 'mini_games'),
        ('🔗 Получить ссылку', 'earn_stars'),
        ('🔄 Обменять звёзды', 'withdraw_stars_menu'),
        ('👤 Профиль', 'my_balance'),
        ('📝 Задания', 'tasks'),
        ('📘 Гайды | FAQ', 'faq'),
        ('🚀 Буст', 'donate'),
        ('🏆 Топ', 'leaders')
    ]
    for text, callback_data in buttons:
        builder_start.button(text=text, callback_data=callback_data)
    if beta_url and beta_name:
        builder_start.button(text=beta_name, url=beta_url)
    builder_start.adjust(1, 1, 2, 2, 2, 2, 1)
    markup_start = builder_start.as_markup()


    referral_id = None
    if len(args) > 1 and args[1].isdigit():
        referral_id = int(args[1])

    is_premium = getattr(user, 'is_premium', None)
    if message.chat.id != id_chat:
        response = await request_op(
            user_id=user_id,
            chat_id=message.chat.id,
            first_name=user.first_name,
            language_code=user.language_code,
            bot=bot,
            ref_id=referral_id,
            is_premium=is_premium
        )

        if response != 'ok':
            return

        if required_subscription and not await check_subscription(user_id, required_subscription, bot, referral_id):
            return

    if not user_exists(user_id):
        if referral_id and user_exists(referral_id):
            capthca_question, capthca_answer = generate_captcha()
            await state.update_data(capthca_answer=capthca_answer)
            keyboard = create_captcha_keyboard(capthca_answer, referral_id)
            await state.set_state(CaptchaState.waiting_for_answer)
            await bot.send_message(
                user_id,
                f"{capthca_question}\nВыберите правильный ответ:",
                parse_mode='HTML',
                reply_markup=keyboard
            )
            return
        else:
            add_user(user_id, user.username, referral_id)
            # increment_referrals(referral_id)
            # increment_stars(referral_id, 0.7)
            # new_ref_link = f"https://t.me/{(await bot.me()).username}?start={referral_id}"
            # await bot.send_message(
            #     referral_id,
            #     f"🎉 Пользователь <code>{user_id}</code> запустил бота по вашей ссылке!\n"
            #     f"Вы получили +0.7⭐️ за реферала.\n"
            #     f"Поделитесь ссылкой ещё раз:\n<code>{new_ref_link}</code>",
            #     parse_mode='HTML'
            # )
    if message.chat.id != id_chat:
        await send_hi_views(
            user_id=message.from_user.id,
            message_id=message.message_id,
            user_first_name=message.from_user.first_name,
            language_code=message.from_user.language_code,
            startplace=True
        )
        await asyncio.sleep(1.2)
    await bot.send_message(user_id, "⭐")
    photo = FSInputFile("photos/start.jpg")
    await bot.send_photo(
        chat_id=user_id,
        photo=photo,
        caption=(
            f"<b>✨ Добро пожаловать в главное меню ✨</b>\n\n"
            f"<b>🌟 Всего заработано: <code>{all_stars[:all_stars.find('.') + 2] if '.' in all_stars else all_stars}</code>⭐️</b>\n"
            f"<b>♻️ Всего обменяли: <code>{withdrawed[:withdrawed.find('.') + 2] if '.' in withdrawed else withdrawed}</code>⭐️</b>\n\n"
            "<b>Как заработать звёзды?</b>\n"
            "<blockquote>🔸 <i>Кликай, собирай ежедневные награды и вводи промокоды</i>\n"
            "— всё это доступно в разделе «Профиль».\n"
            "🔸 <i>Выполняй задания и приглашай друзей</i>\n"
            "🔸 <i>Испытай удачу в увлекательных мини-играх</i>\n"
            "— всё это доступно в главном меню.</blockquote>"
        ),
        parse_mode='HTML',
        reply_markup=markup_start
    )
    # with open("photos/start.jpg", "rb") as photo:

@router.callback_query(CaptchaState.waiting_for_answer)
async def process_captcha(callback_query: CallbackQuery, state: FSMContext, bot: Bot):
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username if callback_query.from_user.username else None
    try:
        if not callback_query.data.startswith("captcha_"):
            await bot.answer_callback_query(callback_query.id, "❌ Неизвестный формат данных.")
            return

        parts = callback_query.data.split('_')
        if len(parts) != 3:
            await bot.answer_callback_query(callback_query.id, "❌ Неверный формат данных.")
            return

        user_answer = int(parts[1])
        referal = int(parts[2])

        data = await state.get_data()
        capthca_answer = data['capthca_answer']

        if user_answer == capthca_answer:
            add_user(user_id, username, referal)
            await bot.answer_callback_query(callback_query.id, "✅ Вы ответили верно!")
            c_refs = get_user_referrals_count(referal)
            increment_referrals(referal)
            if c_refs < 50:
                nac = 0.7 * 2 if user_in_booster(referal) else 0.7
                increment_stars(referal, nac)
            elif 50 <= c_refs < 250:
                nac = 1 * 2 if user_in_booster(referal) else 1
                increment_stars(referal, nac)
            else:
                nac = 1.5 * 2 if user_in_booster(referal) else 1.5
                increment_stars(referal, nac)

            new_ref_link = f"https://t.me/{(await bot.me()).username}?start={referal}"
            await bot.send_message(
                referal,
                f"🎉 Пользователь <code>{user_id}</code> запустил бота по вашей ссылке!\n"
                f"Вы получили +{nac}⭐️ за реферала.\n"
                f"Поделитесь ссылкой ещё раз:\n<code>{new_ref_link}</code>",
                parse_mode='HTML'
            )

            await bot.delete_message(user_id, callback_query.message.message_id)
            await send_main_menu(user_id, bot)
            await state.clear()
        else:
            await bot.answer_callback_query(callback_query.id, "❌ Вы ответили неверно! Попробуйте ещё раз", show_alert=True)
    except Exception as e:
        print(f"Ошибка в process_captcha: {e}")
        await bot.answer_callback_query(callback_query.id, "❌ Произошла ошибка. Попробуйте ещё раз.")

@router.message(F.text == '/adminpanel')
async def adminpanel_command(message: Message, bot: Bot):
    if message.from_user.id in admins_id:
        builder_admin = InlineKeyboardBuilder()
        builder_admin.button(text='🎰 Лотерея', callback_data='admin_lotery')
        builder_admin.button(text='📊 Статистика', callback_data='stats')
        builder_admin.button(text="🔎 Информация о пользователе", callback_data="users_check")
        builder_admin.button(text="⭐️ Выдать звезды", callback_data="add_stars")
        builder_admin.button(text="⭐️ Снять звезды", callback_data="remove_stars")
        builder_admin.button(text="📨 Рассылка", callback_data="mailing")
        builder_admin.button(text="🎁 Добавить промокод", callback_data='add_promo_code')
        builder_admin.button(text="🚫 Удалить промокод", callback_data='remove_promo_code')
        builder_admin.button(text="📝 Добавить канал", callback_data='add_channel')
        builder_admin.button(text="🚫 Удалить канал", callback_data='remove_channel')
        builder_admin.button(text="📝 Добавленные каналы", callback_data='info_added_channels')
        builder_admin.button(text="📝 Добавить задание", callback_data='add_task')
        builder_admin.button(text="🚫 Удалить задание", callback_data='remove_task')
        builder_admin.button(text="🏆 Топ-50 Баланс", callback_data='top_balance')
        builder_admin.button(text="🌠 Выдать буст", callback_data="give_boost")
        builder_admin.button(text="📊 Статистика заданий", callback_data='stats_tasks')
        markup_admin = builder_admin.adjust(1, 1, 1, 2, 1, 2, 2, 1, 2, 2, 1).as_markup()

        try:
            user_count = get_user_count()
            total_withdrawn = get_total_withdrawn()
            await bot.send_message(message.from_user.id, f"<b>🎉 Вы вошли в панель администратора</b>\n\n👥 Пользователей: {user_count}\n💸 Выплачено: {total_withdrawn} ⭐️", parse_mode='HTML', reply_markup=markup_admin)
        except Exception as e:
            logging.error(f"Ошибка при получении статистики для админ-панели: {e}")
            await bot.send_message(message.from_user.id, "<b>🎉 Вы вошли в панель администратора</b>\n\n⚠️ Ошибка при получении статистики.", parse_mode='HTML', reply_markup=markup_admin)
    else:
        await bot.send_message(message.from_user.id, "<b>🚫 У вас нет доступа к панели администратора</b>", parse_mode='HTML')

@router.callback_query(F.data == "stats_tasks")
async def stats_tasks_callback(call: CallbackQuery, bot: Bot):
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    if call.message.chat.id in admins_id:
        tasks = get_active_tasks()
        text = "Статистика по заданиям:\n\n"
        for task in tasks:
            task_id = task[0]
            task_reward = task[2]
            task_max_comp = task[-3]
            task_cur_comp = get_current_completed(task_id)
            text += f"<b>🎯 Задание №<code>{task_id}</code>:\n🎁 Награда: <code>{task_reward}</code>⭐️\n🤝 Количество участников: <code>{task_cur_comp}</code>/<code>{task_max_comp}</code></b>\n\n"

        await bot.send_message(call.message.chat.id, text, parse_mode='HTML')

@router.callback_query(F.data == "admin_lotery")
async def adminka_lottery(call: CallbackQuery, bot: Bot):
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    if call.message.chat.id in admins_id:
        builder_lottery = InlineKeyboardBuilder()
        builder_lottery.button(text='🎉 Начать лотерею', callback_data='start_lotery')
        builder_lottery.button(text='🏁 Завершить лотерею', callback_data='finish_lotery')
        builder_lottery.button(text="⭐️ Админ-Панель", callback_data="adminpanelka")
        markup_lottery = builder_lottery.adjust(2, 1).as_markup()
        lot_id = get_id_lottery_enabled()
        cash = get_cash_in_lottery()
        ticket_cash = get_ticket_cash_in_lottery()

        try:
            await bot.send_message(call.message.chat.id, f"<b>🎉 Вы вошли в админ-лотерею\n\n🎰 Активная лотерея: <code>{lot_id}</code>\n💰 Потрачено Stars: <code>{cash}</code>\n💸 Стоимость билета: <code>{ticket_cash}</code></b>", parse_mode='HTML', reply_markup=markup_lottery)
        except Exception as e:
            logging.error(f"Ошибка при получении статистики для админ-панели: {e}")
    else:
        await bot.send_message(call.message.chat.id, "<b>🚫 У вас нет доступа к панели администратора</b>", parse_mode='HTML')

@router.callback_query(F.data == "finish_lotery")
async def finish_lotery_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    if call.message.chat.id in admins_id:
        active_lottery = get_active_lottery_id()
        if not active_lottery:
            await bot.send_message(call.message.chat.id, "❌ Нет активной лотереи")
            return
        cash = get_cash_in_lottery()
        cash = float(cash) * 0.6
        markup_exit_to_admin = InlineKeyboardBuilder()
        markup_exit_to_admin.button(text="⭐️ Админ-Панель", callback_data="adminpanelka")
        markup_exit_to_admin.adjust(1)
        keyboard = markup_exit_to_admin.as_markup()
        status, win_id = finish_and_update_winner()
        if status:
            try:
                await bot.send_message(call.message.chat.id, f"<b>🎉 Лотерея завершена</b>\n\n<b>🎁 Выиграл <code>{win_id}</code>\n💰 Сумма: {cash:.2f}</b>", parse_mode='HTML', reply_markup=keyboard)
                await bot.send_message(win_id, f"<b>🎉 Вы выиграли лотерею!\n\n💰 Вы забираете 60% со всех звезд в лотерее: {cash:.2f}</b>", parse_mode='HTML')
                increment_stars(win_id, cash)
            except Exception as e:
                logging.error(f"[LOTTERY] Ошибка при отправке сообщения: {e}")
        else:
            await bot.send_message(call.message.chat.id, "<b>🚫 Нет участников с билетами</b>", parse_mode='HTML', reply_markup=keyboard)
    else:
        await bot.send_message(call.message.chat.id, "<b>🚫 У вас нет доступа к панели администратора</b>", parse_mode='HTML')

@router.callback_query(F.data == "start_lotery")
async def start_lotery_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    if call.message.chat.id in admins_id:
        await bot.send_message(call.message.chat.id, "<b>💰 Введите стоимость одного билета: </b>", parse_mode='HTML')
        await state.set_state(LotteryState.ticket_cash)
    else:
        await bot.send_message(call.message.chat.id, "<b>🚫 У вас нет доступа к панели администратора</b>", parse_mode='HTML')

@router.message(StateFilter(LotteryState.ticket_cash))
async def handle_ticket_cash(message: Message, bot: Bot, state: FSMContext):
    try:
        ticket_cash = float(message.text)
    except ValueError:
        await message.reply("❌ Введите число!")
        return

    try:
        await bot.delete_message(message.chat.id, message.message_id)
        await bot.delete_message(message.chat.id, message.message_id - 1)
    except:
        pass

    await asyncio.sleep(1)
    
    create_lottery(0, ticket_cash)

    markuper = InlineKeyboardBuilder()
    markuper.button(text="⭐️ Админ-Панель", callback_data="adminpanelka")
    markuper.adjust(1)
    keyboard = markuper.as_markup()
    
    lot_id = get_id_lottery_enabled()
    cash = get_cash_in_lottery()
    
    await bot.send_message(
        chat_id=message.chat.id,
        text=f"<b>🎉 Лотерея началась!\n\n🎰 Активная лотерея: <code>{lot_id}</code>\n💰 Потрачено Stars: <code>{cash}</code>\n💸 Стоимость билета: <code>{ticket_cash}</code></b>",
        parse_mode='HTML',
        reply_markup=keyboard
    )
    
    await state.clear()

@router.callback_query(F.data == "give_boost")
async def giveboost(call: CallbackQuery, bot: Bot, state: FSMContext):
    if call.from_user.id in admins_id:
        await bot.send_message(call.from_user.id, "Ввдеите ID человека:")
        await state.set_state(AdminState.GIVE_BOOST)
    
@router.message(AdminState.GIVE_BOOST)
async def handle_give(message: Message, bot: Bot, state: FSMContext):
    try:
        user_id = message.text
        current_time = datetime.now()
        delta = timedelta(days=15)
        future_time = current_time + delta
        future_timestamp = future_time.timestamp()

        add_or_update_user_boost(user_id, future_timestamp)
        await bot.send_message(message.from_user.id, f"Вы выдали буст {user_id} на 15 дней")
    except Exception as e:
        logging.error("Ошибка в мануальной выдаче буста", e)
    await state.clear()


@router.callback_query(F.data == "adminpanelka")
async def adminpanelka_callback(call: CallbackQuery, bot: Bot):
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    if call.message.chat.id in admins_id:
        builder_admin = InlineKeyboardBuilder()
        builder_admin.button(text='🎰 Лотерея', callback_data='admin_lotery')
        builder_admin.button(text='📊 Статистика', callback_data='stats')
        builder_admin.button(text="🔎 Информация о пользователе", callback_data="users_check")
        builder_admin.button(text="⭐️ Выдать звезды", callback_data="add_stars")
        builder_admin.button(text="⭐️ Снять звезды", callback_data="remove_stars")
        builder_admin.button(text="📨 Рассылка", callback_data="mailing")
        builder_admin.button(text="🎁 Добавить промокод", callback_data='add_promo_code')
        builder_admin.button(text="🚫 Удалить промокод", callback_data='remove_promo_code')
        builder_admin.button(text="📝 Добавить канал", callback_data='add_channel')
        builder_admin.button(text="🚫 Удалить канал", callback_data='remove_channel')
        builder_admin.button(text="📝 Добавленные каналы", callback_data='info_added_channels')
        builder_admin.button(text="📝 Добавить задание", callback_data='add_task')
        builder_admin.button(text="🚫 Удалить задание", callback_data='remove_task')
        builder_admin.button(text="🏆 Топ-50 Баланс", callback_data='top_balance')
        builder_admin.button(text="🌠 Выдать буст", callback_data="give_boost")
        markup_admin = builder_admin.adjust(1, 1, 1, 2, 1, 2, 2, 1, 2, 1, 1).as_markup()

        try:
            user_count = get_user_count()
            total_withdrawn = get_total_withdrawn()
            await bot.send_message(call.message.chat.id, f"<b>🎉 Вы вошли в панель администратора</b>\n\n👥 Пользователей: {user_count}\n💸 Выплачено: {total_withdrawn} ⭐️", parse_mode='HTML', reply_markup=markup_admin)
        except Exception as e:
            logging.error(f"Ошибка при получении статистики для админ-панели: {e}")
            await bot.send_message(call.message.chat.id, "<b>🎉 Вы вошли в панель администратора</b>\n\n⚠️ Ошибка при получении статистики.", parse_mode='HTML', reply_markup=markup_admin)
    else:
        await bot.send_message(call.message.chat.id, "<b>🚫 У вас нет доступа к панели администратора</b>", parse_mode='HTML')

@router.callback_query(F.data == "stats")
async def stats_callback(call: CallbackQuery, bot: Bot):
    await bot.delete_message(call.message.chat.id, call.message.message_id)
    day_clicker = get_clicks_by_period('day')
    week_clicker = get_clicks_by_period('week')
    month_clicker = get_clicks_by_period('month')

    day_users = get_users_by_period('day')
    week_users = get_users_by_period('week')
    month_users = get_users_by_period('month')

    markup_stats = InlineKeyboardBuilder()
    markup_stats.button(text="⭐️ Админ-Панель", callback_data="adminpanelka")
    markup_stats.adjust(1)
    markup_stats = markup_stats.as_markup()

    await bot.send_message(call.from_user.id, f"""<b>📊 Статистика

🛎 Клики:
• За день: {day_clicker}
• За неделю: {week_clicker}
• За всё время: {month_clicker}

👤 Пользователи:
• За день: {day_users}
• За неделю: {week_users}
• За всё время: {month_users}</b>
""", parse_mode='HTML', reply_markup=markup_stats)


@router.message(F.text == '/why')
async def why_command(message: Message, bot: Bot):
    user_id = message.from_user.id
    # user = message.from_user.id
    # is_premium = getattr(user, 'is_premium', None)
    # response = await request_op(
    #     user_id=user_id,
    #     chat_id=message.chat.id,
    #     first_name=user.first_name,
    #     language_code=user.language_code,
    #     bot=bot,
    #     is_premium=is_premium
    # )

    # if response != 'ok':
    #     return
    await bot.send_message(user_id, f"""<b>🌟 Звезды —</b> <i>официальная</i> валюта Telegram.

💡 За каждого приглашенного друга вы получаете 1⭐️

✨ Звезды можно:
- Вывести в реальные деньги
- Дарить друзьям подарки
- Использовать для оплаты цифровых товаров/услуг в ботах

<b>💫 Счастливые часы</b>
Иногда запускаются в случайное время ⏰!
В это время ты можешь получать:
• 2⭐️ за каждого друга 👫
• <b>Увеличенные бонусы</b> за выполнение заданий и клики до <b>0.02</b>⭐️📝

✨ Следи за уведомлениями, чтобы не упустить шанс!

<b>🗓️ Вывод звезд</b>
Выдача подарков(звезд) проходит по субботам и в ограниченном количестве.
Подавай заявку заранее, что-бы получить раньше всех!

<b>☎️ По всем вопросам/рекламе/сотрудничеству:</b> {admin_username}
""", parse_mode='HTML')


@router.callback_query(F.data.startswith('withdraw:'))
async def handle_withdraw_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    username = call.from_user.username
    if username is None:
        await bot.answer_callback_query(call.id, "⚠️ Для вывода необходимо установить username.", show_alert=True)
        return
    builder_back = InlineKeyboardBuilder()
    builder_back.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_back = builder_back.as_markup()

    stars = call.data.split(':')[1]
    # print(stars)
    if stars != "premium1" and stars != "premium2":
        # print(stars)
        emoji = call.data.split(':')[2]
    count_refs = get_weekly_referrals(call.from_user.id)
    try:
        if stars != "premium1" and stars != "premium2":
            stars = int(stars)
        elif stars == "premium1":
            stars = 400
        elif stars == "premium2":
            stars = 1100
        if get_balance_user(call.from_user.id) < stars:
            await bot.answer_callback_query(call.id, "❌ У вас недостаточно звезд для вывода!", show_alert=True)
            return
        elif count_refs < 15 if user_in_booster(user_id) else count_refs < 20 :
            if user_in_booster(user_id):
                await bot.answer_callback_query(call.id, f"❌ Для вывода надо минимум 10 рефералов за текущую неделю! У тебя {count_refs}", show_alert=True)
                return
            else:
                await bot.answer_callback_query(call.id, f"❌ Для вывода надо минимум 20 рефералов за текущую неделю! У тебя {count_refs}", show_alert=True)
                return
        else:
            await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
            deincrement_stars(user_id, stars)
            add_withdrawal(user_id, stars)
            if stars == 400:
                for admin in admins_id:
                    button_refs = InlineKeyboardBuilder()
                    button_refs.button(text="👤 Рефераллы", callback_data=f"refferals:{user_id}")
                    markup_adminser = button_refs.as_markup()
                    await bot.send_message(admin, f"<b>❗️❗️❗️\n⚠️ Пользователь {user_id} | @{username} запросил вывод Telegram Premium на 1 месяц</b>", parse_mode='HTML', reply_markup=markup_adminser)
            elif stars == 1100:
                for admin in admins_id:
                    button_refs = InlineKeyboardBuilder()
                    button_refs.button(text="👤 Рефераллы", callback_data=f"refferals:{user_id}")
                    markup_adminser = button_refs.as_markup()                    
                    await bot.send_message(admin, f"<b>❗️❗️❗️\n⚠️ Пользователь {user_id} | @{username} запросил вывод Telegram Premium на 3 месяца</b>", parse_mode='HTML', reply_markup=markup_adminser)
            else:
                for admin in admins_id:
                    button_refs = InlineKeyboardBuilder()
                    button_refs.button(text="👤 Рефераллы", callback_data=f"refferals:{user_id}")
                    markup_adminser = button_refs.as_markup()
                    await bot.send_message(admin, f"<b>⚠️ Пользователь {user_id} | @{username} запросил вывод {stars}⭐️</b>", parse_mode='HTML', reply_markup=markup_adminser)
            if stars != 400 and stars != 1100:
                success, id_v = add_withdrawale(username, user_id, stars)
                status = get_status_withdrawal(user_id)
                # print(f"Отправляю сообщение в {channel_viplat_id}")
                pizda = await bot.send_message(channel_viplat_id, f"<b>✅ Запрос на вывод №{id_v}</b>\n\n👤 Пользователь: @{username} | ID {user_id}\n💫 Количество: <code>{stars}</code>⭐️ [{emoji}]\n\n🔄 Статус: <b>{status}</b>", disable_web_page_preview=True, parse_mode='HTML')
                builder_channel = InlineKeyboardBuilder()
                builder_channel.button(text="✅ Отправить", callback_data=f"paid:{id_v}:{pizda.message_id}:{user_id}:{username}:{stars}:{emoji}")
                builder_channel.button(text="❌ Отклонить", callback_data=f"denied:{id_v}:{pizda.message_id}:{user_id}:{username}:{stars}:{emoji}")
                builder_channel.button(text="👤 Профиль", url=f"https://t.me/{username}")
                markup_channel = builder_channel.adjust(2, 1).as_markup()
                await bot.edit_message_text(chat_id=pizda.chat.id, message_id=pizda.message_id, text=f"<b>✅ Запрос на вывод №{id_v}</b>\n\n👤 Пользователь: @{username} | ID {user_id}\n💫 Количество: <code>{stars}</code>⭐️ [{emoji}]\n\n🔄 Статус: <b>{status}</b>", parse_mode='HTML', reply_markup=markup_channel, disable_web_page_preview=True)
                await bot.send_message(user_id, f"<b>✅ Вы успешно отправили заявку на вывод {stars}⭐️</b>", parse_mode='HTML', reply_markup=markup_back)
            elif stars == 400:
                level_premium = 1
                success, id_v = add_withdrawale(username, user_id, stars)
                status = get_status_withdrawal(user_id)
                pizda = await bot.send_message(channel_viplat_id, f"<b>✅ Запрос на вывод №{id_v}</b>\n\n👤 Пользователь: @{username} | ID {user_id}\n🎁 Telegram Premium: 1 месяц\n\n🔄 Статус: <b>{status}</b>", disable_web_page_preview=True, parse_mode='HTML')
                builder_channel = InlineKeyboardBuilder()
                builder_channel.button(text="✅ Отправить", callback_data=f"premium_paid:{id_v}:{pizda.message_id}:{user_id}:{username}:{level_premium}")
                builder_channel.button(text="❌ Отклонить", callback_data=f"premium_denied:{id_v}:{pizda.message_id}:{user_id}:{username}:{level_premium}")
                builder_channel.button(text="👤 Профиль", url=f"https://t.me/{username}")
                markup_channel = builder_channel.adjust(2, 1).as_markup()
                await bot.edit_message_text(chat_id=pizda.chat.id, message_id=pizda.message_id, text=f"<b>✅ Запрос на вывод №{id_v}</b>\n\n👤 Пользователь: @{username} | ID {user_id}\n🎁 Telegram Premium: 1 месяц\n\n🔄 Статус: <b>{status}</b>", disable_web_page_preview=True, parse_mode='HTML', reply_markup=markup_channel)
                await bot.send_message(user_id, f"<b>✅ Вы успешно отправили заявку на вывод 🎁 Telegram Premium: 1 месяц</b>", parse_mode='HTML', reply_markup=markup_back)
            elif stars == 1100:
                level_premium = 3
                success, id_v = add_withdrawale(username, user_id, stars)
                status = get_status_withdrawal(user_id)
                pizda = await bot.send_message(channel_viplat_id, f"<b>✅ Запрос на вывод №{id_v}</b>\n\n👤 Пользователь: @{username} | ID {user_id}\n🎁 Telegram Premium: 3 месяца\n\n🔄 Статус: <b>{status}</b>", disable_web_page_preview=True, parse_mode='HTML')
                builder_channel = InlineKeyboardBuilder()
                builder_channel.button(text="✅ Отправить", callback_data=f"premium_paid:{id_v}:{pizda.message_id}:{user_id}:{username}:{level_premium}")
                builder_channel.button(text="❌ Отклонить", callback_data=f"premium_denied:{id_v}:{pizda.message_id}:{user_id}:{username}:{level_premium}")
                builder_channel.button(text="👤 Профиль", url=f"https://t.me/{username}")
                markup_channel = builder_channel.adjust(2, 1).as_markup()
                await bot.edit_message_text(chat_id=pizda.chat.id, message_id=pizda.message_id, text=f"<b>✅ Запрос на вывод №{id_v}</b>\n\n👤 Пользователь: @{username} | ID {user_id}\n🎁 Telegram Premium: 3 месяца\n\n🔄 Статус: <b>{status}</b>", disable_web_page_preview=True, parse_mode='HTML', reply_markup=markup_channel)
                await bot.send_message(user_id, f"<b>✅ Вы успешно отправили заявку на вывод 🎁 Telegram Premium: 3 месяца</b>", parse_mode='HTML', reply_markup=markup_back)
    except ValueError:
        await bot.answer_callback_query(call.id, "❌ Неверный формат суммы вывода.", show_alert=True)
    except Exception as e:
        logging.error(f"Ошибка при обработке вывода: {e}")
        await bot.answer_callback_query(call.id, "❌ Произошла ошибка при обработке вашего запроса на вывод.", show_alert=True)

@router.callback_query(F.data.startswith('refferals'))
async def handle_refferals_callback(call: CallbackQuery, bot: Bot):
    if call.from_user.id not in admins_id:
        return
    
    try:
        _, user_id_str = call.data.split(":")
        user_id = int(user_id_str)
    except (ValueError, IndexError):
        await call.answer("Неверный формат callback_data", show_alert=True)
        return

    refferals = get_user_refferals_list_and_username(user_id)
    
    base_data = [
        ("🆔 ID Пользователя", f"<code>{user_id}</code>"),
        ("🚀 Количество рефералов", f"{len(refferals)}")
    ]

    html_response = [f"<b>{key}: {value}</b>" for key, value in base_data]
    
    file_lines = [f"{key}: {value}" for key, value in base_data]

    if refferals:
        html_response.append("<b>Список рефералов (ID и username):</b>")
        file_lines.append("Список рефералов (ID и username):")
        
        for index, (ref_id, username) in enumerate(refferals, 1):
            html_line = f"{index}. ID: {ref_id}, Username: @{username}"
            file_line = f"{index}. ID: {ref_id}, Username: @{username}"
            
            html_response.append(html_line)
            file_lines.append(file_line)
    else:
        html_response.append("<i>У пользователя нет рефералов</i>")
        file_lines.append("У пользователя нет рефералов")

    html_message = '\n'.join(html_response)
    file_content = '\n'.join(file_lines).encode('utf-8')
    
    try:
        if len(refferals) < 50:
            await call.message.answer(html_message, parse_mode='HTML')
        else:
            document = BufferedInputFile(
                file_content, 
                filename=f'refferals_{user_id}.txt'
            )
            await bot.send_document(
                chat_id=call.from_user.id,
                document=document
            )
        
        await call.answer()
        
    except Exception as e:
        error_msg = "Ошибка при отправке сообщения" if len(refferals) < 50 else "Ошибка при отправке файла"
        print(f"Error: {e}")
        await call.answer(error_msg, show_alert=True)

@router.callback_query(F.data.startswith('premium_paid'))
async def handle_premium_paid_callback(call: CallbackQuery, bot: Bot):
    if call.from_user.id in admins_id:
        id_v = int(call.data.split(":")[1])
        mesag_id = int(call.data.split(":")[2])
        us_id = int(call.data.split(":")[3])
        us_name = call.data.split(":")[4]
        level_premium = int(call.data.split(":")[5])
        if level_premium == 1:
            await bot.edit_message_text(chat_id=channel_viplat_id, message_id=mesag_id, text=f"<b>✅ Запрос на вывод №{id_v}</b>\n\n👤 Пользователь: @{us_name} | ID: {us_id}\n🎁 Telegram Premium: 1 месяц\n\n🔄 Статус: <b>Подарок отправлен 🎁</b>\n\n<b><a href='{channel_osn}'>Основной канал</a></b> | <b><a href='{chater}'>Чат</a></b> | <b><a href='{'https://t.me/' + (await bot.me()).username}'>Бот</a></b>", parse_mode='HTML', disable_web_page_preview=True)
        elif level_premium == 2:
            await bot.edit_message_text(chat_id=channel_viplat_id, message_id=mesag_id, text=f"<b>✅ Запрос на вывод №{id_v}</b>\n\n👤 Пользователь: @{us_name} | ID: {us_id}\n🎁 Telegram Premium: 3 месяца\n\n🔄 Статус: <b>Подарок отправлен 🎁</b>\n\n<b><a href='{channel_osn}'>Основной канал</a></b> | <b><a href='{chater}'>Чат</a></b> | <b><a href='{'https://t.me/' + (await bot.me()).username}'>Бот</a></b>", parse_mode='HTML', disable_web_page_preview=True)
    else:
        await bot.answer_callback_query(call.id, "⚠️ Вы не администратор.")

@router.callback_query(F.data.startswith('premium_denied'))
async def handle_premium_denied_callback(call: CallbackQuery, bot: Bot):
    if call.from_user.id in admins_id:
        id_v = int(call.data.split(":")[1])
        mesag_id = int(call.data.split(":")[2])
        us_id = int(call.data.split(":")[3])
        us_name = call.data.split(":")[4]
        level_premium = int(call.data.split(":")[5])
        if level_premium == 1:
            await bot.edit_message_text(chat_id=channel_viplat_id, message_id=mesag_id, text=f"<b>✅ Запрос на вывод №{id_v}</b>\n\n👤 Пользователь: @{us_name} | ID: {us_id}\n🎁 Telegram Premium: 1 месяц\n\n🔄 Статус: <b>Отказано 🚫</b>\n\n<b><a href='{channel_osn}'>Основной канал</a></b> | <b><a href='{chater}'>Чат</a></b> | <b><a href='{'https://t.me/' + (await bot.me()).username}'>Бот</a></b>", parse_mode='HTML', disable_web_page_preview=True)
        elif level_premium == 2:
             await bot.edit_message_text(chat_id=channel_viplat_id, message_id=mesag_id, text=f"<b>✅ Запрос на вывод №{id_v}</b>\n\n👤 Пользователь: @{us_name} | ID: {us_id}\n🎁 Telegram Premium: 3 месяца\n\n🔄 Статус: <b>Отказано 🚫</b>\n\n<b><a href='{channel_osn}'>Основной канал</a></b> | <b><a href='{chater}'>Чат</a></b> | <b><a href='{'https://t.me/' + (await bot.me()).username}'>Бот</a></b>", parse_mode='HTML', disable_web_page_preview=True)
    else:
        await bot.answer_callback_query(call.id, "⚠️ Вы не администратор.")

@router.callback_query(F.data.startswith('play_game_with_bet'))
async def handle_game_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    try:
        bet = float(call.data.split(':')[1])
        balance = get_balance_user(user_id)

        if balance >= bet:
            deincrement_stars(user_id, bet)

            if random.random() < 0.30:
                coefficients = [0, 0.5, 1, 1.5, 2, 3, 5, 10]
                weights = [0.35, 0.3, 0.2, 0.08, 0.04, 0.02, 0.005, 0.005]
                coefficient = random.choices(coefficients, weights=weights)[0]
                winnings = bet * coefficient

                if coefficient > 0:
                    await bot.answer_callback_query(call.id, f"🎉 ОГРОМНАЯ ПОБЕДА! Вы выиграли: {winnings:.2f}", show_alert=True)
                    chat = await bot.get_chat(user_id)
                    first_name = chat.first_name
                    bot_url = "https://t.me/" + (await bot.me()).username
                    await bot.send_message(
                        id_channel_game,
                        f"<b>🎉 Поздравляем! 🏆</b>\n\nПользователь {first_name}(ID: <code>{user_id}</code>)\n"
                        f"<i>выиграл</i> <b>{winnings:.2f}</b>⭐️ на ставке <b>{bet:.2f}</b>⭐️ 🎲\n\n"
                        f"Коэффициент: <i>{coefficient}</i>✨\n\n"
                        f"<b>🎉 Потрясающий выигрыш! 🏆✨ 🎉</b>\n\n🎯 Не упусти свой шанс! <a href='{bot_url}'>Испытать удачу!🍀</a>",
                        disable_web_page_preview=True,
                        parse_mode='HTML'
                    )
                    increment_stars(user_id, winnings)
                    new_balance = get_balance_user(user_id)

                    builder_game = InlineKeyboardBuilder()
                    builder_game.button(text="Ставка 0.5⭐️", callback_data="play_game_with_bet:0.5")
                    builder_game.button(text="Ставка 1⭐️", callback_data="play_game_with_bet:1")
                    builder_game.button(text="Ставка 2⭐️", callback_data="play_game_with_bet:2")
                    builder_game.button(text="Ставка 3⭐️", callback_data="play_game_with_bet:3")
                    builder_game.button(text="Ставка 4⭐️", callback_data="play_game_with_bet:4")
                    builder_game.button(text="Ставка 5⭐️", callback_data="play_game_with_bet:5")
                    builder_game.button(text="Назад в меню мини-игр", callback_data="mini_games")
                    markup_game = builder_game.adjust(3, 3, 1).as_markup()

                    input_photo_game = FSInputFile("photos/mini_game.jpg")
                    await bot.delete_message(chat_id=user_id, message_id=call.message.message_id)
                    await bot.send_photo(user_id, photo=input_photo_game, caption=f"<b>💰 У тебя на счету:</b> {new_balance}⭐️\n\n🔔 Ты выбрал игру 'Испытать удачу'. Выбери ставку и попытайся победить! 🍀\n\n📊 Онлайн статистика выигрышей: {channel_link}", parse_mode='HTML', reply_markup=markup_game)
                else:
                    await bot.answer_callback_query(call.id, f"😔 Удача была близко, но коэффициент 0.\nВы ничего не выиграли.", show_alert=True)
                    new_balance = get_balance_user(user_id)
                    builder_game = InlineKeyboardBuilder()
                    builder_game.button(text="Ставка 0.5⭐️", callback_data="play_game_with_bet:0.5")
                    builder_game.button(text="Ставка 1⭐️", callback_data="play_game_with_bet:1")
                    builder_game.button(text="Ставка 2⭐️", callback_data="play_game_with_bet:2")
                    builder_game.button(text="Ставка 3⭐️", callback_data="play_game_with_bet:3")
                    builder_game.button(text="Ставка 4⭐️", callback_data="play_game_with_bet:4")
                    builder_game.button(text="Ставка 5⭐️", callback_data="play_game_with_bet:5")
                    builder_game.button(text="Назад в меню мини-игр", callback_data="mini_games")
                    markup_game = builder_game.adjust(3, 3, 1).as_markup()
                    input_photo_game_lose = FSInputFile("photos/mini_game.jpg")
                    await bot.delete_message(chat_id=user_id, message_id=call.message.message_id)
                    await bot.send_photo(user_id, photo=input_photo_game_lose, caption=f"<b>💰 У тебя на счету:</b> {new_balance}⭐️\n\n🔔 Ты выбрал игру 'Испытать удачу'. Выбери ставку и попытайся победить! 🍀\n\n📊 Онлайн статистика выигрышей: {channel_link}", parse_mode='HTML', reply_markup=markup_game)

            else:
                await bot.answer_callback_query(call.id, f"😔 К сожалению, сегодня удача не на вашей стороне.", show_alert=True)
                new_balance = get_balance_user(user_id)
                builder_game = InlineKeyboardBuilder()
                builder_game.button(text="Ставка 0.5⭐️", callback_data="play_game_with_bet:0.5")
                builder_game.button(text="Ставка 1⭐️", callback_data="play_game_with_bet:1")
                builder_game.button(text="Ставка 2⭐️", callback_data="play_game_with_bet:2")
                builder_game.button(text="Ставка 3⭐️", callback_data="play_game_with_bet:3")
                builder_game.button(text="Ставка 4⭐️", callback_data="play_game_with_bet:4")
                builder_game.button(text="Ставка 5⭐️", callback_data="play_game_with_bet:5")
                builder_game.button(text="Назад в меню мини-игр", callback_data="mini_games")
                markup_game = builder_game.adjust(3, 3, 1).as_markup()
                input_photo_game_no_luck = FSInputFile("photos/mini_game.jpg")
                await bot.delete_message(chat_id=user_id, message_id=call.message.message_id)
                await bot.send_photo(user_id, photo=input_photo_game_no_luck, caption=f"<b>💰 У тебя на счету:</b> {new_balance}⭐️\n\n🔔 Ты выбрал игру 'Испытать удачу'. Выбери ставку и попытайся победить! 🍀\n\n📊 Онлайн статистика выигрышей: {channel_link}", parse_mode='HTML', reply_markup=markup_game)
        else:
            await bot.answer_callback_query(call.id, "😞 У тебя недостаточно звезд для этой ставки.", show_alert=True)
    except ValueError:
        await bot.answer_callback_query(call.id, "❌ Неверный формат ставки.", show_alert=True)
    except Exception as e:
        logging.error(f"Ошибка в мини-игре: {e}")
        await bot.answer_callback_query(call.id, "❌ Произошла ошибка в игре.", show_alert=True)


@router.callback_query(F.data.startswith('task_check'))
async def handle_task_callback(call: CallbackQuery, bot: Bot):
    try:
        _, reward, task_id_str, chat_id = call.data.split(":")
        task_id = int(task_id_str)
        user_id = call.from_user.id
        reward = float(reward)
        completed_task = get_completed_tasks_for_user(user_id)
        if task_id in completed_task:
            await bot.answer_callback_query(call.id, "❌ Задание уже выполнено.", show_alert=True)
            return

        try:
            all_stars = str(sum_all_stars())
            withdrawed = str(sum_all_withdrawn())
        except Exception as e:
            logging.error(f"Ошибка при получении статистики: {e}")
            all_stars = "Ошибка"
            withdrawed = "Ошибка"
        if chat_id != "None":
            try:
                chat_member = await bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                if chat_member.status not in ['member', 'administrator', 'creator']:
                    await bot.answer_callback_query(call.id, "❌ Вы не подписались на канал!")
                    return
            except Exception as e:
                print(f"error in check subs in tasks: {e}")
        await bot.answer_callback_query(call.id, f"✅ Задание выполнено. Начислено: {reward}⭐️")
        increment_current_completed(task_id)
        complete_task_for_user(user_id, task_id)
        increment_stars(user_id, reward)
        await bot.delete_message(chat_id=user_id, message_id=call.message.message_id)

        builder_start = InlineKeyboardBuilder()
        buttons = [
            ('✨ Фармить звёзды', 'click_star'),
            ('🎮 Мини-игры', 'mini_games'),
            ('🔗 Получить ссылку', 'earn_stars'),
            ('🔄 Обменять звёзды', 'withdraw_stars_menu'),
            ('👤 Профиль', 'my_balance'),
            ('📝 Задания', 'tasks'),
            ('📘 Гайды | FAQ', 'faq'),
            ('🚀 Буст', 'donate'),
            ('🏆 Топ', 'leaders')
        ]
        for text, callback_data in buttons:
            builder_start.button(text=text, callback_data=callback_data)
        if beta_url and beta_name:
            builder_start.button(text=beta_name, url=beta_url)
        builder_start.adjust(1, 1, 2, 2, 2, 2, 1)
        markup_start = builder_start.as_markup()

        photo = FSInputFile("photos/start.jpg")
        await bot.send_photo(
            chat_id=user_id,
            photo=photo,
            caption=(
                f"<b>✨ Добро пожаловать в главное меню ✨</b>\n\n"
                f"<b>🌟 Всего заработано: <code>{all_stars[:all_stars.find('.') + 2] if '.' in all_stars else all_stars}</code>⭐️</b>\n"
                f"<b>♻️ Всего обменяли: <code>{withdrawed[:withdrawed.find('.') + 2] if '.' in withdrawed else withdrawed}</code>⭐️</b>\n\n"
                "<b>Как заработать звёзды?</b>\n"
                "<blockquote>🔸 <i>Кликай, собирай ежедневные награды и вводи промокоды</i>\n"
                "— всё это доступно в разделе «Профиль».\n"
                "🔸 <i>Выполняй задания и приглашай друзей</i>\n"
                "🔸 <i>Испытай удачу в увлекательных мини-играх</i>\n"
                "— всё это доступно в главном меню.</blockquote>"
            ),
            parse_mode='HTML',
            reply_markup=markup_start
        )
        # await bot.send_message(user_id, f"<b>✨ Добро пожаловать на ферму звёзд! ✨</b>\n\n🏦 <b>Всего заработано:</b> {all_stars[:all_stars.find('.') + 2] if '.' in all_stars else all_stars}⭐️\n💸 <b>Всего выведено:</b> {withdrawed[:withdrawed.find('.') + 2] if '.' in withdrawed else withdrawed}⭐️\n\nТы присоединился к проекту, где звезды Telegram можно зарабатывать абсолютно бесплатно! ⭐️\n<b>Чем больше друзей — тем больше звёзд!</b>\n\n<b>🚀 Как приглашать друзей?</b>\n• Поделись ссылкой с друзьями в ЛС 👥\n• Размести её в своём Telegram-канале 📢\n• Напиши в группах и комментариях 🗨️\n• Распространяй в соцсетях (TikTok, Instagram, WhatsApp и др.) 🌍", parse_mode='HTML', reply_markup=markup_start)
    except ValueError:
        await bot.answer_callback_query(call.id, "Ошибка обработки данных задания.")
    except Exception as e:
        logging.error(f"Ошибка в handle_task: {e}")
        await bot.answer_callback_query(call.id, "Произошла ошибка при обработке задания.")

@router.callback_query(F.data == 'click_star')
async def click_star_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = call.from_user.id
    current_time = time.time()
    try:
        last_click_time_db = get_last_click_time(user_id)
        if last_click_time_db:
            time_since_last_click = current_time - last_click_time_db
            if time_since_last_click < DELAY_TIME:
                remaining_time = DELAY_TIME - time_since_last_click
                await bot.answer_callback_query(call.id, f"⌛️ Подождите еще {int(remaining_time)} секунд перед следующим кликом.", show_alert=True)
                return
    except Exception as e:
        logging.error(f"Ошибка при проверке времени клика: {e}")
        await bot.answer_callback_query(call.id, "⚠️ Произошла ошибка при проверке времени. Попробуйте позже.", show_alert=True)
        return

    try:
        click_count = get_count_clicks(user_id)
        if click_count % 5 != 0:
            update_last_click_time(user_id)
            if user_exists(user_id):
                random_value = get_random_value()
                await bot.answer_callback_query(call.id, f"🎉 Ты получил {random_value * 2.5 if user_in_booster(user_id) else random_value}⭐️", show_alert=True)
                increment_stars(user_id, random_value * 2.5 if user_in_booster(user_id) else random_value)
                update_click_count(user_id)
            else:
                await bot.answer_callback_query(call.id, "⚠️ Произошла ошибка. Пожалуйста, перезапустите бота командой /start.", show_alert=True)
        else:
            await bot.answer_callback_query(call.id, "⚠️ Обнаружена подозрительная активность, пройдите проверку на бота.")
            if call.message:
                await bot.delete_message(chat_id=user_id, message_id=call.message.message_id)
            else:
                logging.warning("call.message is None, cannot delete message.")

            vegetables_emojis = ['🥕', '🍅', '🍆', '🥔', '🥦', '🥬', '🥒', '🧅', '🌽', '🌶️']
            correct_vegetable = random.choice(vegetables_emojis)
            other_vegetables = random.sample([v for v in vegetables_emojis if v != correct_vegetable], 2)
            options = [correct_vegetable] + other_vegetables
            random.shuffle(options)
            markup_captcha = InlineKeyboardBuilder()
            for option in options:
                markup_captcha.button(text=option, callback_data=f'veg_{option}')
            markup_captcha.adjust(3)
            await bot.send_message(user_id, f"<b>Ответ на капчу: {correct_vegetable}</b>", reply_markup=markup_captcha.as_markup(), parse_mode='HTML')
            await state.update_data(captcha_correct_answer=correct_vegetable)
            await state.set_state(CaptchaClick.waiting_click_captcha)


    except Exception as e:
        logging.error(f"Ошибка при обработке клика: {e}, type: {type(e)}")
        await bot.answer_callback_query(call.id, "⚠️ Произошла ошибка при начислении звезд за клик.", show_alert=True)

@router.callback_query(F.data.startswith('veg_'))
async def handle_captcha_click(call: CallbackQuery, bot: Bot, state: FSMContext):
    user_id = call.from_user.id
    user_answer = call.data.split('_')[1]
    
    data = await state.get_data()
    correct_answer = data.get('captcha_correct_answer')
    
    if correct_answer is None:
        logging.error(f"Ошибка: captcha_correct_answer не найден для пользователя {user_id}")
        await bot.answer_callback_query(call.id, "⚠️ Произошла ошибка. Пожалуйста, повторите попытку.", show_alert=True)
        await state.clear()
        return
    
    if correct_answer == user_answer:
        update_last_click_time(user_id)
        if user_exists(user_id):
            random_value = get_random_value()
            await bot.answer_callback_query(call.id, f"💫 Вы прошли проверку на бота\n🎉 Ты получил(а) {random_value * 2.5 if user_in_booster(user_id) else random_value}⭐️", show_alert=True)
            increment_stars(user_id, random_value * 2.5 if user_in_booster(user_id) else random_value)
            update_click_count(user_id)
            await bot.delete_message(chat_id=user_id, message_id=call.message.message_id)
            await send_main_menu(user_id, bot)
            await state.clear()
        else:
            await bot.answer_callback_query(call.id, "⚠️ Произошла ошибка. Пожалуйста, перезапустите бота командой /start.", show_alert=True)
            await state.clear()
    else:
        await bot.answer_callback_query(call.id, "❌ Неправильно!", show_alert=True)

@router.callback_query(F.data == "users_check")
async def users_check_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.send_message(call.from_user.id, "Введите ID пользователя:")
    await state.set_state(AdminState.USERS_CHECK)

@router.callback_query(F.data == "add_stars")
async def admin_add_stars_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.send_message(call.from_user.id, "Для выдачи звезд необходимо написать ID:Количество звезд.\nПример: 123:5")
    await state.set_state(AdminState.ADD_STARS)


@router.callback_query(F.data == "remove_stars")
async def admin_remove_stars_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.send_message(call.from_user.id, "Для снятия звезд необходимо написать ID:Количество звезд.\nПример: 123:5")
    await state.set_state(AdminState.REMOVE_STARS)

@router.callback_query(F.data.startswith("subgram-op"))
async def subgram_op_callback(call: CallbackQuery, bot: Bot):
    try:
        user = call.from_user
        user_id = user.id
        ref_id = None

        if len(call.data.split(":")) > 1:
            try:
                ref_id = int(call.data.split(":")[1])
            except ValueError:
                logging.warning(f"Invalid ref_id format: {call.data}")

        response = await request_op(
            user_id=user_id,
            chat_id=call.message.chat.id,
            first_name=user.first_name,
            language_code=user.language_code,
            bot=bot,
            ref_id=ref_id,
            is_premium=getattr(user, 'is_premium', None)
        )

        if response != 'ok':
            await bot.answer_callback_query(call.id, "❌ Вы всё ещё не подписаны на все каналы!", show_alert=True)
            return

        await bot.answer_callback_query(call.id, 'Спасибо за подписку 👍', show_alert=True)


        if not user_exists(user_id):
            try:
                add_user(user_id, user.username, ref_id)
                await handle_referral_bonus(ref_id, user_id, bot)
            except Exception as e:
                logging.error(f"User registration error: {e}")

        await send_main_menu(user_id, bot)

    except Exception as e:
        logging.error(f"Subgram op error: {e}", exc_info=True)
        await bot.answer_callback_query(call.id, "⚠️ Произошла ошибка при проверке подписки", show_alert=True)

async def handle_referral_bonus(ref_id: Optional[int], new_user_id: int, bot: Bot):
    if not ref_id or not user_exists(ref_id):
        return

    try:
        increment_referrals(ref_id)
        c_refs = get_user_referrals_count(ref_id)
        if c_refs < 50:
            nac = 0.7 * 2 if user_in_booster(ref_id) else 0.7
            increment_stars(ref_id, nac)
        elif 50 <= c_refs < 250:
            nac = 1 * 2 if user_in_booster(ref_id) else 1
            increment_stars(ref_id, nac)
        else:
            nac = 1.5 * 2 if user_in_booster(ref_id) else 1.5
            increment_stars(ref_id, nac)
        new_ref_link = f"https://t.me/{(await bot.me()).username}?start={ref_id}"
        await bot.send_message(
                ref_id,
                f"🎉 Пользователь <code>{new_user_id}</code> запустил бота по вашей ссылке!\n"
                f"Вы получили +{nac}⭐️ за реферала.\n"
                f"Поделитесь ссылкой ещё раз:\n<code>{new_ref_link}</code>",
                parse_mode='HTML'
        )
        # increment_stars(ref_id, 0.7)
        
        # new_ref_link = f"https://t.me/{(await bot.me()).username}?start={ref_id}"
        # await bot.send_message(
        #     ref_id,
        #     f"🎉 Новый реферал!\n"
        #     f"Пользователь ID: <code>{new_user_id}</code>\n"
        #     f"Ваш баланс пополнен на +0.7⭐\n"
        #     f"Реферальная ссылка:\n<code>{new_ref_link}</code>",
        #     parse_mode='HTML'
        # )
    except Exception as e:
        logging.error(f"Referral bonus error: {e}")

async def send_main_menu(user_id: int, bot: Bot):
    try:
        total_stars = sum_all_stars()
        total_withdrawn = sum_all_withdrawn()
        stars_str = f"{total_stars:.2f}" if isinstance(total_stars, float) else str(total_stars)
        withdrawn_str = f"{total_withdrawn:.2f}" if isinstance(total_withdrawn, float) else str(total_withdrawn)

        builder = InlineKeyboardBuilder()
        builder.add(
            *[
                InlineKeyboardButton(text='✨ Фармить звёзды', callback_data='click_star'),
                InlineKeyboardButton(text='🎮 Мини-игры', callback_data='mini_games'),
                InlineKeyboardButton(text='🔗 Получить ссылку', callback_data='earn_stars'),
                InlineKeyboardButton(text='🔄 Обменять звёзды', callback_data='withdraw_stars_menu'),
                InlineKeyboardButton(text='👤 Профиль', callback_data='my_balance'),
                InlineKeyboardButton(text='📝 Задания', callback_data='tasks'),
                InlineKeyboardButton(text='📘 Гайды | FAQ', callback_data='faq'),
                InlineKeyboardButton(text='🚀 Буст', callback_data='donate'),
                InlineKeyboardButton(text='🏆 Топ', callback_data='leaders')
            ]
        )
        
        if beta_url and beta_name:
            builder.add(InlineKeyboardButton(text=beta_name, url=beta_url))
            
        builder.adjust(1, 1, 2, 2, 2, 1)

        photo = FSInputFile("photos/start.jpg")
        await bot.send_photo(
            chat_id=user_id,
            photo=photo,
            caption=(
                "<b>✨ Добро пожаловать в главное меню ✨</b>\n\n"
                f"<b>🌟 Всего заработано: <code>{stars_str}</code>⭐️</b>\n"
                f"<b>♻️ Всего обменяли: <code>{withdrawn_str}</code>⭐️</b>\n\n"
                "<b>Как заработать звёзды?</b>\n"
                "<blockquote>🔸 Кликай, собирай ежедневные награды и вводи промокоды\n"
                "— всё это доступно в разделе «Профиль».\n"
                "🔸 Выполняй задания и приглашай друзей\n"
                "🔸 Испытай удачу в мини-играх\n"
                "— всё это доступно в главном меню.</blockquote>"
            ),
            parse_mode='HTML',
            reply_markup=builder.as_markup()
        )

    except Exception as e:
        logging.error(f"Main menu send error: {e}")

@router.callback_query(F.data == "mailing")
async def admin_mailing_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.send_message(call.from_user.id, "Введите текст рассылки:")
    await state.set_state(AdminState.MAILING)


@router.callback_query(F.data == "add_promo_code")
async def admin_add_promo_code_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.send_message(call.from_user.id, "Введите промокод:награда:макс. пользований")
    await state.set_state(AdminState.ADD_PROMO_CODE)


@router.callback_query(F.data == "remove_promo_code")
async def admin_remove_promo_code_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.send_message(call.from_user.id, "Введите промокод:")
    await state.set_state(AdminState.REMOVE_PROMO_CODE)


@router.callback_query(F.data == "add_task")
async def admin_add_task_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.send_message(call.from_user.id, "Введите текст задания:")
    await state.set_state(AdminState.ADD_TASK)

@router.callback_query(F.data == "top_balance")
async def admin_top_balance_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    top_users_data = get_top_balance()
    text_balance = "<b>🏆 Топ-50 по балансу:</b>\n\n"
    for index, user_data in enumerate(top_users_data):
        username = user_data[0]
        balance = user_data[1]
        if isinstance(balance, float):
            balance_formatted = f"{balance:.2f}" 
        else:
            balance_formatted = str(balance)
        text_balance += f"<b>{index + 1}. @{username}</b> - <code>{balance_formatted}</code> ⭐️\n"
    await bot.send_message(call.from_user.id, text_balance, parse_mode='HTML')


@router.callback_query(F.data == "remove_task")
async def admin_remove_task_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.send_message(call.from_user.id, "Введите ID задания:")
    await state.set_state(AdminState.REMOVE_TASK)


@router.callback_query(F.data == "add_channel")
async def admin_add_channel_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.send_message(call.from_user.id, "Введите ID канала:")
    await state.set_state(AdminState.ADD_CHANNEL)


@router.callback_query(F.data == "remove_channel")
async def admin_remove_channel_callback(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.send_message(call.from_user.id, "Введите ID канала:")
    await state.set_state(AdminState.REMOVE_CHANNEL)


@router.callback_query(F.data.startswith("paid"))
async def paid_callback(call: CallbackQuery, bot: Bot):
    if call.from_user.id in admins_id:
        id_v = int(call.data.split(":")[1])
        mesag_id = int(call.data.split(":")[2])
        us_id = int(call.data.split(":")[3])
        us_name = call.data.split(":")[4]
        strs = int(call.data.split(":")[5])
        emoji = call.data.split(":")[6]
        await bot.edit_message_text(chat_id=channel_viplat_id, message_id=mesag_id, text=f"<b>✅ Запрос на вывод №{id_v}</b>\n\n👤 Пользователь: @{us_name} | ID: {us_id}\n💫 Количество: <code>{strs}</code>⭐️ [{emoji}]\n\n🔄 Статус: <b>Подарок отправлен 🎁</b>\n\n<b><a href='{channel_osn}'>Основной канал</a></b> | <b><a href='{chater}'>Чат</a></b> | <b><a href='{'https://t.me/' + (await bot.me()).username}'>Бот</a></b>", parse_mode='HTML', disable_web_page_preview=True)
    else:
        await bot.answer_callback_query(call.id, "⚠️ Вы не администратор.")


async def safe_edit_message(bot, chat_id, message_id, new_text, reply_markup=None):
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=new_text,
            parse_mode='HTML',
            disable_web_page_preview=True,
            reply_markup=reply_markup
        )
    except TelegramBadRequest as e:
        print("error")
        if "message is not modified" not in str(e):
            raise

@router.callback_query(F.data.startswith("denied"))
async def denied_callback(call: CallbackQuery, bot: Bot):
    if call.from_user.id in admins_id:
        data = call.data.split(":")
        id_v, mesag_id, us_id, us_name, strs, emoji = map(str, data[1:7])

        reason_markup = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎰 Накрутка", callback_data=f"balk:{id_v}:{mesag_id}:{us_id}:{us_name}:{strs}:{emoji}:narkutka")],
            [InlineKeyboardButton(text="🎫 Не выполнены условия вывода", callback_data=f"balk:{id_v}:{mesag_id}:{us_id}:{us_name}:{strs}:{emoji}:usloviya")],
            [InlineKeyboardButton(text="❌ Черный список", callback_data=f"balk:{id_v}:{mesag_id}:{us_id}:{us_name}:{strs}:{emoji}:black_list")],
            [InlineKeyboardButton(text="⚠️ Багаюз", callback_data=f"balk:{id_v}:{mesag_id}:{us_id}:{us_name}:{strs}:{emoji}:bagous")]
        ])

        text = (
            f"<b>✅ Запрос на вывод №{id_v}</b>\n\n"
            f"👤 Пользователь: @{us_name} | ID: {us_id}\n"
            f"💫 Количество: <code>{strs}</code>⭐️ [{emoji}]\n\n"
            f"🔄 Статус: <b>Отказано 🚫</b>\n\n"
            f"<b><a href='{channel_osn}'>Основной канал</a></b> | "
            f"<b><a href='{chater}'>Чат</a></b> | "
            f"<b><a href='{'https://t.me/' + (await bot.me()).username}'>Бот</a></b>"
        )

        await safe_edit_message(bot, channel_viplat_id, int(mesag_id), text, reason_markup)
    else:
        await bot.answer_callback_query(call.id, "⚠️ Вы не администратор.")

@router.callback_query(F.data.startswith("balk"))
async def denied_reason_callback(call: CallbackQuery, bot: Bot):
    # print(1)
    if call.from_user.id in admins_id:
        # print("called")
        data = call.data.split(":")
        id_v, mesag_id, us_id, us_name, strs, emoji, reason = map(str, data[1:8])

        reasons = {
            "narkutka": "🎰 Накрутка",
            "usloviya": "🎫 Отсутствует подписка на канал/чат",
            "black_list": "❌ Черный список",
            "bagous": "⚠️ Багаюз"
        }

        reason_text = reasons.get(reason, "Неизвестная причина")

        text = (
            f"<b>✅ Запрос на вывод №{id_v}</b>\n\n"
            f"👤 Пользователь: @{us_name} | ID: {us_id}\n"
            f"💫 Количество: <code>{strs}</code>⭐️ [{emoji}]\n\n"
            f"🔄 Статус: <b>Отказано 🚫</b>\n"
            f"⚠️Причина: {reason_text} \u200B\n\n"
            f"<b><a href='{channel_osn}'>Основной канал</a></b> | "
            f"<b><a href='{chater}'>Чат</a></b> | "
            f"<b><a href='{'https://t.me/' + (await bot.me()).username}'>Бот</a></b>"
        )

        await safe_edit_message(bot, channel_viplat_id, int(mesag_id), text, None)
    else:
        await bot.answer_callback_query(call.id, "⚠️ Вы не администратор.")


# @router.callback_query(F.data == "donate_ymka")
# async def donate_ymka_callback(call: CallbackQuery, bot: Bot):
#     await bot.delete_message(call.from_user.id, call.message.message_id)
#     with open("photos/donate.jpg", "rb") as photo:
#         input_photo_donate_ymka = FSInputFile("photos/donate.jpg")
#         builder_pay = InlineKeyboardBuilder()
#         builder_pay.button(text="💛 Поддержать", url="https://yoomoney.ru/to/4100116335672818")
#         builder_pay.button(text="⬅️ В главное меню", callback_data="back_main")
#         markup_pay = builder_pay.adjust(1).as_markup()
#         await bot.send_photo(call.from_user.id, photo=input_photo_donate_ymka, caption=f'<b>💛 Поддержи наш проект</b>\n\n🌟 Переходи по ссылке для оплаты:', parse_mode='HTML', reply_markup=markup_pay)


@router.callback_query(F.data == "donate")
async def donate_callback(call: CallbackQuery, bot: Bot):
    user_is_boost = user_in_booster(call.from_user.id)
    if user_is_boost:
        await bot.answer_callback_query(call.id, f"⚠️ У вас и так есть буст.")
        return
    await bot.delete_message(call.from_user.id, call.message.message_id)
    prices = [LabeledPrice(label="XTR", amount=599)]
    builder_donate = InlineKeyboardBuilder()
    builder_donate.button(text=f"Заплатить ⭐599", pay=True)
    builder_donate.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_donate = builder_donate.adjust(1).as_markup()

    description = (
        "✨ Поддержи проект и получи бонусы!"
        "                                                       "
        "🌟 Множитель x2.5 к кликам на 15 дней."
        "                                                       "
        "🤝 Множитель x2 за рефералов на 15 дней."
    )
    # await bot.create_invoice_link
    await bot.send_invoice(call.from_user.id, title='Донат💛 ', description=description, prices=prices, provider_token="", payload="channel_support", currency="XTR", reply_markup=markup_donate)
    # input_photo_donate = FSInputFile("photos/donate.jpg")
    # await bot.send_photo(call.from_user.id, photo=input_photo_donate, caption=f'<b>💛 Выберите способ поддержки:</b>\n\n<i>Временно отключено.</i>\n\nВыберите подходящий вариант ниже.', parse_mode='HTML', reply_markup=markup_donate)


@router.pre_checkout_query()
async def pre_checkout_handler(pre_checkout_query: PreCheckoutQuery):  
    await pre_checkout_query.answer(ok=True)

@router.message(F.content_type == 'successful_payment')
async def successful_payment_handler(message: Message, bot: Bot):
    try:
        await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
        payment_info = message.successful_payment
        user_id = message.from_user.id
        username = message.from_user.username if message.from_user.username else "Нету"
        amount = payment_info.total_amount
        currency = payment_info.currency
        if currency == "XTR":
            currency = "⭐️"
        
        current_time = datetime.now()
        delta = timedelta(days=15)
        future_time = current_time + delta
        future_timestamp = future_time.timestamp()

        add_or_update_user_boost(user_id, future_timestamp)
        # time_until = get_time_until_boost(user_id)
        time_until_normal = datetime.fromtimestamp(future_timestamp)
        
        for admin in admins_id:
            await bot.send_message(
                admin,
                f"<b>❤️ Получен платёж.\n\nℹ️ Информация о полученном платеже:\n🆔 Айди: {user_id}\n🚹 Username: {username if username else None}\n💰 Получено: {amount} {currency}</b>",
                parse_mode='HTML'
            )
        
        await bot.send_message(
            user_id,
            f"<b>❤️ Получен платёж.\n\n✨ Буст был успешно активирован на 15 дней.</b>\n\n<i>У вас осталось времени буста до: {time_until_normal}</i>",
            parse_mode='HTML'
        )
    
    except Exception as e:
        logging.error(f"Ошибка при обработке успешного платежа: {e}")
        await bot.send_message(user_id, "<b>Произошла ошибка при обработке платежа. Пожалуйста, свяжитесь с администратором.</b>", parse_mode='HTML')

@router.callback_query(F.data == "info_added_channels")
async def info_added_channels_callback(call: CallbackQuery, bot: Bot):
    text = "⚙️ <b>В данный момент добавлены следующие каналы:</b>\n\n"
    if len(required_subscription) == 0:
        text += "<b>Нет добавленных каналов</b>\n"
    else:
        for index, channel_id in enumerate(required_subscription, start=1):
            try:
                text += f"<b>{index}. ID: <code>{channel_id}</code></b>\n"
            except Exception as e:
                logging.error(f"Ошибка при получении информации о канале: {e}")
    await bot.send_message(call.from_user.id, text, parse_mode='HTML')


@router.callback_query(F.data.startswith("check_subs"))
async def check_subs_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    refferal_id = None
    try:
        refferal_id = int(call.data.split(":")[1])
    except IndexError:
        pass

    if await check_subscription(user_id, required_subscription, bot, refferal_id=refferal_id):
        if not user_exists(user_id):
            add_user(user_id, call.from_user.username, refferal_id)
            if refferal_id is not None:
                c_refs = get_user_referrals_count(refferal_id)
                if c_refs < 50:
                    nac = 0.7 * 2 if user_in_booster(refferal_id) else 0.7
                    increment_stars(refferal_id, nac)
                elif 50 <= c_refs < 250:
                    nac = 1 * 2 if user_in_booster(refferal_id) else 1
                    increment_stars(refferal_id, nac)
                else:
                    nac = 1.5 * 2 if user_in_booster(refferal_id) else 1.5
                    increment_stars(refferal_id, nac)
                increment_referrals(refferal_id)
                # increment_stars(refferal_id, 0.7)
                new_ref_link = f"https://t.me/{ (await bot.me()).username }?start={refferal_id}"
                await bot.send_message(
                    refferal_id,
                    f"🎉 Пользователь <code>{user_id}</code> запустил бота по вашей ссылке!\n"
                    f"Вы получили +{nac}⭐️ за реферала.\n"
                    f"Поделитесь ссылкой ещё раз:\n<code>{new_ref_link}</code>",
                    parse_mode='HTML'
                )
                await bot.answer_callback_query(call.id, "🎉 Спасибо за подписку!")
                builder_new_markup = InlineKeyboardBuilder()
                builder_new_markup.button(text="⬅️ В главное меню", callback_data="back_main")
                new_markup = builder_new_markup.as_markup()
                await bot.send_message(user_id, "<b>✅ Вы успешно подписались! Перейдите в главное меню.</b>", parse_mode='HTML', reply_markup=new_markup)
        else:
            await bot.answer_callback_query(call.id, "🎉 Спасибо за подписку!")
            builder_new_markup = InlineKeyboardBuilder()
            builder_new_markup.button(text="⬅️ В главное меню", callback_data="back_main")
            new_markup = builder_new_markup.as_markup()
            await bot.send_message(user_id, "<b>✅ Вы успешно подписались! Перейдите в главное меню.</b>", parse_mode='HTML', reply_markup=new_markup)
    else:
        await bot.answer_callback_query(call.id, "❌ Подписка не найдена")


@router.callback_query(F.data == "mini_games")
async def mini_games_callback(call: CallbackQuery, bot: Bot):
    try:
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")
    builder_games = InlineKeyboardBuilder()
    # builder_games.button(text="[🔥] Монетка 🏵", callback_data="monetka_game")
    builder_games.button(text="[🔥] КНБ ✊✌️🖐", callback_data="knb_game")
    builder_games.button(text="Лотерея 🎰", callback_data="lottery_game")
    builder_games.button(text="Все или ничего 🎲", callback_data="play_game")
    builder_games.button(text="В главное меню", callback_data="back_main")
    markup_games = builder_games.adjust(1, 1, 2, 1).as_markup()

    with open('photos/mini_game.jpg', 'rb') as photo:
        input_photo_minigames = FSInputFile("photos/mini_game.jpg")
        await bot.send_photo(call.from_user.id, photo=input_photo_minigames, caption="<b>🎮 Добро пожаловать в мини-игры!</b> Выбери игру, чтобы начать:\n\n<b>1️⃣ Испытать удачу</b> — попробуй победить с разными ставками!\n<b>2️⃣ Лотерея</b> — купи билет и выиграй много звезд!\n<b>3️⃣ КНБ</b> — камень ножницы бумага", reply_markup=markup_games, parse_mode='HTML')

@router.callback_query(F.data == "knb_game")
async def knb_game_starter(call: CallbackQuery, bot: Bot, state: FSMContext):
    try:
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")

    builder_knb = InlineKeyboardBuilder()
    builder_knb.button(text="Назад в меню мини-игр", callback_data="mini_games")
    markup_knb = builder_knb.as_markup()
    input_photo_minigames = FSInputFile("photos/mini_game.jpg")
    await bot.send_photo(call.from_user.id, photo=input_photo_minigames, caption="<b>🕹 Вы вошли в мини-игру КНБ!</b>\n\n<blockquote><b>🎮 Суть игры: </b>\n<i>После ввода Username человека, ставки — вам первым дают на выбор 3 действия: Камень, Ножницы, Бумага. После вашего выбора — выбор переходит к сопернику и система анализирует победителя в игре.</i></blockquote>\n\n<blockquote><b>😊 Для начала игры введите Username человека</b></blockquote>", reply_markup=markup_knb, parse_mode='HTML')
    await state.set_state(KNBGame.waiting_username)

@router.message(KNBGame.waiting_username)
async def knb_game_username(message: Message, bot: Bot, state: FSMContext):
    username = message.text
    balance = get_balance_user(message.from_user.id)
    if balance <= 0:
        await bot.send_message(message.from_user.id , "🚫 У вас баланс меньше или равно 0.")
    if username.startswith('@'):
        username = username[1:]
    if username == (message.from_user.username):
        await bot.send_message(message.from_user.id, "🚫 Вы не можете играть сам с собой.")
        return
    user_id = get_id_from_username(username)
    if user_id is None:
        await bot.send_message(message.from_user.id, "🚫 Пользователь не найден.")
        return
    await state.update_data(username=username)
    await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
    # await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id - 1)
    builder_knb = InlineKeyboardBuilder()
    builder_knb.button(text="Назад в меню мини-игр", callback_data="mini_games")
    markup_knb = builder_knb.as_markup()
    input_photo_minigames = FSInputFile("photos/mini_game.jpg")
    await bot.send_photo(message.from_user.id, photo=input_photo_minigames, caption=f"<b>🕹 Вы вошли в мини-игру КНБ!</b>\n\n<blockquote><b>👤 Выбран игрок: <code>{username}</code> | <code>{user_id}</code></b></blockquote>\n\n<blockquote><b>💰 Введите ставку:</b></blockquote>", reply_markup=markup_knb, parse_mode='HTML')
    await state.set_state(KNBGame.waiting_stake)

@router.message(KNBGame.waiting_stake)
async def knb_game_stake(message: Message, bot: Bot, state: FSMContext):
    try:
        stake = float(message.text)
        balance_user1 = get_balance_user(message.from_user.id)
        username = await state.get_data()
        username = username['username']
        user_id = get_id_from_username(username)
        balance_user2 = get_balance_user(user_id)
        if balance_user1 < stake:
            await bot.send_message(message.from_user.id, "🚫 У вас недостаточно звёзд.")
            return
        elif balance_user2 < stake:
            await bot.send_message(message.from_user.id, "🚫 У игрока недостаточно звёзд.")
            return
        elif stake < 0:
            await bot.send_message(message.from_user.id, "🚫 Ставка не может быть отрицательной.")
    except ValueError:
        await bot.send_message(message.from_user.id, "🚫 Пожалуйста, введите число.")
        return
    await state.update_data(stake=stake)
    await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id)
    # await bot.delete_message(chat_id=message.from_user.id, message_id=message.message_id - 1)
    id = create_knb(message.from_user.id, user_id, bet=stake)
    input_photo_minigames = FSInputFile("photos/mini_game.jpg")
    await bot.send_photo(message.from_user.id, photo=input_photo_minigames, caption=f"<b>🕹 Вы вошли в мини-игру КНБ!</b>\n\n<blockquote><b>👤 Выбран игрок: <code>{username}</code> | <code>{user_id}</code>\n💰 Ставка: <code>{stake}</code></b></blockquote>\n\n<i>Ожидайте, пока пользователь примет игру.</i>", parse_mode='HTML')
    player_builder = InlineKeyboardBuilder()
    player_builder.button(text="✅ Принять игру", callback_data=f"accept_knb:{id}:{stake}:{message.from_user.id}")
    player_builder.button(text="❌ Отказаться", callback_data=f"decline_knb:{id}:{message.from_user.id}")
    player_markup = player_builder.adjust(1, 1).as_markup()
    await bot.send_message(user_id, f"🕹 Вас пригласили в мини-игру КНБ!\n\n<blockquote><b>🆔 Игры: {id}\n👤 Пригласил игрок: <code>{message.from_user.first_name}</code> | <code>{message.from_user.id}</code>\n💰 Ставка: <code>{stake}</code></b></blockquote>", parse_mode='HTML', reply_markup=player_markup)

@router.callback_query(F.data.startswith("accept_knb:"))
async def accept_knb_callback(call: CallbackQuery, bot: Bot):
    id_game = call.data.split(':')[1]
    stake = call.data.split(':')[2]
    use_id = call.data.split(':')[3]
    await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    await bot.answer_callback_query(call.id, "✅ Вы приняли игру.")
    await bot.send_message(call.from_user.id, "⌛️ Ожидайте, пока пользователь сделает свой ход.")

    deincrement_stars(use_id, stake)
    deincrement_stars(call.from_user.id, stake)
    markup_choice = InlineKeyboardBuilder()
    markup_choice.button(text="[✊] Камень", callback_data=f"stone_knb:{id_game}:first_player")
    markup_choice.button(text="[✌️] Ножницы", callback_data=f"scissors_knb:{id_game}:first_player")
    markup_choice.button(text="[✋] Бумага", callback_data=f"paper_knb:{id_game}:first_player")
    markup = markup_choice.adjust(3).as_markup()
    await bot.send_message(use_id, f"<b>✅ Пользователь {call.from_user.first_name} принял игру.</b>\n\n<blockquote><b>💰 Ставка: {stake}</b></blockquote>", parse_mode='HTML', reply_markup=markup)

@router.callback_query(F.data.split(":")[2] == "first_player")
async def handle_first_player_choice(call: CallbackQuery, bot: Bot):
    data_parts = call.data.split(":")
    choice_type = data_parts[0].split("_")[0]
    game_id = data_parts[1]
    
    change_choice(game_id, "first_player", choice_type)
    
    game = get_knb_game(game_id)
    # print(game)
    second_player_id = game[2]
    stake = game[6]
    
    markup_choice = InlineKeyboardBuilder()
    markup_choice.button(text="✊ Камень", callback_data=f"stone_knb:{game_id}:second_player")
    markup_choice.button(text="✌️ Ножницы", callback_data=f"scissors_knb:{game_id}:second_player")
    markup_choice.button(text="✋ Бумага", callback_data=f"paper_knb:{game_id}:second_player")
    markup = markup_choice.adjust(3).as_markup()
    await bot.send_message(
        second_player_id,
        f"<b>🎲 Ваш ход в игре против {call.from_user.first_name}</b>\n\n"
        f"<blockquote><b>💰 Ставка:</b> <code>{stake}</code></blockquote>",
        reply_markup=markup,
        parse_mode='HTML'
    )
    await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    await bot.answer_callback_query(call.id, "✅ Вы выбрали свой ход.")

@router.message(F.text == '/клики')
async def clicks_command(message: Message, bot: Bot):
    if message.chat.id == id_chat:
        await message.answer(f"<b>🎉 Количество кликов: {get_count_clicks(message.from_user.id)}</b>", parse_mode='HTML')
        # await bot.send_message(message.chat.id, f"<b>🎉 Количество кликов: {get_count_clicks(message.from_user.id)}</b>", parse_mode='HTML')

@router.message(F.text == "/рефералы")
async def ref_command(message: Message, bot: Bot):
    if message.chat.id == id_chat:
        await message.answer(f"<b>🎉 Количество рефералов: {get_user_referrals_count(message.from_user.id)}</b>", parse_mode='HTML')
        # await bot.send_message(message.chat.id, f"<b>🎉 Количество рефералов: {get_user_referrals_count(message.from_user.id)}</b>", parse_mode='HTML')

@router.message(F.text == "/баланс")
async def balance_command(message: Message, bot: Bot):
    if message.chat.id == id_chat:
        await message.answer(f"<b>🎉 Ваш баланс: {get_balance_user(message.from_user.id):.2f}</b>", parse_mode='HTML')
        # await bot.send_message(message.chat.id, f"<b>🎉 Ваш баланс: {get_balance_user(message.from_user.id):.2f}</b>", parse_mode='HTML')
    
@router.message(F.text == "/статистика")
async def stats_command(message: Message, bot: Bot):
    if message.chat.id == id_chat:
        clicks = get_count_clicks(message.from_user.id)
        refs = get_user_referrals_count(message.from_user.id)
        withdrawed = get_withdrawn(message.from_user.id)
        if user_in_booster(message.from_user.id):
            time_until = get_time_until_boost(message.from_user.id)
            time_until = datetime.fromtimestamp(time_until).strftime("%d")
            await message.answer(f"<b>👤 Статистика: {message.from_user.id} | {message.from_user.first_name}</b>\n\n<blockquote><i>💫 Количество кликов: {clicks}</i>\n<i>👥 Количество рефераллов: {refs}</i>\n<i>⭐️ Выведено звёзд: {withdrawed:.2f}</i>\n<i>⌛️ Дней до окончания буста: {time_until}</i></blockquote>", parse_mode='HTML')
        else:
            await message.answer(f"<b>👤 Статистика: {message.from_user.id} | {message.from_user.first_name}</b>\n\n<blockquote><i>💫 Количество кликов: {clicks}</i>\n<i>👥 Количество рефераллов: {refs}</i>\n<i>⭐️ Выведено звёзд: {withdrawed:.2f}</i></blockquote>", parse_mode='HTML')
        # await bot.send_message(message.chat.id, f"<b>👤 Статистика: {message.from_user.id} | {message.from_user.first_name}</b>\n\n<blockquote><i>💫 Количество кликов: {clicks}</i>\n<i>👥 Количество рефераллов: {refs}</i>\n<i>⭐️ Выведено звёзд: {withdrawed:.2f}</i></blockquote>", parse_mode='HTML')

@router.callback_query(F.data.split(":")[2] == "second_player_chat")
async def handle_second_player_choice(call: CallbackQuery, bot: Bot):
    data_parts = call.data.split(":")
    choice_type = data_parts[0].split("_")[0]
    game_id = data_parts[1]
    
    change_choice(game_id, "second_player", choice_type)
    
    await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    await bot.answer_callback_query(call.id, "✅ Вы выбрали свой ход.")
    winner_text = ""

    game = get_knb_game(game_id)
    first_player_id = game[1]
    second_player_id = game[2]
    choice_1 = game[3]
    # print(choice_1)
    choice_2 = game[4]
    # print(choice_2)
    stake = game[6]
    result = set_result(game_id, choice_1, choice_2)
    # print(result)
    if result == "Ничья":
        winner_text = "Ничья! 🟰"
        increment_stars(first_player_id, stake)
        increment_stars(second_player_id, stake)
    else:
        winner_id = first_player_id if result == "Первый игрок победил!" else second_player_id
        # print(winner_id)
        increment_stars(winner_id, stake * 2)
        winner = await bot.get_chat(winner_id)
        winner_text = f"Победу одержал @{winner.username}"
        # print(winner_text)

    if choice_1 == "stone":
        choice_1 = "[✊] Камень"
    elif choice_1 == "scissors":
        choice_1 = "[✌️] Ножницы"
    elif choice_1 == "paper":
        choice_1 = "[✋] Бумага"
    
    if choice_2 == "stone":
        choice_2 = "[✊] Камень"
    elif choice_2 == "scissors":
        choice_2 = "[✌️] Ножницы"
    elif choice_2 == "paper":
        choice_2 = "[✋] Бумага"
    
    
    for player_id in [first_player_id, second_player_id]:
        builder_knb = InlineKeyboardBuilder()
        builder_knb.button(text="Назад в меню мини-игр", callback_data="mini_games")
        markup_knb = builder_knb.as_markup()
        first_player = await bot.get_chat(first_player_id)
        second_player = await bot.get_chat(second_player_id)
        await bot.send_message(
            player_id,
            f"<b>🎉 Игра завершена!</b>\n"
            f"<blockquote>➖➖➖➖➖➖➖\n"
            f"<b><a href='https://t.me/{first_player.username}'>👤 Игрок 1</a>: {choice_1}\n"
            f"<a href='https://t.me/{second_player.username}'>👤 Игрок 2</a>: {choice_2}</b>\n"
            f"➖➖➖➖➖➖➖\n"
            f"<b>🏆 Результат игры: {winner_text}</b>\n"
            f"<b>💰 Ставка: <code>{stake}</code></b></blockquote>",
            parse_mode='HTML',
            disable_web_page_preview=True,
            reply_markup=markup_knb
        )
    await bot.send_message(
            id_channel_game,
            f"<b>🎉 Игра завершена!</b>\n"
            f"<blockquote>➖➖➖➖➖➖➖\n"
                f"<b><a href='https://t.me/{first_player.username}'>👤 Игрок 1</a>: {choice_1}\n"
            f"<a href='https://t.me/{second_player.username}'>👤 Игрок 2</a>: {choice_2}</b>\n"
            f"➖➖➖➖➖➖➖\n"
            f"<b>🏆 Результат игры: {winner_text}</b>\n"
            f"<b>💰 Ставка: <code>{stake}</code></b></blockquote>",
            parse_mode='HTML',
            disable_web_page_preview=True
        )



@router.callback_query(F.data.split(":")[2] == "second_player")
async def handle_second_player_choice(call: CallbackQuery, bot: Bot):
    data_parts = call.data.split(":")
    choice_type = data_parts[0].split("_")[0]
    game_id = data_parts[1]
    
    change_choice(game_id, "second_player", choice_type)
    
    await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    await bot.answer_callback_query(call.id, "✅ Вы выбрали свой ход.")
    winner_text = ""

    game = get_knb_game(game_id)
    first_player_id = game[1]
    second_player_id = game[2]
    choice_1 = game[3]
    # print(choice_1)
    choice_2 = game[4]
    # print(choice_2)
    stake = game[6]
    result = set_result(game_id, choice_1, choice_2)
    # print(result)
    if result == "Ничья":
        winner_text = "Ничья! 🟰"
        increment_stars(first_player_id, stake)
        increment_stars(second_player_id, stake)
    else:
        winner_id = first_player_id if result == "Первый игрок победил!" else second_player_id
        # print(winner_id)
        increment_stars(winner_id, stake * 2)
        winner = await bot.get_chat(winner_id)
        winner_text = f"Победу одержал @{winner.username}"
        # print(winner_text)

    if choice_1 == "stone":
        choice_1 = "[✊] Камень"
    elif choice_1 == "scissors":
        choice_1 = "[✌️] Ножницы"
    elif choice_1 == "paper":
        choice_1 = "[✋] Бумага"
    
    if choice_2 == "stone":
        choice_2 = "[✊] Камень"
    elif choice_2 == "scissors":
        choice_2 = "[✌️] Ножницы"
    elif choice_2 == "paper":
        choice_2 = "[✋] Бумага"
    
    
    for player_id in [first_player_id, second_player_id]:
        builder_knb = InlineKeyboardBuilder()
        builder_knb.button(text="Назад в меню мини-игр", callback_data="mini_games")
        markup_knb = builder_knb.as_markup()
        first_player = await bot.get_chat(first_player_id)
        second_player = await bot.get_chat(second_player_id)
        await bot.send_message(
            player_id,
            f"<b>🎉 Игра завершена!</b>\n"
            f"<blockquote>➖➖➖➖➖➖➖\n"
            f"<b><a href='https://t.me/{first_player.username}'>👤 Игрок 1</a>: {choice_1}\n"
            f"<a href='https://t.me/{second_player.username}'>👤 Игрок 2</a>: {choice_2}</b>\n"
            f"➖➖➖➖➖➖➖\n"
            f"<b>🏆 Результат игры: {winner_text}</b>\n"
            f"<b>💰 Ставка: <code>{stake}</code></b></blockquote>",
            parse_mode='HTML',
            disable_web_page_preview=True,
            reply_markup=markup_knb
        )
    await bot.send_message(
            id_channel_game,
            f"<b>🎉 Игра завершена!</b>\n"
            f"<blockquote>➖➖➖➖➖➖➖\n"
                f"<b><a href='https://t.me/{first_player.username}'>👤 Игрок 1</a>: {choice_1}\n"
            f"<a href='https://t.me/{second_player.username}'>👤 Игрок 2</a>: {choice_2}</b>\n"
            f"➖➖➖➖➖➖➖\n"
            f"<b>🏆 Результат игры: {winner_text}</b>\n"
            f"<b>💰 Ставка: <code>{stake}</code></b></blockquote>",
            parse_mode='HTML',
            disable_web_page_preview=True
        )


@router.callback_query(F.data.startswith("decline_knb:"))
async def decline_knb_callback(call: CallbackQuery, bot: Bot):
    id_game = call.data.split(':')[1]
    use_id = call.data.split(':')[2]
    delete_knb(id_game)
    await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    await bot.answer_callback_query(call.id, "🚫 Вы отказались от игры.")
    await bot.send_message(use_id, "❌ Пользователь отказался от игры.")

@router.callback_query(F.data == "lottery_game")
async def lottery_game_callback(call: CallbackQuery, bot: Bot):
    lot_id = get_id_lottery_enabled()
    if lot_id != "Нет.":
        count_tickets_user = get_count_tickets_by_user(lot_id, call.from_user.id)
        if count_tickets_user > 0:
            await bot.answer_callback_query(call.id, "🎉 Вы уже купили билет в данную лотерею.")
            return
        all_cash = get_cash_in_lottery()
        # money_user = get_balance_user(call.from_user.id)
        ticket_cash = get_ticket_cash_in_lottery()
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
        lottery_game = InlineKeyboardBuilder()
        lottery_game.button(text="🎫 Купить билет", callback_data=f"buy_ticket:{lot_id}:{ticket_cash}")
        lottery_game.button(text="Назад в меню мини-игр", callback_data="mini_games")
        markup_lottery_game = lottery_game.adjust(1, 1).as_markup()
        await bot.send_message(call.from_user.id, f"<b>🎉 Вы вошли в лотерею №{lot_id}\n\n💰 Текущий джекпот: {all_cash}\n💵 Стоимость одного билета: {ticket_cash}</b>", parse_mode='HTML', reply_markup=markup_lottery_game)
    else:
        await bot.answer_callback_query(call.id, "😇 В данный момент лотерея не проводится.")

@router.callback_query(F.data.startswith("buy_ticket:"))
async def buy_ticket_callback(call: CallbackQuery, bot: Bot):
    lot_id = call.data.split(':')[1]
    count_tickets_user = get_count_tickets_by_user(lot_id, call.from_user.id)
    if count_tickets_user > 0:
        await bot.answer_callback_query(call.id, "🎉 Вы уже купили билет в данную лотерею.")
        return
    ticket_cash = call.data.split(':')[2]
    money_user = get_balance_user(call.from_user.id)
    if float(ticket_cash) > money_user:
        await bot.answer_callback_query(call.id, "❌ У вас недостаточно звезд.")
        return
    await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    add_lottery_entry(lot_id, call.from_user.id, call.from_user.username, ticket_cash)
    deincrement_stars(call.from_user.id, float(ticket_cash))
    lottery_back = InlineKeyboardBuilder()
    lottery_back.button(text="Назад в меню мини-игр", callback_data="mini_games")
    markup_lottery_back = lottery_back.adjust(1).as_markup()
    await bot.send_message(call.from_user.id, f"<b>🎫 Вы купили билет в лотерею №{lot_id}</b>", parse_mode='HTML', reply_markup=markup_lottery_back)

@router.callback_query(F.data == "play_game")
async def play_game_callback(call: CallbackQuery, bot: Bot):
    # user = call.message.from_user
    # user_id = user.id
    # is_premium = getattr(user, 'is_premium', None)
    # response = await request_op(
    #     user_id=user_id,
    #     chat_id=call.message.chat.id,
    #     first_name=user.first_name,
    #     language_code=user.language_code,
    #     bot=bot,
    #     is_premium=is_premium
    # )

    # if response != 'ok':
    #     return
    builder_game = InlineKeyboardBuilder()
    builder_game.button(text="Ставка 0.5⭐️", callback_data="play_game_with_bet:0.5")
    builder_game.button(text="Ставка 1⭐️", callback_data="play_game_with_bet:1")
    builder_game.button(text="Ставка 2⭐️", callback_data="play_game_with_bet:2")
    builder_game.button(text="Ставка 3⭐️", callback_data="play_game_with_bet:3")
    builder_game.button(text="Ставка 4⭐️", callback_data="play_game_with_bet:4")
    builder_game.button(text="Ставка 5⭐️", callback_data="play_game_with_bet:5")
    builder_game.button(text="Назад в меню мини-игр", callback_data="mini_games")
    markup_game = builder_game.adjust(3, 3, 1).as_markup()

    try:
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")
    try:
        balance = get_balance_user(call.from_user.id)
        with open('photos/mini_game.jpg', 'rb') as photo:
            input_photo_playgame = FSInputFile("photos/mini_game.jpg")
            await bot.send_photo(call.from_user.id, photo=input_photo_playgame, caption=f"<b>💰 У тебя на счету:</b> {balance} ⭐️\n\n🔔 Ты выбрал игру 'Испытать удачу'. Выбери ставку и попытайся победить! 🍀\n\n📊 Онлайн статистика выигрышей: {channel_link}", parse_mode='HTML', reply_markup=markup_game)
    except Exception as e:
        logging.error(f"Ошибка при получении баланса: {e}")
        await bot.send_message(call.from_user.id, f"<b>⚠️ Ошибка при получении баланса.</b>\n\n🔔 Ты выбрал игру 'Испытать удачу'. Выбери ставку и попытайся победить! 🍀\n\n📊 Онлайн статистика выигрышей: {channel_link}", parse_mode='HTML', reply_markup=markup_game)


@router.callback_query(F.data == "giftday")
async def giftday_callback(call: CallbackQuery, bot: Bot):
    user_id = call.from_user.id
    try:
        last_claim_time = get_last_daily_gift_time(user_id)
        current_time = time.time()
        if last_claim_time and (current_time - last_claim_time) < DAILY_COOLDOWN:
            remaining_time = int(DAILY_COOLDOWN - (current_time - last_claim_time))
            hours = remaining_time // 3600
            minutes = (remaining_time % 3600) // 60
            seconds = remaining_time % 60
            await bot.answer_callback_query(call.id, f"⌛️ Подождите еще {hours} часов, {minutes} минут(ы), {seconds} секунд(ы) перед следующим подарком", show_alert=True)
        else:
            increment_stars(user_id, GIFT_AMOUNT)
            update_last_daily_gift_time(user_id)
            await bot.answer_callback_query(call.id, f"🎉 Вы получили ежедневный подарок в размере {GIFT_AMOUNT}⭐️", show_alert=True)
    except Exception as e:
        logging.error(f"Ошибка при обработке ежедневного подарка: {e}")
        await bot.answer_callback_query(call.id, "⚠️ Произошла ошибка при получении ежедневного подарка.", show_alert=True)


@router.callback_query(F.data == "leaders")
async def leaders_callback(call: CallbackQuery, bot: Bot):
    await show_leaderboard(call.message, 'day', bot)


@router.callback_query(F.data == "week")
async def week_callback(call: CallbackQuery, bot: Bot):
    await show_leaderboard(call.message, 'week', bot)


@router.callback_query(F.data == "month")
async def month_callback(call: CallbackQuery, bot: Bot):
    await show_leaderboard(call.message, 'month', bot)

def extract_chat_info(link: str) -> str:
    parts = link.strip().split("/")
    identifier = parts[-1]
    if identifier.startswith("+"):
        return identifier
    
    return f"@{identifier}"


@router.callback_query(F.data == "tasks")
async def tasks_callback(call: CallbackQuery, bot: Bot):
    builder_back = InlineKeyboardBuilder()
    builder_back.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_back = builder_back.as_markup()

    try:
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")
    
    try:
        tasks = get_active_tasks()
        completed = get_completed_tasks_for_user(call.from_user.id)
        
        if not tasks:
            await bot.send_message(call.from_user.id, "<b>🎯 На данный момент нет доступных заданий!\n\nВозвращайся позже!</b>", parse_mode='HTML', reply_markup=markup_back)
            return

        global message_ids
        if 'message_ids' not in globals():
            message_ids = {}

        has_available_tasks = False

        for task_data in tasks:
            task_id, description, reward, link, is_active, boter, max_comp, cur_compl, id_chanel_private = task_data
            
            if task_id in completed:
                continue
                
            if cur_compl >= max_comp:
                continue
            
            has_available_tasks = True

            chat = None
            try:
                if id_chanel_private in (0, None):
                    chat_identifier = extract_chat_info(link)
                    chat = await bot.get_chat(chat_identifier)
                else:
                    chat = await bot.get_chat(id_chanel_private)
            except Exception as e:
                logging.error(f"Ошибка получения чата: {e}")

            builder_task_kb = InlineKeyboardBuilder()
            builder_task_kb.button(text="✅ Подписаться на канал", url=link)
            builder_task_kb.button(
                text="🔎 Проверить подписку", 
                callback_data=f"task_check:{reward}:{task_id}:{chat.id if chat else 'none'}"
            )
            builder_task_kb.button(text="⬅️ В главное меню", callback_data="back_main")
            markup_task = builder_task_kb.adjust(1).as_markup()

            with open('photos/task.jpg', 'rb') as photo:
                input_photo_task = FSInputFile("photos/task.jpg")
                msg = await bot.send_photo(
                    chat_id=call.from_user.id,
                    photo=input_photo_task,
                    caption=f'<b>✨ Новое задание! ✨!\n\n• {description}\n\nНаграда: {reward} ⭐️</b>\n\n📌 Чтобы получить награду полностью, подпишитесь и не ОТПИСЫВАЙТЕСЬ от канала/группы в течение 3-х дней "Проверить подписку" 👇',
                    parse_mode='HTML',
                    reply_markup=markup_task
                )
                message_ids[f"{call.from_user.id}_{task_id}"] = msg.message_id

        if not has_available_tasks:
            await bot.send_message(call.from_user.id, "<b>🎯 На данный момент нет доступных заданий!\n\nВозвращайся позже!</b>", parse_mode='HTML', reply_markup=markup_back)

    except Exception as e:
        logging.error(f"Ошибка при обработке заданий: {e}")
        await bot.send_message(call.from_user.id, "<b>⚠️ Ошибка при получении списка заданий.</b>", parse_mode='HTML', reply_markup=markup_back)


@router.callback_query(F.data == "withdraw_stars_menu")
async def withdraw_stars_menu_callback(call: CallbackQuery, bot: Bot):
    try:
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")

    # user = call.message.from_user
    # user_id = user.id
    # is_premium = getattr(user, 'is_premium', None)
    # response = await request_op(
    #     user_id=user_id,
    #     chat_id=call.message.chat.id,
    #     first_name=user.first_name,
    #     language_code=user.language_code,
    #     bot=bot,
    #     is_premium=is_premium
    # )

    # if response != 'ok':
    #     return

    builder_stars = InlineKeyboardBuilder()
    builder_stars.button(text="15 ⭐️(🧸)", callback_data="withdraw:15:🧸")
    builder_stars.button(text="15 ⭐️(💝)", callback_data="withdraw:15:💝")
    builder_stars.button(text="25 ⭐️(🌹)", callback_data="withdraw:25:🌹")
    builder_stars.button(text="25 ⭐️(🎁)", callback_data="withdraw:25:🎁")
    builder_stars.button(text="50 ⭐️(🍾)", callback_data="withdraw:50:🍾")
    builder_stars.button(text="50 ⭐️(🚀)", callback_data="withdraw:50:🚀")
    builder_stars.button(text="50 ⭐️(💐)", callback_data="withdraw:50:💐")
    builder_stars.button(text="50 ⭐️(🎂)", callback_data="withdraw:50:🎂")
    builder_stars.button(text="100 ⭐️(🏆)", callback_data="withdraw:100:🏆")
    builder_stars.button(text="100 ⭐️(💍)", callback_data="withdraw:100:💍")
    builder_stars.button(text="100 ⭐️(💎)", callback_data="withdraw:100:💎")
    builder_stars.button(text="Telegram Premium 1мес. (400 ⭐️)", callback_data="withdraw:premium1")
    builder_stars.button(text="Telegram Premium 3мес. (1100 ⭐️)", callback_data="withdraw:premium2")
    builder_stars.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_stars = builder_stars.adjust(2, 2, 2, 2, 2, 1, 1, 1).as_markup()

    try:
        balance = str(get_balance_user(call.from_user.id))
        with open('photos/withdraw_stars.jpg', 'rb') as photo:
            input_photo_withdraw = FSInputFile("photos/withdraw_stars.jpg")
            await bot.send_photo(call.from_user.id, photo=input_photo_withdraw, caption=f'<b>🔸 У тебя на счету: {balance[:balance.find(".") + 2]}⭐️</b>\n\n<b>❗️ Важно!</b> Для получения выплаты (подарка) нужно быть подписанным на:\n<a href="{channel_osn}">Основной канал</a> | <a href="{chater}">Чат</a> | <a href="{channel_viplat}">Канал выплат</a>\n\n<blockquote>‼️ Если не будет подписки в момент отправки подарка - выплата будет удалена, звёзды не возвращаются!</blockquote>\n\n<b>Выбери количество звёзд, которое хочешь обменять, из доступных вариантов ниже:</b>', parse_mode='HTML', reply_markup=markup_stars)
    except Exception as e:
        logging.error(f"Ошибка при отображении меню вывода: {e}")
        await bot.send_message(call.from_user.id, "<b>⚠️ Ошибка при отображении меню вывода.</b>", parse_mode='HTML', reply_markup=markup_stars)


@router.callback_query(F.data == "my_balance")
async def my_balance_callback(call: CallbackQuery, bot: Bot):
    try:
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")

    builder_profile = InlineKeyboardBuilder()
    builder_profile.button(text='🎁 Ежедневка', callback_data='giftday')
    builder_profile.button(text="🎫 Промокод", callback_data="promocode")
    builder_profile.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_profile = builder_profile.adjust(2, 1).as_markup()

    # Экранирование с помощью стандартной библиотеки
    nickname = html.escape(call.from_user.first_name)
    user_id = html.escape(str(call.from_user.id))

    try:
        balance = float(get_balance_user(call.from_user.id))
        count_refs = get_user_referrals_count(call.from_user.id)
        
        with open('photos/profile.jpg', 'rb') as photo:
            input_photo_profile = FSInputFile("photos/profile.jpg")
            if user_in_booster(call.from_user.id):
                time_until = get_time_until_boost(call.from_user.id)
                time_until_str = html.escape(datetime.fromtimestamp(time_until).strftime("%d"))
                caption = (
                    f"<b>✨ Профиль\n──────────────\n👤 Имя: {nickname}\n🆔 ID: <code>{user_id}</code>\n"
                    f"──────────────\n💰 Баланс:</b> {html.escape(f'{balance:.2f}')}⭐️\n"
                    f"<b>👥 Рефералов:</b> {html.escape(str(count_refs))}\n"
                    f"<b>──────────────</b>\n<b>⏳ Дней до окончания буста</b>: {time_until_str}\n"
                    f"<b>──────────────</b>\n⬇️ <i>Используй кнопки ниже для действий.</i>"
                )
                await bot.send_photo(
                    call.from_user.id,
                    photo=input_photo_profile,
                    caption=caption,
                    parse_mode='HTML',
                    reply_markup=markup_profile
                )
            else:
                caption = (
                    f"<b>✨ Профиль\n──────────────\n👤 Имя: {nickname}\n🆔 ID: <code>{user_id}</code>\n"
                    f"──────────────\n💰 Баланс:</b> {html.escape(f'{balance:.2f}')}⭐️\n"
                    f"<b>👥 Рефералов:</b> {html.escape(str(count_refs))}\n"
                    f"<b>──────────────</b>\n⬇️ <i>Используй кнопки ниже для действий.</i>"
                )
                await bot.send_photo(
                    call.from_user.id,
                    photo=input_photo_profile,
                    caption=caption,
                    parse_mode='HTML',
                    reply_markup=markup_profile
                )
    except Exception as e:
        logging.error(f"Ошибка при отображении профиля: {e}")
        error_message = (
            f"<b>Профиль: {nickname} | ID: <code>{user_id}</code></b>\n\n"
            f"<b>⚠️ Ошибка при получении данных профиля.\n"
            f"Пропишите /start для перезагрузки статистики</b>"
        )
        await bot.send_message(
            call.from_user.id,
            error_message,
            parse_mode='HTML',
            reply_markup=markup_profile
        )

@router.callback_query(F.data == "promocode")
async def promocode_callback_query(call: CallbackQuery, bot: Bot, state: FSMContext):
    await bot.delete_message(call.from_user.id, call.message.message_id)
    # user = call.message.from_user
    # user_id = user.id
    # is_premium = getattr(user, 'is_premium', None)
    # response = await request_op(
    #     user_id=user_id,
    #     chat_id=call.message.chat.id,
    #     first_name=user.first_name,
    #     language_code=user.language_code,
    #     bot=bot,
    #     is_premium=is_premium
    # )

    # if response != 'ok':
    #     return
    with open('photos/promocode.jpg', 'rb') as photo:
        input_photo_promo = FSInputFile("photos/promocode.jpg")
        await bot.send_photo(call.from_user.id, photo=input_photo_promo, caption=f"✨ Для получения звезд на ваш баланс введите промокод:\n*<i>Найти промокоды можно в <a href='{channel_osn}'>канале</a> и <a href='{chater}'>чате</a></i>", parse_mode='HTML')
    await state.set_state(AdminState.PROMOCODE_INPUT)


@router.callback_query(F.data == "faq")
async def faq_callback(call: CallbackQuery, bot: Bot):
    try:
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")
    
    # user = call.message.from_user
    # user_id = user.id
    # is_premium = getattr(user, 'is_premium', None)
    # response = await request_op(
    #     user_id=user_id,
    #     chat_id=call.message.chat.id,
    #     first_name=user.first_name,
    #     language_code=user.language_code,
    #     bot=bot,
    #     is_premium=is_premium
    # )

    # if response != 'ok':
    #     return
    
    builder_back = InlineKeyboardBuilder()
    builder_back.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_back = builder_back.as_markup()

    await bot.send_message(call.from_user.id, f"""<b>❓ Часто задаваемые вопросы (FAQ):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>
                         
<blockquote><b>🫡 Ответы на часто задаваемые вопросы

🟩Запросил(а) звёзды, когда придут? - Отправим вам подарок на сумму запрошенных звёзд в течение  3-х дней

🟩 Я получил(а) подарок а не звёзды! - Все верно, при клике на подарок вы можете забрать его или же конвертировать в звёзды

🟩 Люди переходят по ссылке, но я не получаю звёзд! - Значит данный пользователь уже переходил по чьей либо ссылке или же перешл в бота не по реф.ссылке

🟩 Могу купить или продать звёзды у вас? - Нет, мы не покупаем и не продаем звёзды телеграм!</b></blockquote>

<b>❗️ Обратите внимание:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━</b>
                 
<blockquote>Заявка может быть отклонена, если вы не подписаны на какой-либо канал или чат проекта.
📩 В таком случае свяжитесь с <a href="{admin_link}">Администрацией</a>, указав:
— Ссылку на пост с выплатой
— Ваш ID из бота
✨ Удачи и приятного фарма звёзд! 🌟</blockquote>
""", parse_mode='HTML', reply_markup=markup_back, disable_web_page_preview=True)


@router.callback_query(F.data == "earn_stars")
async def earn_stars_callback(call: CallbackQuery, bot: Bot):
    try:
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")
    
    # user = call.message.from_user
    # user_id = user.id
    # is_premium = getattr(user, 'is_premium', None)
    # response = await request_op(
    #     user_id=user_id,
    #     chat_id=call.message.chat.id,
    #     first_name=user.first_name,
    #     language_code=user.language_code,
    #     bot=bot,
    #     is_premium=is_premium
    # )

    # if response != 'ok':
    #     return

    ref_link = f"https://t.me/{ (await bot.me()).username }?start={call.from_user.id}"
    builder_earn = InlineKeyboardBuilder()
    builder_earn.button(text="👉 Поделиться ссылкой", url=f"https://t.me/share/url?url={ref_link}")
    builder_earn.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_earn = builder_earn.adjust(1).as_markup()
    c_refs = get_user_referrals_count(call.from_user.id)
    user_is_booster = user_in_booster(call.from_user.id)
    stars = 0
    level = 0
    if c_refs < 50:
        stars = 0.7
        level = 1
    elif c_refs >= 50 and c_refs < 250:
        stars = 1
        level = 2
    else:
        stars = 1.5
        level = 3

    blockquote_text = f"""
    <blockquote>🔹 <b>Ваш текущий уровень: {level}</b>

🔹 <b>Уровни и награды:</b>
- <b>1 уровень:</b> {0.7 * 2 if user_is_booster else 0.7} звезд ⭐️ (до 50 приглашений)
- <b>2 уровень:</b> {1 * 2 if user_is_booster else 1} звезда ⭐️ (от 50 до 250 приглашений)
- <b>3 уровень:</b> {1.5 * 2 if user_is_booster else 1.5} звезды ⭐️ (250+ приглашений)
    </blockquote>
    """

    with open("photos/get_url.jpg", "rb") as photo:
        input_photo_earn = FSInputFile("photos/get_url.jpg")
        await bot.send_photo(call.from_user.id, photo=input_photo_earn, caption=f'<b>🎉 Приглашай друзей и получай звёзды! ⭐️\n\n🚀 Как использовать свою реферальную ссылку?\n</b><i>• Отправь её друзьям в личные сообщения 👥\n• Поделись ссылкой в своём Telegram-канале 📢\n• Оставь её в комментариях или чатах 🗨️\n• Распространяй ссылку в соцсетях: TikTok, Instagram, WhatsApp и других 🌍</i>\n\n<b>💎 Что ты получишь?</b>\nЗа каждого друга, который перейдет по твоей ссылке, ты получаешь +<b>{stars * 2 if user_is_booster else stars}⭐️</b>!\n{blockquote_text}\n\n<b>🔗 Твоя реферальная ссылка:\n<code>{ref_link}</code>\n\nДелись и зарабатывай уже сейчас! 🚀</b>', parse_mode='HTML', reply_markup=markup_earn)

@router.callback_query(F.data == "back_main")
async def back_main_callback(call: CallbackQuery, bot: Bot):
    try:
        await bot.delete_message(chat_id=call.from_user.id, message_id=call.message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")

    builder_start = InlineKeyboardBuilder()
    buttons = [
        ('✨ Фармить звёзды', 'click_star'),
        ('🎮 Мини-игры', 'mini_games'),
        ('🔗 Получить ссылку', 'earn_stars'),
        ('🔄 Обменять звёзды', 'withdraw_stars_menu'),
        ('👤 Профиль', 'my_balance'),
        ('📝 Задания', 'tasks'),
        ('📘 Гайды | FAQ', 'faq'),
        ('🚀 Буст', 'donate'),
        ('🏆 Топ', 'leaders')
    ]
    for text, callback_data in buttons:
        builder_start.button(text=text, callback_data=callback_data)
    if beta_url and beta_name:
        builder_start.button(text=beta_name, url=beta_url)
    builder_start.adjust(1, 1, 2, 2, 2, 2, 1)
    markup_start = builder_start.as_markup()

    try:
        all_stars = str(sum_all_stars())
        withdrawed = str(sum_all_withdrawn())
        with open('photos/start.jpg', 'rb') as photo:
            input_photo_back_main = FSInputFile("photos/start.jpg")
            await bot.send_photo(call.from_user.id, photo=input_photo_back_main, caption=f"<b>✨ Добро пожаловать в главное меню ✨</b>\n\n<b>🌟 Всего заработано: <code>{all_stars[:all_stars.find('.') + 2] if '.' in all_stars else all_stars}</code>⭐️</b>\n<b>♻️ Всего обменяли: <code>{withdrawed[:withdrawed.find('.') + 2] if '.' in withdrawed else withdrawed}</code>⭐️</b>\n\n<b>Как заработать звёзды?</b>\n<blockquote>🔸 <i>Кликай, собирай ежедневные награды и вводи промокоды</i>\n— всё это доступно в разделе «Профиль».\n🔸 <i>Выполняй задания и приглашай друзей</i>\n🔸 <i>Испытай удачу в увлекательных мини-играх</i>\n— всё это доступно в главном меню.</blockquote>", parse_mode='HTML', reply_markup=markup_start)
    except Exception as e:
        logging.error(f"Ошибка при отображении главного меню: {e}")
        await bot.send_message(call.from_user.id, "<b>⚠️ Ошибка при отображении главного меню.</b>", parse_mode='HTML', reply_markup=markup_start)

@router.message(AdminState.USERS_CHECK)
async def users_check_handler(message: Message, state: FSMContext, bot: Bot):
    try:
        from datetime import datetime, timezone
        user_id = int(message.text)
        balance = get_balance_user(user_id)
        usname = get_username(user_id)
        count_ref = get_user_referrals_count(user_id)
        ref_id = get_id_refferer(user_id)
        withdrawd = get_withdrawn(user_id)
        reg_time = get_normal_time_registration(user_id)
        reg_time = datetime.fromtimestamp(reg_time, tz=timezone.utc).strftime('%d/%m/%Y %H:%M')
        click_count = get_count_clicks(user_id)
        await bot.send_message(message.from_user.id, f"🧾<b>Информация о пользователе:</b>\n\n👤 <b>ID пользователя:</b> <code>{user_id}</code>\n📛 <b>Имя пользователя:</b> @{usname}\n⭐️<b>Звёзды:</b> {balance}\n<b>────────────────────────────────────────</b>\n👥 <b>Количество рефералов:</b> {count_ref}\n🔗 <b>ID реферера:</b> {ref_id}\n<b>────────────────────────────────────────</b>\n💰 <b>Выведено:</b> {withdrawd}\n🌍 <b>Язык:</b> ru\n<b>────────────────────────────────────────</b>\n⏰ <b>Дата регистрации:</b> {reg_time}\n🪞 <b>Количество кликов:</b> {click_count}\n<b>────────────────────────────────────────</b>\n<b>Статус:</b> 🟢 Не заблокирован\n\n📊 <i>Информация актуальна на момент запроса.</i>", parse_mode='HTML')
    except ValueError:
        await bot.send_message(message.from_user.id, "<b>⚠️ Ошибка при проверке пользователя.</b>", parse_mode='HTML')
    finally:
        await state.clear()
@router.message(AdminState.ADD_STARS)
async def add_stars_handler(message: Message, state: FSMContext, bot: Bot):
    try:
        new = message.text.split(":")
        user_id = int(new[0])
        stars = float(new[1])
        balance_prev = get_balance_user(user_id)
        increment_stars(user_id, stars)
        balance_after = get_balance_user(user_id)
        await bot.send_message(message.from_user.id, f"<b>✅ Звезды успешно добавлены!</b>\n\n<b>💰 Предыдущий баланс:</b> {balance_prev:.2f}⭐️\n<b>💰 Новый баланс:</b> {balance_after:.2f}⭐️", parse_mode='HTML')
        await bot.send_message(user_id, "<b>✅ Администратор выдал вам звезды.</b>", parse_mode='HTML')
    except ValueError:
        await message.reply("<b>❌ Неверный формат ввода. Используйте ID:Количество звезд (числа).</b>", parse_mode='HTML')
    except Exception as e:
        logging.error(f"Ошибка в add_stars: {e}")
        await message.reply("<b>❌ Произошла ошибка при добавлении звезд.</b>", parse_mode='HTML')
    finally:
        await state.clear()


async def send_message_with_retry(
    bot: Bot,
    chat_id: int,
    text: str,
    parse_mode=None,
    reply_markup=None,
    photo_file_id: Optional[str] = None,
    attempt: int = 0
):
    try:
        if photo_file_id:
            await bot.send_photo(
                chat_id,
                photo=photo_file_id,
                caption=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
        else:
            await bot.send_message(
                chat_id,
                text,
                parse_mode=parse_mode,
                reply_markup=reply_markup
            )
    except (TelegramForbiddenError, TelegramNotFound) as e:
        logging.error(f"Сообщение запрещено/пользователь не найден: {chat_id}. Причина: {e}")
        raise
    except TelegramMigrateToChat as e:
        logging.info(f"Чат перенесён. Новый ID: {e.migrate_to_chat_id}")
        await send_message_with_retry(
            bot, e.migrate_to_chat_id, text, parse_mode, reply_markup, photo_file_id, attempt + 1
        )
    except TelegramRetryAfter as e:
        logging.warning(f"Ожидаем {e.retry_after} сек. из-за лимитов.")
        await asyncio.sleep(e.retry_after)
        await send_message_with_retry(
            bot, chat_id, text, parse_mode, reply_markup, photo_file_id, attempt + 1
        )
    except Exception as e:
        logging.exception(f"Ошибка отправки: {e}")
        raise


async def broadcast(
    bot: Bot,
    start_msg: types.Message,
    users: List[Tuple[int]],
    text: str,
    photo_file_id: str = None,
    keyboard=None
):
    total_users = len(users)
    if not total_users:
        await start_msg.reply("Нет пользователей для рассылки.")
        return

    progress_message = await start_msg.reply(
        f"Прогресс: 🟩⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️⬜️ 0%\nОбработано: 0/{total_users}\nУспешно: 0"
    )
    
    success = 0
    progress_blocks = 10

    for i, (user_id,) in enumerate(users):
        try:
            await send_message_with_retry(
                bot, user_id, text, "HTML", keyboard, photo_file_id
            )
            success += 1
        except Exception as e:
            logging.error(f"Ошибка для {user_id}: {e}")
        
        current = i + 1
        percent = (current / total_users) * 100
        filled = int(percent / 10)
        progress_bar = '🟩' * filled + '⬜️' * (10 - filled)
        
        if current % max(1, total_users//10) == 0 or current == total_users:
            try:
                await progress_message.edit_text(
                    f"Прогресс: {progress_bar} {percent:.1f}%\n"
                    f"Обработано: {current}/{total_users}\n"
                    f"Успешно: {success}"
                )
            except Exception as e:
                logging.error(f"Ошибка обновления прогресса: {e}")
        
        await asyncio.sleep(0.1)
    
    await progress_message.edit_text(f"✅ Успешно: {success}/{total_users}")


@router.message(AdminState.MAILING)
async def mailing_handler(message: types.Message, state: FSMContext):
    text = message.text or message.caption or ""
    photo_file_id = message.photo[-1].file_id if message.photo else None
    users = get_users_ids()

    buttons = re.findall(r"\{([^{}]+)\}:([^{}]+)", text)
    keyboard = None
    if buttons:
        kb = InlineKeyboardBuilder()
        for btn_text, btn_url in buttons:
            kb.button(text=btn_text.strip(), url=btn_url.strip())
        kb.adjust(2)
        keyboard = kb.as_markup()
        text = re.sub(r"\{[^{}]+\}:([^{}]+)", "", text).strip()

    formatted_text = apply_html_formatting(text, message.entities or [])

    await broadcast(
        message.bot, message, users, formatted_text, photo_file_id, keyboard
    )
    await state.clear()

def apply_html_formatting(text, entities):
    text = html.escape(text)
    formatted_text = list(text)
    tag_map = {
        "bold": ("<b>", "</b>"),
        "italic": ("<i>", "</i>"),
        "underline": ("<u>", "</u>"),
        "strikethrough": ("<s>", "</s>"),
        "spoiler": ("<span class='tg-spoiler'>", "</span>"),
        "code": ("<code>", "</code>"),
        "pre": ("<pre>", "</pre>"),
        "blockquote": ("<blockquote>", "</blockquote>"),
    }

    for entity in sorted(entities, key=lambda e: e.offset, reverse=True):
        start, end = entity.offset, entity.offset + entity.length
        if entity.type in tag_map:
            open_tag, close_tag = tag_map[entity.type]
            formatted_text.insert(end, close_tag)
            formatted_text.insert(start, open_tag)

    return "".join(formatted_text)

@router.message(AdminState.ADD_CHANNEL)
async def add_channel_handler(message: Message, state: FSMContext, bot: Bot):
    try:
        channel_id = message.text
        required_subscription.append(int(channel_id))
        await message.reply(f"<b>✅ Канал успешно добавлен!</b>", parse_mode='HTML')
    except Exception as e:
        logging.error(f"Ошибка при добавлении канала: {e}")
        await message.reply("<b>❌ Произошла ошибка при добавлении канала.</b>", parse_mode='HTML')
    finally:
        await state.clear()


@router.message(AdminState.REMOVE_CHANNEL)
async def delete_channel_handler(message: Message, state: FSMContext, bot: Bot):
    try:
        channel_id = message.text
        required_subscription.remove(int(channel_id))
        await message.reply(f"<b>✅ Канал успешно удален!</b>", parse_mode='HTML')
    except Exception as e:
        logging.error(f"Ошибка при удалении канала: {e}")
        await message.reply("<b>❌ Произошла ошибка при удалении канала.</b>", parse_mode='HTML')
    finally:
        await state.clear()


@router.message(AdminState.PROMOCODE_INPUT)
async def promocode_handler(message: Message, state: FSMContext, bot: Bot):
    user_id = message.from_user.id
    markup_back_inline = InlineKeyboardBuilder()
    markup_back_inline.button(text="⬅️ В главное меню", callback_data="back_main")
    markup_back = markup_back_inline.as_markup()

    promocode_text = message.text
    try:
        success, result = use_promocode(promocode_text, message.from_user.id)
        if success:
            await message.reply(f"<b>✅ Промокод успешно активирован!\nВам начислено {result} ⭐️</b>", parse_mode='HTML', reply_markup=markup_back)
            await send_main_menu(user_id, bot)
        else:
            await message.reply(f"<b>❌ Ошибка: {result}</b>", parse_mode='HTML')
            await send_main_menu(user_id, bot)
    except Exception as e:
        logging.error(f"Ошибка при активации промокода: {e}")
        await message.reply("<b>❌ Произошла ошибка при активации промокода.</b>", parse_mode='HTML')
        await send_main_menu(user_id, bot)
    finally:
        await state.clear()


@router.message(AdminState.ADD_PROMO_CODE)
async def add_promo_code_handler(message: Message, state: FSMContext, bot: Bot):
    try:
        promocode, stars_str, max_uses_str = message.text.split(":")
        stars = int(stars_str)
        max_uses = int(max_uses_str)
        add_promocode(promocode, stars, max_uses)
        await message.reply(f"<b>✅ Промокод успешно добавлен!</b>", parse_mode='HTML')
    except ValueError:
        await message.reply("<b>❌ Неверный формат ввода. Используйте промокод:награда:макс. пользований (числа).</b>", parse_mode='HTML')
    except Exception as e:
        logging.error(f"Ошибка при добавлении промокода: {e}")
        await message.reply("<b>❌ Произошла ошибка при добавлении промокода.</b>", parse_mode='HTML')
    finally:
        await state.clear()


@router.message(AdminState.REMOVE_PROMO_CODE)
async def delete_promo_code_handler(message: Message, state: FSMContext, bot: Bot):
    promocode = message.text
    try:
        deactivate_promocode(promocode)
        await message.reply(f"<b>✅ Промокод успешно удален!</b>", parse_mode='HTML')
    except Exception as e:
        logging.error(f"Ошибка при удалении промокода: {e}")
        await message.reply("<b>❌ Произошла ошибка при удалении промокода.</b>", parse_mode='HTML')
    finally:
        await state.clear()


@router.message(AdminState.ADD_TASK)
async def add_task_handler(message: Message, state: FSMContext, bot: Bot):
    text = message.text
    await state.update_data(task_text=text)
    await bot.send_message(message.chat.id, "<b>Введите награду в звездах: </b>", parse_mode='HTML')
    await state.set_state(AdminState.ADD_TASK_REWARD)


@router.message(AdminState.ADD_TASK_REWARD)
async def add_task_reward_handler(message: Message, state: FSMContext, bot: Bot):
    stars = message.text
    await state.update_data(task_reward=stars)
    await bot.send_message(message.chat.id, "<b>Введите ссылку на канал: </b>", parse_mode='HTML')
    await state.set_state(AdminState.CHECK_TASK_BOT)

@router.message(AdminState.CHECK_TASK_BOT)
async def check_task_bot(message: Message, state: FSMContext, bot: Bot):
    channel = message.text
    await state.update_data(task_channel=channel)
    await bot.send_message(message.chat.id, "<b>Бот? Да/нет</b>", parse_mode='HTML')
    await state.set_state(AdminState.ADD_MAX_USES)

@router.message(AdminState.ADD_MAX_USES)
async def add_max_uses_handler(message: Message, state: FSMContext, bot: Bot):
    boter = message.text
    # print(boter)
    await state.update_data(task_bot=boter)
    await bot.send_message(message.chat.id, "<b>Введите максимальное количество использований: </b>", parse_mode='HTML')
    await state.set_state(AdminState.ADD_TASK_PRIVATE)

@router.message(AdminState.ADD_TASK_PRIVATE)
async def add_task_private_handler(message: Message, state: FSMContext, bot: Bot):
    max_compl = message.text
    await state.update_data(task_max_compl=max_compl)
    await bot.send_message(message.chat.id, "<b>Введите ID приватного канала: (Если канал не приватный -> введите 0)</b>", parse_mode='HTML')
    await state.set_state(AdminState.ADD_TASK_CHANNEL)

@router.message(AdminState.ADD_TASK_CHANNEL)
async def add_task_channel_handler(message: Message, state: FSMContext, bot: Bot):
    channel_id_private = int(message.text)
    data = await state.get_data()
    text = data.get('task_text')
    stars = data.get('task_reward')
    channel = data.get('task_channel')
    boter = str(data.get('task_bot'))
    max_compl = data.get('task_max_compl')
    try:
        await state.clear()
        add_tasker(text, stars, channel, boter if boter.lower() == "да" else "none", int(max_compl), channel_id_private) 
        await message.reply(f"<b>✅ Задание успешно добавлено!</b>", parse_mode='HTML')
    except Exception as e:
        logging.error(f"Ошибка при добавлении задания: {e}")
        await message.reply("<b>❌ Произошла ошибка при добавлении задания.</b>", parse_mode='HTML')

@router.message(AdminState.REMOVE_TASK)
async def delete_task_handler(message: Message, state: FSMContext, bot: Bot):
    try:
        task_id = int(message.text)
        delete_task(task_id)
        await message.reply(f"<b>✅ Задание успешно удалено!</b>", parse_mode='HTML')
    except ValueError:
        await message.reply("<b>❌ Неверный формат ввода. Введите ID задания (число).</b>", parse_mode='HTML')
    except Exception as e:
        logging.error(f"Ошибка при удалении задания: {e}")
        await message.reply("<b>❌ Произошла ошибка при удалении задания.</b>", parse_mode='HTML')
    finally:
        await state.clear()


async def show_leaderboard(message: Message, period, bot: Bot):
    user_id = message.chat.id
    try:
        await bot.delete_message(user_id, message.message_id)
    except Exception as e:
        logging.error(f"Ошибка при удалении сообщения: {e}")

    # user = message.from_user.id
    # is_premium = getattr(user, 'is_premium', None)
    # response = await request_op(
    #     user_id=user,
    #     chat_id=message.chat.id,
    #     first_name=user.first_name,
    #     language_code=user.language_code,
    #     bot=bot,
    #     is_premium=is_premium
    # )

    # if response != 'ok':
    #     return

    try:
        top_referrals = get_top_referrals_formatted(period)
        user_rank = get_user_referral_rank_formatted(user_id, period)
        builder = InlineKeyboardBuilder()
        if period == "day":
            builder.button(text="📅 Топ за месяц", callback_data="month")
            builder.button(text="📅 Топ за неделю", callback_data="week")
        elif period == "week":
            builder.button(text="📅 Топ за день", callback_data="leaders")
            builder.button(text="📅 Топ за месяц", callback_data="month")
        elif period == "month":
            builder.button(text="📅 Топ за день", callback_data="leaders")
            builder.button(text="📅 Топ за неделю", callback_data="week")
        builder.button(text="⬅️ В главное меню", callback_data="back_main")
        markup = builder.adjust(2, 1).as_markup()

        if isinstance(top_referrals, str):
            text = f"<b>⚠️ Ошибка при получении списка лидеров за {get_period_name(period)}:</b>\n\n{top_referrals}"
        else:
            text = f"<b>Топ 5 рефералов за {get_period_name(period)}:</b>\n\n"
            for line in top_referrals:
                text += line + "\n"
            text += "\n" + user_rank

        with open('photos/leaders.jpg', 'rb') as photo:
            input_photo_leaders = FSInputFile("photos/leaders.jpg")
            await bot.send_photo(user_id, photo=input_photo_leaders, caption=text, parse_mode='HTML', reply_markup=markup)

    except Exception as e:
        logging.error(f"Ошибка при получении топа рефералов за {period}: {e}")
        builder = InlineKeyboardBuilder()
        builder.button(text="⬅️ В главное меню", callback_data="back_main")
        markup = builder.as_markup()
        await bot.send_message(user_id, f"<b>⚠️ Ошибка при получении списка лидеров за {get_period_name(period)}.</b>", parse_mode='HTML', reply_markup=markup)


def get_period_name(period):
    if period == 'day':
        return "24 часа"
    elif period == 'week':
        return "неделю"
    elif period == 'month':
        return "месяц"
    return period

async def set_bot_commands(bot: Bot):
    commands = [
        types.BotCommand(command='start', description='🌟 Заработать звёзды 🌟')
    ]
    await bot.set_my_commands(commands=commands)
    await bot.set_chat_menu_button(menu_button=types.MenuButtonCommands())

async def on_startup(bot: Bot):
    await set_bot_commands(bot)

async def main():    
    bot = Bot(token=TOKEN)
    dp = Dispatcher()
    dp.message.middleware(AntiFloodMiddleware(limit=1))
    dp.callback_query.middleware(AntiFloodMiddleware(limit=1))
    dp.startup.register(on_startup)
    dp.include_router(router)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(check_expired_boosts, 'interval', hours=24)
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())