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

async def send_fasting_reminders(bot: Bot):
    now = database.get_tashkent_now()
    active_users = database.get_active_fasting_users()
    
    from handlers.user import FASTING_HOURS, get_fasting_stage_info
    import locales
    
    for user in active_users:
        telegram_id = user['telegram_id']
        lang = user.get('language', 'ru')
        t = locales.LOCALES.get(lang, locales.LOCALES['ru'])
        
        if not user.get('fasting_is_active') or not user.get('fasting_start_time'):
            continue
            
        try:
            start_dt = datetime.datetime.fromisoformat(user['fasting_start_time'])
            plan = user.get('fasting_plan') or 'medium'
            target_hours = FASTING_HOURS.get(plan, 16)
            end_dt = start_dt + datetime.timedelta(hours=target_hours)
            
            diff_seconds = (now - start_dt).total_seconds()
            if diff_seconds < 0:
                continue
                
            elapsed_hours = int(diff_seconds // 3600)
            
            # 1. Check 30-minute pre-end warning
            remaining_seconds = (end_dt - now).total_seconds()
            if 0 < remaining_seconds <= 1800 and not user.get('fasting_notified_end_warn'):
                try:
                    await bot.send_message(telegram_id, t['fasting_warn_end'], parse_mode="HTML")
                    database.update_fasting_state(telegram_id, fasting_notified_end_warn=1)
                except Exception as e:
                    logger.error(f"Error sending fasting end warning to {telegram_id}: {e}")
                    
            # 2. Hourly stage notifications
            last_notified = user.get('fasting_last_notified_hour')
            if last_notified is None:
                last_notified = -1
                
            if elapsed_hours > last_notified and elapsed_hours <= target_hours:
                stage_text = get_fasting_stage_info(elapsed_hours, lang)
                stage_msg = f"⏳ <b>Голодание ({elapsed_hours}ч / {target_hours}ч):</b>\n\n{stage_text}" if lang == 'ru' else f"⏳ <b>Ochlik ({elapsed_hours}soat / {target_hours}soat):</b>\n\n{stage_text}"
                try:
                    await bot.send_message(telegram_id, stage_msg, parse_mode="HTML")
                    database.update_fasting_state(telegram_id, fasting_last_notified_hour=elapsed_hours)
                except Exception as e:
                    logger.error(f"Error sending hourly fasting update to {telegram_id}: {e}")
                    
        except Exception as e:
            logger.error(f"Error in send_fasting_reminders for user {telegram_id}: {e}")

def setup_scheduler(bot: Bot):
    scheduler = AsyncIOScheduler(timezone="Asia/Tashkent")
    
    # Run every minute to check for meal times & fasting reminders
    scheduler.add_job(send_meal_reminders, "cron", minute="*", args=[bot])
    scheduler.add_job(send_fasting_reminders, "cron", minute="*", args=[bot])
    
    # Run every Sunday at 20:00
    scheduler.add_job(send_weekly_reports, "cron", day_of_week="sun", hour=20, minute=0, args=[bot])
        
    scheduler.start()
