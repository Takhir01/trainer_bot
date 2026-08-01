import google.generativeai as genai
import config
from PIL import Image
import io
import re

if config.GEMINI_API_KEY:
    genai.configure(api_key=config.GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-2.5-flash')
else:
    model = None

chat_sessions = {}

async def analyze_food(data: str | bytes, is_photo: bool = True, lang: str = 'ru') -> dict:
    """Analyzes food photo or text and returns description and calories"""
    if not model:
        return {"description": "Gemini API key not configured", "calories": 0}
        
    try:
        if is_photo:
            img = Image.open(data) # data is photo_path
            prompt = (
                "Analyze this food photo. "
                "1. Give a short description of what you see. "
                "2. Estimate the total calories in kcal. "
                "3. Estimate macronutrients in grams (Protein, Carbs, Fats). "
                "4. Mention any notable vitamins or fiber. "
                "Format the response exactly like this:\n"
                "Description: [your description]\n"
                "Calories: [number]\n"
                "Protein: [number]\n"
                "Carbs: [number]\n"
                "Fats: [number]\n"
                "Micros: [short text about vitamins/fiber]\n"
                f"Respond in {'Russian' if lang == 'ru' else 'Uzbek'} language."
            )
            response = await model.generate_content_async([prompt, img])
        else:
            prompt = (
                f"Estimate the calories and macros for the following food: '{data}'. "
                "Format the response exactly like this:\n"
                "Description: [short summary of the food]\n"
                "Calories: [number]\n"
                "Protein: [number]\n"
                "Carbs: [number]\n"
                "Fats: [number]\n"
                "Micros: [short text about vitamins/fiber]\n"
                f"Respond in {'Russian' if lang == 'ru' else 'Uzbek'} language."
            )
            response = await model.generate_content_async(prompt)
            
        text = response.text
        
        # Parse the response
        desc_match = re.search(r'Description:\s*(.+)', text, re.IGNORECASE)
        cal_match = re.search(r'Calories:\s*(\d+)', text, re.IGNORECASE)
        prot_match = re.search(r'Protein:\s*(\d+)', text, re.IGNORECASE)
        carb_match = re.search(r'Carbs:\s*(\d+)', text, re.IGNORECASE)
        fat_match = re.search(r'Fats:\s*(\d+)', text, re.IGNORECASE)
        micros_match = re.search(r'Micros:\s*(.+)', text, re.IGNORECASE)
        
        description = format_tg_html(desc_match.group(1)) if desc_match else "Unknown food"
        calories = int(cal_match.group(1)) if cal_match else 0
        protein = int(prot_match.group(1)) if prot_match else 0
        carbs = int(carb_match.group(1)) if carb_match else 0
        fats = int(fat_match.group(1)) if fat_match else 0
        micros = format_tg_html(micros_match.group(1)) if micros_match else "Нет данных / Ma'lumot yo'q"
        
        return {
            "description": description, 
            "calories": calories,
            "protein": protein,
            "carbs": carbs,
            "fats": fats,
            "micros": micros
        }
    except Exception as e:
        print(f"Error analyzing food: {e}")
        return {"description": "Error analyzing food", "calories": 0, "protein": 0, "carbs": 0, "fats": 0, "micros": ""}

async def analyze_activity(data: str | bytes, user_data: dict, lang: str = 'ru', is_audio: bool = False) -> dict:
    if not model:
        return {"description": "Gemini API key not configured", "calories": 0, "steps": 0}
        
    try:
        sys_info = (
            f"User stats: {user_data.get('weight')}kg, {user_data.get('height')}cm, {user_data.get('gender')}. "
            f"Estimate the calories burned for the described activity."
        )
        
        prompt = (
            f"{sys_info}\n"
            "Analyze the activity and return ONLY the result in this exact format:\n"
            "Description: [short summary of what the user did in Russian or Uzbek]\n"
            "Calories: [estimated calories burned as integer]\n"
            "Steps: [number of steps taken as integer, if mentioned. if not mentioned, return 0]\n"
            f"Respond in {'Russian' if lang == 'ru' else 'Uzbek'} language."
        )
        
        if is_audio:
            parts = [{"mime_type": "audio/ogg", "data": data}, prompt]
            response = await model.generate_content_async(parts)
        else:
            response = await model.generate_content_async([prompt, data])
            
        text = response.text
        
        desc_match = re.search(r'Description:\s*(.+)', text, re.IGNORECASE)
        cal_match = re.search(r'Calories:\s*(\d+)', text, re.IGNORECASE)
        steps_match = re.search(r'Steps:\s*(\d+)', text, re.IGNORECASE)
        
        description = format_tg_html(desc_match.group(1).strip()) if desc_match else "Activity"
        calories = int(cal_match.group(1)) if cal_match else 0
        steps = int(steps_match.group(1)) if steps_match else 0
        
        return {"description": description, "calories": calories, "steps": steps}
    except Exception as e:
        print(f"Error analyzing activity: {e}")
        return {"description": "Error analyzing activity", "calories": 0, "steps": 0}

def format_tg_html(text: str) -> str:
    if not text: return text
    text = text.replace('<', '&lt;').replace('>', '&gt;')
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text, flags=re.DOTALL)
    text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', text, flags=re.DOTALL)
    return text

