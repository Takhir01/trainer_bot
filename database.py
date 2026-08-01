import sqlite3
import datetime
import config

def get_db_connection():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Users table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        language TEXT DEFAULT 'ru',
        goal TEXT, -- 'lose_weight' or 'gain_weight'
        age INTEGER,
        weight REAL,
        target_weight REAL,
        height REAL,
        gender TEXT,
        activity_level TEXT,
        meal_times TEXT, -- JSON array of meal times
        subscription_end_date TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')

    # Payments table
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER,
        amount REAL,
        payment_method TEXT, -- 'stars', 'receipt'
        receipt_photo TEXT,
        status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
    )
    ''')

    # Daily logs table (activities, steps, workouts, calories)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS daily_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER,
        date DATE,
        calories_consumed INTEGER DEFAULT 0,
        calories_burned INTEGER DEFAULT 0,
        steps INTEGER DEFAULT 0,
        workout_duration_min INTEGER DEFAULT 0,
        protein INTEGER DEFAULT 0,
        carbs INTEGER DEFAULT 0,
        fats INTEGER DEFAULT 0,
        vitamins TEXT DEFAULT '',
        UNIQUE(telegram_id, date),
        FOREIGN KEY(telegram_id) REFERENCES users(telegram_id)
    )
    ''')

    try:
        cursor.execute("ALTER TABLE daily_logs ADD COLUMN protein INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE daily_logs ADD COLUMN carbs INTEGER DEFAULT 0")
        cursor.execute("ALTER TABLE daily_logs ADD COLUMN fats INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass # Columns exist
        
    try:
        cursor.execute("ALTER TABLE daily_logs ADD COLUMN vitamins TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass # Column exists

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN activity_level TEXT")
    except sqlite3.OperationalError:
        pass # Column exists

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN target_weight REAL")
    except sqlite3.OperationalError:
        pass # Column exists

    try:
        cursor.execute("ALTER TABLE users ADD COLUMN country TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass # Column exists

    conn.commit()
    conn.close()

def get_tashkent_now():
    # Simple UTC+5
    return datetime.datetime.utcnow() + datetime.timedelta(hours=5)

def add_user(telegram_id, username, first_name, last_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute('''
        INSERT INTO users (telegram_id, username, first_name, last_name)
        VALUES (?, ?, ?, ?)
        ''', (telegram_id, username, first_name, last_name))
        conn.commit()
    except sqlite3.IntegrityError:
        # Update username/name if exists
        cursor.execute('''
        UPDATE users SET username=?, first_name=?, last_name=? WHERE telegram_id=?
        ''', (username, first_name, last_name, telegram_id))
        conn.commit()
    finally:
        conn.close()

def get_user(telegram_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id=?", (telegram_id,))
    user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def get_all_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users")
    users = cursor.fetchall()
    conn.close()
    return [dict(u) for u in users]

def update_user_profile(telegram_id, goal=None, age=None, weight=None, target_weight=None, height=None, gender=None, activity_level=None, meal_times=None, language=None, country=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    
    updates = []
    params = []
    if goal is not None:
        updates.append("goal=?")
        params.append(goal)
    if age is not None:
        updates.append("age=?")
        params.append(age)
    if weight is not None:
        updates.append("weight=?")
        params.append(weight)
    if target_weight is not None:
        updates.append("target_weight=?")
        params.append(target_weight)
    if height is not None:
        updates.append("height=?")
        params.append(height)
    if gender is not None:
        updates.append("gender=?")
        params.append(gender)
    if activity_level is not None:
        updates.append("activity_level=?")
        params.append(activity_level)
    if meal_times is not None:
        updates.append("meal_times=?")
        params.append(meal_times)
    if language is not None:
        updates.append("language=?")
        params.append(language)
    if country is not None:
        updates.append("country=?")
        params.append(country)
        
    if updates:
        params.append(telegram_id)
        query = f"UPDATE users SET {', '.join(updates)} WHERE telegram_id=?"
        cursor.execute(query, tuple(params))
        conn.commit()
    conn.close()

def has_active_subscription(telegram_id):
    user = get_user(telegram_id)
    if not user or not user['subscription_end_date']:
        return False
    end_date = datetime.datetime.fromisoformat(user['subscription_end_date'])
    return end_date > get_tashkent_now()

def extend_subscription(telegram_id, days=config.SUBSCRIPTION_DAYS):
    user = get_user(telegram_id)
    now = get_tashkent_now()
    if user and user['subscription_end_date']:
        current_end = datetime.datetime.fromisoformat(user['subscription_end_date'])
        if current_end > now:
            new_end = current_end + datetime.timedelta(days=days)
        else:
            new_end = now + datetime.timedelta(days=days)
    else:
        new_end = now + datetime.timedelta(days=days)
        
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET subscription_end_date=? WHERE telegram_id=?", (new_end.isoformat(), telegram_id))
    conn.commit()
    conn.close()
    return new_end

def create_payment(telegram_id, amount, payment_method, receipt_photo=None):
    conn = get_db_connection()
    cursor = conn.cursor()
    status = 'pending' if payment_method == 'receipt' else 'approved'
    cursor.execute('''
    INSERT INTO payments (telegram_id, amount, payment_method, receipt_photo, status)
    VALUES (?, ?, ?, ?, ?)
    ''', (telegram_id, amount, payment_method, receipt_photo, status))
    payment_id = cursor.lastrowid
    conn.commit()
    conn.close()
    
    if status == 'approved':
        extend_subscription(telegram_id)
        
    return payment_id

def approve_payment(payment_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id, status FROM payments WHERE id=?", (payment_id,))
    payment = cursor.fetchone()
    if payment and payment['status'] == 'pending':
        cursor.execute("UPDATE payments SET status='approved' WHERE id=?", (payment_id,))
        conn.commit()
        extend_subscription(payment['telegram_id'])
        conn.close()
        return payment['telegram_id']
    conn.close()
    return None

def reject_payment(payment_id):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE payments SET status='rejected' WHERE id=?", (payment_id,))
    conn.commit()
    cursor.execute("SELECT telegram_id FROM payments WHERE id=?", (payment_id,))
    payment = cursor.fetchone()
    conn.close()
    return payment['telegram_id'] if payment else None

def get_or_create_daily_log(telegram_id):
    date_str = get_tashkent_now().date().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM daily_logs WHERE telegram_id=? AND date=?", (telegram_id, date_str))
    log = cursor.fetchone()
    if not log:
        cursor.execute('''
        INSERT INTO daily_logs (telegram_id, date) VALUES (?, ?)
        ''', (telegram_id, date_str))
        conn.commit()
        cursor.execute("SELECT * FROM daily_logs WHERE telegram_id=? AND date=?", (telegram_id, date_str))
        log = cursor.fetchone()
    conn.close()
    return dict(log)

def add_calories(telegram_id, calories, protein=0, carbs=0, fats=0, vitamins=''):
    date_str = get_tashkent_now().date().isoformat()
    get_or_create_daily_log(telegram_id) # ensure exists
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Append vitamins if provided
    vitamins_update = "vitamins"
    if vitamins:
        vitamins_update = f"vitamins || ' ' || '{vitamins}'"
        
    cursor.execute(f'''
    UPDATE daily_logs 
    SET calories_consumed = calories_consumed + ?,
        protein = protein + ?,
        carbs = carbs + ?,
        fats = fats + ?,
        vitamins = {vitamins_update}
    WHERE telegram_id=? AND date=?
    ''', (calories, protein, carbs, fats, telegram_id, date_str))
    conn.commit()
    conn.close()

def log_workout(telegram_id, duration_min, calories_burned=0, steps=0):
    date_str = get_tashkent_now().date().isoformat()
    get_or_create_daily_log(telegram_id) # ensure exists
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE daily_logs 
    SET workout_duration_min = workout_duration_min + ?,
        calories_burned = calories_burned + ?,
        steps = steps + ?
    WHERE telegram_id=? AND date=?
    ''', (duration_min, calories_burned, steps, telegram_id, date_str))
    conn.commit()
    conn.close()
    
def add_steps(telegram_id, steps):
    date_str = get_tashkent_now().date().isoformat()
    get_or_create_daily_log(telegram_id)
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE daily_logs SET steps = steps + ?
    WHERE telegram_id=? AND date=?
    ''', (steps, telegram_id, date_str))
    conn.commit()
    conn.close()

def get_weekly_stats(telegram_id):
    now = get_tashkent_now().date()
    start_date = (now - datetime.timedelta(days=7)).isoformat()
    end_date = now.isoformat()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT SUM(calories_consumed) as sum_consumed, 
               SUM(calories_burned) as sum_burned,
               SUM(workout_duration_min) as sum_duration,
               SUM(steps) as sum_steps,
               COUNT(id) as days_logged
        FROM daily_logs 
        WHERE telegram_id=? AND date >= ? AND date <= ?
    ''', (telegram_id, start_date, end_date))
    stats = cursor.fetchone()
    conn.close()
    return dict(stats) if stats and stats['days_logged'] else None

def get_monthly_stats(telegram_id):
    now = get_tashkent_now().date()
    start_date = (now - datetime.timedelta(days=30)).isoformat()
    end_date = now.isoformat()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT SUM(calories_consumed) as sum_consumed, 
               SUM(calories_burned) as sum_burned,
               SUM(workout_duration_min) as sum_duration,
               SUM(steps) as sum_steps,
               COUNT(id) as days_logged
        FROM daily_logs 
        WHERE telegram_id=? AND date >= ? AND date <= ?
    ''', (telegram_id, start_date, end_date))
    stats = cursor.fetchone()
    conn.close()
    return dict(stats) if stats and stats['days_logged'] else None

