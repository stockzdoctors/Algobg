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
if 'filtered_stocks' not in st.session_state:
    st.session_state.filtered_stocks = []
if 'filtered_df' not in st.session_state:
    st.session_state.filtered_df = pd.DataFrame()
if 'use_filtered' not in st.session_state:
    st.session_state.use_filtered = False

# Stock symbols - Complete NIFTY 200 List (200+ stocks)
SYMBOLS = [
    "GROWW", "HDFCBANK", "ICICIBANK", "VEDL", "BSE", "TCS", "INFY", "LT", 
    "HINDALCO", "MCX", "ETERNAL", "RELIANCE", "SBIN", "ADANIPOWER", "BHARTIARTL", 
    "SUZLON", "MARUTI", "INDIGO", "SHRIRAMFIN", "TATAPOWER", "M&M", "HAL", 
    "WAAREEENER", "HINDZINC", "BPCL", "DIXON", "DRREDDY", "AXISBANK", "NATIONALUM", 
    "EICHERMOT", "SIEMENS", "ICICIAMC", "LGEINDIA", "POWERINDIA", "BAJFINANCE", 
    "MAZDOCK", "TATASTEEL", "ITC", "WIPRO", "BAJAJ-AUTO", "JIOFIN", "ADANIENT", 
    "PFC", "ADANIPORTS", "TMCV", "KOTAKBANK", "JSWENERGY", "ADANIGREEN", "GVT&D", 
    "INDUSTOWER", "BEL", "IDEA", "BOSCHLTD", "BHEL", "LODHA", "TMPV", "HINDPETRO", 
    "CANBK", "ONGC", "HCLTECH", "ASHOKLEY", "HDFCLIFE", "SUNPHARMA", "HDFCAMC", 
    "MUTHOOTFIN", "APOLLOHOSP", "PAGEIND", "HEROMOTOCO", "SWIGGY", "RVNL", "OIL", 
    "PERSISTENT", "CGPOWER", "SAIL", "MOTHERSON", "COALINDIA", "ABB", "SOLARINDS", 
    "MAXHEALTH", "POLYCAB", "SBILIFE", "IOC", "TITAN", "CUMMINSIND", "MPHASIS", 
    "ADANIENSOL", "BANKBARODA", "ASIANPAINT", "NMDC", "GODFRYPHLP", "POWERGRID", 
    "COFORGE", "SHREECEM", "VBL", "PRESTIGE", "NTPC", "DMART", "LAURUSLABS", 
    "PREMIERENE", "INDIANB", "TORNTPHARM", "HINDUNILVR", "BLUESTARCO", "ATGL", 
    "COCHINSHIP", "GAIL", "INDUSINDBK", "GMRAIRPORT", "TVSMOTOR", "IRFC", "LTM", 
    "UNIONBANK", "TRENT", "CHOLAFIN", "360ONE", "AUROPHARMA", "RECLTD", "ULTRACEMCO", 
    "TATAINVEST", "PNB", "OFSS", "LTF", "INDHOTEL", "GRASIM", "LENSKART", "KALYANKJIL", 
    "YESBANK", "FEDERALBNK", "AMBUJACEM", "BDL", "DLF", "APLAPOLLO", "UNITDSPR", 
    "HYUNDAI", "IRCTC", "AUBANK", "TATAELXSI", "VOLTAS", "PAYTM", "JINDALSTEL", 
    "ASTRAL", "GODREJPROP", "IDFCFIRSTB", "TECHM", "BAJAJFINSV", "OBEROIRLTY", 
    "RADICO", "BHARATFORG", "ABCAPITAL", "BRITANNIA", "DABUR", "PIIND", "ENRIN", 
    "IREDA", "KPITTECH", "JUBLFOOD", "NHPC", "NAUKRI", "PATANJALI", "LUPIN", 
    "ICICIGI", "BANKINDIA", "POLICYBZR", "PIDILITIND", "CIPLA", "JSWSTEEL", 
    "BIOCON", "HUDCO", "NESTLEIND", "MFSL", "VMM", "GLENMARK", "DIVISLAB", 
    "MARICO", "KEI", "UPL", "TATACONSUM", "MRF", "FORTIS", "MOTILALOFS", 
    "CONCOR", "SRF", "TATACAP", "HAVELLS", "LICHSGFIN", "GODREJCP", "M&MFIN", 
    "MANKIND", "BAJAJHLDNG", "TIINDIA", "COLPAL", "EXIDEIND", "SBICARD", 
    "COROMANDEL", "SUPREMEIND", "NYKAA", "ALKEM", "PHOENIXLTD", "ZYDUSLIFE", "TATACOMM"
]

