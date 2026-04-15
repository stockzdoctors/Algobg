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
if 'page' not in st.session_state:
    st.session_state.page = "Screener"  # Screener or Trading

DISCLAIMER = """
━━━━━━━━━━━━━━━━━━
📢 **EDUCATIONAL DISCLAIMER:**
This is for STUDY & ANALYSIS only.
We are NOT SEBI registered advisors.
No trading recommendations provided.
Always consult registered experts.
━━━━━━━━━━━━━━━━━━"""

# --- NSE NIFTY 200 FETCH FUNCTION ---
@st.cache_data(ttl=300)
def fetch_nifty200_stocks():
    """Fetch NIFTY 200 stocks from NSE India"""
    try:
        nse_url = "https://www.nseindia.com/api/equity-stockIndices?index=NIFTY%20200"
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.nseindia.com/',
            'X-Requested-With': 'XMLHttpRequest'
        }
        
        session = requests.Session()
        session.headers.update(headers)
        session.get("https://www.nseindia.com", timeout=10)
        time.sleep(2)
        
        response = session.get(nse_url, timeout=15)
        
        if response.status_code == 200:
            data = response.json()
            stocks_data = []
            
            for item in data.get('data', []):
                try:
                    ltp = float(item.get('lastPrice', 0))
                    change_percent = float(item.get('pChange', 0))
                    
                    stocks_data.append({
                        'Symbol': item.get('symbol', ''),
                        'Company Name': item.get('symbol', ''),
                        'LTP': ltp,
                        'Change %': change_percent,
                        'Volume': item.get('totalTradedVolume', 0)
                    })
                except (ValueError, TypeError, KeyError):
                    continue
            
            if stocks_data:
                return pd.DataFrame(stocks_data)
        
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Error fetching NSE data: {str(e)}")
        return pd.DataFrame()

def filter_stocks(df, min_change=2, max_change=5, min_ltp=500, max_ltp=3000):
    if df.empty:
        return df
    
    filtered = df[
        (df['Change %'] >= min_change) & 
        (df['Change %'] <= max_change) & 
        (df['LTP'] > min_ltp) & 
        (df['LTP'] < max_ltp)
    ]
    return filtered.sort_values('Change %', ascending=False)