async def get_meal_advice(goal: str, remaining_calories: int, meal_type: str, lang: str = 'ru', user_data: dict = None) -> str:
    if not model:
        return "Gemini API key not configured"
        
    goal_str = "lose weight" if goal == "lose_weight" else "gain weight"
    target_info = ""
    if user_data and user_data.get('target_weight'):
        target_info = f" My current weight is {user_data.get('weight')} kg and my target is {user_data.get('target_weight')} kg."
        
    country_info = f" The user lives in {user_data.get('country')}. Recommend dishes and products locally popular and available in {user_data.get('country')}." if user_data and user_data.get('country') else ""
    
    prompt = (
        f"I want to {goal_str}.{target_info}{country_info} I have {remaining_calories} kcal left for today. "
        f"Give me 2-3 specific meal ideas for {meal_type}. "
        f"For EACH meal idea, you MUST include the estimated total calories. "
        f"Also, break down the ingredients, showing EXACTLY how many grams of each product I should use. "
        f"Keep the answer short, friendly, and practical. "
        f"Respond in {'Russian' if lang == 'ru' else 'Uzbek'} language."
    )
    
    try:
        response = await model.generate_content_async(prompt)
        return format_tg_html(response.text)
    except Exception as e:
        print(f"Error generating advice: {e}")
        return "Sorry, I couldn't generate advice right now."

async def generate_workout(goal: str, lang: str = 'ru', user_data: dict = None, duration: int = 30, location: str = 'home', equipment: str = 'none') -> str:
    if not model:
        return "Gemini API key not configured"
        
    goal_str = "lose weight" if goal == "lose_weight" else "gain weight"
    target_info = ""
    if user_data and user_data.get('target_weight'):
        target_info = f" My current weight is {user_data.get('weight')} kg and my target is {user_data.get('target_weight')} kg."
        
    loc_str = "at home" if location == 'home' else "at the gym"
    
    prompt = (
        f"I want to {goal_str}.{target_info} Give me a specific {duration}-minute workout routine to do {loc_str}. "
        f"Available equipment: {equipment}. "
        f"IMPORTANT: Keep your answer VERY short and practical. Just list the exercises (with sets/reps). "
        f"At the VERY END of your response, you MUST include a line exactly like this: 'Calories: X' where X is the estimated total calories burned. "
        f"Respond in {'Russian' if lang == 'ru' else 'Uzbek'} language."
    )
    
    try:
        response = await model.generate_content_async(prompt)
        return format_tg_html(response.text)
    except Exception as e:
        print(f"Error generating workout: {e}")
        return "Sorry, I couldn't generate a workout right now."