# Simple disclaimer for Telegram
DISCLAIMER = """
━━━━━━━━━━━━━━━━━━
📢 **EDUCATIONAL DISCLAIMER:**
This is for STUDY & ANALYSIS only.
We are NOT SEBI registered advisors.
No trading recommendations provided.
Always consult registered experts.
━━━━━━━━━━━━━━━━━━"""

# --- FETCH STOCK DATA FROM TVDATAFEED ---
@st.cache_data(ttl=300)
def fetch_stocks_data_from_tv(symbols_list):
    """Fetch current stock data (LTP, Change %) from TVDatafeed for multiple symbols"""
    stocks_data = []
    tv = TvDatafeed()
    
    with st.spinner(f"Fetching data for {len(symbols_list)} stocks..."):
        for symbol in symbols_list:
            try:
                # Fetch daily data to get current price and change
                data = tv.get_hist(symbol=symbol, exchange="NSE", interval=Interval.in_daily, n_bars=2)
                if data is not None and len(data) >= 2:
                    current_price = round(float(data['close'].iloc[-1]), 2)
                    prev_close = round(float(data['close'].iloc[-2]), 2)
                    change_percent = round(((current_price - prev_close) / prev_close) * 100, 2)
                    
                    stocks_data.append({
                        'Symbol': symbol,
                        'LTP': current_price,
                        'Change %': change_percent,
                        'Volume': int(data['volume'].iloc[-1]) if 'volume' in data else 0,
                        'Open': round(float(data['open'].iloc[-1]), 2),
                        'High': round(float(data['high'].iloc[-1]), 2),
                        'Low': round(float(data['low'].iloc[-1]), 2),
                        'Prev Close': prev_close
                    })
                time.sleep(0.3)  # Rate limiting
            except:
                continue
    
    return pd.DataFrame(stocks_data)

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
    """Strategy: First candle reference, any future candle breakout, one signal per day"""
    
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
        
        # Filter only Today's Data
        today_df = df[df.index.date == today_date]
        
        if len(today_df) < 1:
            return None

        # Find the VERY FIRST candle of today
        reference_candle = today_df.iloc[0]
        
        high_ref = round_to_2_decimals(reference_candle['high'])
        low_ref = round_to_2_decimals(reference_candle['low'])
        date_str = today_date.strftime('%Y-%m-%d')
        
        if date_tracker is not None:
            key = f"{symbol}_{date_str}"
            if date_tracker.get(key, False):
                return None
        
        # Check every candle from the 2nd candle onwards to find a breakout
        for i in range(1, len(today_df)):
            current_candle = today_df.iloc[i]
            current_high = round_to_2_decimals(current_candle['high'])
            current_low = round_to_2_decimals(current_candle['low'])
            
            # BUY Condition
            if current_high > high_ref:
                entry = high_ref
                stop_loss = low_ref
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
            
            # SELL Condition
            elif current_low < low_ref:
                entry = low_ref
                stop_loss = high_ref
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

class MovingAverageCrossStrategy:
    def __init__(self, timeframe='15min', fast_ma=9, slow_ma=21, risk_amount=10000, mode="Live Trading"):
        self.timeframe, self.fast_ma, self.slow_ma, self.risk_amount, self.mode = timeframe, fast_ma, slow_ma, risk_amount, mode
    def analyze(self, df, symbol, date_tracker=None):
        return None

class RSIBreakoutStrategy:
    def __init__(self, timeframe='15min', rsi_period=14, risk_amount=10000, mode="Live Trading"):
        self.timeframe, self.rsi_period, self.risk_amount, self.mode = timeframe, rsi_period, risk_amount, mode
    def analyze(self, df, symbol, date_tracker=None):
        return None

def fetch_data(symbol, interval, n_bars=100):
    try:
        tv = TvDatafeed()
        inv_map = {'5min': Interval.in_5_minute, '15min': Interval.in_15_minute, 'daily': Interval.in_daily}
        return tv.get_hist(symbol=symbol, exchange="NSE", interval=inv_map.get(interval, Interval.in_15_minute), n_bars=n_bars)
    except: 
        return None

