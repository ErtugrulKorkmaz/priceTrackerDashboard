# models.py

from datetime import datetime
from app import db 

class Instrument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    symbol = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    
    prices = db.relationship('Price', backref='instrument', lazy=True)

    def __repr__(self):
        return f"Instrument('{self.symbol}', '{self.name}')"

class Price(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    instrument_id = db.Column(db.Integer, db.ForeignKey('instrument.id'), nullable=False)
    date = db.Column(db.Date, nullable=False)
    open = db.Column(db.Float, nullable=False)
    high = db.Column(db.Float, nullable=False)
    low = db.Column(db.Float, nullable=False)
    close = db.Column(db.Float, nullable=False)
    volume = db.Column(db.Integer, nullable=False)

    def __repr__(self):
        return f"Price('{self.instrument.symbol}', '{self.date}', '{self.close}')"
