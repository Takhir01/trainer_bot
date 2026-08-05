import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage

import config
import database

# Handlers will be imported here
from handlers.user import user_router
from handlers.admin import admin_router

logging.basicConfig(level=logging.INFO, filename="bot.log", filemode="a",
                    format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

async def check_and_send_startup_update(bot: Bot):
    import os
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    update_file = "UPDATE_TEXT.txt"
    if os.path.exists(update_file):
        try:
            users = database.get_all_users()
            start_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Запустить / Ishga tushirish", url=f"https://t.me/{(await bot.get_me()).username}?start=update")]
            ])
            count = 0
            for user in users:
                try:
                    await bot.send_message(
                        user['telegram_id'],
                        "🚀 <b>Бот обновлен!</b> 🚀\n\n👉 Нажмите кнопку ниже или введите /start, чтобы применить обновления!",
                        reply_markup=start_kb
                    )
                    count += 1
                except Exception as e:
                    logger.error(f"Error sending update to {user.get('telegram_id')}: {e}")
            print(f"Announcement sent to {count} users.")
            os.remove(update_file)
        except Exception as e:
            logger.error(f"Error processing update announcement: {e}")

async def main():
    database.init_db()

    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    
    import scheduler
    scheduler.setup_scheduler(bot)
    
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(admin_router)
    dp.include_router(user_router)

    try:
        print("Bot ThirtyFiveCoach is starting...")
        await bot.delete_webhook(drop_pending_updates=True)
        await check_and_send_startup_update(bot)
        await dp.start_polling(bot)
    except Exception as e:
        logger.error(f"Critical error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
