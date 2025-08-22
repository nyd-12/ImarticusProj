from flask_sqlalchemy import SQLAlchemy

# In your main app file (app.py), you would initialize db like this:
# from flask import Flask
# app = Flask(__name__)
# app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///portfolio.db'
# db = SQLAlchemy(app)
#
# For this example, we'll define it here for context.
db = SQLAlchemy()


class Client(db.Model):
    """Stores client information."""
    __tablename__ = 'clients'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)

    # Relationship to Portfolios
    portfolios = db.relationship('Portfolio', back_populates='client', cascade="all, delete-orphan")


class Portfolio(db.Model):
    """Links clients to their portfolios."""
    __tablename__ = 'portfolios'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, default='Default Portfolio')
    base_currency = db.Column(db.String(3), nullable=False, default='USD')
    client_id = db.Column(db.Integer, db.ForeignKey('clients.id'), nullable=False)

    # Relationships
    client = db.relationship('Client', back_populates='portfolios')
    trades = db.relationship('Trade', back_populates='portfolio', cascade="all, delete-orphan")
    cash_balances = db.relationship('CashBalance', back_populates='portfolio', cascade="all, delete-orphan")


class Security(db.Model):
    """The Security Master table for all tradable assets."""
    __tablename__ = 'securities'
    id = db.Column(db.Integer, primary_key=True)
    ticker = db.Column(db.String(20), unique=True, nullable=False)
    name = db.Column(db.String(150), nullable=False)
    security_type = db.Column(db.String(50), nullable=False)  # e.g., 'Stock', 'Bond'
    currency = db.Column(db.String(3), nullable=False)
    exchange = db.Column(db.String(50))
    beta = db.Column(db.Float)
    benchmark_index_id = db.Column(db.Integer, db.ForeignKey('market_indices.id'))

    # Relationships
    benchmark_index = db.relationship('MarketIndex')
    daily_prices = db.relationship('DailyPrice', back_populates='security', cascade="all, delete-orphan")


class Trade(db.Model):
    """Records every buy and sell transaction."""
    __tablename__ = 'trades'
    id = db.Column(db.Integer, primary_key=True)
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolios.id'), nullable=False)
    security_id = db.Column(db.Integer, db.ForeignKey('securities.id'), nullable=False)
    trade_date = db.Column(db.Date, nullable=False)
    trade_type = db.Column(db.String(4), nullable=False)  # 'BUY' or 'SELL'
    quantity = db.Column(db.Float, nullable=False)
    price_per_unit = db.Column(db.Float, nullable=False)

    # Relationships
    portfolio = db.relationship('Portfolio', back_populates='trades')
    security = db.relationship('Security')


class CashBalance(db.Model):
    """Tracks cash in different currencies for each portfolio."""
    __tablename__ = 'cash_balances'
    id = db.Column(db.Integer, primary_key=True)
    portfolio_id = db.Column(db.Integer, db.ForeignKey('portfolios.id'), nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    amount = db.Column(db.Float, nullable=False, default=0.0)

    # Relationship
    portfolio = db.relationship('Portfolio', back_populates='cash_balances')


class DailyPrice(db.Model):
    """Stores the end-of-day closing prices for MTM calculation."""
    __tablename__ = 'daily_prices'
    id = db.Column(db.Integer, primary_key=True)
    security_id = db.Column(db.Integer, db.ForeignKey('securities.id'), nullable=False)
    price_date = db.Column(db.Date, nullable=False)
    closing_price = db.Column(db.Float, nullable=False)

    # Relationship
    security = db.relationship('Security', back_populates='daily_prices')


class MarketIndex(db.Model):
    """Static data for benchmark indices."""
    __tablename__ = 'market_indices'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    ticker = db.Column(db.String(20), unique=True, nullable=False)

    # Relationship
    index_prices = db.relationship('IndexPrice', back_populates='market_index', cascade="all, delete-orphan")


class IndexPrice(db.Model):
    """Daily closing values for the benchmark indices."""
    __tablename__ = 'index_prices'
    id = db.Column(db.Integer, primary_key=True)
    index_id = db.Column(db.Integer, db.ForeignKey('market_indices.id'), nullable=False)
    price_date = db.Column(db.Date, nullable=False)
    closing_value = db.Column(db.Float, nullable=False)

    # Relationship
    market_index = db.relationship('MarketIndex', back_populates='index_prices')
