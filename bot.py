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
    update_file = "UPDATE_TEXT.txt"
    if os.path.exists(update_file):
        try:
            with open(update_file, "r", encoding="utf-8") as f:
                update_text = f.read().strip()
            
            if update_text:
                users = database.get_all_users()
                count = 0
                for user in users:
                    try:
                        await bot.send_message(
                            user['telegram_id'],
                            f"🚀 <b>ВНИМАНИЕ! Бот обновлен!</b> 🚀\n\n{update_text}\n\n👉 <b>Нажмите /start</b>, чтобы применить обновления и обновить меню!"
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

    dp.include_router(user_router)
    dp.include_router(admin_router)

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
