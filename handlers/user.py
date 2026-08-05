from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, PreCheckoutQuery, LabeledPrice
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
import datetime
import json
import os
import uuid

import config
import database
import keyboards
import locales
from states import RegistrationStates, PaymentStates, FoodLogStates, WorkoutLogStates, GenerateWorkoutStates, StepsLogStates
from services import gemini

user_router = Router()

PENDING_FOOD_LOGS = {}
PENDING_ACTIVITY_LOGS = {}


def get_lang(user_id: int) -> str:
    user = database.get_user(user_id)
    return user.get('language', 'ru') if user and user.get('language') else 'ru'

def calculate_base_calories(weight, height, age, gender, goal, activity_level='sedentary'):
    # Mifflin-St Jeor Equation
    if not all([weight, height, age, gender]):
        return 2000 # default
    
    if gender == 'male':
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
        
    multipliers = {
        'sedentary': 1.2,
        'light': 1.375,
        'moderate': 1.55,
        'active': 1.725
    }
    multiplier = multipliers.get(activity_level, 1.2)
    tdee = bmr * multiplier
    
    if goal == 'lose_weight':
        return int(tdee - 500)
    elif goal == 'gain_weight':
        return int(tdee + 500)
    else:
        return int(tdee)

# =====================================================================
# Onboarding & /start
# =====================================================================

@user_router.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()

    user = database.get_user(message.from_user.id)
    if not user:
        database.add_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name
        )
        
        # Start onboarding
        await state.set_state(RegistrationStates.waiting_for_language)
        welcome_msg = (
            "👋 Здравствуйте! Выберите язык интерфейса / Qulay tilni tanlang:\n\n"
            "🇷🇺 Для продолжения на русском нажмите кнопку ниже.\n"
            "🇺🇿 Davom etish uchun o'zbek tilidagi tugmani bosing."
        )
        await message.answer(welcome_msg, reply_markup=keyboards.get_language_selection_keyboard())
    else:
        lang = user['language']
        t = locales.LOCALES[lang]
        if database.has_active_subscription(message.from_user.id):
            end_date = datetime.datetime.fromisoformat(user['subscription_end_date']).strftime("%d.%m.%Y")
            await message.answer(
                t['welcome_back'].format(end_date=end_date),
                reply_markup=keyboards.get_main_menu(lang, is_admin=message.from_user.id in config.ADMIN_IDS)
            )
        else:
            await check_paywall(message, user)


