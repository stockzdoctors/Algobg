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

# Stock symbols
SYMBOLS = ["BANKNIFTY", "NIFTY", "UPL", "INFY", "ULTRACEMCO", "RELIANCE", 
           "ASIANPAINT", "ABB", "ACC", "LT", "HDFCBANK"]

# Simple disclaimer for Telegram
DISCLAIMER = """
━━━━━━━━━━━━━━━━━━
📢 **EDUCATIONAL DISCLAIMER:**
This is for STUDY & ANALYSIS only.
We are NOT SEBI registered advisors.
No trading recommendations provided.
Always consult registered experts.
━━━━━━━━━━━━━━━━━━"""

def send_telegram_message_sync(message):
    """Send Telegram message using simple HTTP Request (More stable for Cloud)"""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, data=payload)
        if response.status_code == 200:
            return True
        else:
            st.error(f"Telegram API Error: {response.text}")
            return False
    except Exception as e:
        st.error(f"Failed to send Telegram alert: {str(e)}")
        return False

def send_telegram_alert(signal, alert_type="ENTRY"):
    """Send signal alert to Telegram group"""
    try:
        if signal['SIGNAL'] == 'BUY':
            emoji = "🟢"
        else:
            emoji = "🔴"
        
        if alert_type == "ENTRY":
            title = "NEW TRADE SIGNAL"
            message = f"""
{emoji} *{title}* {emoji}

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
        elif alert_type == "STOPLOSS":
            title = "STOP LOSS HIT"
            pnl = signal.get('PNL', 0)
            message = f"""
{emoji} *{title}* {emoji}

📊 *Symbol:* {signal['SYMBOL']}
🎯 *Signal:* {signal['SIGNAL']}
💰 *Entry:* ₹{signal['ENTRY']}
🛑 *Stop Loss Hit:* ₹{signal['STOPLOSS']}
📉 *Loss:* ₹{abs(pnl):,.2f}
⏰ *Time:* {datetime.now().strftime('%H:%M:%S')}
📅 *Date:* {datetime.now().strftime('%Y-%m-%d')}

Trade Closed with Loss ❌
{DISCLAIMER}
            """
        elif alert_type == "TARGET1":
            title = "TARGET 1 HIT"
            pnl = signal.get('PNL', 0)
            message = f"""
{emoji} *{title}* {emoji}

📊 *Symbol:* {signal['SYMBOL']}
🎯 *Signal:* {signal['SIGNAL']}
💰 *Entry:* ₹{signal['ENTRY']}
✅ *Target 1 Hit:* ₹{signal['T1']}
📈 *Profit:* ₹{pnl:,.2f}
⏰ *Time:* {datetime.now().strftime('%H:%M:%S')}
📅 *Date:* {datetime.now().strftime('%Y-%m-%d')}

Partial Profit Booked! 🎯
{DISCLAIMER}
            """
        elif alert_type == "TARGET2":
            title = "TARGET 2 HIT"
            pnl = signal.get('PNL', 0)
            message = f"""
{emoji} *{title}* {emoji}

📊 *Symbol:* {signal['SYMBOL']}
🎯 *Signal:* {signal['SIGNAL']}
💰 *Entry:* ₹{signal['ENTRY']}
✅ *Target 2 Hit:* ₹{signal['T2']}
📈 *Profit:* ₹{pnl:,.2f}
⏰ *Time:* {datetime.now().strftime('%H:%M:%S')}
📅 *Date:* {datetime.now().strftime('%Y-%m-%d')}

Partial Profit Booked! 🎯🎯
{DISCLAIMER}
            """
        elif alert_type == "TARGET3":
            title = "TARGET 3 HIT"
            pnl = signal.get('PNL', 0)
            message = f"""
{emoji} *{title}* {emoji}

