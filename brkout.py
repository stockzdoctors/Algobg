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
if 'nifty200_stocks_df' not in st.session_state:
    st.session_state.nifty200_stocks_df = pd.DataFrame()  # Changed to DataFrame
if 'filtered_nifty200_symbols' not in st.session_state:
    st.session_state.filtered_nifty200_symbols = []

# Stock symbols (original)
ORIGINAL_SYMBOLS = ["BANKNIFTY", "NIFTY", "UPL", "INFY", "ULTRACEMCO", "RELIANCE", 
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

# --- NSE NIFTY 200 DATA FETCHING FUNCTION ---
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
        time.sleep(1)
        
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
                        'Previous Close': float(item.get('previousClose', 0)),
                        'Open': float(item.get('open', 0)),
                        'High': float(item.get('dayHigh', 0)),
                        'Low': float(item.get('dayLow', 0)),
                        'Volume': item.get('totalTradedVolume', 0)
                    })
                except (ValueError, TypeError, KeyError):
                    continue
            
            return pd.DataFrame(stocks_data)
        
        return pd.DataFrame()
        
    except Exception as e:
        st.error(f"Error fetching NSE data: {str(e)}")
        return pd.DataFrame()

def filter_nifty200_stocks(df, min_change=2, max_change=5, min_ltp=500, max_ltp=3000):
    """Filter NIFTY 200 stocks based on criteria"""
    if df.empty:
        return df, []
    
    filtered = df[
        (df['Change %'] >= min_change) & 
        (df['Change %'] <= max_change) & 
        (df['LTP'] > min_ltp) & 
        (df['LTP'] < max_ltp)
    ]
    
    filtered = filtered.sort_values('Change %', ascending=False)
    symbols_list = filtered['Symbol'].tolist()
    
    return filtered, symbols_list

# --- TELEGRAM FUNCTIONS ---
def send_telegram_message_sync(message):
    """Send Telegram message using simple HTTP Request"""
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

# --- STRATEGY CLASS ---
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
        today_date = datetime.now().date()
        
        # Filter only Today's Data
        today_df = df[df.index.date == today_date]
        
        if len(today_df) < 1:
            return None

        # Find the VERY FIRST candle of today
        reference_candle = today_df.iloc[0]
        
        high_915 = round_to_2_decimals(reference_candle['high'])
        low_915 = round_to_2_decimals(reference_candle['low'])
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
                    if date_tracker is not None: 
                        date_tracker[key] = True
                    signals.append(signal)
                    break
            
            # SELL Condition
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
                    if date_tracker is not None: 
                        date_tracker[key] = True
                    signals.append(signal)
                    break
        return signals

def fetch_data(symbol, interval, n_bars=100):
    """Fetch historical data for a symbol"""
    try:
        tv = TvDatafeed()
        inv_map = {'5min': Interval.in_5_minute, '15min': Interval.in_15_minute, 'daily': Interval.in_daily}
        return tv.get_hist(symbol=symbol, exchange="NSE", interval=inv_map.get(interval, Interval.in_15_minute), n_bars=n_bars)
    except Exception as e:
        return None

def check_for_new_signals(selected_symbols, timeframe, risk_amount, mode):
    """Check for new signals for selected symbols"""
    all_new_signals = []
    strategy = CandleBreakoutStrategy(timeframe, risk_amount, mode)
    
    for symbol in selected_symbols:
        data = fetch_data(symbol, timeframe)
        if data is not None and not data.empty:
            signals = strategy.analyze(data, symbol, st.session_state.signal_count_per_stock)
            if signals:
                all_new_signals.extend(signals)
                st.success(f"✅ Signal generated for {symbol}!")
    
    return all_new_signals

