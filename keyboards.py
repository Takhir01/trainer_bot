from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from locales import LOCALES

def get_language_selection_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_set:ru")],
        [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_set:uz")]
    ])
    return keyboard

def get_goal_selection_keyboard(lang):
    t = LOCALES[lang]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['goal_lose'], callback_data="goal_set:lose_weight")],
        [InlineKeyboardButton(text=t['goal_gain'], callback_data="goal_set:gain_weight")]
    ])
    return keyboard

def get_gender_selection_keyboard(lang):
    t = LOCALES[lang]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['gender_male'], callback_data="gender_set:male")],
        [InlineKeyboardButton(text=t['gender_female'], callback_data="gender_set:female")]
    ])
    return keyboard

def get_country_selection_keyboard(lang):
    t = LOCALES[lang]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['country_uz'], callback_data="country_set:Узбекистан")],
        [InlineKeyboardButton(text=t['country_ru'], callback_data="country_set:Россия")],
        [InlineKeyboardButton(text=t['country_kz'], callback_data="country_set:Казахстан")],
        [InlineKeyboardButton(text=t['country_tr'], callback_data="country_set:Турция")],
        [InlineKeyboardButton(text=t['country_uae'], callback_data="country_set:ОАЭ")],
        [InlineKeyboardButton(text=t['country_other'], callback_data="country_set:other")]
    ])
    return keyboard

def get_activity_level_keyboard(lang):
    t = LOCALES[lang]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['activity_sedentary'], callback_data="activity_set:sedentary")],
        [InlineKeyboardButton(text=t['activity_light'], callback_data="activity_set:light")],
        [InlineKeyboardButton(text=t['activity_moderate'], callback_data="activity_set:moderate")],
        [InlineKeyboardButton(text=t['activity_active'], callback_data="activity_set:active")]
    ])
    return keyboard

def get_main_menu(lang, is_admin=False):
    t = LOCALES[lang]
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t['btn_advisor']), KeyboardButton(text=t['btn_generate_workout'])],
            [KeyboardButton(text=t['btn_food_log']), KeyboardButton(text=t['btn_workout_log'])],
            [KeyboardButton(text=t['btn_recipe']), KeyboardButton(text=t['btn_fasting'])],
            [KeyboardButton(text=t['btn_stats']), KeyboardButton(text=t['btn_settings'])]
        ],
        resize_keyboard=True
    )
    return keyboard

def get_fasting_menu_keyboard(lang: str, is_active: bool = False) -> InlineKeyboardMarkup:
    t = LOCALES[lang]
    buttons = []
    if is_active:
        buttons.append([InlineKeyboardButton(text=t['btn_stop_fasting'], callback_data="fasting_stop")])
    else:
        buttons.append([InlineKeyboardButton(text=t['btn_start_fasting'], callback_data="fasting_start")])
    
    buttons.append([InlineKeyboardButton(text=t['btn_fasting_settings'], callback_data="fasting_plans")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_fasting_plans_keyboard(lang: str) -> InlineKeyboardMarkup:
    t = LOCALES[lang]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['fasting_plan_light'], callback_data="fast_plan:light")],
        [InlineKeyboardButton(text=t['fasting_plan_medium'], callback_data="fast_plan:medium")],
        [InlineKeyboardButton(text=t['fasting_plan_hard'], callback_data="fast_plan:hard")]
    ])
    return keyboard

def get_stats_keyboard(lang: str) -> InlineKeyboardMarkup:
    t = LOCALES[lang]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t['btn_stats_day'], callback_data="stats_day"),
            InlineKeyboardButton(text=t['btn_stats_week'], callback_data="stats_week"),
            InlineKeyboardButton(text=t['btn_stats_month'], callback_data="stats_month")
        ],
        [
            InlineKeyboardButton(text=t['btn_update_weight'], callback_data="update_weight")
        ]
    ])
    return keyboard

def get_payment_keyboard(lang):
    t = LOCALES[lang]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['btn_pay_stars'], callback_data="pay_stars")],
        [InlineKeyboardButton(text=t['btn_pay_receipt'], callback_data="pay_receipt")]
    ])
    return keyboard

def get_advisor_meals_keyboard(lang):
    t = LOCALES[lang]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['meal_breakfast'], callback_data="adv_meal:breakfast")],
        [InlineKeyboardButton(text=t['meal_lunch'], callback_data="adv_meal:lunch")],
        [InlineKeyboardButton(text=t['meal_dinner'], callback_data="adv_meal:dinner")],
        [InlineKeyboardButton(text=t['meal_snack'], callback_data="adv_meal:snack")],
    ])
    return keyboard

def get_workout_location_keyboard(lang):
    t = LOCALES[lang]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['location_home'], callback_data="workout_loc:home")],
        [InlineKeyboardButton(text=t['location_gym'], callback_data="workout_loc:gym")]
    ])
    return keyboard

def get_admin_receipt_keyboard(payment_id: int):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Одобрить", callback_data=f"admin_approve_receipt:{payment_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"admin_reject_receipt:{payment_id}")]
    ])
    return keyboard

def get_confirm_food_keyboard(lang: str, token: str):
    t = LOCALES[lang]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t['btn_save'], callback_data=f"save_food:{token}"),
            InlineKeyboardButton(text=t['btn_delete'], callback_data=f"del_food:{token}")
        ],
        [
            InlineKeyboardButton(text=t['btn_cancel'], callback_data="cancel_food")
        ]
    ])
    return keyboard

def get_confirm_activity_keyboard(lang: str, token: str):
    t = LOCALES[lang]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=t['btn_save'], callback_data=f"save_act:{token}"),
            InlineKeyboardButton(text=t['btn_delete'], callback_data=f"del_act:{token}")
        ],
        [
            InlineKeyboardButton(text=t['btn_cancel'], callback_data="cancel_activity")
        ]
    ])
    return keyboard

def get_cancel_food_keyboard(lang: str):
    """Keyboard shown while waiting for food photo/text input."""
    t = LOCALES[lang]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['btn_cancel'], callback_data="cancel_food")]
    ])
    return keyboard

def get_cancel_activity_keyboard(lang: str):
    """Keyboard shown while waiting for activity description input."""
    t = LOCALES[lang]
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t['btn_cancel'], callback_data="cancel_activity")]
    ])
    return keyboard
