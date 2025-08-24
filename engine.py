# engine.py

from datetime import date, timedelta
import pandas as pd
import numpy as np
from sqlalchemy import and_
from models import db, Portfolio, Trade, DailyPrice, Security, CashBalance, IndexPrice


# ===================================================================
#  HELPER FUNCTIONS (DEFINED FIRST)
# ===================================================================

def get_price_on_date(security_id, target_date):
    """Fetches the most recent price for a security on or before a given date."""
    price_entry = DailyPrice.query.filter(
        DailyPrice.security_id == security_id,
        DailyPrice.price_date <= target_date
    ).order_by(DailyPrice.price_date.desc()).first()
    return price_entry.closing_price if price_entry else 0


def calculate_historical_portfolio_value(portfolio_id: int, report_date: date):
    """
    Calculates the actual daily total value of the portfolio for the past year
    and returns a pandas Series of daily percentage returns.
    """
    start_date = report_date - timedelta(days=365)

    trades = Trade.query.filter(
        Trade.portfolio_id == portfolio_id,
        Trade.trade_date <= report_date
    ).order_by(Trade.trade_date).all()

    if not trades:
        return pd.Series(dtype=float)

    security_ids = list(set(trade.security_id for trade in trades))
    prices = DailyPrice.query.filter(
        DailyPrice.security_id.in_(security_ids),
        DailyPrice.price_date.between(start_date, report_date)
    ).all()

    price_df = pd.DataFrame([(p.price_date, p.security.ticker, p.closing_price) for p in prices],
                            columns=['date', 'ticker', 'price']).pivot(index='date', columns='ticker', values='price')

    # Define the full date range for alignment
    date_range = pd.date_range(start=start_date, end=report_date, freq='D') # basically add rows to the missing 
    #fields in the panda series
    
    # Reindex the price_df to match the full date_range and forward-fill missing values.
    # This ensures that if a price for report_date is missing, the last known price is used.
    price_df = price_df.reindex(date_range).ffill()

    holdings_df = pd.DataFrame(index=date_range, columns=price_df.columns).fillna(0)

    for trade in trades:
        trade_date = pd.to_datetime(trade.trade_date)
        if trade.security.ticker in holdings_df.columns:
            if trade.trade_type == 'BUY':
                holdings_df.loc[trade_date:, trade.security.ticker] += trade.quantity
            elif trade.trade_type == 'SELL':
                holdings_df.loc[trade_date:, trade.security.ticker] -= trade.quantity

    # Now that price_df is aligned, this calculation will be correct
    daily_values = holdings_df.mul(price_df).sum(axis=1)
    daily_returns = daily_values.pct_change()

    daily_returns.replace([np.inf, -np.inf], np.nan, inplace=True)
    daily_returns.dropna(inplace=True)

    return daily_returns


def calculate_sharpe_ratio(daily_returns: pd.Series, risk_free_rate=0.02):
    """Calculates Sharpe Ratio from an actual series of returns."""
    if daily_returns.empty or daily_returns.std() == 0:
        return None

    excess_returns = daily_returns - (risk_free_rate / 252)
    sharpe = (np.sqrt(252) * excess_returns.mean()) / excess_returns.std()
    return sharpe


def benchmark_performance(portfolio_id: int, portfolio_returns: pd.Series, report_date: date):
    """Compares portfolio performance against its main holding's benchmark, fallback to NASDAQ Composite."""
    from models import Portfolio, Security, MarketIndex
    # Support multiple periods: 1M, 3M, 6M, 1Y
    periods = {
        "1M": 30,
        "3M": 90,
        "6M": 180,
        "1Y": 365
    }

    # Find all market indices
    all_indices = MarketIndex.query.all()
    results = []
    for index in all_indices:
        for period_name, days in periods.items():
            start_date = report_date - timedelta(days=days)
            # Portfolio returns for this period
            port_returns_period = portfolio_returns[portfolio_returns.index >= pd.to_datetime(start_date)] if not portfolio_returns.empty else pd.Series(dtype=float)

            if port_returns_period.empty:
                portfolio_return_pct = "N/A"
            else:
                portfolio_total_return = (1 + port_returns_period).prod() - 1
                portfolio_return_pct = round(portfolio_total_return * 100, 2)

            index_prices = IndexPrice.query.filter(
                IndexPrice.index_id == index.id,
                IndexPrice.price_date.between(start_date, report_date)
            ).order_by(IndexPrice.price_date).all()

            if not index_prices:
                benchmark_return_pct = "N/A"
            else:
                index_df = pd.DataFrame([(p.price_date, p.closing_value) for p in index_prices],
                                        columns=['date', 'value']).set_index('date')
                index_returns = index_df['value'].pct_change()
                index_returns.replace([np.inf, -np.inf], np.nan, inplace=True)
                index_returns.dropna(inplace=True)
                if index_returns.empty:
                    benchmark_return_pct = "N/A"
                else:
                    benchmark_total_return = (1 + index_returns).prod() - 1
                    benchmark_return_pct = round(benchmark_total_return * 100, 2)

            results.append({
                "vs_index": index.name if index else "Benchmark",
                "period": period_name,
                "portfolio_return_pct": portfolio_return_pct,
                "benchmark_return_pct": benchmark_return_pct
            })

    return results


