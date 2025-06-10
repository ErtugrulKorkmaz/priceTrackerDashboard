
from flask import Flask, flash, get_flashed_messages 
from flask_sqlalchemy import SQLAlchemy
from config import Config
import logging


app = Flask(__name__)
app.config.from_object(Config) 
app.config['SECRET_KEY'] = 'senin_cok_gizli_anahtarin' 
db = SQLAlchemy(app)

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


from routes import *


with app.app_context():
    db.create_all()
    app.logger.info("Veritabanı tabloları oluşturuldu veya zaten mevcut.")


if __name__ == '__main__':
    app.run(debug=True)
