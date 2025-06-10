

from flask import render_template, request, jsonify, redirect, url_for, flash, get_flashed_messages
from app import app, db
from models import Instrument, Price
import requests
import pandas as pd
from datetime import datetime, timedelta


@app.route('/')
def index():
    instruments = Instrument.query.all()
    return render_template('index.html', instruments=instruments, messages=get_flashed_messages(with_categories=True))


@app.route('/instrument/<int:instrument_id>')
def instrument_details(instrument_id):
    instrument = db.session.get(Instrument, instrument_id)
    if not instrument:
        flash("Enstrüman bulunamadı.", 'error')
        return redirect(url_for('index'))
    

    timeframe = request.args.get('days', '90')

    end_date = datetime.now().date()
    start_date = None 

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
        
        start_date = datetime(2010, 1, 1).date()
    else:
        
        start_date = end_date - timedelta(days=90)
        timeframe = '90' 

 
    prices_query = Price.query.filter_by(instrument_id=instrument_id)\
                               .filter(Price.date >= start_date)\
                               .order_by(Price.date.asc())
    
    prices = prices_query.all()

    if not prices:
        flash(f"{instrument.name} için seçilen zaman aralığında veri bulunamadı.", 'info')
        return render_template('details.html',
                               instrument=instrument,
                               dates=[],
                               closes=[],
                               sma_data_20=[],
                               sma_data_50=[],
                               selected_timeframe=timeframe) 

    df = pd.DataFrame([{'date': p.date, 'close': p.close} for p in prices])
    df['date'] = pd.to_datetime(df['date'])
    df = df.set_index('date')
    df = df.sort_index()

    
    sma_period_20 = 20
    sma_period_50 = 50 
    
    df[f'SMA_{sma_period_20}'] = df['close'].rolling(window=sma_period_20).mean()
    df[f'SMA_{sma_period_50}'] = df['close'].rolling(window=sma_period_50).mean()

   
    
    
    df_with_smas = df.dropna(subset=[f'SMA_{sma_period_20}']) 

    dates = [d.strftime('%Y-%m-%d') for d in df_with_smas.index]
    closes = [c for c in df_with_smas['close']]
    sma_data_20 = [s for s in df_with_smas[f'SMA_{sma_period_20}']]
    
    
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
                           selected_timeframe=timeframe) 


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