# ------------------------- NEW: Monitor active trades for target/SL hits -------------------------
def monitor_active_trades():
    """Check all active trades for target or stop-loss hits and send alerts"""
    tv = TvDatafeed()
    trades_to_remove = []
    
    for trade in st.session_state.active_trades:
        symbol = trade['SYMBOL']
        try:
            # Fetch latest price (1-min interval for real-time)
            data = tv.get_hist(symbol=symbol, exchange="NSE", interval=Interval.in_1_minute, n_bars=1)
            if data is None or data.empty:
                continue
            current_price = round(float(data['close'].iloc[-1]), 2)
            
            if trade['SIGNAL'] == 'BUY':
                # Check Stop Loss
                if not trade.get('STOPLOSS_HIT', False) and current_price <= trade['STOPLOSS']:
                    pnl = (trade['STOPLOSS'] - trade['ENTRY']) * trade['QUANTITY']
                    trade['PNL'] = pnl
                    send_telegram_alert(trade, "STOPLOSS")
                    trade['STOPLOSS_HIT'] = True
                    trades_to_remove.append(trade)
                    continue
                
                # Check Targets
                if not trade.get('T1_HIT', False) and current_price >= trade['T1']:
                    pnl = (trade['T1'] - trade['ENTRY']) * trade['QUANTITY']
                    trade['PNL'] = pnl
                    send_telegram_alert(trade, "TARGET1")
                    trade['T1_HIT'] = True
                
                if not trade.get('T2_HIT', False) and current_price >= trade['T2']:
                    pnl = (trade['T2'] - trade['ENTRY']) * trade['QUANTITY']
                    trade['PNL'] = pnl
                    send_telegram_alert(trade, "TARGET2")
                    trade['T2_HIT'] = True
                
                if not trade.get('T3_HIT', False) and current_price >= trade['T3']:
                    pnl = (trade['T3'] - trade['ENTRY']) * trade['QUANTITY']
                    trade['PNL'] = pnl
                    send_telegram_alert(trade, "TARGET3")
                    trade['T3_HIT'] = True
                    trades_to_remove.append(trade)
            
            else:  # SELL trade
                if not trade.get('STOPLOSS_HIT', False) and current_price >= trade['STOPLOSS']:
                    pnl = (trade['ENTRY'] - trade['STOPLOSS']) * trade['QUANTITY']
                    trade['PNL'] = pnl
                    send_telegram_alert(trade, "STOPLOSS")
                    trade['STOPLOSS_HIT'] = True
                    trades_to_remove.append(trade)
                    continue
                
                if not trade.get('T1_HIT', False) and current_price <= trade['T1']:
                    pnl = (trade['ENTRY'] - trade['T1']) * trade['QUANTITY']
                    trade['PNL'] = pnl
                    send_telegram_alert(trade, "TARGET1")
                    trade['T1_HIT'] = True
                
                if not trade.get('T2_HIT', False) and current_price <= trade['T2']:
                    pnl = (trade['ENTRY'] - trade['T2']) * trade['QUANTITY']
                    trade['PNL'] = pnl
                    send_telegram_alert(trade, "TARGET2")
                    trade['T2_HIT'] = True
                
                if not trade.get('T3_HIT', False) and current_price <= trade['T3']:
                    pnl = (trade['ENTRY'] - trade['T3']) * trade['QUANTITY']
                    trade['PNL'] = pnl
                    send_telegram_alert(trade, "TARGET3")
                    trade['T3_HIT'] = True
                    trades_to_remove.append(trade)
                    
        except Exception as e:
            print(f"Error monitoring {symbol}: {e}")
    
    # Move completed trades to completed_trades list
    for trade in trades_to_remove:
        if trade in st.session_state.active_trades:
            st.session_state.active_trades.remove(trade)
            st.session_state.completed_trades.append(trade)
# ---------------------------------------------------------------------------------------------

def check_for_new_signals(selected_symbols, timeframe, strategy_name, risk_amount, mode, existing_signals, **strategy_params):
    all_new_signals = []
    if strategy_name == "Candle Breakout Strategy":
        strategy = CandleBreakoutStrategy(timeframe, risk_amount, mode)
    else:
        strategy = CandleBreakoutStrategy(timeframe, risk_amount, mode)
    
    for symbol in selected_symbols:
        data = fetch_data(symbol, timeframe)
        if data is not None:
            signals = strategy.analyze(data, symbol, st.session_state.signal_count_per_stock)
            if signals: 
                for signal in signals:
                    # Add missing flag for stop loss hit
                    signal['STOPLOSS_HIT'] = False
                    # Add to active trades for monitoring
                    st.session_state.active_trades.append(signal)
                all_new_signals.extend(signals)
        time.sleep(0.3)  # Rate limiting
    return all_new_signals

