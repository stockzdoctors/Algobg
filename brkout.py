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
        [data-testid="stHeader"] { display: none !important; }
        [data-testid="stFooter"], footer { display: none !important; }
        [data-testid="stToolbar"] { display: none !important; }
        .viewerBadge_container__1QSob, .stAppDeployButton, div[class*="viewerBadge"] { display: none !important; }
        .main .block-container { padding-top: 2rem !important; padding-bottom: 0rem !important; }
        [data-testid="stStatusWidget"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

# Apply nest_asyncio
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
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)

# Initialize session state
if 'trading_active' not in st.session_state: st.session_state.trading_active = False
if 'signals' not in st.session_state: st.session_state.signals = []
if 'active_trades' not in st.session_state: st.session_state.active_trades = []
if 'completed_trades' not in st.session_state: st.session_state.completed_trades = []
if 'last_update' not in st.session_state: st.session_state.last_update = None
if 'mode' not in st.session_state: st.session_state.mode = "Live Trading"
if 'signal_count_per_stock' not in st.session_state: st.session_state.signal_count_per_stock = {}
if 'last_signal_time' not in st.session_state: st.session_state.last_signal_time = {}
if 'auto_refresh' not in st.session_state: st.session_state.auto_refresh = False
if 'refresh_counter' not in st.session_state: st.session_state.refresh_counter = 0
if 'last_check_time' not in st.session_state: st.session_state.last_check_time = None
if 'bot_thread' not in st.session_state: st.session_state.bot_thread = None
if 'stop_bot' not in st.session_state: st.session_state.stop_bot = False

# Stock symbols
SYMBOLS = ["BANKNIFTY", "NIFTY", "UPL", "INFY", "ULTRACEMCO", "RELIANCE", 
           "ASIANPAINT", "ABB", "ACC", "LT", "HDFCBANK"]

DISCLAIMER = """━━━━━━━━━━━━━━━━━━\n📢 **EDUCATIONAL DISCLAIMER:**\nThis is for STUDY & ANALYSIS only.\n━━━━━━━━━━━━━━━━━━"""

