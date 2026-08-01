FROM python:3.10-slim

# Установка рабочей директории
WORKDIR /app

# Копирование файла зависимостей
COPY requirements.txt .

# Установка зависимостей Python
RUN pip install --no-cache-dir -r requirements.txt

# Копирование всего исходного кода
COPY . .

# Команда запуска
CMD ["python", "bot.py"]
