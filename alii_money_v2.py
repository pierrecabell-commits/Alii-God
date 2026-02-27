from datetime import timezone
import yfinance as yf ; r = yf.Ticker("BTC-USD").history(period="1d") ; print(r["Close"][-1])
import ccxt ; b = ccxt.binance() ; print(b.fetch_ticker("BTC/USDT"))