def display_signals_table(signals, title="Trading Signals"):
    """Display signals in a formatted table"""
    if signals:
        df = pd.DataFrame(signals)
        # Select relevant columns for display
        display_cols = ['SYMBOL', 'SIGNAL', 'ENTRY', 'STOPLOSS', 'T1', 'T2', 'T3', 'QUANTITY', 'ENTRY_TIME']
        display_df = df[display_cols] if all(col in df.columns for col in display_cols) else df
        
        st.dataframe(
            display_df.style.applymap(
                lambda x: 'background-color: #00ff00; color: black' if x == 'BUY' 
                else ('background-color: #ff0000; color: white' if x == 'SELL' else ''),
                subset=['SIGNAL']
            ),
            use_container_width=True,
            height=400
        )

def run_bot_cycle(selected_symbols, timeframe, risk_amount, selected_mode, refresh_interval, progress_bar, status_text):
    """Run one cycle of the trading bot"""
    st.session_state.refresh_counter += 1
    st.session_state.last_check_time = datetime.now()
    
    # Update progress
    for i in range(refresh_interval, 0, -1):
        progress_bar.progress((refresh_interval - i) / refresh_interval)
        status_text.text(f"🔄 Next check in {i} seconds... (Cycle: {st.session_state.refresh_counter})")
        time.sleep(1)
    
    return check_for_new_signals(selected_symbols, timeframe, risk_amount, selected_mode)

