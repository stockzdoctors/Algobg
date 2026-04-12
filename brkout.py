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
        
        # Find the 9:15 reference candle
        reference_candle = None
        reference_idx = None
        
        for i in range(len(df)):
            time_val = df.index[i]
            if hasattr(time_val, 'strftime'):
                time_str = time_val.strftime('%H:%M')
            else:
                time_str = str(time_val)[-8:-3] if len(str(time_val)) > 8 else str(time_val)
            
            if time_str == '09:15':
                reference_candle = df.iloc[i]
                reference_idx = i
                break
        
        if reference_candle is None:
            return None
        
        high_915 = round_to_2_decimals(reference_candle['high'])
        low_915 = round_to_2_decimals(reference_candle['low'])
        
        if hasattr(reference_candle.name, 'strftime'):
            date_str = reference_candle.name.strftime('%Y-%m-%d')
        else:
            date_str = str(reference_candle.name).split()[0] if ' ' in str(reference_candle.name) else str(reference_candle.name)[:10]
        
        if date_tracker is not None:
            key = f"{symbol}_{date_str}"
            if date_tracker.get(key, False):
                return None
        
        for i in range(reference_idx + 1, len(df)):
            current_candle = df.iloc[i]
            
            if hasattr(current_candle.name, 'strftime'):
                current_time_str = current_candle.name.strftime('%H:%M')
                current_time_full = current_candle.name.strftime('%H:%M:%S')
                current_date = current_candle.name.strftime('%Y-%m-%d')
            else:
                current_time_str = str(current_candle.name)[-8:-3] if len(str(current_candle.name)) > 8 else str(current_candle.name)
                current_time_full = str(current_candle.name)[-8:] if len(str(current_candle.name)) > 8 else str(current_candle.name)
                current_date = str(current_candle.name).split()[0] if ' ' in str(current_candle.name) else str(current_candle.name)[:10]
            
            open_price = round_to_2_decimals(current_candle['open'])
            high_price = round_to_2_decimals(current_candle['high'])
            low_price = round_to_2_decimals(current_candle['low'])
            volume = int(current_candle['volume'])
            
            # BUY Condition
            if high_price > high_915:
                if self.mode == "Live Trading":
                    entry = high_price
                else:
                    if i + 1 < len(df):
                        next_candle = df.iloc[i + 1]
                        entry = round_to_2_decimals(next_candle['open'])
                    else:
                        entry = open_price
                
                stop_loss = low_915
                risk_per_share = round_to_2_decimals(entry - stop_loss)
                
                if risk_per_share > 0:
                    quantity = int(self.risk_amount / risk_per_share)
                    
                    if quantity > 0:
                        target1 = round_to_2_decimals(entry + (risk_per_share * 1))
                        target2 = round_to_2_decimals(entry + (risk_per_share * 2))
                        target3 = round_to_2_decimals(entry + (risk_per_share * 3))
                        
                        signal = {
                            'DATE': current_date,
                            'ENTRY_TIME': current_time_full,
                            'BREAKOUT_CANDLE': current_time_str,
                            'SYMBOL': symbol,
                            'SIGNAL': 'BUY',
                            'ENTRY': entry,
                            'QUANTITY': quantity,
                            'STOPLOSS': stop_loss,
                            'T1': target1,
                            'T2': target2,
                            'T3': target3,
                            'VOLUME': volume,
                            'T1_HIT': False,
                            'T2_HIT': False,
                            'T3_HIT': False
                        }
                        
                        if date_tracker is not None:
                            date_tracker[key] = True
                        
                        signals.append(signal)
                        break
                        
            # SELL Condition
            elif low_price < low_915:
                if self.mode == "Live Trading":
                    entry = low_price
                else:
                    if i + 1 < len(df):
                        next_candle = df.iloc[i + 1]
                        entry = round_to_2_decimals(next_candle['open'])
                    else:
                        entry = open_price
                
                stop_loss = high_915
                risk_per_share = round_to_2_decimals(stop_loss - entry)
                
                if risk_per_share > 0:
                    quantity = int(self.risk_amount / risk_per_share)
                    
                    if quantity > 0:
                        target1 = round_to_2_decimals(entry - (risk_per_share * 1))
                        target2 = round_to_2_decimals(entry - (risk_per_share * 2))
                        target3 = round_to_2_decimals(entry - (risk_per_share * 3))
                        
                        signal = {
                            'DATE': current_date,
                            'ENTRY_TIME': current_time_full,
                            'BREAKOUT_CANDLE': current_time_str,
                            'SYMBOL': symbol,
                            'SIGNAL': 'SELL',
                            'ENTRY': entry,
                            'QUANTITY': quantity,
                            'STOPLOSS': stop_loss,
                            'T1': target1,
                            'T2': target2,
                            'T3': target3,
                            'VOLUME': volume,
                            'T1_HIT': False,
                            'T2_HIT': False,
                            'T3_HIT': False
                        }
                        
                        if date_tracker is not None:
                            date_tracker[key] = True
                        
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
        current_volume = int(current_candle['volume'])
        
        if hasattr(current_candle.name, 'strftime'):
            date_str = current_candle.name.strftime('%Y-%m-%d')
            time_str = current_candle.name.strftime('%H:%M:%S')
            time_only = current_candle.name.strftime('%H:%M')
        else:
            date_str = str(current_candle.name).split()[0] if ' ' in str(current_candle.name) else str(current_candle.name)[:10]
            time_str = str(current_candle.name)[-8:] if len(str(current_candle.name)) > 8 else str(current_candle.name)
            time_only = str(current_candle.name)[-8:-3] if len(str(current_candle.name)) > 8 else str(current_candle.name)
        
        if date_tracker is not None:
            key = f"{symbol}_{date_str}"
            if date_tracker.get(key, False):
                return None
        
        if current_crossover and not prev_crossover:
            if self.mode == "Live Trading":
                entry = round_to_2_decimals(current_candle['close'])
            else:
                entry = round_to_2_decimals(current_candle['open'])
            
            atr = self.calculate_atr(df)
            stop_loss = round_to_2_decimals(entry - (atr * 1.5))
            risk_per_share = round_to_2_decimals(entry - stop_loss)
            
            if risk_per_share > 0:
                quantity = int(self.risk_amount / risk_per_share)
                
                if quantity > 0:
                    target1 = round_to_2_decimals(entry + (risk_per_share * 1))
                    target2 = round_to_2_decimals(entry + (risk_per_share * 2))
                    target3 = round_to_2_decimals(entry + (risk_per_share * 3))
                    
                    signal = {
                        'DATE': date_str,
                        'ENTRY_TIME': time_str,
                        'BREAKOUT_CANDLE': time_only,
                        'SYMBOL': symbol,
                        'SIGNAL': 'BUY',
                        'ENTRY': entry,
                        'QUANTITY': quantity,
                        'STOPLOSS': stop_loss,
                        'T1': target1,
                        'T2': target2,
                        'T3': target3,
                        'VOLUME': current_volume,
                        'T1_HIT': False,
                        'T2_HIT': False,
                        'T3_HIT': False
                    }
                    
                    if date_tracker is not None:
                        date_tracker[key] = True
                    signals.append(signal)
            
        elif not current_crossover and prev_crossover:
            if self.mode == "Live Trading":
                entry = round_to_2_decimals(current_candle['close'])
            else:
                entry = round_to_2_decimals(current_candle['open'])
            
            atr = self.calculate_atr(df)
            stop_loss = round_to_2_decimals(entry + (atr * 1.5))
            risk_per_share = round_to_2_decimals(stop_loss - entry)
            
            if risk_per_share > 0:
                quantity = int(self.risk_amount / risk_per_share)
                
                if quantity > 0:
                    target1 = round_to_2_decimals(entry - (risk_per_share * 1))
                    target2 = round_to_2_decimals(entry - (risk_per_share * 2))
                    target3 = round_to_2_decimals(entry - (risk_per_share * 3))
                    
                    signal = {
                        'DATE': date_str,
                        'ENTRY_TIME': time_str,
                        'BREAKOUT_CANDLE': time_only,
                        'SYMBOL': symbol,
                        'SIGNAL': 'SELL',
                        'ENTRY': entry,
                        'QUANTITY': quantity,
                        'STOPLOSS': stop_loss,
                        'T1': target1,
                        'T2': target2,
                        'T3': target3,
                        'VOLUME': current_volume,
                        'T1_HIT': False,
                        'T2_HIT': False,
                        'T3_HIT': False
                    }
                    
                    if date_tracker is not None:
                        date_tracker[key] = True
                    signals.append(signal)
            
        return signals
    
    def calculate_atr(self, df, period=14):
        high = df['high']
        low = df['low']
        close = df['close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(window=period).mean()
        
        return round_to_2_decimals(atr.iloc[-1])

class RSIBreakoutStrategy:
    """Strategy 3: RSI + Breakout Strategy"""
    
    def __init__(self, timeframe='15min', rsi_period=14, risk_amount=10000, mode="Live Trading"):
        self.timeframe = timeframe
        self.rsi_period = rsi_period
        self.risk_amount = risk_amount
        self.mode = mode
        self.name = f"RSI Breakout ({rsi_period})"
        
    def analyze(self, df, symbol, date_tracker=None):
        if df is None or len(df) < self.rsi_period + 2:
            return None
            
        signals = []
        df['RSI'] = self.calculate_rsi(df['close'], self.rsi_period)
        
        # Find the 9:15 reference candle
        reference_candle = None
        reference_idx = None
        
        for i in range(len(df)):
            time_val = df.index[i]
            if hasattr(time_val, 'strftime'):
                time_str = time_val.strftime('%H:%M')
            else:
                time_str = str(time_val)[-8:-3] if len(str(time_val)) > 8 else str(time_val)
            
            if time_str == '09:15':
                reference_candle = df.iloc[i]
                reference_idx = i
                break
        
        if reference_candle is None:
            return None
        
        high_915 = round_to_2_decimals(reference_candle['high'])
        low_915 = round_to_2_decimals(reference_candle['low'])
        
        if hasattr(reference_candle.name, 'strftime'):
            date_str = reference_candle.name.strftime('%Y-%m-%d')
        else:
            date_str = str(reference_candle.name).split()[0] if ' ' in str(reference_candle.name) else str(reference_candle.name)[:10]
        
        if date_tracker is not None:
            key = f"{symbol}_{date_str}"
            if date_tracker.get(key, False):
                return None
        
        for i in range(reference_idx + 1, len(df)):
            current_candle = df.iloc[i]
            current_rsi = round_to_2_decimals(df['RSI'].iloc[i])
            
            if hasattr(current_candle.name, 'strftime'):
                current_time_str = current_candle.name.strftime('%H:%M')
                current_time_full = current_candle.name.strftime('%H:%M:%S')
            else:
                current_time_str = str(current_candle.name)[-8:-3] if len(str(current_candle.name)) > 8 else str(current_candle.name)
                current_time_full = str(current_candle.name)[-8:] if len(str(current_candle.name)) > 8 else str(current_candle.name)
            
            open_price = round_to_2_decimals(current_candle['open'])
            high_price = round_to_2_decimals(current_candle['high'])
            low_price = round_to_2_decimals(current_candle['low'])
            volume = int(current_candle['volume'])
            
            if high_price > high_915 and current_rsi > 50:
                if self.mode == "Live Trading":
                    entry = high_price
                else:
                    if i + 1 < len(df):
                        next_candle = df.iloc[i + 1]
                        entry = round_to_2_decimals(next_candle['open'])
                    else:
                        entry = open_price
                
                stop_loss = low_915
                risk_per_share = round_to_2_decimals(entry - stop_loss)
                
                if risk_per_share > 0:
                    quantity = int(self.risk_amount / risk_per_share)
                    
                    if quantity > 0:
                        target1 = round_to_2_decimals(entry + (risk_per_share * 1))
                        target2 = round_to_2_decimals(entry + (risk_per_share * 2))
                        target3 = round_to_2_decimals(entry + (risk_per_share * 3))
                        
                        signal = {
                            'DATE': date_str,
                            'ENTRY_TIME': current_time_full,
                            'BREAKOUT_CANDLE': current_time_str,
                            'SYMBOL': symbol,
                            'SIGNAL': 'BUY',
                            'ENTRY': entry,
                            'QUANTITY': quantity,
                            'STOPLOSS': stop_loss,
                            'T1': target1,
                            'T2': target2,
                            'T3': target3,
                            'VOLUME': volume,
                            'T1_HIT': False,
                            'T2_HIT': False,
                            'T3_HIT': False
                        }
                        
                        if date_tracker is not None:
                            date_tracker[key] = True
                        signals.append(signal)
                        break
                        
            elif low_price < low_915 and current_rsi < 50:
                if self.mode == "Live Trading":
                    entry = low_price
                else:
                    if i + 1 < len(df):
                        next_candle = df.iloc[i + 1]
                        entry = round_to_2_decimals(next_candle['open'])
                    else:
                        entry = open_price
                
                stop_loss = high_915
                risk_per_share = round_to_2_decimals(stop_loss - entry)
                
                if risk_per_share > 0:
                    quantity = int(self.risk_amount / risk_per_share)
                    
                    if quantity > 0:
                        target1 = round_to_2_decimals(entry - (risk_per_share * 1))
                        target2 = round_to_2_decimals(entry - (risk_per_share * 2))
                        target3 = round_to_2_decimals(entry - (risk_per_share * 3))
                        
                        signal = {
                            'DATE': date_str,
                            'ENTRY_TIME': current_time_full,
                            'BREAKOUT_CANDLE': current_time_str,
                            'SYMBOL': symbol,
                            'SIGNAL': 'SELL',
                            'ENTRY': entry,
                            'QUANTITY': quantity,
                            'STOPLOSS': stop_loss,
                            'T1': target1,
                            'T2': target2,
                            'T3': target3,
                            'VOLUME': volume,
                            'T1_HIT': False,
                            'T2_HIT': False,
                            'T3_HIT': False
                        }
                        
                        if date_tracker is not None:
                            date_tracker[key] = True
                        signals.append(signal)
                        break
                
        return signals
    
    def calculate_rsi(self, prices, period=14):
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return rsi

def fetch_data(symbol, interval, n_bars=50):
    """Fetch historical data from TradingView"""
    try:
        tv = TvDatafeed()
        
        interval_map = {
            '5min': Interval.in_5_minute,
            '15min': Interval.in_15_minute,
            '30min': Interval.in_30_minute,
            '45min': Interval.in_45_minute,
            '1h': Interval.in_1_hour,
            'daily': Interval.in_daily
        }
        
        tv_interval = interval_map.get(interval, Interval.in_15_minute)
        
        data = tv.get_hist(
            symbol=symbol, 
            exchange="NSE", 
            interval=tv_interval, 
            n_bars=n_bars, 
            extended_session=False
        )
        
        return data
    except Exception as e:
        st.error(f"Error fetching data for {symbol}: {str(e)}")
        return None

def get_last_n_market_days(n=2):
    """Get last n market days (excluding weekends)"""
    market_days = []
    current_date = datetime.now()
    
    while len(market_days) < n:
        current_date -= timedelta(days=1)
        if current_date.weekday() < 5:
            market_days.append(current_date)
    
    return market_days

def check_for_new_signals(selected_symbols, timeframe, strategy_name, risk_amount, mode, existing_signals, **strategy_params):
    """Check for new signals and return only new ones"""
    all_new_signals = []
    date_tracker = {}
    
    for signal in existing_signals:
        key = f"{signal['SYMBOL']}_{signal['DATE']}"
        date_tracker[key] = True
    
    if strategy_name == "Candle Breakout Strategy":
        strategy = CandleBreakoutStrategy(timeframe, risk_amount, mode)
    elif strategy_name == "MA Crossover Strategy":
        fast_ma = strategy_params.get('fast_ma', 9)
        slow_ma = strategy_params.get('slow_ma', 21)
        strategy = MovingAverageCrossStrategy(timeframe, fast_ma, slow_ma, risk_amount, mode)
    else:
        rsi_period = strategy_params.get('rsi_period', 14)
        strategy = RSIBreakoutStrategy(timeframe, rsi_period, risk_amount, mode)
    
    for symbol in selected_symbols:
        data = fetch_data(symbol, timeframe, n_bars=50)
        
        if data is not None and len(data) > 0:
            signals = strategy.analyze(data, symbol, date_tracker)
            if signals:
                all_new_signals.extend(signals)
    
    return all_new_signals

def backtest_strategy(selected_symbols, timeframe, strategy_name, start_date, end_date, risk_amount, mode, **strategy_params):
    """Run backtest on historical data"""
    all_signals = []
    date_tracker = {}
    
    if strategy_name == "Candle Breakout Strategy":
        strategy = CandleBreakoutStrategy(timeframe, risk_amount, mode)
    elif strategy_name == "MA Crossover Strategy":
        fast_ma = strategy_params.get('fast_ma', 9)
        slow_ma = strategy_params.get('slow_ma', 21)
        strategy = MovingAverageCrossStrategy(timeframe, fast_ma, slow_ma, risk_amount, mode)
    else:
        rsi_period = strategy_params.get('rsi_period', 14)
        strategy = RSIBreakoutStrategy(timeframe, rsi_period, risk_amount, mode)
    
    progress_bar = st.progress(0)
    
    for idx, symbol in enumerate(selected_symbols):
        data = fetch_data(symbol, timeframe, n_bars=500)
        
        if data is not None and len(data) > 0:
            data.index = pd.to_datetime(data.index)
            mask = (data.index >= pd.to_datetime(start_date)) & (data.index <= pd.to_datetime(end_date) + timedelta(days=1))
            filtered_data = data[mask]
            
            if len(filtered_data) > 0:
                signals = strategy.analyze(filtered_data, symbol, date_tracker)
                if signals:
                    all_signals.extend(signals)
        
        progress_bar.progress((idx + 1) / len(selected_symbols))
    
    return all_signals

def simulate_live_signals(selected_symbols, timeframe, strategy_name, risk_amount, mode, **strategy_params):
    """Simulate live signals using latest data"""
    all_signals = []
    date_tracker = {}
    
    if strategy_name == "Candle Breakout Strategy":
        strategy = CandleBreakoutStrategy(timeframe, risk_amount, mode)
    elif strategy_name == "MA Crossover Strategy":
        fast_ma = strategy_params.get('fast_ma', 9)
        slow_ma = strategy_params.get('slow_ma', 21)
        strategy = MovingAverageCrossStrategy(timeframe, fast_ma, slow_ma, risk_amount, mode)
    else:
        rsi_period = strategy_params.get('rsi_period', 14)
        strategy = RSIBreakoutStrategy(timeframe, rsi_period, risk_amount, mode)
    
    for symbol in selected_symbols:
        data = fetch_data(symbol, timeframe, n_bars=50)
        
        if data is not None and len(data) > 0:
            signals = strategy.analyze(data, symbol, date_tracker)
            if signals:
                all_signals.extend(signals)
    
    return all_signals

def monitor_active_trades(current_prices):
    """Monitor active trades and send alerts when SL or targets are hit"""
    alerts_sent = []
    
    for trade in st.session_state.active_trades[:]:
        symbol = trade['SYMBOL']
        if symbol in current_prices:
            current_price = current_prices[symbol]
            signal_type = trade['SIGNAL']
            
            if signal_type == 'BUY':
                if current_price <= trade['STOPLOSS']:
                    pnl = (trade['STOPLOSS'] - trade['ENTRY']) * trade['QUANTITY']
                    trade['PNL'] = pnl
                    send_telegram_alert(trade, "STOPLOSS")
                    st.session_state.active_trades.remove(trade)
                    st.session_state.completed_trades.append(trade)
                    alerts_sent.append(f"{symbol} - Stop Loss Hit")
                
                elif current_price >= trade['T1'] and not trade.get('T1_HIT', False):
                    trade['T1_HIT'] = True
                    pnl = (trade['T1'] - trade['ENTRY']) * trade['QUANTITY']
                    trade['PNL_T1'] = pnl
                    send_telegram_alert(trade, "TARGET1")
                    alerts_sent.append(f"{symbol} - Target 1 Hit")
                
                elif current_price >= trade['T2'] and not trade.get('T2_HIT', False):
                    trade['T2_HIT'] = True
                    pnl = (trade['T2'] - trade['ENTRY']) * trade['QUANTITY']
                    trade['PNL_T2'] = pnl
                    send_telegram_alert(trade, "TARGET2")
                    alerts_sent.append(f"{symbol} - Target 2 Hit")
                
                elif current_price >= trade['T3'] and not trade.get('T3_HIT', False):
                    trade['T3_HIT'] = True
                    pnl = (trade['T3'] - trade['ENTRY']) * trade['QUANTITY']
                    trade['PNL_T3'] = pnl
                    send_telegram_alert(trade, "TARGET3")
                    st.session_state.active_trades.remove(trade)
                    st.session_state.completed_trades.append(trade)
                    alerts_sent.append(f"{symbol} - Target 3 Hit - Trade Closed")
            
            else:
                if current_price >= trade['STOPLOSS']:
                    pnl = (trade['ENTRY'] - trade['STOPLOSS']) * trade['QUANTITY']
                    trade['PNL'] = pnl
                    send_telegram_alert(trade, "STOPLOSS")
                    st.session_state.active_trades.remove(trade)
                    st.session_state.completed_trades.append(trade)
                    alerts_sent.append(f"{symbol} - Stop Loss Hit")
                
                elif current_price <= trade['T1'] and not trade.get('T1_HIT', False):
                    trade['T1_HIT'] = True
                    pnl = (trade['ENTRY'] - trade['T1']) * trade['QUANTITY']
                    trade['PNL_T1'] = pnl
                    send_telegram_alert(trade, "TARGET1")
                    alerts_sent.append(f"{symbol} - Target 1 Hit")
                
                elif current_price <= trade['T2'] and not trade.get('T2_HIT', False):
                    trade['T2_HIT'] = True
                    pnl = (trade['ENTRY'] - trade['T2']) * trade['QUANTITY']
                    trade['PNL_T2'] = pnl
                    send_telegram_alert(trade, "TARGET2")
                    alerts_sent.append(f"{symbol} - Target 2 Hit")
                
                elif current_price <= trade['T3'] and not trade.get('T3_HIT', False):
                    trade['T3_HIT'] = True
                    pnl = (trade['ENTRY'] - trade['T3']) * trade['QUANTITY']
                    trade['PNL_T3'] = pnl
                    send_telegram_alert(trade, "TARGET3")
                    st.session_state.active_trades.remove(trade)
                    st.session_state.completed_trades.append(trade)
                    alerts_sent.append(f"{symbol} - Target 3 Hit - Trade Closed")
    
    return alerts_sent

def get_current_prices(selected_symbols, timeframe):
    """Fetch current prices for all active symbols"""
    current_prices = {}
    for symbol in selected_symbols:
        data = fetch_data(symbol, timeframe, n_bars=5)
        if data is not None and len(data) > 0:
            current_prices[symbol] = data['close'].iloc[-1]
    return current_prices

def display_signals_table(signals, title="Trading Signals"):
    """Display signals in a formatted table"""
    if not signals:
        st.info("No signals generated")
        return None
    
    df_signals = pd.DataFrame(signals)
    
    float_columns = ['ENTRY', 'STOPLOSS', 'T1', 'T2', 'T3']
    for col in float_columns:
        if col in df_signals.columns:
            if df_signals[col].dtype == 'object':
                df_signals[col] = df_signals[col].astype(float)
            df_signals[col] = df_signals[col].apply(lambda x: f"{x:.2f}")
    
    display_columns = ['DATE', 'ENTRY_TIME', 'BREAKOUT_CANDLE', 'SYMBOL', 'SIGNAL', 
                      'ENTRY', 'QUANTITY', 'STOPLOSS', 'T1', 'T2', 'T3', 'VOLUME']
    
    available_columns = [col for col in display_columns if col in df_signals.columns]
    df_display = df_signals[available_columns]
    
    def color_signal(val):
        if val == 'BUY':
            return 'background-color: #00ff00; color: black; font-weight: bold'
        elif val == 'SELL':
            return 'background-color: #ff0000; color: white; font-weight: bold'
        return ''
    
    styled_df = df_display.style.map(color_signal, subset=['SIGNAL'])
    
    st.dataframe(
        styled_df,
        use_container_width=True,
        height=400
    )
    
    return df_display

def display_active_trades():
    """Display currently active trades"""
    if st.session_state.active_trades:
        st.subheader("🟡 Active Trades")
        df_active = pd.DataFrame(st.session_state.active_trades)
        display_columns = ['SYMBOL', 'SIGNAL', 'ENTRY', 'QUANTITY', 'STOPLOSS', 'T1', 'T2', 'T3']
        available_cols = [col for col in display_columns if col in df_active.columns]
        st.dataframe(df_active[available_cols], use_container_width=True)
    else:
        st.info("No active trades")

def run_bot_cycle(selected_symbols, timeframe, strategy, risk_amount, selected_mode, strategy_params, refresh_interval, progress_bar, status_text):
    """Run one cycle of bot operations with progress bar update"""
    
    # Update last check time
    current_time = datetime.now()
    st.session_state.last_check_time = current_time
    st.session_state.refresh_counter += 1
    
    # Update progress bar
    for i in range(refresh_interval, 0, -1):
        progress_bar.progress((refresh_interval - i) / refresh_interval)
        status_text.text(f"🔄 Next check in {i} seconds... (Cycle: {st.session_state.refresh_counter})")
        time.sleep(1)
    
    # Check for new signals
    status_text.text(f"📊 Checking for signals... (Cycle: {st.session_state.refresh_counter})")
    new_signals = check_for_new_signals(
        selected_symbols, timeframe, strategy, risk_amount, 
        selected_mode, st.session_state.signals, **strategy_params
    )
    
    if new_signals:
        st.session_state.signals.extend(new_signals)
        
        for signal in new_signals:
            st.session_state.active_trades.append(signal.copy())
        
        send_bulk_telegram_alerts(new_signals)
        status_text.success(f"🎯 {len(new_signals)} New Signal(s) Found!")
        return new_signals
    
    status_text.info(f"✅ No new signals. Active trades: {len(st.session_state.active_trades)}")
    return []

def main():
    st.title("📈 Algorithmic Trading System")
    st.markdown("---")
    
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        selected_mode = st.radio(
            "Select Mode",
            options=["Live Trading", "Backtest (Last 2 Days)", "Simulation (Market Closed)"],
            index=2
        )
        st.session_state.mode = selected_mode
        
        st.markdown("---")
        
        st.subheader("💰 Risk Management")
        risk_amount = st.number_input(
            "Risk Amount per Trade (₹)",
            min_value=1000,
            max_value=1000000,
            value=10000,
            step=1000
        )
        
        st.markdown("---")
        
        timeframe = st.selectbox(
            "Select Timeframe",
            options=['5min', '15min', '30min', '45min', '1h', 'daily'],
            index=1
        )
        
        strategy = st.selectbox(
            "Select Strategy",
            options=[
                "Candle Breakout Strategy",
                "MA Crossover Strategy",
                "RSI Breakout Strategy"
            ],
            index=0
        )
        
        if strategy == "MA Crossover Strategy":
            fast_ma = st.number_input("Fast MA Period", min_value=5, max_value=50, value=9)
            slow_ma = st.number_input("Slow MA Period", min_value=10, max_value=100, value=21)
            strategy_params = {'fast_ma': fast_ma, 'slow_ma': slow_ma}
        elif strategy == "RSI Breakout Strategy":
            rsi_period = st.number_input("RSI Period", min_value=5, max_value=30, value=14)
            strategy_params = {'rsi_period': rsi_period}
        else:
            strategy_params = {}
        
        st.subheader("🤖 Bot Settings")
        update_interval = st.slider(
            "Update Interval (seconds)",
            min_value=5,
            max_value=60,
            value=10,
            step=5,
            help="How often to check for new signals (in seconds)"
        )
        
        st.subheader("📊 Stock Selection")
        select_all = st.checkbox("Select All Stocks", value=True)
        
        if select_all:
            selected_symbols = SYMBOLS
            st.info(f"✅ All {len(SYMBOLS)} stocks selected")
        else:
            selected_symbols = st.multiselect(
                "Choose stocks to trade",
                options=SYMBOLS,
                default=["NIFTY", "BANKNIFTY", "RELIANCE"]
            )
        
        if selected_mode == "Backtest (Last 2 Days)":
            st.subheader("📅 Backtest Date Range")
            market_days = get_last_n_market_days(2)
            if market_days:
                end_date = market_days[0]
                start_date = market_days[-1]
                st.info(f"Testing from {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
                
                custom_range = st.checkbox("Custom Date Range")
                if custom_range:
                    start_date = st.date_input("Start Date", start_date)
                    end_date = st.date_input("End Date", datetime.now().date())
        
        st.markdown("---")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if selected_mode == "Backtest (Last 2 Days)":
                if st.button("🚀 Run Backtest", type="primary", use_container_width=True):
                    st.session_state.signals = []
                    st.session_state.active_trades = []
                    st.session_state.completed_trades = []
                    st.session_state.signal_count_per_stock = {}
                    st.session_state.auto_refresh = False
                    
                    with st.spinner("Running backtest..."):
                        signals = backtest_strategy(selected_symbols, timeframe, strategy, start_date, end_date, risk_amount, selected_mode, **strategy_params)
                        st.session_state.signals = signals
                        st.session_state.active_trades = signals.copy()
                        if signals:
                            st.success(f"✅ Backtest complete! Generated {len(signals)} signals")
                            send_bulk_telegram_alerts(signals) # Sends historical signals to Telegram
                        else:
                            st.warning("⚠️ No signals generated")
                            
            elif selected_mode == "Simulation (Market Closed)":
                if st.button("🚀 Run Simulation", type="primary", use_container_width=True):
                    st.session_state.signals = []
                    st.session_state.active_trades = []
                    st.session_state.completed_trades = []
                    st.session_state.signal_count_per_stock = {}
                    st.session_state.auto_refresh = False
                    
                    with st.spinner("Generating signals..."):
                        signals = simulate_live_signals(selected_symbols, timeframe, strategy, risk_amount, selected_mode, **strategy_params)
                        st.session_state.signals = signals
                        st.session_state.active_trades = signals.copy()
                        if signals:
                            st.success(f"✅ Simulation complete! Generated {len(signals)} signals")
                            send_bulk_telegram_alerts(signals) # Sends simulation signals to Telegram
                        else:
                            st.warning("⚠️ No signals generated")
                            
            else:
                if not st.session_state.auto_refresh:
                    if st.button("🚀 Start Bot", type="primary", use_container_width=True):
                        st.session_state.auto_refresh = True
                        st.session_state.signals = []
                        st.session_state.active_trades = []
                        st.session_state.completed_trades = []
                        st.session_state.signal_count_per_stock = {}
                        st.session_state.refresh_counter = 0
                        startup_msg = "🤖 *Trading Bot Started* 🤖\n\nBot is now running and monitoring for breakout signals.\n\nStrategy: " + strategy + "\nTimeframe: " + timeframe + "\nRisk Amount: ₹" + str(risk_amount) + f"\n\nUpdate Interval: {update_interval} seconds"
                        send_telegram_message_sync(startup_msg)
                        st.rerun()
                else:
                    if st.button("⏹️ Stop Bot", type="secondary", use_container_width=True):
                        st.session_state.auto_refresh = False
                        stop_msg = "🛑 *Trading Bot Stopped* 🛑\n\nBot is no longer monitoring for signals."
                        send_telegram_message_sync(stop_msg)
                        st.rerun()
        
        with col2:
            if st.button("🗑️ Clear Signals", use_container_width=True):
                st.session_state.signals = []
                st.session_state.active_trades = []
                st.session_state.completed_trades = []
                st.session_state.auto_refresh = False
                st.success("Signals cleared!")
        
        st.markdown("---")
        st.subheader("📊 Status")
        
        if selected_mode == "Live Trading":
            if st.session_state.auto_refresh:
                st.success("🟢 BOT RUNNING")
                st.info(f"🔄 Checking every {update_interval} seconds")
                st.info("📨 Telegram alerts: ENABLED")
            else:
                st.warning("🔴 BOT STOPPED")
        else:
            st.info(f"📊 Mode: {selected_mode}")
        
        st.write(f"**Strategy:** {strategy}")
        st.write(f"**Risk per Trade:** ₹{risk_amount:,.0f}")
        st.write(f"**Symbols:** {len(selected_symbols)}")
        st.write(f"**Active Trades:** {len(st.session_state.active_trades)}")
        
        if st.session_state.last_update:
            st.write(f"**Last Update:** {st.session_state.last_update.strftime('%H:%M:%S')}")
    
    # ====================== FIXED LIVE TRADING SECTION ======================
    if selected_mode == "Live Trading":
        if st.session_state.auto_refresh:
            # Live status
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("🔄 Refresh Cycle", st.session_state.refresh_counter)
            with col2:
                if st.session_state.last_check_time:
                    st.metric("⏰ Last Check", st.session_state.last_check_time.strftime('%H:%M:%S'))
                else:
                    st.metric("⏰ Last Check", "Waiting...")
            with col3:
                st.metric("📊 Active Trades", len(st.session_state.active_trades))
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            
            # Monitor active trades
            current_prices = get_current_prices(selected_symbols, timeframe)
            alerts = monitor_active_trades(current_prices)
            if alerts:
                for alert in alerts:
                    st.info(f"📢 {alert}")
            
            # Run cycle
            new_signals = run_bot_cycle(selected_symbols, timeframe, strategy, risk_amount, selected_mode, strategy_params, update_interval, progress_bar, status_text)
            
            if new_signals:
                for signal in new_signals:
                    st.balloons()
                    st.success(f"🎯 {signal['SYMBOL']} - {signal['SIGNAL']} at ₹{signal['ENTRY']}")
            
            # Display
            if st.session_state.signals:
                display_signals_table(st.session_state.signals, "Live Trading Signals")
                display_active_trades()
            else:
                st.info("👀 **Waiting for new signals...** No signals generated yet.")
            
            # Auto refresh
            time.sleep(0.5)
            st.rerun()
        else:
            if st.session_state.signals:
                display_signals_table(st.session_state.signals, "Live Trading Signals")
                display_active_trades()
            else:
                st.info("👈 Click 'Start Bot' to begin live trading")
                
    elif selected_mode == "Backtest (Last 2 Days)":
        if st.session_state.signals:
            display_signals_table(st.session_state.signals, "Backtest Results")
            display_active_trades()
        else:
            st.info("👈 Click 'Run Backtest' to start")
            
    else:
        if st.session_state.signals:
            display_signals_table(st.session_state.signals, "Simulation Results")
            display_active_trades()
        else:
            st.info("👈 Click 'Run Simulation' to start")

if __name__ == "__main__":
    main()
