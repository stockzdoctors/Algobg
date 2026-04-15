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
if 'nifty_data_fetched' not in st.session_state:
    st.session_state.nifty_data_fetched = False

# Stock symbols
SYMBOLS = ["BANKNIFTY", "NIFTY", "UPL", "INFY", "ULTRACEMCO", "RELIANCE", 
           "ASIANPAINT", "ABB", "ACC", "LT", "HDFCBANK"]

DISCLAIMER = """
━━━━━━━━━━━━━━━━━━
📢 **EDUCATIONAL DISCLAIMER:**
This is for STUDY & ANALYSIS only.
We are NOT SEBI registered advisors.
No trading recommendations provided.
Always consult registered experts.
━━━━━━━━━━━━━━━━━━"""

# --- WORKING NSE NIFTY 200 FETCH FUNCTION (FROM YOUR WORKING CODE) ---
@st.cache_data(ttl=300)
def fetch_nifty200_stocks():
    """Fetch NIFTY 200 stocks from NSE India - WORKING VERSION"""
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
        
        # First, visit the main page to get cookies
        session.get("https://www.nseindia.com", timeout=10)
        time.sleep(2)  # Increased delay for cookie setting
        
        # Now fetch the NIFTY 200 data
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
    
    # Sidebar
    with st.sidebar:
        selected_mode = st.radio("Select Mode", ["Live Trading", "Backtest (Last 2 Days)"])
        risk_amount = st.number_input("Risk per Trade", 1000, 1000000, 10000)
        timeframe = st.selectbox("Timeframe", ['15min', '5min'])
        strategy = st.selectbox("Strategy", ["Candle Breakout Strategy"])
        update_interval = st.slider("Update Interval", 5, 60, 10)
        
        st.markdown("---")
        st.subheader("📊 NIFTY 200 Filter")
        
        min_change = st.number_input("Min Change %", 0.0, 100.0, 2.0, 0.5)
        max_change = st.number_input("Max Change %", 0.0, 100.0, 5.0, 0.5)
        min_ltp = st.number_input("Min LTP (₹)", 0, 10000, 500, 100)
        max_ltp = st.number_input("Max LTP (₹)", 0, 50000, 3000, 100)
        
        if st.button("🚀 GET NIFTY 200 DATA", type="primary", use_container_width=True):
            with st.spinner("Fetching NIFTY 200 stocks from NSE..."):
                nifty_df = fetch_nifty200_stocks()
                if not nifty_df.empty:
                    filtered = nifty_df[
                        (nifty_df['Change %'] >= min_change) & 
                        (nifty_df['Change %'] <= max_change) & 
                        (nifty_df['LTP'] > min_ltp) & 
                        (nifty_df['LTP'] < max_ltp)
                    ]
                    st.session_state.filtered_stocks = filtered['Symbol'].tolist()
                    st.session_state.filtered_df = filtered
                    st.session_state.nifty_data_fetched = True
                    st.success(f"✅ Found {len(st.session_state.filtered_stocks)} stocks!")
                    st.rerun()
                else:
                    st.error("Failed to fetch data. Please try again.")
        
        st.markdown("---")
        
        # Show fetched stocks count
        if st.session_state.filtered_stocks:
            st.success(f"📊 {len(st.session_state.filtered_stocks)} stocks available")
            st.session_state.use_filtered = st.checkbox("📌 Use Filtered Stocks for Trading", value=st.session_state.use_filtered)
            
            if st.session_state.use_filtered:
                st.info(f"✅ Trading with {len(st.session_state.filtered_stocks)} filtered stocks")
            else:
                st.info(f"📊 Trading with {len(SYMBOLS)} default stocks")
        else:
            st.warning("⚠️ No stocks fetched yet. Click 'GET NIFTY 200 DATA' first.")
        
        st.markdown("---")
        
        if not st.session_state.auto_refresh:
            if st.button("🚀 Start Bot", type="primary", use_container_width=True):
                if st.session_state.filtered_stocks or not st.session_state.use_filtered:
                    st.session_state.auto_refresh = True
                    st.session_state.signals = []
                    st.session_state.refresh_counter = 0
                    st.rerun()
                else:
                    st.error("Please fetch NIFTY 200 data first!")
        else:
            if st.button("⏹ Stop Bot", type="secondary", use_container_width=True):
                st.session_state.auto_refresh = False
                st.rerun()
    
    # --- MAIN PAGE CONTENT ---
    
    # Display Filtered Stocks on Main Page
    if st.session_state.filtered_df is not None and not st.session_state.filtered_df.empty:
        st.subheader("📊 NIFTY 200 Filtered Stocks")
        st.markdown(f"**Criteria:** Change % {min_change}% to {max_change}% | LTP ₹{min_ltp} to ₹{max_ltp}")
        
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Stocks Found", len(st.session_state.filtered_df))
        with col2:
            st.metric("Avg Change %", f"{st.session_state.filtered_df['Change %'].mean():.2f}%")
        with col3:
            st.metric("Max Change %", f"{st.session_state.filtered_df['Change %'].max():.2f}%")
        with col4:
            st.metric("Avg LTP", f"₹{st.session_state.filtered_df['LTP'].mean():,.2f}")
        
        display_df = st.session_state.filtered_df.copy()
        display_df['LTP'] = display_df['LTP'].apply(lambda x: f"₹{x:,.2f}")
        display_df['Change %'] = display_df['Change %'].apply(lambda x: f"{x:+.2f}%")
        display_df['Volume'] = display_df['Volume'].apply(lambda x: f"{int(x):,}")
        
        st.dataframe(display_df, use_container_width=True, height=300)
        st.markdown("---")
    
    # Bot Status and Signals
    if st.session_state.auto_refresh and selected_mode == "Live Trading":
        col1, col2, col3 = st.columns(3)
        col1.metric("Bot Status", "🟢 RUNNING")
        col2.metric("Cycle", st.session_state.refresh_counter)
        col3.metric("Time", datetime.now().strftime('%H:%M:%S'))
        
        # Determine which stocks to trade
        if st.session_state.use_filtered and st.session_state.filtered_stocks:
            trading_symbols = st.session_state.filtered_stocks
            st.success(f"🎯 Trading with {len(trading_symbols)} FILTERED stocks from NIFTY 200")
        else:
            trading_symbols = SYMBOLS
            st.info(f"🎯 Trading with {len(trading_symbols)} DEFAULT stocks")
        
        # Show first few stocks
        st.caption(f"Monitoring: {', '.join(trading_symbols[:10])}{'...' if len(trading_symbols) > 10 else ''}")
        
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
        time.sleep(1)
        st.rerun()
    
    elif st.session_state.auto_refresh and selected_mode != "Live Trading":
        st.warning("Backtest mode is not implemented yet. Please use Live Trading mode.")
    
    else:
        if st.session_state.filtered_stocks:
            st.info("✅ Click **Start Bot** to begin monitoring these stocks for trading signals")
            st.info(f"📊 Ready to trade with {len(st.session_state.filtered_stocks)} filtered stocks")
        else:
            st.info("👈 **Get Started:** Click 'GET NIFTY 200 DATA' in sidebar to fetch stocks, then click 'Start Bot'")
        
        if st.session_state.signals:
            st.subheader(f"📋 Previous Signals ({len(st.session_state.signals)})")
            display_signals_table(st.session_state.signals)
        
        with st.expander("ℹ️ How to Use", expanded=False):
            st.markdown("""
            **Step 1:** Set filter criteria in sidebar (Change % and LTP)
            
            **Step 2:** Click **GET NIFTY 200 DATA** to fetch filtered stocks
            
            **Step 3:** Check **Use Filtered Stocks for Trading** (optional)
            
            **Step 4:** Click **Start Bot** to begin monitoring
            
            **Strategy:** Candle Breakout - First candle of the day sets reference, any breakout generates signal
            
            **Note:** NIFTY 200 data fetches once and caches for 5 minutes
            """)

if __name__ == "__main__":
    main()