# --- MAIN FUNCTION ---
def main():
    st.title("📈 Algorithmic Trading System")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        selected_mode = st.radio("Select Mode", ["Live Trading", "Backtest (Last 2 Days)"])
        risk_amount = st.number_input("Risk per Trade (₹)", 1000, 1000000, 10000)
        timeframe = st.selectbox("Timeframe", ['15min', '5min'])
        update_interval = st.slider("Update Interval (seconds)", 5, 60, 10)
        
        st.markdown("---")
        st.header("📊 NIFTY 200 Filter")
        st.info("Filter NIFTY 200 stocks by Change % and LTP")
        
        min_change = st.number_input("Min Change %", 0.0, 100.0, 2.0, 0.5)
        max_change = st.number_input("Max Change %", 0.0, 100.0, 5.0, 0.5)
        min_ltp = st.number_input("Min LTP (₹)", 0, 10000, 500, 100)
        max_ltp = st.number_input("Max LTP (₹)", 0, 50000, 3000, 100)
        
        # GET DATA Button for NIFTY 200
        if st.button("🚀 GET NIFTY 200 DATA", type="primary", use_container_width=True):
            with st.spinner("Fetching NIFTY 200 stocks from NSE..."):
                nifty_df = fetch_nifty200_stocks()
                if not nifty_df.empty:
                    filtered_df, symbols_list = filter_nifty200_stocks(nifty_df, min_change, max_change, min_ltp, max_ltp)
                    st.session_state.nifty200_stocks_df = filtered_df
                    st.session_state.filtered_nifty200_symbols = symbols_list
                    st.success(f"✅ Found {len(symbols_list)} stocks matching criteria!")
                    st.rerun()
                else:
                    st.error("Failed to fetch NIFTY 200 data")
        
        st.markdown("---")
        
        # Stock selection
        st.header("📈 Stock Selection")
        
        use_nifty200 = st.checkbox("Use NIFTY 200 Filtered Stocks", value=False)
        
        if use_nifty200 and st.session_state.filtered_nifty200_symbols:
            selected_symbols = st.multiselect(
                "Select Stocks for Trading",
                st.session_state.filtered_nifty200_symbols,
                default=st.session_state.filtered_nifty200_symbols[:5] if st.session_state.filtered_nifty200_symbols else []
            )
            st.info(f"📊 {len(selected_symbols)} stocks selected from NIFTY 200 filter")
        else:
            selected_symbols = st.multiselect(
                "Select Stocks for Trading",
                ORIGINAL_SYMBOLS,
                default=["BANKNIFTY", "NIFTY"]
            )
        
        # Bot control buttons
        st.markdown("---")
        if not st.session_state.auto_refresh:
            if st.button("🚀 START BOT", type="primary", use_container_width=True):
                st.session_state.auto_refresh = True
                st.session_state.signals = []
                st.session_state.refresh_counter = 0
                st.session_state.signal_count_per_stock = {}
                st.rerun()
        else:
            if st.button("⏹ STOP BOT", type="secondary", use_container_width=True):
                st.session_state.auto_refresh = False
                st.rerun()
    
    # Main content area
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Bot Status", "🟢 RUNNING" if st.session_state.auto_refresh else "🔴 STOPPED")
    with col2:
        st.metric("Total Signals", len(st.session_state.signals))
    with col3:
        st.metric("Refresh Cycle", st.session_state.refresh_counter)
    with col4:
        st.metric("Last Check", st.session_state.last_check_time.strftime('%H:%M:%S') if st.session_state.last_check_time else "Never")
    
    # Display NIFTY 200 filtered stocks if available
    if st.session_state.nifty200_stocks_df is not None and not st.session_state.nifty200_stocks_df.empty:
        with st.expander("📊 NIFTY 200 Filtered Stocks", expanded=False):
            display_df = st.session_state.nifty200_stocks_df.copy()
            display_df['LTP'] = display_df['LTP'].apply(lambda x: f"₹{x:,.2f}")
            display_df['Change %'] = display_df['Change %'].apply(lambda x: f"{x:+.2f}%")
            st.dataframe(display_df[['Symbol', 'LTP', 'Change %', 'Volume']], use_container_width=True)
    
    st.markdown("---")
    
    # Trading signals section
    st.subheader("📊 Trading Signals")
    
    if st.session_state.auto_refresh and selected_mode == "Live Trading" and selected_symbols:
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Run bot cycle
        new_signals = run_bot_cycle(
            selected_symbols, 
            timeframe, 
            risk_amount, 
            selected_mode, 
            update_interval, 
            progress_bar, 
            status_text
        )
        
        if new_signals:
            st.session_state.signals.extend(new_signals)
            send_bulk_telegram_alerts(new_signals)
            st.balloons()
            st.success(f"🎯 {len(new_signals)} new signals generated!")
        
        # Display all signals
        if st.session_state.signals:
            display_signals_table(st.session_state.signals)
        else:
            st.info("No signals generated yet. Waiting for breakout conditions...")
        
        # Auto refresh
        time.sleep(1)
        st.rerun()
    
    elif st.session_state.auto_refresh and not selected_symbols:
        st.warning("⚠️ Please select at least one stock for trading!")
        st.session_state.auto_refresh = False
        st.rerun()
    
    else:
        # Display existing signals if any
        if st.session_state.signals:
            display_signals_table(st.session_state.signals)
        else:
            st.info("👈 Configure settings and click START BOT to begin trading, or click GET NIFTY 200 DATA to fetch stocks")
        
        # Show instructions
        with st.expander("ℹ️ How to Use", expanded=False):
            st.markdown("""
            **Trading Strategy: Candle Breakout Strategy**
            
            1. **Get NIFTY 200 Data**: Click the button in sidebar to fetch NIFTY 200 stocks filtered by Change % and LTP
            2. **Select Stocks**: Choose stocks from NIFTY 200 filter or original list
            3. **Configure**: Set risk amount, timeframe, and update interval
            4. **Start Bot**: Click START BOT to begin monitoring
            
            **How it works:**
            - First candle of the day (9:15 AM) sets the reference high/low
            - Any subsequent candle breaking these levels generates a BUY/SELL signal
            - One signal per stock per day
            - Risk-Reward ratio: 1:1, 1:2, 1:3
            
            **Telegram Alerts:**
            - Entry signals with entry price, stop loss, and targets
            - Target hit notifications
            - Stop loss hit alerts
            """)
    
    # Footer
    st.markdown("---")
    st.caption(f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Strategy: Candle Breakout | Powered by NSE Data")

if __name__ == "__main__":
    main()
