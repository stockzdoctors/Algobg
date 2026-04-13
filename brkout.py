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
warnings.filterwarnings('ignore')

# --- REMOVE ALL STREAMLIT & GITHUB BRANDING ---
st.markdown("""
    <style>
        /* 1. Remove the header entirely */
        [data-testid="stHeader"] {
            display: none !important;
        }

        /* 2. Remove the footer and any branding links */
        [data-testid="stFooter"], footer {
            display: none !important;
        }

        /* 3. Remove the GitHub/Deploy toolbar in the top right */
        [data-testid="stToolbar"] {
            display: none !important;
        }

        /* 4. Remove the 'Made with Streamlit' and GitHub badges specifically */
        .viewerBadge_container__1QSob, 
        .stAppDeployButton,
        div[class*="viewerBadge"] {
            display: none !important;
        }

        /* 5. Force the main content to fill the empty space */
        .main .block-container {
            padding-top: 2rem !important;
            padding-bottom: 0rem !important;
        }

        /* 6. Remove the 'Running...' man icon to keep it clean */
        [data-testid="stStatusWidget"] {
            display: none !important;
        }
    </style>
    """, unsafe_allow_html=True)
# Apply nest_asyncio to allow multiple asyncio runs
nest_asyncio.apply()

# Page configuration
st.set_page_config(
    page_title="Algo Trading System",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Telegram Configuration
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

# Initialize Telegram Bot
telegram_bot = Bot(token=TELEGRAM_TOKEN)

# Create a permanent event loop for Telegram
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
if 'dynamic_symbols' not in st.session_state:
    st.session_state.dynamic_symbols = []

# Simple disclaimer for Telegram
DISCLAIMER = """
━━━━━━━━━━━━━━━━━━
📢 **EDUCATIONAL DISCLAIMER:**
This is for STUDY & ANALYSIS only.
━━━━━━━━━━━━━━━━━━"""

def get_nifty200_filtered_gainers():
    """Step 1: Fresh Live Market Scan for Nifty 200 Gainers with persistent session to avoid connection error"""
    try:
        # NSE requires a specific header and cookies to allow connection
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Referer": "https://www.nseindia.com/market-data/live-equity-market"
        }
        session = requests.Session()
        # First visit the home page to get the necessary cookies
        session.get("https://www.nseindia.com", headers=headers, timeout=10)
        
        # Now fetch the Nifty 200 Gainers
        url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20200"
        response = session.get(url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            stocks_data = data.get("data", [])
            final_list = []
            for stock in stocks_data:
                symbol = stock.get("symbol")
                try:
                    ltp = float(str(stock.get("lastPrice", 0)).replace(',', ''))
                    pct_change = float(str(stock.get("pChange", 0)).replace(',', ''))
                    
                    # FILTER: LTP between 500-3000 AND %Change between 4% and 6%
                    if 500 <= ltp <= 3000 and 4.0 <= pct_change <= 6.0:
                        final_list.append(symbol)
                except:
                    continue
            return final_list
        else:
            return []
    except Exception as e:
        st.error(f"NSE Connection Error: {str(e)}")
        return []

def send_telegram_message_sync(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        response = requests.post(url, data=payload)
        return response.status_code == 200
    except: return False

def send_telegram_alert(signal, alert_type="ENTRY"):
    try:
        emoji = "🟢" if signal['SIGNAL'] == 'BUY' else "🔴"
        if alert_type == "ENTRY":
            title = "NEW TRADE SIGNAL"
            message = f"""
{emoji} *{title}* {emoji}

📊 *Symbol:* {signal['SYMBOL']}
🎯 *Signal:* {signal['SIGNAL']}
💰 *Entry:* ₹{signal['ENTRY']}
🛑 *Stop Loss:* ₹{signal['STOPLOSS']}
📈 *Target 1:* ₹{signal['T1']}
📦 *Quantity:* {signal['QUANTITY']}
⏰ *Time:* {signal['ENTRY_TIME']}
⚡ *Breakout at:* {signal['BREAKOUT_CANDLE']}

{DISCLAIMER}
            """
        return send_telegram_message_sync(message)
    except: return False

def send_bulk_telegram_alerts(signals):
    for signal in signals:
        send_telegram_alert(signal, "ENTRY")
        time.sleep(1)

def round_to_2_decimals(value):
    return round(float(value), 2)

class CandleBreakoutStrategy:
    def __init__(self, timeframe='15min', risk_amount=10000, mode="Live Trading"):
        self.timeframe, self.risk_amount, self.mode = timeframe, risk_amount, mode
        self.name = "Candle Breakout Strategy"

    def analyze(self, df, symbol, date_tracker=None):
        if df is None or len(df) < 2: return None
        signals = []
        df.index = pd.to_datetime(df.index)
        today_date = datetime.now().date()
        today_df = df[df.index.date == today_date]
        if len(today_df) < 1: return None

        reference_candle = today_df.iloc[0]
        h915, l915 = round_to_2_decimals(reference_candle['high']), round_to_2_decimals(reference_candle['low'])
        date_str = today_date.strftime('%Y-%m-%d')

        if date_tracker is not None:
            key = f"{symbol}_{date_str}"
            if date_tracker.get(key, False): return None

        for i in range(1, len(today_df)):
            curr = today_df.iloc[i]
            if curr['high'] > h915:
                entry = h915
                risk = round_to_2_decimals(h915 - l915)
                if risk > 0:
                    qty = int(self.risk_amount / risk)
                    sig = {'DATE': date_str, 'ENTRY_TIME': today_df.index[i].strftime('%H:%M:%S'), 'BREAKOUT_CANDLE': today_df.index[i].strftime('%H:%M'), 'SYMBOL': symbol, 'SIGNAL': 'BUY', 'ENTRY': entry, 'QUANTITY': qty, 'STOPLOSS': l915, 'T1': round_to_2_decimals(entry + risk), 'T2': round_to_2_decimals(entry + risk*2), 'T3': round_to_2_decimals(entry + risk*3), 'VOLUME': int(curr['volume'])}
                    if date_tracker is not None: date_tracker[key] = True
                    signals.append(sig)
                    break
            elif curr['low'] < l915:
                entry = l915
                risk = round_to_2_decimals(h915 - l915)
                if risk > 0:
                    qty = int(self.risk_amount / risk)
                    sig = {'DATE': date_str, 'ENTRY_TIME': today_df.index[i].strftime('%H:%M:%S'), 'BREAKOUT_CANDLE': today_df.index[i].strftime('%H:%M'), 'SYMBOL': symbol, 'SIGNAL': 'SELL', 'ENTRY': entry, 'QUANTITY': qty, 'STOPLOSS': h915, 'T1': round_to_2_decimals(entry - risk), 'T2': round_to_2_decimals(entry - risk*2), 'T3': round_to_2_decimals(entry - risk*3), 'VOLUME': int(curr['volume'])}
                    if date_tracker is not None: date_tracker[key] = True
                    signals.append(sig)
                    break
        return signals

def fetch_data(symbol, interval, n_bars=100):
    try:
        tv = TvDatafeed()
        inv_map = {'5min': Interval.in_5_minute, '15min': Interval.in_15_minute, 'daily': Interval.in_daily}
        return tv.get_hist(symbol=symbol, exchange="NSE", interval=inv_map.get(interval, Interval.in_15_minute), n_bars=n_bars)
    except: return None

def check_for_new_signals(selected_symbols, timeframe, strategy_name, risk_amount, mode):
    all_new_signals = []
    strat = CandleBreakoutStrategy(timeframe, risk_amount, mode)
    for symbol in selected_symbols:
        data = fetch_data(symbol, timeframe)
        if data is not None:
            sigs = strat.analyze(data, symbol, st.session_state.signal_count_per_stock)
            if sigs: all_new_signals.extend(sigs)
    return all_new_signals

def run_bot_cycle(symbols, timeframe, strategy, risk, mode, interval, progress_bar, status_text):
    st.session_state.refresh_counter += 1
    st.session_state.last_check_time = datetime.now()
    for i in range(interval, 0, -1):
        progress_bar.progress((interval - i) / interval)
        status_text.text(f"🔄 Next check in {i} seconds... (Cycle: {st.session_state.refresh_counter})")
        time.sleep(1)
    return check_for_new_signals(symbols, timeframe, risk, mode)

def display_signals_table(signals):
    if signals:
        df = pd.DataFrame(signals)
        st.dataframe(df.style.map(lambda x: 'background-color: #00ff00; color: black' if x == 'BUY' else ('background-color: #ff0000; color: white' if x == 'SELL' else ''), subset=['SIGNAL']), use_container_width=True)

def main():
    st.title("📈 Algorithmic Trading System")
    st.markdown("---")
    with st.sidebar:
        st.header("⚙️ Configuration")
        selected_mode = st.radio("Select Mode", ["Live Trading", "Backtest (Last 2 Days)"])
        risk_amount = st.number_input("Risk per Trade", 1000, 1000000, 10000)
        timeframe = st.selectbox("Timeframe", ['15min', '5min'])
        update_interval = st.slider("Update Interval", 5, 60, 60)

        if st.button("🔗 Step 1: Connect NSE Website"):
            with st.spinner("Fetching Nifty 200 Gainers..."):
                st.session_state.dynamic_symbols = get_nifty200_filtered_gainers()
                if st.session_state.dynamic_symbols:
                    st.success(f"✅ Found {len(st.session_state.dynamic_symbols)} Stocks (Change 4-6%, Price 500-3000)")
                else:
                    st.error("No stocks matched filtering criteria at this moment.")

        if st.button("🚀 Step 2: Get Signal (Start Bot)"):
            if not st.session_state.dynamic_symbols: st.error("Click Step 1 first!")
            else:
                st.session_state.auto_refresh = True
                st.rerun()

        if st.button("⏹ Stop Bot"):
            st.session_state.auto_refresh = False
            st.rerun()

    if st.session_state.auto_refresh:
        col1, col2, col3 = st.columns(3)
        col1.metric("Cycle", st.session_state.refresh_counter)
        col2.metric("Time", datetime.now().strftime('%H:%M:%S'))
        col3.metric("Stocks", len(st.session_state.dynamic_symbols))

        progress_bar = st.progress(0)
        status_text = st.empty()

        new_sigs = run_bot_cycle(st.session_state.dynamic_symbols, timeframe, "Candle Breakout Strategy", risk_amount, selected_mode, update_interval, progress_bar, status_text)
        if new_sigs:
            st.session_state.signals.extend(new_sigs)
            send_bulk_telegram_alerts(new_sigs)
            st.balloons()

        display_signals_table(st.session_state.signals)
        st.rerun()

if __name__ == "__main__":
    main()
