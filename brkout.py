import streamlit as st
import pandas as pd
import time
from datetime import datetime
import threading
from tvDatafeed import TvDatafeed, Interval
from telegram import Bot
import asyncio
import nest_asyncio

# Setup for Cloud environment
nest_asyncio.apply()

# --- SECRETS CONFIGURATION ---
# --- SECRETS CONFIGURATION ---
TOKEN = st.secrets["TELEGRAM_TOKEN"]
CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
SYMBOLS = ["BANKNIFTY", "NIFTY", "RELIANCE", "INFY", "HDFCBANK", "TCS", "ICICIBANK"]

# Initialize Telegram
telegram_bot = Bot(token=TOKEN)

# Memory for active trades
if 'active_trades' not in st.session_state:
    st.session_state.active_trades = {} 

def send_msg(text):
    """Instant Telegram Sender"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(telegram_bot.send_message(chat_id=CHAT_ID, text=text, parse_mode='Markdown'))
    except Exception as e:
        print(f"Telegram Error: {e}")

def monitor_market():
    """The main background engine"""
    tv = TvDatafeed()
    processed_today = set()

    while True:
        now = datetime.now()
        
        # Indian Market Hours check (9:16 AM to 3:30 PM)
        if (now.hour == 9 and now.minute >= 16) or (9 < now.hour < 15) or (now.hour == 15 and now.minute <= 30):
            current_date = now.strftime("%Y-%m-%d")
            
            for symbol in SYMBOLS:
                try:
                    # 1. Fetch Data
                    df = tv.get_hist(symbol=symbol, exchange="NSE", interval=Interval.in_15_minute, n_bars=50)
                    if df is None or df.empty:
                        continue
                    
                    df.index = pd.to_datetime(df.index)
                    today_df = df[df.index.date == now.date()]
                    if len(today_df) < 1:
                        continue

                    # 2. Set 9:15 Candle Levels
                    candle_915 = today_df.iloc[0]
                    high_915 = round(float(candle_915['high']), 2)
                    low_915 = round(float(candle_915['low']), 2)
                    current_price = round(float(df['close'].iloc[-1]), 2)
                    range_size = high_915 - low_915

                    # 3. MONITOR ACTIVE TRADES (Target/SL Tracking)
                    if symbol in st.session_state.active_trades:
                        trade = st.session_state.active_trades[symbol]
                        
                        # --- BUY EXIT LOGIC ---
                        if trade['type'] == 'BUY':
                            if current_price >= trade['target']:
                                send_msg(f"🎯 *TARGET HIT: {symbol}*\nExit Price: {current_price}\nProfit Booked! ✅")
                                del st.session_state.active_trades[symbol]
                            elif current_price <= trade['sl']:
                                send_msg(f"🛑 *STOP LOSS HIT: {symbol}*\nExit Price: {current_price}\nTrade Closed. ❌")
                                del st.session_state.active_trades[symbol]
                        
                        # --- SELL EXIT LOGIC ---
                        elif trade['type'] == 'SELL':
                            if current_price <= trade['target']:
                                send_msg(f"🎯 *TARGET HIT: {symbol}*\nExit Price: {current_price}\nProfit Booked! ✅")
                                del st.session_state.active_trades[symbol]
                            elif current_price >= trade['sl']:
                                send_msg(f"🛑 *STOP LOSS HIT: {symbol}*\nExit Price: {current_price}\nTrade Closed. ❌")
                                del st.session_state.active_trades[symbol]
                        
                        continue # Skip entry check if trade is already active

                    # 4. CHECK FOR NEW BREAKOUTS
                    trade_key = f"{symbol}_{current_date}"
                    if trade_key not in processed_today:
                        
                        # BUY BREAKOUT (Price crosses above 9:15 High)
                        if current_price > high_915:
                            target = round(high_915 + range_size, 2)
                            sl = low_915
                            
                            msg = f"🚀 *ENTRY SIGNAL: {symbol}*\nAction: **BUY**\nPrice: {current_price}\n🎯 Target: {target}\n🛑 SL: {sl}"
                            send_msg(msg)
                            
                            st.session_state.active_trades[symbol] = {
                                'type': 'BUY', 'entry': current_price, 'target': target, 'sl': sl
                            }
                            processed_today.add(trade_key)

                        # SELL BREAKOUT (Price crosses below 9:15 Low)
                        elif current_price < low_915:
                            target = round(low_915 - range_size, 2)
                            sl = high_915
                            
                            msg = f"📉 *ENTRY SIGNAL: {symbol}*\nAction: **SELL**\nPrice: {current_price}\n🎯 Target: {target}\n🛑 SL: {sl}"
                            send_msg(msg)
                            
                            st.session_state.active_trades[symbol] = {
                                'type': 'SELL', 'entry': current_price, 'target': target, 'sl': sl
                            }
                            processed_today.add(trade_key)

                except Exception as e:
                    print(f"Error checking {symbol}: {e}")

        # High-speed check every 10 seconds
        time.sleep(10)

# --- WEB DASHBOARD ---
st.set_page_config(page_title="24/7 NSE Bot", layout="wide")
st.title("🤖 24/7 Algorithmic Trading Bot")

if 'bg_running' not in st.session_state:
    # Start the engine
    t = threading.Thread(target=monitor_market, daemon=True)
    t.start()
    st.session_state.bg_running = True
    send_msg("📟 *NSE Algo Bot is now LIVE and Monitoring...*")

st.divider()

col1, col2 = st.columns(2)
with col1:
    st.subheader("📊 Active Monitoring List")
    st.write(SYMBOLS)

with col2:
    st.subheader("🟡 Current Open Positions")
    if st.session_state.active_trades:
        st.json(st.session_state.active_trades)
    else:
        st.info("No active trades. Waiting for 9:15 breakout.")

st.sidebar.write(f"**Server Status:** 🟢 Active")
st.sidebar.write(f"**Last Sync:** {datetime.now().strftime('%H:%M:%S')}")
