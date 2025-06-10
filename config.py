import os 
class Config:
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(os.path.abspath(os.path.dirname(__file__)), 'site.db') 
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ALPHA_VANTAGE_API_KEY = 'AE4AJQ4LPMHWDBTR'


