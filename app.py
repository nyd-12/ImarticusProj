# app.py
import os
from flask import Flask, request, jsonify, render_template
from datetime import datetime
from models import db, Client, Portfolio, Security, Trade, CashBalance
from engine import generate_portfolio_statement

# --- App Configuration ---
app = Flask(__name__)
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'portfolio.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


# --- Helper Functions ---
def get_report_date():
    """Gets and validates the report date from request arguments."""
    date_str = request.args.get('date')
    if not date_str:
        return datetime.utcnow().date(), None
    try:
        return datetime.strptime(date_str, '%Y-%m-%d').date(), None
    except ValueError:
        return None, jsonify({"error": "Invalid date format. Please use YYYY-MM-DD."})


# --- API Endpoints ---
@app.route('/')
def index():
    """Renders the main HTML page."""
    return render_template('index.html')


@app.route('/portfolio/<int:portfolio_id>/statement', methods=['GET'])
def get_portfolio_statement(portfolio_id):
    """Generates and returns the portfolio statement."""
    report_date, error_response = get_report_date()
    if error_response:
        return error_response, 400

    statement = generate_portfolio_statement(portfolio_id, report_date)
    if "error" in statement:
        return jsonify(statement), 404
    return jsonify(statement)


# app.py

@app.route('/trade', methods=['POST'])
def add_trade():
    """Adds a new trade to the database and updates cash balance."""
    data = request.get_json()
    if not data:
        return jsonify({"error": "Invalid JSON payload"}), 400

    required_fields = ['portfolio_id', 'security_id', 'trade_date', 'trade_type', 'quantity', 'price_per_unit']
    if not all(field in data for field in required_fields):
        return jsonify({"error": "Missing required fields"}), 400

    try:
        # --- START OF IMPROVED LOGIC ---

        # 1. Fetch portfolio and security objects first to ensure they exist.
        portfolio_id = int(data['portfolio_id'])
        security_id = int(data['security_id'])

        portfolio = Portfolio.query.get(portfolio_id)
        security = Security.query.get(security_id)

        if not portfolio or not security:
            return jsonify({"error": "Portfolio or Security not found"}), 404

        # 2. Parse and validate the rest of the data.
        trade_date = datetime.strptime(data['trade_date'], '%Y-%m-%d').date()
        quantity = float(data['quantity'])
        price = float(data['price_per_unit'])
        trade_type = data['trade_type'].upper()

        if trade_type not in ['BUY', 'SELL']:
            raise ValueError("trade_type must be BUY or SELL")

        # 3. Create the new trade object.
        new_trade = Trade(
            portfolio_id=portfolio.id,
            security_id=security.id,
            trade_date=trade_date,
            trade_type=trade_type,
            quantity=quantity,
            price_per_unit=price
        )
        db.session.add(new_trade)

        # 4. Find or create the correct cash balance and update it.
        cash = CashBalance.query.filter_by(
            portfolio_id=portfolio.id,
            currency=security.currency
        ).first()

        if not cash:
            cash = CashBalance(portfolio_id=portfolio.id, currency=security.currency, amount=0)
            db.session.add(cash)

        total_amount = quantity * price
        if trade_type == 'BUY':
            cash.amount -= total_amount
        else:  # SELL
            cash.amount += total_amount

        # 5. Commit the transaction to the database.
        db.session.commit()

        # --- END OF IMPROVED LOGIC ---

        return jsonify({"message": "Trade added successfully", "trade_id": new_trade.id}), 201

    except (ValueError, KeyError) as e:
        db.session.rollback()
        return jsonify({"error": f"Invalid data provided: {e}"}), 400
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"An unexpected error occurred: {e}")
        return jsonify({"error": "An internal server error occurred."}), 500


# --- Main Execution ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
