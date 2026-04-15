import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime
from tvDatafeed import TvDatafeed, Interval
import time
import requests
import asyncio
import nest_asyncio
from telegram import Bot
import warnings
warnings.filterwarnings('ignore')

nest_asyncio.apply()

st.set_page_config(
    page_title="Trading Bot",
    page_icon="🤖",
    layout="wide"
)

# Remove branding
st.markdown("""
    <style>
        [data-testid="stHeader"] { display: none !important; }
        [data-testid="stFooter"], footer { display: none !important; }
        [data-testid="stToolbar"] { display: none !important; }
        .main .block-container { padding-top: 2rem !important; }
    </style>
""", unsafe_allow_html=True)

st.title("🤖 Algorithmic Trading Bot")
st.markdown("---")

# Telegram Config
TELEGRAM_TOKEN = st.secrets["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]

# Initialize session state
if 'trading_active' not in st.session_state:
    st.session_state.trading_active = False
if 'signals' not in st.session_state:
    st.session_state.signals = []
if 'signal_count_per_stock' not in st.session_state:
    st.session_state.signal_count_per_stock = {}
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = False
if 'refresh_counter' not in st.session_state:
    st.session_state.refresh_counter = 0
if 'saved_stocks' not in st.session_state:
    st.session_state.saved_stocks = []
if 'saved_stocks_df' not in st.session_state:
    st.session_state.saved_stocks_df = pd.DataFrame()

DISCLAIMER = """
━━━━━━━━━━━━━━━━━━
📢 EDUCATIONAL DISCLAIMER
For STUDY & ANALYSIS only
Not SEBI registered advisors
━━━━━━━━━━━━━━━━━━"""

def send_telegram_alert(signal):
    try:
        emoji = "🟢" if signal['SIGNAL'] == 'BUY' else "🔴"
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
{DISCLAIMER}
"""
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}, timeout=10)
        return True
    except:
        return False

def round_to_2_decimals(value):
    return round(float(value), 2)

class CandleBreakoutStrategy:
    def __init__(self, risk_amount=10000):
        self.risk_amount = risk_amount
        
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
                    }
                    if date_tracker is not None: 
                        date_tracker[key] = True
                    signals.append(signal)
                    break
        return signals

def fetch_data(symbol, interval, n_bars=100):
    try:
        tv = TvDatafeed()
        inv_map = {'5min': Interval.in_5_minute, '15min': Interval.in_15_minute}
        return tv.get_hist(symbol=symbol, exchange="NSE", 
                          interval=inv_map.get(interval, Interval.in_15_minute), 
                          n_bars=n_bars)
    except: 
        return None

# Sidebar
with st.sidebar:
    st.header("⚙️ Bot Settings")
    
    # Show saved stocks
    if st.session_state.saved_stocks:
        st.success(f"✅ {len(st.session_state.saved_stocks)} stocks loaded from screener")
        
        if st.button("📊 View Loaded Stocks", use_container_width=True):
            st.session_state.show_stocks = True
    else:
        st.warning("⚠️ No stocks loaded")
        st.info("1. Go to Stock Screener page\n2. Fetch NIFTY 200 data\n3. Filter and save stocks\n4. Come back here")
    
    st.markdown("---")
    
    risk_amount = st.number_input("Risk per Trade (₹)", 1000, 100000, 10000)
    timeframe = st.selectbox("Timeframe", ['15min', '5min'])
    update_interval = st.slider("Check Interval (seconds)", 10, 60, 30)
    
    st.markdown("---")
    
    if st.session_state.saved_stocks:
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

# Main content
if st.session_state.saved_stocks:
    # Show loaded stocks
    if st.session_state.get('show_stocks', False):
        st.subheader("📋 Loaded Stocks")
        st.write(st.session_state.saved_stocks)
        st.markdown("---")
    
    # Bot running
    if st.session_state.auto_refresh:
        col1, col2, col3 = st.columns(3)
        col1.metric("Bot Status", "🟢 RUNNING")
        col2.metric("Check Cycle", st.session_state.refresh_counter)
        col3.metric("Last Check", datetime.now().strftime('%H:%M:%S'))
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Run bot cycle
        st.session_state.refresh_counter += 1
        
        for i in range(update_interval, 0, -1):
            progress_bar.progress((update_interval - i) / update_interval)
            status_text.text(f"🔄 Next check in {i} seconds... (Cycle: {st.session_state.refresh_counter})")
            time.sleep(1)
        
        # Check for signals
        strategy = CandleBreakoutStrategy(risk_amount)
        new_signals = []
        
        for symbol in st.session_state.saved_stocks[:20]:  # Limit to 20 for performance
            data = fetch_data(symbol, timeframe)
            if data is not None:
                signals = strategy.analyze(data, symbol, st.session_state.signal_count_per_stock)
                if signals:
                    new_signals.extend(signals)
            time.sleep(0.3)
        
        if new_signals:
            st.session_state.signals.extend(new_signals)
            for signal in new_signals:
                send_telegram_alert(signal)
            st.balloons()
            st.success(f"🎯 {len(new_signals)} New Signals Generated!")
        
        # Display signals
        if st.session_state.signals:
            st.subheader(f"📋 Trading Signals ({len(st.session_state.signals)})")
            signals_df = pd.DataFrame(st.session_state.signals)
            st.dataframe(signals_df, use_container_width=True)
        
        time.sleep(1)
        st.rerun()
    
    else:
        # Bot stopped - show previous signals
        if st.session_state.signals:
            st.subheader(f"📋 Previous Signals ({len(st.session_state.signals)})")
            signals_df = pd.DataFrame(st.session_state.signals)
            st.dataframe(signals_df, use_container_width=True)
        else:
            st.info("👈 Click 'START BOT' to begin automated trading")
else:
    st.info("""
    ### No stocks loaded for trading!
    
    **Please follow these steps:**
    
    1. Go to the **Stock Screener** page (select from sidebar)
    2. Click **FETCH NIFTY 200 DATA**
    3. Adjust filters if needed
    4. Click **SAVE FOR TRADING BOT**
    5. Return to this page and click **START BOT**
    """)
