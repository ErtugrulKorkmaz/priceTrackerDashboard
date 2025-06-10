# routes.py

from flask import render_template, request, jsonify, redirect, url_for, flash, get_flashed_messages
from app import app, db
from models import Instrument, Price
import requests
import pandas as pd
from datetime import datetime, timedelta

# Ana sayfa: Tüm enstrümanları listele
@app.route('/')
def index():
    instruments = Instrument.query.all()
    return render_template('index.html', instruments=instruments, messages=get_flashed_messages(with_categories=True))

# Enstrüman detay sayfası: Seçilen enstrümanın fiyat grafiğini göster
# 'days' parametresi eklendi, varsayılanı 90 (90 gün)
@app.route('/instrument/<int:instrument_id>')
def instrument_details(instrument_id):
    instrument = db.session.get(Instrument, instrument_id)
    if not instrument:
        flash("Enstrüman bulunamadı.", 'error')
        return redirect(url_for('index'))
    
    # URL'den 'days' parametresini al, varsayılanı '90'
    # Kullanıcı "max" seçerse 'max' stringi gelir.
    timeframe = request.args.get('days', '90') # Varsayılan: 90 gün

    end_date = datetime.now().date()
    start_date = None # Başlangıç tarihini dinamik olarak belirleyeceğiz

    if timeframe == '7':
        start_date = end_date - timedelta(days=7)
    elif timeframe == '30':
        start_date = end_date - timedelta(days=30)
    elif timeframe == '90':
        start_date = end_date - timedelta(days=90)
    elif timeframe == '180': # Yeni seçenek: 6 Ay
        start_date = end_date - timedelta(days=180)
    elif timeframe == '365': # Yeni seçenek: 1 Yıl
        start_date = end_date - timedelta(days=365)
    elif timeframe == 'max':
        # 'max' seçeneği için başlangıç tarihini ayarlamıyoruz, tüm veriyi çekeceğiz.
        start_date = datetime(2010, 1, 1).date() # Çok eski bir tarih, pratikte tüm veriyi çeker
    else:
        # Geçersiz bir 'timeframe' gelirse varsayılan olarak 90 günü gösterelim
        start_date = end_date - timedelta(days=90)
        timeframe = '90' # timeframi de varsayılana çek

    # Veritabanından fiyat verilerini çek
    # Eğer 'max' seçildiyse 'start_date' çok eski bir tarih olacak ve tümünü çekecek.
    prices_query = Price.query.filter_by(instrument_id=instrument_id)\
                               .filter(Price.date >= start_date)\
                               .order_by(Price.date.asc())
    
    prices = prices_query.all()

    if not prices:
        flash(f"{instrument.name} için seçilen zaman aralığında veri bulunamadı.", 'info') # Bilgi mesajı
        return render_template('details.html',
                               instrument=instrument,
                               dates=[],
                               closes=[],
                               sma_data_20=[],
                               sma_data_50=[],
                               selected_timeframe=timeframe) # Seçilen zaman aralığını da gönder

    df = pd.DataFrame([{'date': p.date, 'close': p.close} for p in prices])
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    df = df.sort_index()

    # Eğer yeterli veri yoksa SMA hesaplamamaya dikkat etmeliyiz
    sma_period_20 = 20
    sma_period_50 = 50 
    
    df[f'SMA_{sma_period_20}'] = df['close'].rolling(window=sma_period_20).mean()
    df[f'SMA_{sma_period_50}'] = df['close'].rolling(window=sma_period_50).mean()

    # NaN (ilk N günkü boş) değerleri kaldırarak sadece SMA'sı olan satırları al
    # Hem 20 hem 50 günlük SMA'nın olduğu satırları alalım ki grafikler hizalı olsun
    # Ancak burada dikkat: Eğer seçilen aralık 50 günden kısaysa (örn 7 gün), 50 günlük SMA hiç oluşmaz.
    # Bu durumda sadece 20 günlük veya kapanış fiyatını gösterelim.
    
    # Sadece hesaplanabilen SMA'ları alalım
    df_with_smas = df.dropna(subset=[f'SMA_{sma_period_20}']) # En azından 20 günlük SMA olanları al

    dates = [d.strftime('%Y-%m-%d') for d in df_with_smas.index]
    closes = [c for c in df_with_smas['close']]
    sma_data_20 = [s for s in df_with_smas[f'SMA_{sma_period_20}']]
    
    # 50 günlük SMA varsa onu da gönder
    sma_data_50 = []
    if f'SMA_{sma_period_50}' in df_with_smas.columns:
        sma_data_50 = [s for s in df_with_smas[f'SMA_{sma_period_50}']]

    return render_template('details.html',
                           instrument=instrument,
                           dates=dates,
                           closes=closes,
                           sma_data_20=sma_data_20,
                           sma_data_50=sma_data_50,
                           sma_period_20=sma_period_20,
                           sma_period_50=sma_period_50,
                           selected_timeframe=timeframe) # <-- Seçilen zaman aralığını da gönderiyoruz