async def chat_with_coach(telegram_id: int, message: str, user_data: dict, remaining_calories: int, lang: str) -> str:
    if not model:
        return "Gemini API key not configured"
        
    if telegram_id not in chat_sessions:
        goal_str = "lose weight" if user_data.get('goal') == "lose_weight" else "gain weight"
        country_str = f", Country: {user_data.get('country')}" if user_data.get('country') else ""
        sys_prompt = (
            f"You are a friendly and professional AI fitness coach. "
            f"Your client's data: Gender: {user_data.get('gender')}, Age: {user_data.get('age')}, "
            f"Weight: {user_data.get('weight')}kg, Target Weight: {user_data.get('target_weight')}kg, "
            f"Height: {user_data.get('height')}cm, Activity level: {user_data.get('activity_level')}{country_str}. "
            f"Their goal is to {goal_str}. They have {remaining_calories} kcal remaining for today. "
            f"Consider local cuisine and products of their country when giving food advice. "
            f"Keep your answers helpful, motivating, concise, and in {'Russian' if lang == 'ru' else 'Uzbek'}."
        )
        chat = model.start_chat(history=[
            {"role": "user", "parts": [sys_prompt]},
            {"role": "model", "parts": ["Understood! I'm ready to help you."]}
        ])
        chat_sessions[telegram_id] = chat
        
    chat = chat_sessions[telegram_id]
    
    try:
        response = await chat.send_message_async(message)
        return format_tg_html(response.text)
    except Exception as e:
        print(f"Error in chat: {e}")
        return "Извините, произошла ошибка. / Kechirasiz, xatolik yuz berdi."

async def analyze_recipe(data: str | bytes, remaining_calories: int, goal: str, is_photo: bool = False, lang: str = 'ru', country: str = '') -> str:
    if not model:
        return "Gemini API key not configured"
        
    goal_str = "lose weight" if goal == "lose_weight" else "gain weight"
    country_info = f" The user is located in {country}, so tailor recommendations to products and menu items typical for {country}." if country else ""
    
    if is_photo:
        img = PIL.Image.open(io.BytesIO(data))
        prompt = (
            f"This is a photo of a restaurant menu or a set of ingredients. "
            f"My goal is to {goal_str}. I have {remaining_calories} kcal remaining for today. "
            f"Based on this image, suggest exactly WHAT I should eat/cook and HOW MUCH (portion size) "
            f"to best fit my calorie limit. Include the estimated total calories of your suggestion. "
            f"Be concise, practical, and helpful. "
            f"Respond in {'Russian' if lang == 'ru' else 'Uzbek'} language."
        )
        try:
            response = await model.generate_content_async([prompt, img])
            return format_tg_html(response.text)
        except Exception as e:
            print(f"Error analyzing recipe photo: {e}")
            return "Извините, не удалось проанализировать фото." if lang == 'ru' else "Kechirasiz, rasmni tahlil qilib bo'lmadi."
    else:
        prompt = (
            f"I have these ingredients or menu options: '{data}'. "
            f"My goal is to {goal_str}. I have {remaining_calories} kcal remaining for today. "
            f"Based on this list, suggest exactly WHAT I should eat/cook and HOW MUCH (portion size or recipe) "
            f"to best fit my calorie limit. Include the estimated total calories of your suggestion. "
            f"Be concise, practical, and helpful. "
            f"Respond in {'Russian' if lang == 'ru' else 'Uzbek'} language."
        )
        try:
            response = await model.generate_content_async(prompt)
            return format_tg_html(response.text)
        except Exception as e:
            print(f"Error analyzing recipe text: {e}")
            return "Извините, не удалось сгенерировать рецепт." if lang == 'ru' else "Kechirasiz, retsept yarata olmadim."