@user_router.callback_query(RegistrationStates.waiting_for_language, F.data.startswith("lang_set:"))
async def process_lang_set(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.split(":")[1]
    t = locales.LOCALES[lang]
    await callback.answer(t['lang_selected'])
    
    database.update_user_profile(callback.from_user.id, language=lang)
    
    await state.set_state(RegistrationStates.waiting_for_country)
    await callback.message.edit_text(
        t['ask_country'],
        reply_markup=keyboards.get_country_selection_keyboard(lang)
    )

@user_router.callback_query(RegistrationStates.waiting_for_country, F.data.startswith("country_set:"))
async def process_country_set(callback: CallbackQuery, state: FSMContext):
    country = callback.data.split(":")[1]
    lang = get_lang(callback.from_user.id)
    t = locales.LOCALES[lang]
    await callback.answer()
    
    if country == "other":
        await callback.message.edit_text(t['ask_country'])
        return
        
    database.update_user_profile(callback.from_user.id, country=country)
    
    await state.set_state(RegistrationStates.waiting_for_goal)
    await callback.message.edit_text(
        t['welcome_new'] + "\n\n" + t['ask_goal'],
        reply_markup=keyboards.get_goal_selection_keyboard(lang)
    )

@user_router.message(RegistrationStates.waiting_for_country, F.text)
async def process_country_text(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    
    country = message.text.strip()
    database.update_user_profile(message.from_user.id, country=country)
    
    await state.set_state(RegistrationStates.waiting_for_goal)
    await message.answer(
        t['welcome_new'] + "\n\n" + t['ask_goal'],
        reply_markup=keyboards.get_goal_selection_keyboard(lang)
    )

@user_router.callback_query(RegistrationStates.waiting_for_goal, F.data.startswith("goal_set:"))
async def process_goal_set(callback: CallbackQuery, state: FSMContext):
    goal = callback.data.split(":")[1]
    lang = get_lang(callback.from_user.id)
    t = locales.LOCALES[lang]
    await callback.answer()
    
    database.update_user_profile(callback.from_user.id, goal=goal)
    
    await state.set_state(RegistrationStates.waiting_for_gender)
    await callback.message.edit_text(t['ask_gender'], reply_markup=keyboards.get_gender_selection_keyboard(lang))

@user_router.callback_query(RegistrationStates.waiting_for_gender, F.data.startswith("gender_set:"))
async def process_gender_set(callback: CallbackQuery, state: FSMContext):
    gender = callback.data.split(":")[1]
    lang = get_lang(callback.from_user.id)
    t = locales.LOCALES[lang]
    await callback.answer()
    
    database.update_user_profile(callback.from_user.id, gender=gender)
    
    await state.set_state(RegistrationStates.waiting_for_age)
    await callback.message.edit_text(t['ask_age'])

@user_router.message(RegistrationStates.waiting_for_age, F.text)
async def process_age(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    
    if not message.text.isdigit():
        await message.answer(t['ask_age'])
        return
        
    age = int(message.text)
    database.update_user_profile(message.from_user.id, age=age)
    
    await state.set_state(RegistrationStates.waiting_for_weight)
    await message.answer(t['ask_weight'])

@user_router.message(RegistrationStates.waiting_for_weight, F.text)
async def process_weight(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    
    try:
        weight = float(message.text.replace(',', '.'))
    except ValueError:
        await message.answer(t['ask_weight'])
        return
        
    database.update_user_profile(message.from_user.id, weight=weight)
    
    await state.set_state(RegistrationStates.waiting_for_target_weight)
    await message.answer(t['ask_target_weight'])

@user_router.message(RegistrationStates.waiting_for_target_weight, F.text)
async def process_target_weight(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    
    try:
        target_weight = float(message.text.replace(',', '.'))
    except ValueError:
        await message.answer(t['ask_target_weight'])
        return
        
    database.update_user_profile(message.from_user.id, target_weight=target_weight)
    
    await state.set_state(RegistrationStates.waiting_for_height)
    await message.answer(t['ask_height'])

@user_router.message(RegistrationStates.waiting_for_height, F.text)
async def process_height(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    
    if not message.text.isdigit():
        await message.answer(t['ask_height'])
        return
        
    height = int(message.text)
    database.update_user_profile(message.from_user.id, height=height)
    
    await state.set_state(RegistrationStates.waiting_for_activity_level)
    await message.answer(t['ask_activity_level'], reply_markup=keyboards.get_activity_level_keyboard(lang))

@user_router.callback_query(RegistrationStates.waiting_for_activity_level, F.data.startswith("activity_set:"))
async def process_activity_level(callback: CallbackQuery, state: FSMContext):
    activity_level = callback.data.split(":")[1]
    lang = get_lang(callback.from_user.id)
    t = locales.LOCALES[lang]
    await callback.answer()
    
    database.update_user_profile(callback.from_user.id, activity_level=activity_level)
    
    await state.set_state(RegistrationStates.waiting_for_meal_times)
    await callback.message.edit_text(t['ask_meal_times'])

@user_router.message(RegistrationStates.waiting_for_meal_times, F.text)
async def process_meal_times(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    
    meal_times_str = message.text
    # Simple store for now
    database.update_user_profile(message.from_user.id, meal_times=json.dumps([meal_times_str]))
    
    # 3 days trial
    database.extend_subscription(message.from_user.id, days=3)
    
    user = database.get_user(message.from_user.id)
    cals = calculate_base_calories(user['weight'], user['height'], user['age'], user['gender'], user['goal'], user['activity_level'])
    
    await state.clear()
    await message.answer(
        t['registration_complete'].format(calories=cals),
        reply_markup=keyboards.get_main_menu(lang, is_admin=message.from_user.id in config.ADMIN_IDS)
    )

def calculate_macro_norms(weight: float, goal_calories: int, goal: str) -> dict:
    weight = weight or 70.0
    goal = goal or 'lose_weight'
    protein_per_kg = 2.0 if goal == 'gain_weight' else 1.5
    norm_protein = int(weight * protein_per_kg)
    norm_fats = int(weight * 1.0)
    remaining_kcal = goal_calories - (norm_protein * 4 + norm_fats * 9)
    norm_carbs = max(0, int(remaining_kcal / 4))
    
    return {
        "protein": norm_protein,
        "fats": norm_fats,
        "carbs": norm_carbs
    }

# =====================================================================
# Paywall & Payments
# =====================================================================

async def check_paywall(message: Message, user: dict = None, telegram_id: int = None) -> bool:
    if telegram_id is None:
        telegram_id = message.from_user.id
    if not user:
        user = database.get_user(telegram_id)
        
    if telegram_id in config.ADMIN_IDS:
        return True # Admins skip paywall
        
    if database.has_active_subscription(telegram_id):
        return True
        
    lang = user['language'] if user else 'ru'
    t = locales.LOCALES[lang]
    
    await message.answer(
        t['paywall_message'].format(
            price=config.SUBSCRIPTION_PRICE_UZS,
            card_number=config.CARD_NUMBER,
            card_holder=config.CARD_HOLDER
        ),
        reply_markup=keyboards.get_payment_keyboard(lang)
    )
    return False

@user_router.callback_query(F.data == "pay_receipt")
async def pay_receipt(callback: CallbackQuery, state: FSMContext):
    lang = get_lang(callback.from_user.id)
    t = locales.LOCALES[lang]
    await callback.answer()
    
    await state.set_state(PaymentStates.waiting_for_receipt)
    await callback.message.answer(t['send_receipt_prompt'])

@user_router.message(PaymentStates.waiting_for_receipt, F.photo)
async def process_receipt(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    
    file_id = message.photo[-1].file_id
    file_info = await message.bot.get_file(file_id)
    
    receipt_dir = "receipts"
    os.makedirs(receipt_dir, exist_ok=True)
    receipt_path = os.path.join(receipt_dir, f"{file_id}.jpg")
    await message.bot.download_file(file_info.file_path, receipt_path)
    
    payment_id = database.create_payment(
        telegram_id=message.from_user.id,
        amount=config.SUBSCRIPTION_PRICE_UZS,
        payment_method="receipt",
        receipt_photo=receipt_path
    )
    
    # Notify admin
    for admin_id in config.ADMIN_IDS:
        try:
            await message.bot.send_photo(
                admin_id,
                photo=file_id,
                caption=f"Новый чек на подписку ThirtyFiveCoach от @{message.from_user.username} (ID: {message.from_user.id}).\nСумма: {config.SUBSCRIPTION_PRICE_UZS} UZS.",
                reply_markup=keyboards.get_admin_receipt_keyboard(payment_id)
            )
        except Exception:
            pass
            
    await state.clear()
    await message.answer(t['receipt_received'])

# =====================================================================
# Main Menu Handlers
# =====================================================================
@user_router.message(F.text.in_([locales.LOCALES['ru']['btn_advisor'], locales.LOCALES['uz']['btn_advisor']]))
async def handle_advisor(message: Message, state: FSMContext):
    if not await check_paywall(message): return
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    await message.answer(t['advisor_prompt'], reply_markup=keyboards.get_advisor_meals_keyboard(lang))

@user_router.callback_query(F.data.startswith("adv_meal:"))
async def process_adv_meal(callback: CallbackQuery):
    await callback.answer()
    if not await check_paywall(callback.message, database.get_user(callback.from_user.id), telegram_id=callback.from_user.id): return
    
    meal_type = callback.data.split(":")[1]
    telegram_id = callback.from_user.id
    lang = get_lang(telegram_id)
    t = locales.LOCALES[lang]
    
    user = database.get_user(telegram_id)
    daily = database.get_or_create_daily_log(telegram_id)
    goal_cals = calculate_base_calories(user['weight'], user['height'], user['age'], user['gender'], user['goal'], user['activity_level'])
    remaining = goal_cals - daily['calories_consumed'] + daily['calories_burned']
    
    await callback.message.edit_text(t['advising'])
    advice = await gemini.get_meal_advice(user['goal'], remaining, meal_type, lang, user_data=user)
    await callback.message.answer(advice)

@user_router.message(F.text.in_([locales.LOCALES['ru']['btn_food_log'], locales.LOCALES['uz']['btn_food_log']]))
async def handle_food_log(message: Message, state: FSMContext):
    if not await check_paywall(message): return
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    await state.set_state(FoodLogStates.waiting_for_food_photo)
    await message.answer(t['send_food_photo'], reply_markup=keyboards.get_cancel_food_keyboard(lang))

@user_router.message(FoodLogStates.waiting_for_food_photo, F.photo)
async def process_food_photo(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    
    await message.answer(t['analyzing_food'])
    
    file_id = message.photo[-1].file_id
    file_info = await message.bot.get_file(file_id)
    
    downloads_dir = "downloads"
    os.makedirs(downloads_dir, exist_ok=True)
    photo_path = os.path.join(downloads_dir, f"{file_id}.jpg")
    await message.bot.download_file(file_info.file_path, photo_path)
    
    result = await gemini.analyze_food(photo_path, is_photo=True, lang=lang)
    await send_food_confirmation(message, state, result, lang)

@user_router.message(FoodLogStates.waiting_for_food_photo, F.text)
async def process_food_text(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    
    await message.answer(t['analyzing_food'].replace('фото', 'сообщение').replace('Rasmni', 'Matnni'))
    
    result = await gemini.analyze_food(message.text, is_photo=False, lang=lang)
    await send_food_confirmation(message, state, result, lang)

async def send_food_confirmation(message: Message, state: FSMContext, result: dict, lang: str):
    t = locales.LOCALES[lang]
    user = database.get_user(message.from_user.id)
    goal_cals = calculate_base_calories(user['weight'], user['height'], user['age'], user['gender'], user['goal'], user['activity_level'])
    norms = calculate_macro_norms(user['weight'], goal_cals, user['goal'])
    
    token = uuid.uuid4().hex[:8]
    PENDING_FOOD_LOGS[token] = {
        'telegram_id': message.from_user.id,
        'calories': result['calories'],
        'protein': result.get('protein', 0),
        'carbs': result.get('carbs', 0),
        'fats': result.get('fats', 0),
        'micros': result.get('micros', ''),
        'description': result['description']
    }
    
    msg_text = t['food_calculated'].format(
        description=result['description'], 
        calories=result['calories'],
        protein=result.get('protein', 0),
        norm_protein=norms['protein'],
        carbs=result.get('carbs', 0),
        norm_carbs=norms['carbs'],
        fats=result.get('fats', 0),
        norm_fats=norms['fats'],
        micros=result.get('micros', '')
    )
    
    await message.answer(msg_text, reply_markup=keyboards.get_confirm_food_keyboard(lang, token), parse_mode="HTML")
    await state.clear()


@user_router.message(F.text.in_([locales.LOCALES['ru']['btn_generate_workout'], locales.LOCALES['uz']['btn_generate_workout']]))
async def handle_generate_workout(message: Message, state: FSMContext):
    if not await check_paywall(message): return
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    
    await state.set_state(GenerateWorkoutStates.waiting_for_location)
    # Reusing the existing keyboard but we will catch callback differently if needed.
    # Actually, let's just create a new keyboard for it, or use the existing one and change the callback.
    keyboard = keyboards.InlineKeyboardMarkup(inline_keyboard=[
        [keyboards.InlineKeyboardButton(text=t['location_home'], callback_data="gen_loc:home")],
        [keyboards.InlineKeyboardButton(text=t['location_gym'], callback_data="gen_loc:gym")]
    ])
    await message.answer(t['ask_workout_location'], reply_markup=keyboard)

@user_router.callback_query(GenerateWorkoutStates.waiting_for_location, F.data.startswith("gen_loc:"))
async def process_gen_location(callback: CallbackQuery, state: FSMContext):
    location = callback.data.split(":")[1]
    lang = get_lang(callback.from_user.id)
    t = locales.LOCALES[lang]
    await callback.answer()
    
    await state.update_data(location=location)
    await state.set_state(GenerateWorkoutStates.waiting_for_duration)
    await callback.message.edit_text(t['ask_workout_duration_plan'])

@user_router.message(GenerateWorkoutStates.waiting_for_duration, F.text)
async def process_gen_duration(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    
    if not message.text.isdigit():
        await message.answer(t['ask_workout_duration_plan'])
        return
        
    duration = int(message.text)
    data = await state.get_data()
    location = data.get('location')
    await state.update_data(duration=duration)
    
    if location == 'home':
        await state.set_state(GenerateWorkoutStates.waiting_for_equipment)
        await message.answer(t['ask_home_equipment'])
    else:
        # Gym - usually has all equipment, we can skip asking or just pass "gym equipment"
        await finish_generate_workout(message, state, lang, location, duration, "all gym equipment")

@user_router.message(GenerateWorkoutStates.waiting_for_equipment, F.text)
async def process_gen_equipment(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    equipment = message.text
    data = await state.get_data()
    
    await finish_generate_workout(message, state, lang, data.get('location'), data.get('duration'), equipment)

async def finish_generate_workout(message: Message, state: FSMContext, lang: str, location: str, duration: int, equipment: str):
    t = locales.LOCALES[lang]
    user = database.get_user(message.from_user.id)
    
    await message.answer(t['generating_workout'])
    
    # Retrieve recent workouts to avoid duplicates and ensure progression
    recent_workouts = database.get_recent_workout_history(message.from_user.id, limit=3)
    
    import services.gemini
    workout_plan = await services.gemini.generate_workout(
        goal=user['goal'],
        lang=lang,
        user_data=user,
        duration=duration,
        location=location,
        equipment=equipment,
        previous_workouts=recent_workouts
    )
    
    # Save generated workout plan to history
    database.add_workout_history(
        telegram_id=message.from_user.id,
        workout_text=workout_plan,
        duration=duration,
        location=location,
        equipment=equipment
    )
    
    # Parse calories
    import re
    cal_match = re.search(r'Calories:\s*(\d+)', workout_plan, re.IGNORECASE)
    if not cal_match:
        cal_match = re.search(r'Калории:\s*(\d+)', workout_plan, re.IGNORECASE)
        
    calories = int(cal_match.group(1)) if cal_match else int(duration) * 5 # fallback
    
    # Add a Done button
    kb = keyboards.InlineKeyboardMarkup(inline_keyboard=[
        [keyboards.InlineKeyboardButton(text="✅ Сделал! / Bajarildi!" if lang == 'ru' else "✅ Bajarildi!", callback_data=f"done_workout:{calories}")]
    ])
    
    # Split message if it's too long (Telegram limit is 4096)
    max_len = 4000
    for i in range(0, len(workout_plan), max_len):
        if i + max_len >= len(workout_plan):
            # Last chunk gets the keyboard
            await message.answer(workout_plan[i:i+max_len], reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(workout_plan[i:i+max_len], parse_mode="HTML")
        
    await state.clear()

@user_router.callback_query(F.data.startswith("done_workout:"))
async def process_done_workout(callback: CallbackQuery):
    if not await check_paywall(callback, telegram_id=callback.from_user.id): return
    calories = int(callback.data.split(":")[1])
    database.log_workout(callback.from_user.id, duration_min=0, calories_burned=calories)
    
    lang = get_lang(callback.from_user.id)
    text = f"✅ Отлично! Тренировка выполнена, {calories} ккал записаны в статистику." if lang == 'ru' else f"✅ Ajoyib! Mashg'ulot bajarildi, {calories} kkal statistikaga yozildi."
    
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer(text, show_alert=True)
    await callback.message.answer(text)

@user_router.message(F.text.in_([locales.LOCALES['ru']['btn_workout_log'], locales.LOCALES['uz']['btn_workout_log']]))
async def handle_workout_log(message: Message, state: FSMContext):
    if not await check_paywall(message): return
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    
    await state.set_state(WorkoutLogStates.waiting_for_activity_desc)
    await message.answer(t['ask_workout_desc'], reply_markup=keyboards.get_cancel_activity_keyboard(lang))

@user_router.message(WorkoutLogStates.waiting_for_activity_desc, F.text)
async def process_activity_text(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    
    await message.answer(t['analyzing_activity'])
    
    user = database.get_user(message.from_user.id)
    import services.gemini
    result = await services.gemini.analyze_activity(message.text, user, lang, is_audio=False)
    
    await complete_activity_logging(message, state, result, t)

@user_router.message(WorkoutLogStates.waiting_for_activity_desc, F.voice)
async def process_activity_voice(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    
    await message.answer(t['analyzing_activity'])
    
    file_id = message.voice.file_id
    file_info = await message.bot.get_file(file_id)
    
    # Download audio to memory
    audio_file = await message.bot.download_file(file_info.file_path)
    audio_bytes = audio_file.read()
    
    user = database.get_user(message.from_user.id)
    import services.gemini
    result = await services.gemini.analyze_activity(audio_bytes, user, lang, is_audio=True)
    
    await complete_activity_logging(message, state, result, t)

async def complete_activity_logging(message: Message, state: FSMContext, result: dict, t: dict):
    lang = get_lang(message.from_user.id)
    token = uuid.uuid4().hex[:8]
    PENDING_ACTIVITY_LOGS[token] = {
        'telegram_id': message.from_user.id,
        'calories': result['calories'],
        'steps': result.get('steps', 0),
        'description': result['description']
    }
    
    msg = t['workout_calculated'].format(description=result['description'], calories=result['calories'])
    if result.get('steps', 0) > 0:
        msg += f"\n👣 Шаги: {result['steps']}"
    msg += f"\n\n{t['confirm_save_prompt']}"
        
    await message.answer(msg, reply_markup=keyboards.get_confirm_activity_keyboard(lang, token), parse_mode="HTML")
    await state.clear()

# =====================================================================
# Save / Delete Confirmation Handlers
# =====================================================================
@user_router.callback_query(F.data.startswith("save_food:"))
async def process_save_food(callback: CallbackQuery):
    token = callback.data.split(":")[1]
    lang = get_lang(callback.from_user.id)
    t = locales.LOCALES[lang]
    
    data = PENDING_FOOD_LOGS.pop(token, None)
    if not data:
        await callback.answer(t['expired_action'], show_alert=True)
        return
        
    database.add_calories(
        callback.from_user.id,
        data['calories'],
        protein=data['protein'],
        carbs=data['carbs'],
        fats=data['fats'],
        vitamins=data['micros']
    )
    
    await callback.answer(t['saved_success'])
    try:
        text = callback.message.text or ""
        prompt = t['confirm_save_prompt']
        if prompt in text:
            text = text.replace(prompt, "").strip()
        await callback.message.edit_text(f"{text}\n\n✅ {t['saved_success']}", reply_markup=None, parse_mode="HTML")
    except Exception:
        pass

@user_router.callback_query(F.data.startswith("del_food:"))
async def process_del_food(callback: CallbackQuery):
    token = callback.data.split(":")[1]
    lang = get_lang(callback.from_user.id)
    t = locales.LOCALES[lang]
    
    PENDING_FOOD_LOGS.pop(token, None)
    await callback.answer(t['deleted_success'])
    try:
        await callback.message.edit_text(f"🗑️ {t['deleted_success']}", reply_markup=None)
    except Exception:
        pass

@user_router.callback_query(F.data.startswith("save_act:"))
async def process_save_activity(callback: CallbackQuery):
    token = callback.data.split(":")[1]
    lang = get_lang(callback.from_user.id)
    t = locales.LOCALES[lang]
    
    data = PENDING_ACTIVITY_LOGS.pop(token, None)
    if not data:
        await callback.answer(t['expired_action'], show_alert=True)
        return
        
    database.log_workout(
        callback.from_user.id,
        duration_min=0,
        calories_burned=data['calories'],
        steps=data['steps']
    )
    
    await callback.answer(t['saved_success'])
    try:
        text = callback.message.text or ""
        prompt = t['confirm_save_prompt']
        if prompt in text:
            text = text.replace(prompt, "").strip()
        await callback.message.edit_text(f"{text}\n\n✅ {t['saved_success']}", reply_markup=None, parse_mode="HTML")
    except Exception:
        pass

@user_router.callback_query(F.data.startswith("del_act:"))
async def process_del_activity(callback: CallbackQuery):
    token = callback.data.split(":")[1]
    lang = get_lang(callback.from_user.id)
    t = locales.LOCALES[lang]
    
    PENDING_ACTIVITY_LOGS.pop(token, None)
    await callback.answer(t['deleted_success'])
    try:
        await callback.message.edit_text(f"🗑️ {t['deleted_success']}", reply_markup=None)
    except Exception:
        pass

# =====================================================================
# Cancel Handlers
# =====================================================================

@user_router.callback_query(F.data == "cancel_food")
async def process_cancel_food(callback: CallbackQuery, state: FSMContext):
    lang = get_lang(callback.from_user.id)
    t = locales.LOCALES[lang]
    await state.clear()
    await callback.answer(t['action_cancelled'])
    try:
        await callback.message.edit_text(f"↩️ {t['action_cancelled']}", reply_markup=None)
    except Exception:
        pass

@user_router.callback_query(F.data == "cancel_activity")
async def process_cancel_activity(callback: CallbackQuery, state: FSMContext):
    lang = get_lang(callback.from_user.id)
    t = locales.LOCALES[lang]
    await state.clear()
    await callback.answer(t['action_cancelled'])
    try:
        await callback.message.edit_text(f"↩️ {t['action_cancelled']}", reply_markup=None)
    except Exception:
        pass


FASTING_HOURS = {
    'light': 14,
    'medium': 16,
    'hard': 18
}

def get_fasting_stage_info(elapsed_hours: float, lang: str = 'ru') -> str:
    if elapsed_hours < 4:
        if lang == 'ru':
            return "🩸 <b>Фаза 1: Пищеварение (0-4ч)</b>\nУровень сахара в крови приходит в норму, организм усваивает пищу."
        else:
            return "🩸 <b>1-bosqich: Ovqat hazm qilish (0-4soat)</b>\nQondagi shakar darajasi me'yorlashmoqda."
    elif elapsed_hours < 8:
        if lang == 'ru':
            return "📉 <b>Фаза 2: Снижение инсулина (4-8ч)</b>\nУровень инсулина снижается, накопление жира прекращается."
        else:
            return "📉 <b>2-bosqich: Insulin kamayishi (4-8soat)</b>\nInsulin darajasi tushadi, yog' to'planishi to'xtaydi."
    elif elapsed_hours < 12:
        if lang == 'ru':
            return "🔋 <b>Фаза 3: Истощение гликогена (8-12ч)</b>\nЗапасы гликогена в печени истощаются. Начинается расход жировых запасов."
        else:
            return "🔋 <b>3-bosqich: Glikogen sarfi (8-12soat)</b>\nGlikogen zaxiralari tugamoqda, yog' parchala boshlanadi."
    elif elapsed_hours < 14:
        if lang == 'ru':
            return "🔥 <b>Фаза 4: Активное жиросжигание / Кетоз (12-14ч)</b>\nПоздравляем! Ваш организм вошел в фазу активного сжигания жира!"
        else:
            return "🔥 <b>4-bosqich: Faol yog' yoqish / Ketoz (12-14soat)</b>\nTashakkur! Tanangiz faol ravishda yog'larni yoqmoqda!"
    elif elapsed_hours < 16:
        if lang == 'ru':
            return "🧬 <b>Фаза 5: Пик гормона роста (14-16ч)</b>\nГормон роста защищает мышцы и стимулирует метаболизм."
        else:
            return "🧬 <b>5-bosqich: O'sish gormoni cho'qqisi (14-16soat)</b>\nO'sish gormoni mushaklarni himoya qiladi va metabolizmni tezlashtiradi."
    else:
        if lang == 'ru':
            return "✨ <b>Фаза 6: Аутофагия и омоложение (16+ ч)</b>\nАктивировано клеточное самоочищение (аутофагия). Организм перерабатывает поврежденные клетки!"
        else:
            return "✨ <b>6-bosqich: Autofagiya va yangilanish (16+ soat)</b>\nHujayralarni tozalash jarayoni boshlandi!"

@user_router.message(F.text.in_([locales.LOCALES['ru']['btn_fasting'], locales.LOCALES['uz']['btn_fasting']]))
async def handle_fasting_button(message: Message, state: FSMContext):
    if not await check_paywall(message): return
    lang = get_lang(message.from_user.id)
    user = database.get_user(message.from_user.id)
    t = locales.LOCALES[lang]
    
    plan = user.get('fasting_plan') or 'medium'
    plan_name = t.get(f"plan_{plan}_name", plan)
    is_active = bool(user.get('fasting_is_active'))
    
    if is_active and user.get('fasting_start_time'):
        try:
            start_dt = datetime.datetime.fromisoformat(user['fasting_start_time'])
            now = database.get_tashkent_now()
            diff_seconds = max(0, (now - start_dt).total_seconds())
            elapsed_h = int(diff_seconds // 3600)
            elapsed_m = int((diff_seconds % 3600) // 60)
            
            target_hours = FASTING_HOURS.get(plan, 16)
            total_target_seconds = target_hours * 3600
            rem_seconds = max(0, total_target_seconds - diff_seconds)
            rem_h = int(rem_seconds // 3600)
            rem_m = int((rem_seconds % 3600) // 60)
            
            stage_info = get_fasting_stage_info(diff_seconds / 3600, lang)
            
            text = t['fasting_status_active'].format(
                plan_name=plan_name,
                elapsed_h=elapsed_h,
                elapsed_m=elapsed_m,
                rem_h=rem_h,
                rem_m=rem_m,
                stage_info=stage_info
            )
        except Exception:
            text = t['fasting_status_inactive'].format(plan_name=plan_name)
    else:
        text = t['fasting_status_inactive'].format(plan_name=plan_name)
        
    await message.answer(text, reply_markup=keyboards.get_fasting_menu_keyboard(lang, is_active=is_active), parse_mode="HTML")

@user_router.callback_query(F.data == "fasting_plans")
async def process_fasting_plans(callback: CallbackQuery):
    if not await check_paywall(callback, telegram_id=callback.from_user.id): return
    lang = get_lang(callback.from_user.id)
    t = locales.LOCALES[lang]
    await callback.answer()
    await callback.message.edit_text(t['fasting_select_plan'], reply_markup=keyboards.get_fasting_plans_keyboard(lang))

@user_router.callback_query(F.data.startswith("fast_plan:"))
async def process_set_fast_plan(callback: CallbackQuery):
    if not await check_paywall(callback, telegram_id=callback.from_user.id): return
    plan = callback.data.split(":")[1]
    lang = get_lang(callback.from_user.id)
    t = locales.LOCALES[lang]
    
    database.update_fasting_state(callback.from_user.id, fasting_plan=plan)
    await callback.answer(f"✅ {t.get(f'plan_{plan}_name', plan)}")
    
    user = database.get_user(callback.from_user.id)
    plan_name = t.get(f"plan_{plan}_name", plan)
    is_active = bool(user.get('fasting_is_active'))
    text = t['fasting_status_inactive'].format(plan_name=plan_name)
    await callback.message.edit_text(text, reply_markup=keyboards.get_fasting_menu_keyboard(lang, is_active=is_active), parse_mode="HTML")

@user_router.callback_query(F.data == "fasting_start")
async def process_start_fasting(callback: CallbackQuery):
    if not await check_paywall(callback, telegram_id=callback.from_user.id): return
    lang = get_lang(callback.from_user.id)
    t = locales.LOCALES[lang]
    user = database.get_user(callback.from_user.id)
    
    plan = user.get('fasting_plan') or 'medium'
    now = database.get_tashkent_now()
    target_hours = FASTING_HOURS.get(plan, 16)
    end_dt = now + datetime.timedelta(hours=target_hours)
    
    database.update_fasting_state(
        callback.from_user.id,
        fasting_is_active=1,
        fasting_start_time=now.isoformat(),
        fasting_last_notified_hour=0,
        fasting_notified_start_warn=1,
        fasting_notified_end_warn=0
    )
    
    plan_name = t.get(f"plan_{plan}_name", plan)
    msg = t['fasting_started'].format(
        plan_name=plan_name,
        start_time=now.strftime("%H:%M"),
        end_time=end_dt.strftime("%H:%M (%d.%m)")
    )
    
    await callback.answer()
    await callback.message.edit_text(msg, reply_markup=keyboards.get_fasting_menu_keyboard(lang, is_active=True), parse_mode="HTML")

@user_router.callback_query(F.data == "fasting_stop")
async def process_stop_fasting(callback: CallbackQuery):
    if not await check_paywall(callback, telegram_id=callback.from_user.id): return
    lang = get_lang(callback.from_user.id)
    t = locales.LOCALES[lang]
    user = database.get_user(callback.from_user.id)
    
    elapsed_h, elapsed_m = 0, 0
    if user.get('fasting_start_time'):
        try:
            start_dt = datetime.datetime.fromisoformat(user['fasting_start_time'])
            now = database.get_tashkent_now()
            diff_seconds = max(0, (now - start_dt).total_seconds())
            elapsed_h = int(diff_seconds // 3600)
            elapsed_m = int((diff_seconds % 3600) // 60)
        except Exception:
            pass
            
    database.update_fasting_state(
        callback.from_user.id,
        fasting_is_active=0,
        fasting_start_time=None,
        fasting_last_notified_hour=-1,
        fasting_notified_start_warn=0,
        fasting_notified_end_warn=0
    )
    
    msg = t['fasting_stopped'].format(hours=elapsed_h, mins=elapsed_m)
    await callback.answer()
    await callback.message.edit_text(msg, reply_markup=keyboards.get_fasting_menu_keyboard(lang, is_active=False), parse_mode="HTML")

def calculate_weight_prognosis(telegram_id: int, user: dict, lang: str) -> str:
    t = locales.LOCALES[lang]
    weight = user.get('weight')
    target_weight = user.get('target_weight')
    
    if not weight or not target_weight or abs(weight - target_weight) < 0.1:
        return t['prognosis_no_target']
        
    delta_weight = abs(weight - target_weight)
    
    height = user.get('height') or 170
    age = user.get('age') or 25
    gender = user.get('gender') or 'male'
    activity = user.get('activity_level') or 'sedentary'
    
    if gender == 'male':
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
        
    multipliers = {'sedentary': 1.2, 'light': 1.375, 'moderate': 1.55, 'active': 1.725}
    tdee = bmr * multipliers.get(activity, 1.2)
    goal_cals = int(tdee - 500) if user.get('goal') == 'lose_weight' else int(tdee + 500)
    
    stats = database.get_monthly_stats(telegram_id) or database.get_weekly_stats(telegram_id)
    
    if stats and stats.get('days_logged') and stats['days_logged'] > 0:
        days = stats['days_logged']
        avg_consumed = (stats.get('sum_consumed') or 0) / days
        avg_burned = (stats.get('sum_burned') or 0) / days
        daily_net = avg_consumed - avg_burned
        daily_deficit = tdee - daily_net
    else:
        daily_deficit = 500.0
        
    if user.get('goal') == 'lose_weight' and weight > target_weight:
        if daily_deficit <= 50:
            return t['prognosis_header'] + t['prognosis_surplus'].format(
                weight=weight,
                target_weight=target_weight,
                delta_weight=delta_weight,
                goal_cals=goal_cals
            )
            
        total_calories = delta_weight * 7700.0
        days_needed = int(round(total_calories / daily_deficit))
        weeks_needed = round(days_needed / 7.0, 1)
        
        now = database.get_tashkent_now().date()
        target_date = (now + datetime.timedelta(days=days_needed)).strftime("%d.%m.%Y")
        
        return t['prognosis_header'] + t['prognosis_reach_goal'].format(
            weight=weight,
            target_weight=target_weight,
            delta_weight=delta_weight,
            deficit=int(daily_deficit),
            days=days_needed,
            weeks=weeks_needed,
            target_date=target_date
        )
    elif user.get('goal') == 'gain_weight' and weight < target_weight:
        daily_surplus = -daily_deficit if daily_deficit < 0 else 400.0
        total_calories = delta_weight * 5000.0
        days_needed = int(round(total_calories / daily_surplus))
        weeks_needed = round(days_needed / 7.0, 1)
        
        now = database.get_tashkent_now().date()
        target_date = (now + datetime.timedelta(days=days_needed)).strftime("%d.%m.%Y")
        
        return t['prognosis_header'] + t['prognosis_reach_goal'].format(
            weight=weight,
            target_weight=target_weight,
            delta_weight=delta_weight,
            deficit=int(daily_surplus),
            days=days_needed,
            weeks=weeks_needed,
            target_date=target_date
        )
    else:
        return t['prognosis_no_target']

@user_router.message(F.text.in_([locales.LOCALES['ru']['btn_stats'], locales.LOCALES['uz']['btn_stats']]))
async def handle_stats(message: Message, state: FSMContext):
    if not await check_paywall(message): return
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    
    try:
        user = database.get_user(message.from_user.id)
        daily = database.get_or_create_daily_log(message.from_user.id)
        
        c_consumed = daily.get('calories_consumed') or 0
        c_burned = daily.get('calories_burned') or 0
        c_steps = daily.get('steps') or 0
        c_protein = daily.get('protein') or 0
        c_carbs = daily.get('carbs') or 0
        c_fats = daily.get('fats') or 0
        c_vitamins = daily.get('vitamins') or ''
        
        weight = user.get('weight') or 70.0
        height = user.get('height') or 170
        age = user.get('age') or 25
        gender = user.get('gender') or 'male'
        goal = user.get('goal') or 'lose_weight'
        activity = user.get('activity_level') or 'sedentary'
        
        goal_cals = calculate_base_calories(weight, height, age, gender, goal, activity)
        remaining = goal_cals - c_consumed + c_burned
        norms = calculate_macro_norms(weight, goal_cals, goal)
        
        prognosis_text = calculate_weight_prognosis(message.from_user.id, user, lang)
        
        text = t['stats_daily'].format(
            weight=weight,
            consumed=c_consumed,
            goal_calories=goal_cals,
            burned=c_burned,
            steps=c_steps,
            remaining=remaining,
            protein=c_protein,
            norm_protein=norms['protein'],
            carbs=c_carbs,
            norm_carbs=norms['carbs'],
            fats=c_fats,
            norm_fats=norms['fats'],
            vitamins=c_vitamins
        ) + prognosis_text
        
        await message.answer(
            text,
            reply_markup=keyboards.get_stats_keyboard(lang),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Error in handle_stats: {e}")
        await message.answer("Произошла ошибка при загрузке статистики.")

@user_router.callback_query(F.data.in_(["stats_day", "stats_week", "stats_month"]))
async def process_stats_period(callback: CallbackQuery):
    if not await check_paywall(callback, telegram_id=callback.from_user.id): return
    lang = get_lang(callback.from_user.id)
    t = locales.LOCALES[lang]
    period = callback.data.split("_")[1]
    
    user = database.get_user(callback.from_user.id)
    prognosis_text = calculate_weight_prognosis(callback.from_user.id, user, lang)
    
    if period == "day":
        daily = database.get_or_create_daily_log(callback.from_user.id)
        c_consumed = daily.get('calories_consumed') or 0
        c_burned = daily.get('calories_burned') or 0
        c_steps = daily.get('steps') or 0
        c_protein = daily.get('protein') or 0
        c_carbs = daily.get('carbs') or 0
        c_fats = daily.get('fats') or 0
        c_vitamins = daily.get('vitamins') or ''
        
        weight = user.get('weight') or 70.0
        height = user.get('height') or 170
        age = user.get('age') or 25
        gender = user.get('gender') or 'male'
        goal = user.get('goal') or 'lose_weight'
        activity = user.get('activity_level') or 'sedentary'
        
        goal_cals = calculate_base_calories(weight, height, age, gender, goal, activity)
        remaining = goal_cals - c_consumed + c_burned
        norms = calculate_macro_norms(weight, goal_cals, goal)
        
        text = t['stats_daily'].format(
            weight=weight,
            consumed=c_consumed,
            goal_calories=goal_cals,
            burned=c_burned,
            steps=c_steps,
            remaining=remaining,
            protein=c_protein,
            norm_protein=norms['protein'],
            carbs=c_carbs,
            norm_carbs=norms['carbs'],
            fats=c_fats,
            norm_fats=norms['fats'],
            vitamins=c_vitamins
        ) + prognosis_text
    else:
        if period == "week":
            stats = database.get_weekly_stats(callback.from_user.id)
            period_name = t['period_week']
        else:
            stats = database.get_monthly_stats(callback.from_user.id)
            period_name = t['period_month']
            
        if not stats or not stats.get('days_logged'):
            text = ("Нет данных за этот период." if lang == 'ru' else "Bu davr uchun ma'lumot yo'q.") + prognosis_text
        else:
            days = stats['days_logged']
            avg_consumed = (stats.get('sum_consumed') or 0) / days
            total_burned = stats.get('sum_burned') or 0
            total_duration = stats.get('sum_duration') or 0
            total_steps = stats.get('sum_steps') or 0
            
            text = t['stats_period'].format(
                period_name=period_name,
                weight=user.get('weight', 0),
                avg_consumed=f"{avg_consumed:.0f}",
                total_burned=total_burned,
                total_duration=total_duration,
                total_steps=total_steps,
                days_logged=days
            ) + prognosis_text
            
    try:
        await callback.message.edit_text(text, reply_markup=keyboards.get_stats_keyboard(lang), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()

from states import UpdateWeightStates

@user_router.callback_query(F.data == "update_weight")
async def process_update_weight_btn(callback: CallbackQuery, state: FSMContext):
    if not await check_paywall(callback, telegram_id=callback.from_user.id): return
    lang = get_lang(callback.from_user.id)
    t = locales.LOCALES[lang]
    await callback.answer()
    await state.set_state(UpdateWeightStates.waiting_for_weight)
    await callback.message.answer(t['ask_new_weight'])

@user_router.message(UpdateWeightStates.waiting_for_weight, F.text)
async def process_new_weight(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    
    try:
        new_weight = float(message.text.replace(',', '.'))
    except ValueError:
        await message.answer(t['ask_new_weight'])
        return
        
    database.update_user_profile(message.from_user.id, weight=new_weight)
    
    user = database.get_user(message.from_user.id)
    goal_cals = calculate_base_calories(user['weight'], user['height'], user['age'], user['gender'], user['goal'], user['activity_level'])
    
    await message.answer(t['weight_updated'].format(weight=new_weight, calories=goal_cals))
    await state.clear()

@user_router.message(F.text.in_([locales.LOCALES['ru']['btn_settings'], locales.LOCALES['uz']['btn_settings']]))
async def handle_settings(message: Message, state: FSMContext):
    await state.clear()
    await state.set_state(RegistrationStates.waiting_for_language)
    welcome_msg = (
        "👋 Настройки профиля / Profil sozlamalari:\n\n"
        "🇷🇺 Выберите язык интерфейса\n"
        "🇺🇿 Qulay tilni tanlang"
    )
    await message.answer(welcome_msg, reply_markup=keyboards.get_language_selection_keyboard())

# Fallback text handler for free chat with AI Coach
@user_router.message(F.text)
async def handle_free_chat(message: Message, state: FSMContext):
    if not await check_paywall(message): return
    lang = get_lang(message.from_user.id)
    
    user = database.get_user(message.from_user.id)
    daily = database.get_or_create_daily_log(message.from_user.id)
    
    goal_cals = calculate_base_calories(user['weight'], user['height'], user['age'], user['gender'], user['goal'], user['activity_level'])
    remaining = goal_cals - daily['calories_consumed'] + daily['calories_burned']
    
    await message.bot.send_chat_action(message.chat.id, "typing")
    
    import services.gemini
    reply = await services.gemini.chat_with_coach(
        telegram_id=message.from_user.id,
        message=message.text,
        user_data=user,
        remaining_calories=remaining,
        lang=lang
    )
    
    await message.answer(reply)

# =====================================================================
# Recipe / Menu
# =====================================================================
from states import RecipeStates

@user_router.message(F.text.in_([locales.LOCALES['ru']['btn_recipe'], locales.LOCALES['uz']['btn_recipe']]))
async def handle_recipe_request(message: Message, state: FSMContext):
    if not await check_paywall(message): return
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    await message.answer(t['ask_recipe'])
    await state.set_state(RecipeStates.waiting_for_ingredients)

@user_router.message(RecipeStates.waiting_for_ingredients, F.text)
async def process_recipe_text(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    await message.answer(t['generating_recipe'])
    

# =====================================================================
# Recipe / Menu
# =====================================================================
from states import RecipeStates

@user_router.message(F.text.in_([locales.LOCALES['ru']['btn_recipe'], locales.LOCALES['uz']['btn_recipe']]))
async def handle_recipe_request(message: Message, state: FSMContext):
    if not await check_paywall(message): return
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    await message.answer(t['ask_recipe'])
    await state.set_state(RecipeStates.waiting_for_ingredients)

@user_router.message(RecipeStates.waiting_for_ingredients, F.text)
async def process_recipe_text(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    await message.answer(t['generating_recipe'])
    
    user = database.get_user(message.from_user.id)
    goal_cals = calculate_base_calories(user['weight'], user['height'], user['age'], user['gender'], user['goal'], user['activity_level'])
    daily = database.get_or_create_daily_log(message.from_user.id)
    remaining = goal_cals - daily['calories_consumed'] + daily['calories_burned']
    
    import services.gemini
    suggestion = await services.gemini.analyze_recipe(message.text, remaining, user['goal'], is_photo=False, lang=lang, country=user.get('country', ''))
    await message.answer(suggestion)
    await state.clear()

@user_router.message(RecipeStates.waiting_for_ingredients, F.photo)
async def process_recipe_photo(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    t = locales.LOCALES[lang]
    await message.answer(t['generating_recipe'])
    
    file_id = message.photo[-1].file_id
    file_info = await message.bot.get_file(file_id)
    
    import os
    downloads_dir = "downloads"
    os.makedirs(downloads_dir, exist_ok=True)
    photo_path = os.path.join(downloads_dir, f"{file_id}.jpg")
    await message.bot.download_file(file_info.file_path, photo_path)
    
    with open(photo_path, "rb") as f:
        img_bytes = f.read()
    
    user = database.get_user(message.from_user.id)
    goal_cals = calculate_base_calories(user['weight'], user['height'], user['age'], user['gender'], user['goal'], user['activity_level'])
    daily = database.get_or_create_daily_log(message.from_user.id)
    remaining = goal_cals - daily['calories_consumed'] + daily['calories_burned']
    
    import services.gemini
    suggestion = await services.gemini.analyze_recipe(img_bytes, remaining, user['goal'], is_photo=True, lang=lang, country=user.get('country', ''))
    await message.answer(suggestion)
    await state.clear()
