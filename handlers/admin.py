from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery
import database
import locales
from handlers.user import get_lang

admin_router = Router()

@admin_router.callback_query(F.data.startswith("admin_approve_receipt:"))
async def approve_receipt(callback: CallbackQuery):
    payment_id = int(callback.data.split(":")[1])
    
    # Check if user is admin
    import config
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("У вас нет прав.")
        return
        
    user_id = database.approve_payment(payment_id)
    if user_id:
        await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ ОДОБРЕНО")
        await callback.answer("Чек одобрен, подписка продлена!")
        
        # Notify user
        lang = get_lang(user_id)
        t = locales.LOCALES[lang]
        user_info = database.get_user(user_id)
        if user_info and user_info['subscription_end_date']:
            import datetime
            end_date = datetime.datetime.fromisoformat(user_info['subscription_end_date']).strftime("%d.%m.%Y")
            try:
                await callback.bot.send_message(user_id, t['payment_approved'].format(end_date=end_date))
            except Exception:
                pass
    else:
        await callback.answer("Ошибка: платеж уже обработан или не найден.")

@admin_router.callback_query(F.data.startswith("admin_reject_receipt:"))
async def reject_receipt(callback: CallbackQuery):
    payment_id = int(callback.data.split(":")[1])
    
    import config
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("У вас нет прав.")
        return
        
    user_id = database.reject_payment(payment_id)
    if user_id:
        await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ ОТКЛОНЕНО")
        await callback.answer("Чек отклонен.")
        
        # Notify user
        lang = get_lang(user_id)
        t = locales.LOCALES[lang]
        try:
            await callback.bot.send_message(user_id, t['payment_rejected'])
        except Exception:
            pass
    else:
        await callback.answer("Ошибка: платеж уже обработан или не найден.")

from aiogram.filters import Command
from aiogram.types import Message

@admin_router.message(Command("broadcast"))
async def handle_broadcast(message: Message):
    import config
    if message.from_user.id not in config.ADMIN_IDS:
        return
        
    text_to_broadcast = message.text.replace("/broadcast", "").strip()
    if not text_to_broadcast:
        await message.answer("Пожалуйста, напишите текст рассылки. Например: /broadcast Бот обновлен! Добавлено...")
        return
        
    users = database.get_all_users()
    count = 0
    for user in users:
        try:
            await message.bot.send_message(
                user['telegram_id'], 
                f"🚀 <b>ВНИМАНИЕ! Бот обновлен!</b> 🚀\n\n{text_to_broadcast}\n\n👉 <b>Нажмите /start</b>, чтобы применить обновления и обновить меню!"
            )
            count += 1
        except Exception as e:
            pass
            
    await message.answer(f"✅ Рассылка успешно отправлена {count} пользователям.")

import keyboards

@admin_router.message(Command("admin"))
@admin_router.message(F.text == "👑 Админ панель")
async def handle_admin_panel(message: Message):
    import config
    if message.from_user.id not in config.ADMIN_IDS:
        return
        
    await message.answer(
        "👑 <b>Панель администратора</b>\n\nВыберите нужный раздел ниже:",
        reply_markup=keyboards.get_admin_panel_keyboard(),
        parse_mode="HTML"
    )

@admin_router.callback_query(F.data == "admin_stats_view")
async def process_admin_stats(callback: CallbackQuery):
    import config
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("У вас нет прав.")
        return
        
    stats = database.get_admin_stats()
    
    ru_cnt = stats['langs'].get('ru', 0)
    uz_cnt = stats['langs'].get('uz', 0)
    
    text = (
        f"📊 <b>Статистика пользователей ThirtyFiveCoach:</b>\n\n"
        f"👥 Всего пользователей: <b>{stats['total_users']}</b>\n"
        f"⭐ Активных подписок: <b>{stats['active_subscriptions']}</b>\n"
        f"🔥 Активных сегодня: <b>{stats['active_today']}</b>\n"
        f"⏳ Голодают прямо сейчас: <b>{stats['active_fasting']}</b>\n"
        f"🏋️ Сгенерировано тренировок: <b>{stats['total_workouts']}</b>\n"
        f"💳 Ожидают проверки чеков: <b>{stats['pending_payments']}</b>\n\n"
        f"🌐 <b>По языкам:</b>\n"
        f"🇷🇺 Русский: {ru_cnt}\n"
        f"🇺🇿 Узбекский: {uz_cnt}"
    )
    
    await callback.answer()
    await callback.message.edit_text(text, reply_markup=keyboards.get_admin_panel_keyboard(), parse_mode="HTML")

@admin_router.callback_query(F.data == "admin_users_view")
async def process_admin_users(callback: CallbackQuery):
    import config
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("У вас нет прав.")
        return
        
    users = database.get_recent_users(10)
    
    lines = ["👥 <b>Последние 10 пользователей:</b>\n"]
    for u in users:
        uname = f"@{u['username']}" if u.get('username') else u.get('first_name', 'Без имени')
        lang = "🇷🇺" if u.get('language') == 'ru' else "🇺🇿"
        sub_status = "✅ Подписка" if u.get('subscription_end_date') else "❌ Нет подписки"
        lines.append(f"• ID: <code>{u['telegram_id']}</code> | {uname} | {lang} | {sub_status}")
        
    await callback.answer()
    await callback.message.edit_text("\n".join(lines), reply_markup=keyboards.get_admin_panel_keyboard(), parse_mode="HTML")

@admin_router.callback_query(F.data == "admin_broadcast_prompt")
async def process_admin_broadcast_prompt(callback: CallbackQuery):
    import config
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("У вас нет прав.")
        return
        
    text = (
        "📢 <b>Рассылка пользователям</b>\n\n"
        "Чтобы отправить рассылку всем пользователям, напишите команду:\n"
        "<code>/broadcast Текст сообщения</code>\n\n"
        "Пример:\n"
        "<code>/broadcast Вышло новое обновление! Добавлено интервальное голодание!</code>"
    )
    await callback.answer()
    await callback.message.edit_text(text, reply_markup=keyboards.get_admin_panel_keyboard(), parse_mode="HTML")