# --- Trading Bot Functions ---
def send_telegram_message_sync(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
        response = requests.post(url, data=payload, timeout=10)
        return response.status_code == 200
    except:
        return False

def send_telegram_alert(signal, alert_type="ENTRY"):
    try:
        emoji = "🟢" if signal['SIGNAL'] == 'BUY' else "🔴"
        
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

Risk-Reward: 1:1, 1:2, 1:3
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
        high_915 = round_to_2_decimals(reference_candle['high'])
        low_915 = round_to_2_decimals(reference_candle['low'])
        date_str = today_date.strftime('%Y-%m-%d')
        
        if date_tracker is not None:
            key = f"{symbol}_{date_str}"
            if date_tracker.get(key, False):
                return None
        
        for i in range(1, len(today_df)):
            current_candle = today_df.iloc[i]
            current_high = round_to_2_decimals(current_candle['high'])
            current_low = round_to_2_decimals(current_candle['low'])
            
            if current_high > high_915:
                entry = high_915
                stop_loss = low_915
                risk = round_to_2_decimals(entry - stop_loss)
                if risk > 0:
                    quantity = int(self.risk_amount / risk)
                    signal = {
                        'DATE': date_str, 'ENTRY_TIME': today_df.index[i].strftime('%H:%M:%S'),
                        'BREAKOUT_CANDLE': today_df.index[i].strftime('%H:%M'), 'SYMBOL': symbol,
                        'SIGNAL': 'BUY', 'ENTRY': entry, 'QUANTITY': quantity,
                        'STOPLOSS': stop_loss, 'T1': round_to_2_decimals(entry + risk),
                        'T2': round_to_2_decimals(entry + risk * 2), 'T3': round_to_2_decimals(entry + risk * 3),
                        'VOLUME': int(current_candle['volume']), 'T1_HIT': False, 'T2_HIT': False, 'T3_HIT': False
                    }
                    if date_tracker is not None: date_tracker[key] = True
                    signals.append(signal)
                    break
            
            elif current_low < low_915:
                entry = low_915
                stop_loss = high_915
                risk = round_to_2_decimals(stop_loss - entry)
                if risk > 0:
                    quantity = int(self.risk_amount / risk)
                    signal = {
                        'DATE': date_str, 'ENTRY_TIME': today_df.index[i].strftime('%H:%M:%S'),
                        'BREAKOUT_CANDLE': today_df.index[i].strftime('%H:%M'), 'SYMBOL': symbol,
                        'SIGNAL': 'SELL', 'ENTRY': entry, 'QUANTITY': quantity,
                        'STOPLOSS': stop_loss, 'T1': round_to_2_decimals(entry - risk),
                        'T2': round_to_2_decimals(entry - risk * 2), 'T3': round_to_2_decimals(entry - risk * 3),
                        'VOLUME': int(current_candle['volume']), 'T1_HIT': False, 'T2_HIT': False, 'T3_HIT': False
                    }
                    if date_tracker is not None: date_tracker[key] = True
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
        time.sleep(0.3)
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

# --- Screener Page ---
def screener_page():
    st.title("📊 NIFTY 200 Stock Screener")
    st.markdown("**Step 1: Filter and select stocks for trading**")
    st.markdown("---")
    
    # Filters
    col1, col2 = st.columns(2)
    with col1:
        min_change = st.number_input("Min Change %", 0.0, 100.0, 2.0, 0.5)
        min_ltp = st.number_input("Min LTP (₹)", 0, 10000, 500, 100)
    with col2:
        max_change = st.number_input("Max Change %", 0.0, 100.0, 5.0, 0.5)
        max_ltp = st.number_input("Max LTP (₹)", 0, 50000, 3000, 100)
    
    if st.button("🚀 FETCH NIFTY 200 DATA", type="primary", use_container_width=True):
        with st.spinner("Fetching NIFTY 200 stocks from NSE..."):
            nifty_df = fetch_nifty200_stocks()
            if not nifty_df.empty:
                filtered = filter_stocks(nifty_df, min_change, max_change, min_ltp, max_ltp)
                st.session_state.filtered_stocks = filtered['Symbol'].tolist()
                st.session_state.filtered_df = filtered
                st.success(f"✅ Found {len(st.session_state.filtered_stocks)} stocks!")
            else:
                st.error("Failed to fetch data")
    
    # Display filtered stocks
    if st.session_state.filtered_df is not None and not st.session_state.filtered_df.empty:
        st.markdown("---")
        st.subheader(f"📋 Filtered Stocks ({len(st.session_state.filtered_df)})")
        
        display_df = st.session_state.filtered_df.copy()
        display_df['LTP'] = display_df['LTP'].apply(lambda x: f"₹{x:,.2f}")
        display_df['Change %'] = display_df['Change %'].apply(lambda x: f"{x:+.2f}%")
        st.dataframe(display_df, use_container_width=True, height=300)
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("✅ USE THESE STOCKS FOR TRADING", type="primary", use_container_width=True):
                st.session_state.use_filtered = True
                st.session_state.page = "Trading"
                st.rerun()
        with col2:
            if st.button("🔄 REFRESH DATA", use_container_width=True):
                st.rerun()

# --- Trading Page ---
def trading_page():
    st.title("📈 Algorithmic Trading Bot")
    st.markdown("**Step 2: Run trading bot with selected stocks**")
    st.markdown("---")
    
    # Show current stocks
    if st.session_state.filtered_stocks:
        st.success(f"✅ Trading with {len(st.session_state.filtered_stocks)} stocks from NIFTY 200")
        
        # Show stock list
        with st.expander("📋 View Selected Stocks"):
            st.write(st.session_state.filtered_stocks)
        
        # Trading controls
        col1, col2, col3 = st.columns(3)
        with col1:
            risk_amount = st.number_input("Risk per Trade", 1000, 1000000, 10000)
        with col2:
            timeframe = st.selectbox("Timeframe", ['15min', '5min'])
        with col3:
            update_interval = st.slider("Update Interval (seconds)", 5, 60, 10)
        
        st.markdown("---")
        
        # Bot controls
        if not st.session_state.auto_refresh:
            if st.button("🚀 START BOT", type="primary", use_container_width=True):
                st.session_state.auto_refresh = True
                st.session_state.signals = []
                st.session_state.refresh_counter = 0
                st.rerun()
        else:
            if st.button("⏹ STOP BOT", type="secondary", use_container_width=True):
                st.session_state.auto_refresh = False
                st.rerun()
            
            # Bot running status
            col1, col2, col3 = st.columns(3)
            col1.metric("Bot Status", "🟢 RUNNING")
            col2.metric("Cycle", st.session_state.refresh_counter)
            col3.metric("Time", datetime.now().strftime('%H:%M:%S'))
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            new_sigs = run_bot_cycle(
                st.session_state.filtered_stocks, 
                timeframe, 
                "Candle Breakout Strategy", 
                risk_amount, 
                "Live Trading", 
                {}, 
                update_interval, 
                progress_bar, 
                status_text
            )
            
            if new_sigs:
                st.session_state.signals.extend(new_sigs)
                send_bulk_telegram_alerts(new_sigs)
                st.balloons()
                st.success(f"🎯 {len(new_sigs)} New Signals Generated!")
            
            st.subheader(f"📋 Trading Signals ({len(st.session_state.signals)})")
            display_signals_table(st.session_state.signals)
            time.sleep(1)
            st.rerun()
        
        # Show previous signals
        if st.session_state.signals and not st.session_state.auto_refresh:
            st.subheader(f"📋 Previous Signals ({len(st.session_state.signals)})")
            display_signals_table(st.session_state.signals)
    
    else:
        st.warning("No stocks loaded! Please go to Screener page first.")
        if st.button("📊 GO TO SCREENER PAGE", use_container_width=True):
            st.session_state.page = "Screener"
            st.rerun()

# --- Main App with Page Navigation ---
def main():
    # Custom navigation in sidebar
    st.sidebar.title("Navigation")
    
    if st.sidebar.button("📊 Stock Screener", use_container_width=True):
        st.session_state.page = "Screener"
        st.rerun()
    
    if st.sidebar.button("📈 Trading Bot", use_container_width=True):
        st.session_state.page = "Trading"
        st.rerun()
    
    st.sidebar.markdown("---")
    
    # Show current status
    if st.session_state.filtered_stocks:
        st.sidebar.success(f"✅ {len(st.session_state.filtered_stocks)} stocks loaded")
    else:
        st.sidebar.warning("⚠️ No stocks loaded")
    
    st.sidebar.markdown("---")
    
    # Page routing
    if st.session_state.page == "Screener":
        screener_page()
    else:
        trading_page()

if __name__ == "__main__":
    main()
