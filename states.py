from aiogram.fsm.state import State, StatesGroup

class RegistrationStates(StatesGroup):
    waiting_for_language = State()
    waiting_for_country = State()
    waiting_for_goal = State()
    waiting_for_gender = State()
    waiting_for_age = State()
    waiting_for_weight = State()
    waiting_for_target_weight = State()
    waiting_for_height = State()
    waiting_for_activity_level = State()
    waiting_for_meal_times = State()

class PaymentStates(StatesGroup):
    waiting_for_receipt = State()

class AdminStates(StatesGroup):
    pass

class SettingsStates(StatesGroup):
    waiting_for_action = State()

class FoodLogStates(StatesGroup):
    waiting_for_food_photo = State()

class WorkoutLogStates(StatesGroup):
    waiting_for_activity_desc = State()

class GenerateWorkoutStates(StatesGroup):
    waiting_for_location = State()
    waiting_for_duration = State()
    waiting_for_equipment = State()

class RecipeStates(StatesGroup):
    waiting_for_ingredients = State()

class StepsLogStates(StatesGroup):
    waiting_for_steps_count = State()

class UpdateWeightStates(StatesGroup):
    waiting_for_weight = State()

class UpdateCountryStates(StatesGroup):
    waiting_for_country = State()