def calculate_portfolio_delta(holdings_list, total_portfolio_value):
    """
    Calculates the portfolio's delta, defined as the sensitivity of the
    total portfolio value to changes in its underlying equity prices.
    
    This is calculated as the ratio of the total value of stock holdings to the
    total portfolio value (including cash). For a portfolio of only stocks,
    the delta is 1. For a portfolio of 50% stocks and 50% cash, the
    delta is 0.5.
    """
    if not total_portfolio_value or total_portfolio_value == 0:
        return 0
    
    # Sum the current value of all equity holdings
    total_equity_value = sum(h['current_value'] for h in holdings_list)
    
    # Delta is the proportion of the portfolio that is in equities
    portfolio_delta = total_equity_value / total_portfolio_value
    
    return portfolio_delta

# ===================================================================
#  MAIN ENGINE FUNCTION (DEFINED LAST)
# ===================================================================

def generate_portfolio_statement(portfolio_id: int, report_date: date):
    """
    Generates a complete portfolio statement for a given portfolio and date.
    """
    portfolio = Portfolio.query.get(portfolio_id)
    if not portfolio:
        return {"error": "Portfolio not found"}

    trades = Trade.query.filter(
        Trade.portfolio_id == portfolio_id,
        Trade.trade_date <= report_date
    ).join(Security).order_by(Trade.trade_date).all()
    # get the trade data on or before the specified date

    holdings = {}
    for trade in trades:
        sec_id = trade.security_id
        if sec_id not in holdings:
            holdings[sec_id] = {
                'quantity': 0, 'total_cost': 0, 'total_quantity_bought': 0,
                'first_trade_date': trade.trade_date, 'security': trade.security
            }

        if trade.trade_type == 'BUY':
            holdings[sec_id]['quantity'] += trade.quantity
            holdings[sec_id]['total_cost'] += trade.quantity * trade.price_per_unit
            holdings[sec_id]['total_quantity_bought'] += trade.quantity
            if trade.trade_date < holdings[sec_id]['first_trade_date']:
                holdings[sec_id]['first_trade_date'] = trade.trade_date
        elif trade.trade_type == 'SELL':
            holdings[sec_id]['quantity'] -= trade.quantity

    holdings_list = []
    total_portfolio_value = 0

    for sec_id, data in holdings.items():
        if data['quantity'] > 0:
            current_price = get_price_on_date(sec_id, report_date)
            if data['total_quantity_bought'] == 0:
                continue

            avg_buy_price = data['total_cost'] / data['total_quantity_bought']
            buy_value = avg_buy_price * data['quantity']
            current_value = current_price * data['quantity']
            gain_loss = current_value - buy_value

            holdings_list.append({
                "ticker": data['security'].ticker, "name": data['security'].name,
                "quantity": data['quantity'], "average_buy_price": round(avg_buy_price, 2),
                "buy_value": round(buy_value, 2), "current_price": round(current_price, 2),
                "current_value": round(current_value, 2), "gain_loss": round(gain_loss, 2),
                "holding_period_days": (report_date - data['first_trade_date']).days,
                "beta": data['security'].beta or 0
            })
            total_portfolio_value += current_value

    cash_balances = CashBalance.query.filter_by(portfolio_id=portfolio_id).all()
    cash_list = []
    for cb in cash_balances:
        total_portfolio_value += cb.amount
        cash_list.append({"currency": cb.currency, "amount": cb.amount})

    portfolio_beta = 0
    portfolio_delta = 0
    if total_portfolio_value > 0 and holdings_list:
        for holding in holdings_list:
            weight = holding['current_value'] / total_portfolio_value
            portfolio_beta += weight * holding['beta']
        # Use new delta calculation
        portfolio_delta = calculate_portfolio_delta(holdings_list, total_portfolio_value)
    else:
        portfolio_beta = 0
        portfolio_delta = 0

    daily_returns = calculate_historical_portfolio_value(portfolio_id, report_date)
    sharpe_ratio = calculate_sharpe_ratio(daily_returns)
    benchmarks = benchmark_performance(portfolio_id, daily_returns, report_date)

    statement = {
        "portfolio_id": portfolio.id, "portfolio_name": portfolio.name,
        "client_name": portfolio.client.name, "report_date": report_date.isoformat(),
        "base_currency": portfolio.base_currency, "total_portfolio_value": round(total_portfolio_value, 2),
        "holdings": holdings_list, "cash_balances": cash_list,
        "risk_measures": {
            "beta": round(portfolio_beta, 2) if holdings_list else "N/A",
            "sharpe_ratio": round(sharpe_ratio, 2) if sharpe_ratio is not None and holdings_list else "N/A",
            "delta": round(portfolio_delta, 4) if holdings_list else 0  # More precision for delta
        },
        "performance_benchmarks": benchmarks if benchmarks else [
            {"vs_index": "N/A", "period": p, "portfolio_return_pct": "N/A", "benchmark_return_pct": "N/A"} for p in ["1M", "3M", "6M", "1Y"]
        ]
    }
    return statement