# Yeni enstrüman ekleme veya mevcut enstrümanı güncelleme (CoinGecko ile) - Bu kısım DEĞİŞMEDİ
@app.route('/add_or_update_instrument', methods=['POST'])
def add_or_update_instrument():
    symbol_input = request.form['symbol'].strip().lower()
    name_input = request.form.get('name', symbol_input).strip()

    if not symbol_input:
        flash("Sembol boş olamaz!", 'error')
        return redirect(url_for('index'))

    coingecko_id = None
    coin_name_from_api = name_input 
    
    try:
        coin_list_url = 'https://api.coingecko.com/api/v3/coins/list'
        response = requests.get(coin_list_url, timeout=10)
        response.raise_for_status()
        coin_list = response.json()

        for coin in coin_list:
            if coin['symbol'].lower() == symbol_input or coin['id'].lower() == symbol_input or coin['name'].lower() == symbol_input:
                coingecko_id = coin['id']
                coin_name_from_api = coin['name']
                break
        
        if not coingecko_id:
            flash(f"'{symbol_input}' sembolüne veya adına sahip bir kripto para CoinGecko'da bulunamadı. Lütfen 'bitcoin', 'ethereum' gibi tam ID veya isim kullanın.", 'error')
            return redirect(url_for('index'))

        instrument = Instrument.query.filter_by(symbol=coingecko_id).first()

        if not instrument:
            instrument = Instrument(symbol=coingecko_id, name=coin_name_from_api)
            db.session.add(instrument)
            db.session.commit()
            db.session.refresh(instrument)
            app.logger.info(f"Yeni kripto para eklendi: {coingecko_id} ({coin_name_from_api})")
        else:
            instrument.name = coin_name_from_api
            db.session.commit()
            app.logger.info(f"Mevcut kripto para güncelleniyor: {coingecko_id} ({coin_name_from_api})")

        # CoinGecko'dan geçmiş fiyat verilerini çek (Şimdilik her zaman 90 gün çekiyoruz)
        # Daha geniş bir tarih aralığı istersen 'days=max' veya 'days=365' gibi burayı da değiştirebilirsin
        # Ancak CoinGecko'nun 'days=max' endpoint'i rate limit'e daha çabuk takılabilir.
        market_chart_url = f'https://api.coingecko.com/api/v3/coins/{coingecko_id}/market_chart?vs_currency=usd&days=90'
        
        response = requests.get(market_chart_url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "prices" not in data or not data["prices"]:
            flash(f"CoinGecko API'den {coin_name_from_api} için fiyat verisi çekilemedi.", 'error')
            return redirect(url_for('index'))

        prices_data = data["prices"]
        df = pd.DataFrame(prices_data, columns=['timestamp', 'close'])
        df['date'] = pd.to_datetime(df['timestamp'], unit='ms').dt.date
        df = df.drop(columns=['timestamp'])
        df = df.drop_duplicates(subset=['date'], keep='last')
        df = df.sort_values(by='date')

        for index, row in df.iterrows():
            date_obj = row['date']
            existing_price = Price.query.filter_by(instrument_id=instrument.id, date=date_obj).first()

            if existing_price:
                existing_price.close = float(row['close'])
                existing_price.open = float(row['close']) 
                existing_price.high = float(row['close'])
                existing_price.low = float(row['close'])
                existing_price.volume = 0 
            else:
                new_price = Price(
                    instrument_id=instrument.id,
                    date=date_obj,
                    open=float(row['close']),
                    high=float(row['close']),
                    low=float(row['close']),
                    close=float(row['close']),
                    volume=0
                )
                db.session.add(new_price)
        db.session.commit()
        flash(f"{instrument.name} için fiyat verileri başarıyla güncellendi/eklendi.", 'success')
        
    except requests.exceptions.Timeout:
        db.session.rollback()
        flash('API isteği zaman aşımına uğradı. İnternet bağlantınızı kontrol edin veya daha sonra tekrar deneyin.', 'error')
        return redirect(url_for('index'))
    except requests.exceptions.RequestException as e:
        db.session.rollback()
        flash(f'API bağlantı hatası oluştu: {e}', 'error')
        return redirect(url_for('index'))
    except Exception as e:
        db.session.rollback()
        flash(f'Veri işleme sırasında beklenmeyen bir hata oluştu: {e}', 'error')
        return redirect(url_for('index'))

    return redirect(url_for('instrument_details', instrument_id=instrument.id))

# Enstrüman silme - BU KISIM DEĞİŞMEDİ
@app.route('/delete_instrument/<int:instrument_id>', methods=['POST'])
def delete_instrument(instrument_id):
    instrument = db.session.get(Instrument, instrument_id) 
    if not instrument:
        flash("Silinecek enstrüman bulunamadı.", 'error')
        return redirect(url_for('index'))
    
    Price.query.filter_by(instrument_id=instrument.id).delete()

    db.session.delete(instrument)
    db.session.commit()
    flash(f"{instrument.name} başarıyla silindi.", 'success')
    return redirect(url_for('index'))