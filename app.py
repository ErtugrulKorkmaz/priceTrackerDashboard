# app.py

from flask import Flask, flash, get_flashed_messages # <-- BURAYI GÜNCELLE
from flask_sqlalchemy import SQLAlchemy
from config import Config
import logging

# Uygulama başlatma
app = Flask(__name__)
app.config.from_object(Config) # config.py dosyasındaki ayarları yükle
app.config['SECRET_KEY'] = 'senin_cok_gizli_anahtarin' # <-- YENİ EKLENECEK SATIR - Burayı güçlü ve benzersiz bir şeyle değiştir!

# Veritabanı bağlantısı
db = SQLAlchemy(app)

# Loglama ayarları
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# routes.py dosyasındaki rotaları import et (uygulama başlatıldığında yüklenirler)
from routes import *

# Veritabanı tablolarını oluştur (sadece ilk çalıştırmada veya tablo yoksa)
with app.app_context():
    db.create_all()
    app.logger.info("Veritabanı tabloları oluşturuldu veya zaten mevcut.")


if __name__ == '__main__':
    app.run(debug=True)