def send_telegram_message_sync(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        requests.post(url, data=payload)
        return True
    except Exception as e:
        st.error(f"Failed to send Telegram alert: {str(e)}")
        return False

def send_telegram_alert(signal, alert_type="ENTRY"):
    try:
        emoji = "🟢" if signal['SIGNAL'] == 'BUY' else "🔴"
        if alert_type == "ENTRY":
            title = "NEW TRADE SIGNAL"
            message = f"{emoji} *{title}* {emoji}\n\n📊 *Symbol:* {signal['SYMBOL']}\n🎯 *Signal:* {signal['SIGNAL']}\n💰 *Entry:* ₹{signal['ENTRY']}\n🛑 *Stop Loss:* ₹{signal['STOPLOSS']}\n📈 *Target 1:* ₹{signal['T1']}\n⏰ *Time:* {signal['ENTRY_TIME']}\n📅 *Date:* {signal['DATE']}\n{DISCLAIMER}"
        elif alert_type == "STOPLOSS":
            message = f"🛑 *STOP LOSS HIT: {signal['SYMBOL']}* 🛑\n💰 Exit: ₹{signal['STOPLOSS']}\n{DISCLAIMER}"
        else:
            message = f"🎯 *TARGET HIT: {signal['SYMBOL']}* 🎯\n✅ Price: ₹{signal['T1']}\n{DISCLAIMER}"
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
        
    def analyze(self, df, symbol, date_tracker=None):
        if df is None or len(df) < 2: return None
        df.index = pd.to_datetime(df.index)
        
        # --- FIX: Only look for signals for TODAY (April 13) ---
        target_date = datetime.now().date()
        today_df = df[df.index.date == target_date]
        if len(today_df) < 1: return None

        # Find 9:15 candle for today
        reference_candle = None
        for i in range(len(today_df)):
            if today_df.index[i].strftime('%H:%M') == '09:15':
                reference_candle = today_df.iloc[i]
                ref_idx = i
                break
        
        if reference_candle is None: return None
        
        high_915 = round_to_2_decimals(reference_candle['high'])
        low_915 = round_to_2_decimals(reference_candle['low'])
        date_str = target_date.strftime('%Y-%m-%d')
        
        key = f"{symbol}_{date_str}"
        if date_tracker is not None and date_tracker.get(key, False): return None

        # Check latest price (Last candle in full DF)
        current_candle = df.iloc[-1]
        current_price = round_to_2_decimals(current_candle['close'])
        
        signals = []
        if current_price > high_915:
            risk = high_915 - low_915
            qty = int(self.risk_amount / risk) if risk > 0 else 1
            signal = {'DATE': date_str, 'ENTRY_TIME': datetime.now().strftime('%H:%M:%S'), 'BREAKOUT_CANDLE': 'LIVE', 'SYMBOL': symbol, 'SIGNAL': 'BUY', 'ENTRY': current_price, 'QUANTITY': qty, 'STOPLOSS': low_915, 'T1': round_to_2_decimals(current_price + risk), 'T2': 0, 'T3': 0}
            if date_tracker is not None: date_tracker[key] = True
            signals.append(signal)
        elif current_price < low_915:
            risk = high_915 - low_915
            qty = int(self.risk_amount / risk) if risk > 0 else 1
            signal = {'DATE': date_str, 'ENTRY_TIME': datetime.now().strftime('%H:%M:%S'), 'BREAKOUT_CANDLE': 'LIVE', 'SYMBOL': symbol, 'SIGNAL': 'SELL', 'ENTRY': current_price, 'QUANTITY': qty, 'STOPLOSS': high_915, 'T1': round_to_2_decimals(current_price - risk), 'T2': 0, 'T3': 0}
            if date_tracker is not None: date_tracker[key] = True
            signals.append(signal)
        return signals

# --- ALL OTHER CLASSES & FUNCTIONS ---
class MovingAverageCrossStrategy:
    def __init__(self, **kwargs): pass
    def analyze(self, *args): return None

class RSIBreakoutStrategy:
    def __init__(self, **kwargs): pass
    def analyze(self, *args): return None

def fetch_data(symbol, interval, n_bars=100):
    try:
        tv = TvDatafeed()
        inv_map = {'5min': Interval.in_5_minute, '15min': Interval.in_15_minute, 'daily': Interval.in_daily}
        return tv.get_hist(symbol=symbol, exchange="NSE", interval=inv_map.get(interval, Interval.in_15_minute), n_bars=n_bars)
    except: return None

def get_last_n_market_days(n=2):
    return [datetime.now() - timedelta(days=i) for i in range(n)]

def check_for_new_signals(symbols, timeframe, strategy_name, risk_amount, mode, existing, **params):
    all_sigs = []
    strat = CandleBreakoutStrategy(timeframe, risk_amount, mode)
    for s in symbols:
        data = fetch_data(s, timeframe)
        res = strat.analyze(data, s, st.session_state.signal_count_per_stock)
        if res: all_sigs.extend(res)
    return all_sigs

def run_bot_cycle(selected_symbols, timeframe, strategy, risk_amount, selected_mode, strategy_params, refresh_interval, progress_bar, status_text):
    st.session_state.refresh_counter += 1
    st.session_state.last_check_time = datetime.now()
    for i in range(refresh_interval, 0, -1):
        progress_bar.progress((refresh_interval - i) / refresh_interval)
        status_text.text(f"🔄 Next check in {i} seconds...")
        time.sleep(1)
    return check_for_new_signals(selected_symbols, timeframe, strategy, risk_amount, selected_mode, st.session_state.signals)

def display_signals_table(signals, title="Signals"):
    if signals:
        df = pd.DataFrame(signals)
        st.dataframe(df.style.map(lambda x: 'background-color: green' if x=='BUY' else 'background-color: red', subset=['SIGNAL']), use_container_width=True)

def main():
    st.title("📈 Algorithmic Trading System")
    with st.sidebar:
        selected_mode = st.radio("Mode", ["Live Trading", "Backtest (Last 2 Days)"])
        risk_amount = st.number_input("Risk", 1000, 100000, 10000)
        timeframe = st.selectbox("Timeframe", ['15min', '5min'])
        strategy = "Candle Breakout Strategy"
        update_interval = st.slider("Interval", 5, 60, 10)
        if st.button("🚀 Start Bot" if not st.session_state.auto_refresh else "⏹ Stop Bot"):
            st.session_state.auto_refresh = not st.session_state.auto_refresh
            st.rerun()

    if st.session_state.auto_refresh and selected_mode == "Live Trading":
        progress_bar = st.progress(0)
        status_text = st.empty()
        new_sigs = run_bot_cycle(SYMBOLS, timeframe, strategy, risk_amount, selected_mode, {}, update_interval, progress_bar, status_text)
        if new_sigs:
            st.session_state.signals.extend(new_sigs)
            send_bulk_telegram_alerts(new_sigs)
        display_signals_table(st.session_state.signals)
        st.rerun()

if __name__ == "__main__":
    main()
