import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, time, timedelta
import plotly.graph_objects as go
from tvDatafeed import TvDatafeed, Interval
import time
import random
import warnings
import asyncio
import nest_asyncio
from telegram import Bot
from telegram.error import TelegramError
import threading
import requests
import yfinance as yf
warnings.filterwarnings('ignore')

# --- REMOVE ALL STREAMLIT & GITHUB BRANDING ---
st.markdown("""
    <style>
        [data-testid="stHeader"] { display: none !important; }
        [data-testid="stFooter"], footer { display: none !important; }
        [data-testid="stToolbar"] { display: none !important; }
        .viewerBadge_container__1QSob, .stAppDeployButton, div[class*="viewerBadge"] { display: none !important; }
        .main .block-container { padding-top: 2rem !important; padding-bottom: 0rem !important; }
        [data-testid="stStatusWidget"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

nest_asyncio.apply()

st.set_page_config(
    page_title="Algo Trading System",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Telegram Configuration
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
telegram_bot = Bot(token=TELEGRAM_TOKEN)
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Initialize session state
if 'trading_active' not in st.session_state:
    st.session_state.trading_active = False
if 'signals' not in st.session_state:
    st.session_state.signals = []
if 'active_trades' not in st.session_state:
    st.session_state.active_trades = []
if 'completed_trades' not in st.session_state:
    st.session_state.completed_trades = []
if 'last_update' not in st.session_state:
    st.session_state.last_update = None
if 'mode' not in st.session_state:
    st.session_state.mode = "Live Trading"
if 'signal_count_per_stock' not in st.session_state:
    st.session_state.signal_count_per_stock = {}
if 'last_signal_time' not in st.session_state:
    st.session_state.last_signal_time = {}
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False
if 'refresh_counter' not in st.session_state:
    st.session_state.refresh_counter = 0
if 'last_check_time' not in st.session_state:
    st.session_state.last_check_time = None
if 'bot_thread' not in st.session_state:
    st.session_state.bot_thread = None
if 'stop_bot' not in st.session_state:
    st.session_state.stop_bot = False
if 'filtered_stocks' not in st.session_state:
    st.session_state.filtered_stocks = []
if 'filtered_df' not in st.session_state:
    st.session_state.filtered_df = pd.DataFrame()
if 'use_filtered' not in st.session_state:
    st.session_state.use_filtered = False
if 'market_type' not in st.session_state:
    st.session_state.market_type = "Gainers"

# Stock symbols
SYMBOLS = ["BANKNIFTY", "NIFTY", "UPL", "INFY", "ULTRACEMCO", "RELIANCE", 
           "ASIANPAINT", "ABB", "ACC", "LT", "HDFCBANK"]

# Complete NIFTY 200 Stocks List (as of 2024)
NIFTY_200_STOCKS = [
    "RELIANCE", "TCS", "HDFCBANK", "INFY", "HINDUNILVR", "ICICIBANK", "ITC",
    "SBIN", "BHARTIARTL", "KOTAKBANK", "BAJFINANCE", "LT", "AXISBANK", "HCLTECH",
    "WIPRO", "SUNPHARMA", "MARUTI", "TITAN", "ULTRACEMCO", "ASIANPAINT", "ONGC",
    "NTPC", "POWERGRID", "ADANIPORTS", "M&M", "BAJAJFINSV", "NESTLE", "JSWSTEEL",
    "TATASTEEL", "TECHM", "INDUSINDBK", "GRASIM", "DRREDDY", "BPCL", "DIVISLAB",
    "HDFCLIFE", "SBILIFE", "BRITANNIA", "CIPLA", "SHREECEM", "HEROMOTOCO",
    "EICHERMOT", "BAJAJ-AUTO", "COALINDIA", "UPL", "TATAMOTORS", "HINDALCO",
    "VEDL", "IOC", "GAIL", "PIDILITIND", "BERGEPAINT", "DABUR", "MARICO",
    "HAVELLS", "VOLTAS", "AMBUJACEM", "ACC", "DLF", "GODREJCP", "TORNTPHARM",
    "LUPIN", "AUROPHARMA", "BIOCON", "CADILAHC", "ALKEM", "APOLLOHOSP", "COFORGE",
    "MPHASIS", "LTI", "PERSISTENT", "BSOFT", "BANKBARODA", "PNB", "CANBK",
    "IDFCFIRSTB", "FEDERALBNK", "RBLBANK", "SRTRANSFIN", "CHOLAFIN", "MANAPPURAM", "PEL"
]

# Disclaimer
DISCLAIMER = """
━━━━━━━━━━━━━━━━━━
📢 **EDUCATIONAL DISCLAIMER:**
This is for STUDY & ANALYSIS only.
We are NOT SEBI registered advisors.
No trading recommendations provided.
Always consult registered experts.
━━━━━━━━━━━━━━━━━━"""

# --- FUNCTION TO FETCH STOCK DATA USING YFINANCE ---
@st.cache_data(ttl=300)
def fetch_stock_data_with_yfinance(symbols):
    """Fetch stock data using yfinance"""
    try:
        stocks_data = []
        
        for symbol in symbols:
            try:
                # Add .NS suffix for NSE stocks
                ticker = yf.Ticker(f"{symbol}.NS")
                info = ticker.info
                
                # Get current price
                current_price = info.get('currentPrice', info.get('regularMarketPrice', 0))
                previous_close = info.get('previousClose', 0)
                
                if current_price > 0 and previous_close > 0:
                    change_percent = ((current_price - previous_close) / previous_close) * 100
                    
                    stocks_data.append({
                        'Symbol': symbol,
                        'LTP': current_price,
                        'Change %': change_percent,
                        'Volume': info.get('volume', 0),
                        'Previous Close': previous_close,
                        'Day High': info.get('dayHigh', 0),
                        'Day Low': info.get('dayLow', 0)
                    })
                else:
                    # Add with zero values if data not available
                    stocks_data.append({
                        'Symbol': symbol,
                        'LTP': 0,
                        'Change %': 0,
                        'Volume': 0,
                        'Previous Close': 0,
                        'Day High': 0,
                        'Day Low': 0
                    })
                    
            except Exception as e:
                # Add with zero values on error
                stocks_data.append({
                    'Symbol': symbol,
                    'LTP': 0,
                    'Change %': 0,
                    'Volume': 0,
                    'Previous Close': 0,
                    'Day High': 0,
                    'Day Low': 0
                })
        
        df = pd.DataFrame(stocks_data)
        # Filter out stocks with zero LTP (failed to fetch)
        df = df[df['LTP'] > 0]
        return df
        
    except Exception as e:
        st.error(f"Error fetching data: {str(e)}")
        return pd.DataFrame()

# --- ALTERNATIVE: Use pre-defined gainers/losers data ---
def get_sample_gainers_losers():
    """Generate sample gainers/losers data for demonstration"""
    np.random.seed(42)
    n_stocks = min(50, len(NIFTY_200_STOCKS))
    selected_stocks = np.random.choice(NIFTY_200_STOCKS, n_stocks, replace=False)
    
    stocks_data = []
    for stock in selected_stocks:
        ltp = np.random.uniform(100, 5000)
        change = np.random.uniform(-10, 10)
        stocks_data.append({
            'Symbol': stock,
            'LTP': ltp,
            'Change %': change,
            'Volume': np.random.randint(10000, 10000000)
        })
    
    df = pd.DataFrame(stocks_data)
    return df

def send_telegram_message_sync(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        response = requests.post(url, data=payload)
        return response.status_code == 200
    except:
        return False

def send_telegram_alert(signal, alert_type="ENTRY"):
    try:
        if signal['SIGNAL'] == 'BUY':
            emoji = "🟢"
        else:
            emoji = "🔴"
        
        if alert_type == "ENTRY":
            message = f"""
{emoji} *NEW TRADE SIGNAL* {emoji}

📊 *Symbol:* {signal['SYMBOL']}
🎯 *Signal:* {signal['SIGNAL']}
💰 *Entry:* ₹{signal['ENTRY']}
🛑 *Stop Loss:* ₹{signal['STOPLOSS']}
📈 *Target 1:* ₹{signal['T1']}
📈 *Target 2:* ₹{signal['T2']}
📈 *Target 3:* ₹{signal['T3']}
📦 *Quantity:* {signal['QUANTITY']}
⏰ *Time:* {signal['ENTRY_TIME']}
📅 *Date:* {signal['DATE']}
⚡ *Breakout at:* {signal['BREAKOUT_CANDLE']}

{DISCLAIMER}
            """
        return send_telegram_message_sync(message)
    except:
        return False

def send_bulk_telegram_alerts(signals):
    for signal in signals:
        send_telegram_alert(signal, "ENTRY")
        time.sleep(1)

def round_to_2_decimals(value):
    return round(float(value), 2)

class CandleBreakoutStrategy:
    def __init__(self, timeframe='15min', risk_amount=10000, mode="Live Trading"):
        self.timeframe = timeframe
        self.risk_amount = risk_amount
        self.mode = mode
        self.name = "Candle Breakout Strategy"
        
    def analyze(self, df, symbol, date_tracker=None):
        if df is None or len(df) < 2:
            return None
            
        signals = []
        df.index = pd.to_datetime(df.index)
        today_date = datetime.now().date()
        
        today_df = df[df.index.date == today_date]
        
        if len(today_df) < 1:
            return None

        reference_candle = today_df.iloc[0]
        
        high_ref = round_to_2_decimals(reference_candle['high'])
        low_ref = round_to_2_decimals(reference_candle['low'])
        date_str = today_date.strftime('%Y-%m-%d')
        
        if date_tracker is not None:
            key = f"{symbol}_{date_str}"
            if date_tracker.get(key, False):
                return None
        
        for i in range(1, len(today_df)):
            current_candle = today_df.iloc[i]
            current_high = round_to_2_decimals(current_candle['high'])
            current_low = round_to_2_decimals(current_candle['low'])
            
            if current_high > high_ref:
                entry = high_ref
                stop_loss = low_ref
                risk = round_to_2_decimals(entry - stop_loss)
                if risk > 0:
                    quantity = int(self.risk_amount / risk)
                    signal = {
                        'DATE': date_str, 
                        'ENTRY_TIME': today_df.index[i].strftime('%H:%M:%S'),
                        'BREAKOUT_CANDLE': today_df.index[i].strftime('%H:%M'), 
                        'SYMBOL': symbol,
                        'SIGNAL': 'BUY', 
                        'ENTRY': entry, 
                        'QUANTITY': quantity,
                        'STOPLOSS': stop_loss, 
                        'T1': round_to_2_decimals(entry + risk),
                        'T2': round_to_2_decimals(entry + risk * 2), 
                        'T3': round_to_2_decimals(entry + risk * 3),
                        'VOLUME': int(current_candle['volume'])
                    }
                    if date_tracker is not None: 
                        date_tracker[key] = True
                    signals.append(signal)
                    break
            
            elif current_low < low_ref:
                entry = low_ref
                stop_loss = high_ref
                risk = round_to_2_decimals(stop_loss - entry)
                if risk > 0:
                    quantity = int(self.risk_amount / risk)
                    signal = {
                        'DATE': date_str, 
                        'ENTRY_TIME': today_df.index[i].strftime('%H:%M:%S'),
                        'BREAKOUT_CANDLE': today_df.index[i].strftime('%H:%M'), 
                        'SYMBOL': symbol,
                        'SIGNAL': 'SELL', 
                        'ENTRY': entry, 
                        'QUANTITY': quantity,
                        'STOPLOSS': stop_loss, 
                        'T1': round_to_2_decimals(entry - risk),
                        'T2': round_to_2_decimals(entry - risk * 2), 
                        'T3': round_to_2_decimals(entry - risk * 3),
                        'VOLUME': int(current_candle['volume'])
                    }
                    if date_tracker is not None: 
                        date_tracker[key] = True
                    signals.append(signal)
                    break
        return signals

def fetch_data(symbol, interval, n_bars=100):
    try:
        tv = TvDatafeed()
        inv_map = {'5min': Interval.in_5_minute, '15min': Interval.in_15_minute, 'daily': Interval.in_daily}
        return tv.get_hist(symbol=symbol, exchange="NSE", interval=inv_map.get(interval, Interval.in_15_minute), n_bars=n_bars)
    except: 
        return None

def check_for_new_signals(selected_symbols, timeframe, strategy_name, risk_amount, mode, existing_signals, **strategy_params):
    all_new_signals = []
    strategy = CandleBreakoutStrategy(timeframe, risk_amount, mode)
    
    for symbol in selected_symbols:
        data = fetch_data(symbol, timeframe)
        if data is not None:
            signals = strategy.analyze(data, symbol, st.session_state.signal_count_per_stock)
            if signals: 
                all_new_signals.extend(signals)
    return all_new_signals

def run_bot_cycle(selected_symbols, timeframe, strategy, risk_amount, selected_mode, strategy_params, refresh_interval, progress_bar, status_text):
    st.session_state.refresh_counter += 1
    st.session_state.last_check_time = datetime.now()
    for i in range(refresh_interval, 0, -1):
        progress_bar.progress((refresh_interval - i) / refresh_interval)
        status_text.text(f"🔄 Next check in {i} seconds... (Cycle: {st.session_state.refresh_counter})")
        time.sleep(1)
    return check_for_new_signals(selected_symbols, timeframe, strategy, risk_amount, selected_mode, st.session_state.signals, **strategy_params)

def display_signals_table(signals, title="Signals"):
    if signals:
        df = pd.DataFrame(signals)
        st.dataframe(df.style.map(lambda x: 'background-color: #00ff00; color: black' if x == 'BUY' else ('background-color: #ff0000; color: white' if x == 'SELL' else ''), subset=['SIGNAL']), use_container_width=True)

def main():
    st.title("📈 Algorithmic Trading System")
    st.markdown("---")
    
    with st.sidebar:
        selected_mode = st.radio("Select Mode", ["Live Trading", "Backtest (Last 2 Days)"])
        risk_amount = st.number_input("Risk per Trade", 1000, 1000000, 10000)
        timeframe = st.selectbox("Timeframe", ['15min', '5min'])
        strategy = st.selectbox("Strategy", ["Candle Breakout Strategy"])
        update_interval = st.slider("Update Interval", 5, 60, 10)
        
        st.markdown("---")
        st.subheader("📊 NIFTY 200 Screener")
        
        market_type = st.radio(
            "Select Market Type",
            ["🏆 Gainers", "📉 Losers"],
            horizontal=True
        )
        
        if market_type == "🏆 Gainers":
            st.session_state.market_type = "Gainers"
            col1, col2 = st.columns(2)
            with col1:
                min_change = st.number_input("Min Change %", 0.0, 100.0, 2.0, 0.5, key="gainers_min")
                max_change = st.number_input("Max Change %", 0.0, 100.0, 5.0, 0.5, key="gainers_max")
        else:
            st.session_state.market_type = "Losers"
            col1, col2 = st.columns(2)
            with col1:
                min_change = st.number_input("Min Change %", -100.0, 0.0, -5.0, 0.5, key="losers_min")
                max_change = st.number_input("Max Change %", -100.0, 0.0, -2.0, 0.5, key="losers_max")
        
        with col2:
            min_ltp = st.number_input("Min LTP (₹)", 0, 10000, 500, 100)
            max_ltp = st.number_input("Max LTP (₹)", 0, 50000, 3000, 100)
        
        data_source = st.radio("Data Source", ["Live (Yahoo Finance)", "Sample Data (Demo)"], horizontal=True)
        
        if st.button("🚀 GET NIFTY 200 DATA", type="primary", use_container_width=True):
            with st.spinner(f"Fetching {st.session_state.market_type} data..."):
                if data_source == "Live (Yahoo Finance)":
                    nifty_df = fetch_stock_data_with_yfinance(NIFTY_200_STOCKS)
                else:
                    nifty_df = get_sample_gainers_losers()
                
                if not nifty_df.empty:
                    if st.session_state.market_type == "Gainers":
                        filtered = nifty_df[
                            (nifty_df['Change %'] >= min_change) & 
                            (nifty_df['Change %'] <= max_change) & 
                            (nifty_df['LTP'] > min_ltp) & 
                            (nifty_df['LTP'] < max_ltp)
                        ]
                        filtered = filtered.sort_values('Change %', ascending=False)
                    else:
                        filtered = nifty_df[
                            (nifty_df['Change %'] <= min_change) & 
                            (nifty_df['Change %'] >= max_change) & 
                            (nifty_df['LTP'] > min_ltp) & 
                            (nifty_df['LTP'] < max_ltp)
                        ]
                        filtered = filtered.sort_values('Change %', ascending=True)
                    
                    st.session_state.filtered_stocks = filtered['Symbol'].tolist()
                    st.session_state.filtered_df = filtered
                    
                    if len(filtered) > 0:
                        st.success(f"✅ Found {len(st.session_state.filtered_stocks)} {st.session_state.market_type}!")
                    else:
                        st.warning(f"No stocks found. Try adjusting the filters.")
                    st.rerun()
                else:
                    st.error("Failed to fetch data. Try using 'Sample Data' mode.")
        
        st.markdown("---")
        
        if st.session_state.filtered_stocks:
            st.session_state.use_filtered = st.checkbox("📌 Use Filtered Stocks for Trading", value=st.session_state.use_filtered)
            
            if st.session_state.use_filtered:
                st.info(f"✅ Trading with {len(st.session_state.filtered_stocks)} {st.session_state.market_type}")
            else:
                st.info(f"📊 Trading with {len(SYMBOLS)} default stocks")
        
        if not st.session_state.auto_refresh:
            if st.button("🚀 Start Bot", type="primary", use_container_width=True):
                st.session_state.auto_refresh = True
                st.session_state.signals = []
                st.session_state.refresh_counter = 0
                st.rerun()
        else:
            if st.button("⏹ Stop Bot", type="secondary", use_container_width=True):
                st.session_state.auto_refresh = False
                st.rerun()
    
    # Main content
    if st.session_state.filtered_df is not None and not st.session_state.filtered_df.empty:
        if st.session_state.market_type == "Gainers":
            st.subheader(f"🏆 NIFTY 200 {st.session_state.market_type}")
        else:
            st.subheader(f"📉 NIFTY 200 {st.session_state.market_type}")
        
        if data_source == "Sample Data (Demo)":
            st.info("📊 Using sample data for demonstration. Switch to 'Live Data' for real market data.")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric(f"Total {st.session_state.market_type}", len(st.session_state.filtered_df))
        with col2:
            avg_change = st.session_state.filtered_df['Change %'].mean()
            st.metric("Avg Change %", f"{avg_change:+.2f}%")
        with col3:
            if st.session_state.market_type == "Gainers":
                max_change_val = st.session_state.filtered_df['Change %'].max()
            else:
                max_change_val = st.session_state.filtered_df['Change %'].min()
            st.metric(f"Top {st.session_state.market_type}", f"{max_change_val:+.2f}%")
        with col4:
            st.metric("Avg LTP", f"₹{st.session_state.filtered_df['LTP'].mean():,.2f}")
        
        display_df = st.session_state.filtered_df.copy()
        display_df['LTP'] = display_df['LTP'].apply(lambda x: f"₹{x:,.2f}")
        display_df['Change %'] = display_df['Change %'].apply(lambda x: f"{x:+.2f}%")
        display_df['Volume'] = display_df['Volume'].apply(lambda x: f"{int(x):,}")
        
        st.dataframe(display_df, use_container_width=True, height=300)
        st.markdown("---")
    
    # Bot Status
    if st.session_state.auto_refresh and selected_mode == "Live Trading":
        col1, col2, col3 = st.columns(3)
        col1.metric("Bot Status", "🟢 RUNNING")
        col2.metric("Cycle", st.session_state.refresh_counter)
        col3.metric("Time", datetime.now().strftime('%H:%M:%S'))
        
        trading_symbols = st.session_state.filtered_stocks if (st.session_state.use_filtered and st.session_state.filtered_stocks) else SYMBOLS
        market_emoji = "🏆" if st.session_state.market_type == "Gainers" else "📉"
        st.info(f"{market_emoji} Monitoring {len(trading_symbols)} stocks for signals")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        new_sigs = run_bot_cycle(trading_symbols, timeframe, strategy, risk_amount, selected_mode, {}, update_interval, progress_bar, status_text)
        if new_sigs:
            st.session_state.signals.extend(new_sigs)
            send_bulk_telegram_alerts(new_sigs)
            st.balloons()
            st.success(f"🎯 {len(new_sigs)} New Signals Generated!")
        
        st.subheader(f"📋 Trading Signals ({len(st.session_state.signals)})")
        display_signals_table(st.session_state.signals)
        st.rerun()
    
    elif st.session_state.auto_refresh and selected_mode != "Live Trading":
        st.warning("Backtest mode is not implemented yet. Please use Live Trading mode.")
    
    else:
        if st.session_state.filtered_stocks:
            st.info(f"✅ Click **Start Bot** to begin monitoring these {st.session_state.market_type} stocks")
        else:
            st.info("👈 Select Gainers/Losers, set filters, click 'GET NIFTY 200 DATA', then 'Start Bot'")
        
        if st.session_state.signals:
            st.subheader(f"📋 Previous Signals ({len(st.session_state.signals)})")
            display_signals_table(st.session_state.signals)

if __name__ == "__main__":
    main()