📊 *Symbol:* {signal['SYMBOL']}
🎯 *Signal:* {signal['SIGNAL']}
💰 *Entry:* ₹{signal['ENTRY']}
✅ *Target 3 Hit:* ₹{signal['T3']}
📈 *Total Profit:* ₹{pnl:,.2f}
⏰ *Time:* {datetime.now().strftime('%H:%M:%S')}
📅 *Date:* {datetime.now().strftime('%Y-%m-%d')}

Trade Completed - Full Profit! 🎯🎯🎯
{DISCLAIMER}
            """
        
        return send_telegram_message_sync(message)
        
    except Exception as e:
        st.error(f"Failed to send Telegram alert: {str(e)}")
        return False

def send_bulk_telegram_alerts(signals):
    """Send multiple alerts to Telegram"""
    for signal in signals:
        send_telegram_alert(signal, "ENTRY")
        time.sleep(1)

def round_to_2_decimals(value):
    """Round value to 2 decimal places"""
    return round(float(value), 2)

class CandleBreakoutStrategy:
    """Strategy: 9:15 reference, any future candle breakout, one signal per day"""
    
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
        
        # --- FIXED DATE LOGIC FOR LIVE TRADING ---
        if self.mode == "Live Trading":
            target_date = datetime.now().date()
        else:
            # In Backtest, we look at the date of the data provided
            target_date = df.index[-1].date()
            
        # Filter data for the target date only
        today_df = df[df.index.date == target_date]
        
        if len(today_df) < 1:
            return None

        # Find the 9:15 reference candle for TODAY
        reference_candle = None
        reference_idx = None
        
        for i in range(len(today_df)):
            time_str = today_df.index[i].strftime('%H:%M')
            if time_str == '09:15':
                reference_candle = today_df.iloc[i]
                reference_idx = i
                break
        
        if reference_candle is None:
            return None
        
        high_915 = round_to_2_decimals(reference_candle['high'])
        low_915 = round_to_2_decimals(reference_candle['low'])
        date_str = target_date.strftime('%Y-%m-%d')
        
        if date_tracker is not None:
            key = f"{symbol}_{date_str}"
            if date_tracker.get(key, False):
                return None
        
        # Check subsequent candles for breakout
        for i in range(reference_idx + 1, len(today_df)):
            current_candle = today_df.iloc[i]
            current_time_str = today_df.index[i].strftime('%H:%M')
            current_time_full = today_df.index[i].strftime('%H:%M:%S')
            
            open_price = round_to_2_decimals(current_candle['open'])
            high_price = round_to_2_decimals(current_candle['high'])
            low_price = round_to_2_decimals(current_candle['low'])
            volume = int(current_candle['volume'])
            
            # BUY Condition
            if high_price > high_915:
                entry = high_price if self.mode == "Live Trading" else open_price
                stop_loss = low_915
                risk_per_share = round_to_2_decimals(entry - stop_loss)
                
                if risk_per_share > 0:
                    quantity = int(self.risk_amount / risk_per_share)
                    if quantity > 0:
                        signal = {
                            'DATE': date_str, 'ENTRY_TIME': current_time_full,
                            'BREAKOUT_CANDLE': current_time_str, 'SYMBOL': symbol,
                            'SIGNAL': 'BUY', 'ENTRY': entry, 'QUANTITY': quantity,
                            'STOPLOSS': stop_loss, 'T1': round_to_2_decimals(entry + risk_per_share),
                            'T2': round_to_2_decimals(entry + risk_per_share * 2),
                            'T3': round_to_2_decimals(entry + risk_per_share * 3),
                            'VOLUME': volume, 'T1_HIT': False, 'T2_HIT': False, 'T3_HIT': False
                        }
                        if date_tracker is not None: date_tracker[key] = True
                        signals.append(signal)
                        break
                        
            # SELL Condition
            elif low_price < low_915:
                entry = low_price if self.mode == "Live Trading" else open_price
                stop_loss = high_915
                risk_per_share = round_to_2_decimals(stop_loss - entry)
                
                if risk_per_share > 0:
                    quantity = int(self.risk_amount / risk_per_share)
                    if quantity > 0:
                        signal = {
                            'DATE': date_str, 'ENTRY_TIME': current_time_full,
                            'BREAKOUT_CANDLE': current_time_str, 'SYMBOL': symbol,
                            'SIGNAL': 'SELL', 'ENTRY': entry, 'QUANTITY': quantity,
                            'STOPLOSS': stop_loss, 'T1': round_to_2_decimals(entry - risk_per_share),
                            'T2': round_to_2_decimals(entry - risk_per_share * 2),
                            'T3': round_to_2_decimals(entry - risk_per_share * 3),
                            'VOLUME': volume, 'T1_HIT': False, 'T2_HIT': False, 'T3_HIT': False
                        }
                        if date_tracker is not None: date_tracker[key] = True
                        signals.append(signal)
                        break
        return signals

class MovingAverageCrossStrategy:
    """Strategy 2: Moving Average Crossover Strategy"""
    def __init__(self, timeframe='15min', fast_ma=9, slow_ma=21, risk_amount=10000, mode="Live Trading"):
        self.timeframe = timeframe
        self.fast_ma = fast_ma
        self.slow_ma = slow_ma
        self.risk_amount = risk_amount
        self.mode = mode
        self.name = f"MA Crossover ({fast_ma}/{slow_ma})"
        
    def analyze(self, df, symbol, date_tracker=None):
        if df is None or len(df) < self.slow_ma + 1:
            return None
        signals = []
        df['MA_Fast'] = df['close'].rolling(window=self.fast_ma).mean()
        df['MA_Slow'] = df['close'].rolling(window=self.slow_ma).mean()
        current_crossover = df['MA_Fast'].iloc[-1] > df['MA_Slow'].iloc[-1]
        prev_crossover = df['MA_Fast'].iloc[-2] > df['MA_Slow'].iloc[-2]
        current_candle = df.iloc[-1]
        
        date_str = current_candle.name.strftime('%Y-%m-%d') if hasattr(current_candle.name, 'strftime') else str(current_candle.name)[:10]
        
        if current_crossover and not prev_crossover:
            entry = round_to_2_decimals(current_candle['close'])
            signal = {'DATE': date_str, 'SYMBOL': symbol, 'SIGNAL': 'BUY', 'ENTRY': entry, 'QUANTITY': 100, 'STOPLOSS': entry*0.99, 'T1': entry*1.01, 'T2': entry*1.02, 'T3': entry*1.03, 'ENTRY_TIME': 'LIVE', 'BREAKOUT_CANDLE': 'MA'}
            signals.append(signal)
        return signals

class RSIBreakoutStrategy:
    """Strategy 3: RSI + Breakout Strategy"""
    def __init__(self, timeframe='15min', rsi_period=14, risk_amount=10000, mode="Live Trading"):
        self.rsi_period = rsi_period
    def analyze(self, df, symbol, date_tracker=None):
        return None 

def fetch_data(symbol, interval, n_bars=50):
    """Fetch historical data from TradingView"""
    try:
        tv = TvDatafeed()
        interval_map = {'5min': Interval.in_5_minute, '15min': Interval.in_15_minute, 'daily': Interval.in_daily}
        tv_interval = interval_map.get(interval, Interval.in_15_minute)
        data = tv.get_hist(symbol=symbol, exchange="NSE", interval=tv_interval, n_bars=n_bars)
        return data
    except Exception as e:
        st.error(f"Error fetching data for {symbol}: {str(e)}")
        return None

def get_last_n_market_days(n=2):
    market_days = []
    current_date = datetime.now()
    while len(market_days) < n:
        current_date -= timedelta(days=1)
        if current_date.weekday() < 5: market_days.append(current_date)
    return market_days

def check_for_new_signals(selected_symbols, timeframe, strategy_name, risk_amount, mode, existing_signals, **strategy_params):
    all_new_signals = []
    date_tracker = st.session_state.signal_count_per_stock
    
    if strategy_name == "Candle Breakout Strategy":
        strategy = CandleBreakoutStrategy(timeframe, risk_amount, mode)
    elif strategy_name == "MA Crossover Strategy":
        strategy = MovingAverageCrossStrategy(timeframe, risk_amount=risk_amount, mode=mode)
    else:
        strategy = RSIBreakoutStrategy()
    
    for symbol in selected_symbols:
        data = fetch_data(symbol, timeframe, n_bars=100)
        if data is not None:
            signals = strategy.analyze(data, symbol, date_tracker)
            if signals: all_new_signals.extend(signals)
    return all_new_signals

def backtest_strategy(selected_symbols, timeframe, strategy_name, start_date, end_date, risk_amount, mode, **strategy_params):
    return check_for_new_signals(selected_symbols, timeframe, strategy_name, risk_amount, mode, [])

def simulate_live_signals(selected_symbols, timeframe, strategy_name, risk_amount, mode, **strategy_params):
    return check_for_new_signals(selected_symbols, timeframe, strategy_name, risk_amount, mode, [])

def monitor_active_trades(current_prices):
    return []

def get_current_prices(selected_symbols, timeframe):
    return {s: 0 for s in selected_symbols}

def display_signals_table(signals, title="Trading Signals"):
    if not signals:
        st.info("No signals generated")
        return None
    df_display = pd.DataFrame(signals)
    st.dataframe(df_display.style.map(lambda x: 'background-color: #00ff00; color: black' if x == 'BUY' else ('background-color: #ff0000; color: white' if x == 'SELL' else ''), subset=['SIGNAL']), use_container_width=True)

def main():
    st.title("📈 Algorithmic Trading System")
    st.markdown("---")
    
    with st.sidebar:
        st.header("⚙️ Configuration")
        selected_mode = st.radio("Select Mode", options=["Live Trading", "Backtest (Last 2 Days)", "Simulation (Market Closed)"], index=0)
        st.session_state.mode = selected_mode
        risk_amount = st.number_input("Risk Amount per Trade (₹)", min_value=1000, value=10000)
        timeframe = st.selectbox("Select Timeframe", options=['5min', '15min', 'daily'], index=1)
        strategy = st.selectbox("Select Strategy", options=["Candle Breakout Strategy", "MA Crossover Strategy", "RSI Breakout Strategy"], index=0)
        update_interval = st.slider("Update Interval (seconds)", min_value=5, max_value=60, value=10)
        
        if not st.session_state.auto_refresh:
            if st.button("🚀 Start Bot", type="primary", use_container_width=True):
                st.session_state.auto_refresh = True
                st.session_state.refresh_counter = 0
                send_telegram_message_sync(f"🤖 Bot Started: {strategy} | {timeframe}")
                st.rerun()
        else:
            if st.button("⏹️ Stop Bot", type="secondary", use_container_width=True):
                st.session_state.auto_refresh = False
                st.rerun()

    if st.session_state.auto_refresh and selected_mode == "Live Trading":
        st.session_state.refresh_counter += 1
        st.session_state.last_check_time = datetime.now()
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        new_signals = run_bot_cycle(SYMBOLS, timeframe, strategy, risk_amount, selected_mode, {}, update_interval, progress_bar, status_text)
        
        if new_signals:
            st.session_state.signals.extend(new_signals)
            send_bulk_telegram_alerts(new_signals)
            st.balloons()
            
        display_signals_table(st.session_state.signals, "Live Trading Signals")
        time.sleep(update_interval)
        st.rerun()

    elif selected_mode == "Backtest (Last 2 Days)":
        if st.button("🚀 Run Backtest", type="primary"):
            signals = backtest_strategy(SYMBOLS, timeframe, strategy, None, None, risk_amount, selected_mode)
            st.session_state.signals = signals
            display_signals_table(signals)
            send_bulk_telegram_alerts(signals)

if __name__ == "__main__":
    main()
