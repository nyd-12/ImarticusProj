# populate_db.py

import random
from datetime import datetime, timedelta
from faker import Faker
from app import app, db
from models import Client, Portfolio, Security, Trade, CashBalance, MarketIndex, DailyPrice, IndexPrice

# Initialize Faker for generating random data
fake = Faker()

# --- Configuration ---
NUM_CLIENTS = 6
PRICE_HISTORY_DAYS = 365  # Generate one year of historical prices


def clear_all_data():
    """Wipes all data from all tables."""
    print("!!! WARNING: DELETING ALL DATA FROM ALL TABLES !!!")
    # The order is important to avoid foreign key constraint errors
    meta = db.metadata
    for table in reversed(meta.sorted_tables):
        print(f"Clearing table: {table}")
        db.session.execute(table.delete())
    db.session.commit()


def create_master_data():
    """Creates the master data for indices and securities."""
    print("Creating master data (Indices and Securities)...")

    # Create Market Indices
    indices = [
        MarketIndex(id=1, name='NASDAQ Composite', ticker='^IXIC'),
        MarketIndex(id=2, name='FTSE 100', ticker='^FTSE'),
        MarketIndex(id=3, name='S&P 500', ticker='^GSPC')
    ]
    db.session.add_all(indices)

    # Create Securities
    securities = [
        Security(id=101, ticker='AAPL', name='Apple Inc.', security_type='Stock', currency='USD', exchange='NASDAQ',
                 beta=1.29, benchmark_index_id=1),
        Security(id=102, ticker='GOOGL', name='Alphabet Inc.', security_type='Stock', currency='USD', exchange='NASDAQ',
                 beta=1.05, benchmark_index_id=1),
        Security(id=103, ticker='MSFT', name='Microsoft Corporation', security_type='Stock', currency='USD',
                 exchange='NASDAQ', beta=0.92, benchmark_index_id=3),
        Security(id=104, ticker='HSBC', name='HSBC Holdings PLC', security_type='Stock', currency='GBP', exchange='LSE',
                 beta=0.85, benchmark_index_id=2)
    ]
    db.session.add_all(securities)
    db.session.commit()


def generate_price_history(start_price, num_days):
    """Generates a realistic-looking price history using a random walk."""
    prices = []
    today = datetime.utcnow().date()
    current_price = start_price
    for i in range(num_days, 0, -1):
        date = today - timedelta(days=i)
        prices.append((date, round(current_price, 2)))
        # Simulate daily price change
        change_pct = random.normalvariate(0.0005, 0.02)  # (mu, sigma) - small positive drift, 2% volatility
        current_price *= (1 + change_pct)
    return prices


def create_historical_prices():
    """Generates and saves price history for all securities and indices."""
    print(f"Generating {PRICE_HISTORY_DAYS} days of price history...")

    # For Securities
    securities = Security.query.all()
    all_daily_prices = []
    sec_start_prices = {'AAPL': 175, 'GOOGL': 140, 'MSFT': 415, 'HSBC': 630}
    for security in securities:
        history = generate_price_history(sec_start_prices.get(security.ticker, 100), PRICE_HISTORY_DAYS)
        for date, price in history:
            all_daily_prices.append(DailyPrice(security_id=security.id, price_date=date, closing_price=price))

    # For Indices
    indices = MarketIndex.query.all()
    all_index_prices = []
    idx_start_prices = {'^IXIC': 16000, '^FTSE': 7500, '^GSPC': 5100}
    for index in indices:
        history = generate_price_history(idx_start_prices.get(index.ticker, 1000), PRICE_HISTORY_DAYS)
        for date, price in history:
            all_index_prices.append(IndexPrice(index_id=index.id, price_date=date, closing_value=price))

    db.session.bulk_save_objects(all_daily_prices)
    db.session.bulk_save_objects(all_index_prices)
    db.session.commit()


def create_clients_and_portfolios():
    """Creates clients and a corresponding portfolio for each."""
    print(f"Creating {NUM_CLIENTS} new clients and portfolios...")
    clients_to_add = []
    for i in range(1, NUM_CLIENTS + 1):
        client = Client(name=fake.name(), email=fake.email())
        clients_to_add.append(client)
    db.session.add_all(clients_to_add)
    db.session.commit()  # Commit to get client IDs

    portfolios_to_add = []
    for client in clients_to_add:
        portfolio = Portfolio(name=f"{client.name.split()[0]}'s Portfolio", client_id=client.id)
        portfolios_to_add.append(portfolio)
    db.session.add_all(portfolios_to_add)
    db.session.commit()


def create_cash_balances():
    """Creates random cash balances for each portfolio."""
    print("Creating cash balances...")
    portfolios = Portfolio.query.all()
    balances_to_add = []
    currencies = ['USD', 'EUR', 'GBP', 'INR']
    for portfolio in portfolios:
        for currency in random.sample(currencies, k=random.randint(2, 3)):
            balance = CashBalance(
                portfolio_id=portfolio.id,
                currency=currency,
                amount=round(random.uniform(10000, 150000), 2)
            )
            balances_to_add.append(balance)
    db.session.add_all(balances_to_add)
    db.session.commit()


def create_holdings():
    """Creates random holdings (via trades) for each portfolio."""
    print("Creating holdings via back-dated trades...")
    portfolios = Portfolio.query.all()
    trades_to_add = []
    security_ids = [s.id for s in Security.query.all()]
    today = datetime.utcnow().date()

    for portfolio in portfolios:
        for security_id in random.sample(security_ids, k=random.randint(3, 4)):
            trade_date = today - timedelta(days=random.randint(30, 360))
            # Find a realistic price for the trade date
            price_on_date = DailyPrice.query.filter(
                DailyPrice.security_id == security_id,
                DailyPrice.price_date <= trade_date
            ).order_by(DailyPrice.price_date.desc()).first()

            if price_on_date:
                trade = Trade(
                    portfolio_id=portfolio.id,
                    security_id=security_id,
                    trade_date=trade_date,
                    trade_type='BUY',
                    quantity=round(random.uniform(10, 200), 2),
                    price_per_unit=round(price_on_date.closing_price * random.uniform(0.98, 1.02), 2)
                )
                trades_to_add.append(trade)
    db.session.add_all(trades_to_add)
    db.session.commit()


if __name__ == '__main__':
    with app.app_context():
        # --- Ensure database and tables exist before populating ---
        db.create_all()  # <-- This line creates portfolio.db and all tables if not present

        clear_all_data()
        create_master_data()
        create_historical_prices()
        create_clients_and_portfolios()
        create_cash_balances()
        create_holdings()
        print("\n✅ Database has been fully populated with new sample data!")
        print(f"   - Indices: {MarketIndex.query.count()}")
        print(f"   - Securities: {Security.query.count()}")
        print(f"   - Clients: {Client.query.count()}")
        print(f"   - Portfolios: {Portfolio.query.count()}")
        print(f"   - Trades: {Trade.query.count()}")