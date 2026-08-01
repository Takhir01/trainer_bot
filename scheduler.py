import datetime
import json
import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from aiogram import Bot

import database
import services.gemini
from handlers.user import calculate_base_calories

logger = logging.getLogger(__name__)

async def send_meal_reminders(bot: Bot):
    now = database.get_tashkent_now()
    users = database.get_all_users()
    
    for user in users:
        if not user.get('meal_times'):
            continue
            
        try:
            meal_times = json.loads(user['meal_times'])
        except Exception:
            continue
            
        for meal_time_str in meal_times:
            try:
                # meal_time_str should be something like "08:00" or similar text.
                if len(meal_time_str) == 5 and ":" in meal_time_str:
                    h, m = map(int, meal_time_str.split(':'))
                    meal_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
                    
                    # We want to notify 30 minutes before
                    notify_time = meal_time - datetime.timedelta(minutes=30)
                    
                    # If current time is exactly the notify_time (within this minute)
                    if notify_time.hour == now.hour and notify_time.minute == now.minute:
                        # Send reminder
                        daily = database.get_or_create_daily_log(user['telegram_id'])
                        goal_cals = calculate_base_calories(user['weight'], user['height'], user['age'], user['gender'], user['goal'], user['activity_level'])
                        remaining = goal_cals - daily['calories_consumed'] + daily['calories_burned']
                        
                        lang = user.get('language', 'ru')
                        prompt_msg = f"Скоро время приема пищи ({meal_time_str}). Посоветуй, что поесть." if lang == 'ru' else f"Tez orada ovqatlanish vaqti ({meal_time_str}). Nima yeyishni maslahat bering."
                        
                        try:
                            reply = await services.gemini.chat_with_coach(
                                telegram_id=user['telegram_id'],
                                message=prompt_msg,
                                user_data=user,
                                remaining_calories=remaining,
                                lang=lang
                            )
                            await bot.send_message(user['telegram_id'], f"🔔 <b>Напоминание / Eslatma</b>\n\n{reply}")
                        except Exception as e:
                            logger.error(f"Error sending meal reminder to {user['telegram_id']}: {e}")
            except Exception as e:
                pass

async def send_weekly_reports(bot: Bot):
    users = database.get_all_users()
    
    for user in users:
        stats = database.get_weekly_stats(user['telegram_id'])
        if not stats or not stats.get('days_logged'):
            continue
            
        days = stats['days_logged']
        avg_consumed = (stats.get('sum_consumed') or 0) / days
        total_burned = stats.get('sum_burned') or 0
        total_duration = stats.get('sum_duration') or 0
        
        lang = user.get('language', 'ru')
        if lang == 'ru':
            msg = (
                f"📅 <b>Еженедельный отчет!</b>\n\n"
                f"🔥 В среднем потреблено: {avg_consumed:.0f} ккал/день\n"
                f"💧 Сожжено за неделю: {total_burned} ккал\n"
                f"⏱ Тренировок: {total_duration} мин\n\n"
                f"Так держать! 💪 Продолжай в том же духе!"
            )
        else:
            msg = (
                f"📅 <b>Haftalik hisobot!</b>\n\n"
                f"🔥 O'rtacha iste'mol: {avg_consumed:.0f} kkal/kun\n"
                f"💧 Haftada yoqildi: {total_burned} kkal\n"
                f"⏱ Mashg'ulotlar: {total_duration} daqiqa\n\n"
                f"Juda yaxshi! 💪 Shu ruhda davom eting!"
            )
            
        try:
            await bot.send_message(user['telegram_id'], msg)
        except Exception as e:
            logger.error(f"Error sending weekly report to {user['telegram_id']}: {e}")

def setup_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    
    # Run every minute to check for meal times
    scheduler.add_job(send_meal_reminders, "cron", minute="*", args=[bot])
    
    # Run every Sunday at 20:00
    scheduler.add_job(send_weekly_reports, "cron", day_of_week="sun", hour=20, minute=0, args=[bot])
        
    scheduler.start()
