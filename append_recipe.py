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
    suggestion = await services.gemini.analyze_recipe(message.text, remaining, user['goal'], is_photo=False, lang=lang)
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
    suggestion = await services.gemini.analyze_recipe(img_bytes, remaining, user['goal'], is_photo=True, lang=lang)
    await message.answer(suggestion)
    await state.clear()