def run_bot_cycle(selected_symbols, timeframe, strategy, risk_amount, selected_mode, strategy_params, refresh_interval, progress_bar, status_text):
    st.session_state.refresh_counter += 1
    st.session_state.last_check_time = datetime.now()
    
    # Monitor active trades first (for T1/T2/T3/SL alerts)
    monitor_active_trades()
    
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
        st.subheader("📊 Stock Filter (TVDatafeed)")
        
        min_change = st.number_input("Min Change %", 0.0, 100.0, 2.0, 0.5)
        max_change = st.number_input("Max Change %", 0.0, 100.0, 5.0, 0.5)
        min_ltp = st.number_input("Min LTP (₹)", 0, 10000, 500, 100)
        max_ltp = st.number_input("Max LTP (₹)", 0, 50000, 3000, 100)
        
        if st.button("🚀 GET STOCK DATA", type="primary", use_container_width=True):
            with st.spinner("Fetching stock data from TVDatafeed..."):
                stocks_df = fetch_stocks_data_from_tv(SYMBOLS)
                if not stocks_df.empty:
                    filtered = stocks_df[
                        (stocks_df['Change %'] >= min_change) & 
                        (stocks_df['Change %'] <= max_change) & 
                        (stocks_df['LTP'] > min_ltp) & 
                        (stocks_df['LTP'] < max_ltp)
                    ]
                    st.session_state.filtered_stocks = filtered['Symbol'].tolist()
                    st.session_state.filtered_df = filtered
                    st.success(f"✅ Found {len(st.session_state.filtered_stocks)} stocks!")
                    st.rerun()
                else:
                    st.error("Failed to fetch data")
        
        st.markdown("---")
        
        # Option to use filtered stocks (checkbox in sidebar)
        if st.session_state.filtered_stocks:
            st.session_state.use_filtered = st.checkbox("📌 Use Filtered Stocks for Trading", value=st.session_state.use_filtered)
            
            if st.session_state.use_filtered:
                st.info(f"✅ Trading with {len(st.session_state.filtered_stocks)} filtered stocks")
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
    
    # --- MAIN PAGE CONTENT ---
    
    # Display Filtered Stocks on Main Page
    if st.session_state.filtered_df is not None and not st.session_state.filtered_df.empty:
        st.subheader("📊 Filtered Stocks (Data from TVDatafeed)")
        st.markdown(f"**Criteria:** Change % {min_change}% to {max_change}% | LTP ₹{min_ltp} to ₹{max_ltp}")
        
        # Create metrics row
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Stocks Found", len(st.session_state.filtered_df))
        with col2:
            st.metric("Avg Change %", f"{st.session_state.filtered_df['Change %'].mean():.2f}%")
        with col3:
            st.metric("Max Change %", f"{st.session_state.filtered_df['Change %'].max():.2f}%")
        with col4:
            st.metric("Avg LTP", f"₹{st.session_state.filtered_df['LTP'].mean():,.2f}")
        
        # Display the table with OHLC data
        display_df = st.session_state.filtered_df.copy()
        display_df['LTP'] = display_df['LTP'].apply(lambda x: f"₹{x:,.2f}")
        display_df['Change %'] = display_df['Change %'].apply(lambda x: f"{x:+.2f}%")
        display_df['Volume'] = display_df['Volume'].apply(lambda x: f"{int(x):,}")
        display_df['Open'] = display_df['Open'].apply(lambda x: f"₹{x:,.2f}")
        display_df['High'] = display_df['High'].apply(lambda x: f"₹{x:,.2f}")
        display_df['Low'] = display_df['Low'].apply(lambda x: f"₹{x:,.2f}")
        
        st.dataframe(display_df[['Symbol', 'LTP', 'Change %', 'Open', 'High', 'Low', 'Volume']], 
                    use_container_width=True, height=300)
        st.markdown("---")
    
    # Bot Status and Signals
    if st.session_state.auto_refresh and selected_mode == "Live Trading":
        col1, col2, col3 = st.columns(3)
        col1.metric("Bot Status", "🟢 RUNNING")
        col2.metric("Cycle", st.session_state.refresh_counter)
        col3.metric("Time", datetime.now().strftime('%H:%M:%S'))
        
        # Show active trading symbols
        trading_symbols = st.session_state.filtered_stocks if (st.session_state.use_filtered and st.session_state.filtered_stocks) else SYMBOLS
        st.info(f"🎯 Monitoring {len(trading_symbols)} stocks for signals")
        
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
        # Display when bot is not running
        if st.session_state.filtered_stocks:
            st.info("✅ Click **Start Bot** to begin monitoring these stocks for trading signals")
        else:
            st.info("👈 **Get Started:** Click 'GET STOCK DATA' in sidebar to fetch stock data, then click 'Start Bot'")
        
        # Show existing signals if any
        if st.session_state.signals:
            st.subheader(f"📋 Previous Signals ({len(st.session_state.signals)})")
            display_signals_table(st.session_state.signals)
        
        # Instructions
        with st.expander("ℹ️ How to Use", expanded=False):
            st.markdown("""
            **Step 1:** Set filter criteria in sidebar (Change % and LTP)
            
            **Step 2:** Click **GET STOCK DATA** to fetch live data from TVDatafeed
            
            **Step 3:** Check **Use Filtered Stocks for Trading** (optional)
            
            **Step 4:** Click **Start Bot** to begin monitoring
            
            **Strategy:** Candle Breakout - First candle of the day sets reference, any breakout generates signal
            
            **Data Source:** TVDatafeed (Real-time NSE Data)
            """)

if __name__ == "__main__":
    main()
