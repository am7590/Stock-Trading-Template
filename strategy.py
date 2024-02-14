from lumibot.brokers import Alpaca
from lumibot.backtesting import YahooDataBacktesting
from lumibot.strategies.strategy import Strategy
from datetime import datetime
from alpaca_trade_api import REST
from config import ALPACA_CREDS
from sentiment import estimate_sentiment  
from timedelta import Timedelta 

# Constants
# These can change based on your preferences
SYMBOL = "SPY"
TIMEFRAME = "24H"
CASH_AT_RISK = 0.5
BASE_URL = "https://paper-api.alpaca.markets"
POSITIVE_SENTIMENT_THRESHOLD = 0.999
BUY_ORDER = "buy"
SELL_ORDER = "sell"
TAKE_PROFIT_MULTIPLIER = 1.20
STOP_LOSS_MULTIPLIER = 0.95
SELL_TAKE_PROFIT_MULTIPLIER = 0.8
SELL_STOP_LOSS_MULTIPLIER = 1.05

class MLTrader(Strategy):
    """
    Initializes the trading strategy with your paramaters
    """
    def initialize(self, symbol=SYMBOL, cash_at_risk=CASH_AT_RISK):
        self.symbol = symbol
        self.sleeptime = TIMEFRAME
        self.cash_at_risk = cash_at_risk
        self.last_trade = None
        self.api = REST(base_url=BASE_URL, key_id=ALPACA_CREDS["API_KEY"], secret_key=ALPACA_CREDS["API_SECRET"])

    """
    How much cash (what % of your portfolio) do you want to risk each trade?
    """
    def position_sizing(self):
        cash = self.get_cash()
        last_price = self.get_last_price(self.symbol)
        quantity = round(cash * self.cash_at_risk / last_price, 0)
        return cash, last_price, quantity

    """
    This logic is executed once every TIMEFRAME
    """
    def on_trading_iteration(self):
        cash, last_price, quantity = self.position_sizing()
        probability, sentiment = self.get_sentiment()

        if cash > last_price and probability > POSITIVE_SENTIMENT_THRESHOLD:
            if sentiment == "positive":
                if self.last_trade == SELL_ORDER: 
                    self.sell_all()
                self.create_and_submit_order(quantity, last_price, BUY_ORDER)
                self.last_trade = BUY_ORDER
            elif sentiment == "negative":
                if self.last_trade == BUY_ORDER:
                    self.sell_all()
                self.create_and_submit_order(quantity, last_price, SELL_ORDER)
                self.last_trade = SELL_ORDER

    """
    Get news sentiment for a particular stock over the last three days
    This is the only strategy involved to trigger buy/sell orders
    """
    def get_sentiment(self): 
        today = self.get_datetime()
        three_days_prior = today - Timedelta(days=3)
        news = self.api.get_news(symbol=self.symbol, 
                                 start=three_days_prior.strftime('%Y-%m-%d'),
                                 end=today.strftime('%Y-%m-%d')) 
        news = [ev.__dict__["_raw"]["headline"] for ev in news]
        probability, sentiment = estimate_sentiment(news)
        return probability, sentiment 

    """
    Execute an order
    We will discuss order types in the future (market vs. limit)
    """
    def create_and_submit_order(self, quantity, last_price, order_type):
        if order_type == BUY_ORDER:
            order = self.create_order(self.symbol, quantity, order_type, take_profit_price=last_price * TAKE_PROFIT_MULTIPLIER, stop_loss_price=last_price * STOP_LOSS_MULTIPLIER)
        else:
            order = self.create_order(self.symbol, quantity, order_type, take_profit_price=last_price * SELL_TAKE_PROFIT_MULTIPLIER, stop_loss_price=last_price * SELL_STOP_LOSS_MULTIPLIER)
        self.submit_order(order)            
    

if __name__ == "__main__":
    """
    Execute the backtest:
    - A backtest esentially runs your strategy on historical data
    - It's a general estimate on if your strategy could be profitable or not. It does NOT predict future prices.

    Your strategy is "good" if you sharpe ratio is over 1.0, max. drawdown is below 5%, and volatility is lower than the baseline. 

    We can change this from backtesting to live trading on Alpaca in just a few lines of code thanks to lumibot. 
    """
    start_date = datetime(2020, 1, 1)
    end_date = datetime(2023, 12, 31)
    broker = Alpaca(ALPACA_CREDS)
    strategy = MLTrader(name='mlstrat', broker=broker, parameters={"symbol": SYMBOL, "cash_at_risk": CASH_AT_RISK})
    strategy.backtest(YahooDataBacktesting, start_date, end_date, parameters={"symbol": SYMBOL, "cash_at_risk": CASH_AT_RISK})