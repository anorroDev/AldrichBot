from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "Бот работает 24/7! Спасибо Render и UptimeRobot."

def run():
    # Render автоматически ищет открытый порт 8080 или берет свой из окружения
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()