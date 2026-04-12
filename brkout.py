import streamlit as st
import pandas as pd
import time
from datetime import datetime, timedelta
import threading
from tvDatafeed import TvDatafeed, Interval
from telegram import Bot
import asyncio
import nest_asyncio

nest_asyncio.apply()

# --- SECRETS ---
TOKEN = st.secrets["TELEGRAM_TOKEN"]
CHAT_ID = st.secrets["TELEGRAM_CHAT_ID"]
SYMBOLS = ["BANKNIFTY", "NIFTY", "RELIANCE", "INFY", "HDFCBANK"]

telegram_bot = Bot(token=TOKEN)

if 'active_trades' not in st.session_state:
    st.session_state.active_trades = {}

def send_msg(text):
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(telegram_bot.send_message(chat_id=CHAT_ID, text=text, parse_mode='Markdown'))
    except Exception as e:
        print(f"Telegram Error: {e}")

def process_logic(symbol, df, target_date, processed_set):
    """Core Logic to check breakouts"""
    df.index = pd.to_datetime(df.index)
    day_df = df[df.index.date == target_date]
    
    if len(day_df) < 1: return

    candle_915 = day_df.iloc[0]
    high_915 = round(float(candle_915['high']), 2)
    low_915 = round(float(candle_915['low']), 2)
    current_price = round(float(day_df['close'].iloc[-1]), 2)
    range_size = high_915 - low_915

    trade_key = f"{symbol}_{target_date}"
    
    if trade_key not in processed_set:
        if current_price > high_915:
            msg = f"🚀 *TEST ENTRY (BUY): {symbol}*\nDate: {target_date}\nPrice: {current_price}\n🎯 Target: {round(high_915 + range_size, 2)}\n🛑 SL: {low_915}"
            send_msg(msg)
            processed_set.add(trade_key)
        elif current_price < low_915:
            msg = f"📉 *TEST ENTRY (SELL): {symbol}*\nDate: {target_date}\nPrice: {current_price}\n🎯 Target: {round(low_915 - range_size, 2)}\n🛑 SL: {high_915}"
            send_msg(msg)
            processed_set.add(trade_key)

def monitor_market():
    tv = TvDatafeed()
    processed_today = set()
    while True:
        now = datetime.now()
        # Market Hours: 9:16 to 15:30
        if (now.hour == 9 and now.minute >= 16) or (9 < now.hour < 15) or (now.hour == 15 and now.minute <= 30):
            for symbol in SYMBOLS:
                try:
                    df = tv.get_hist(symbol=symbol, exchange="NSE", interval=Interval.in_15_minute, n_bars=50)
                    if df is not None:
                        process_logic(symbol, df, now.date(), processed_today)
                except: pass
        time.sleep(10)

# --- DASHBOARD ---
st.title("🤖 NSE Algo Bot & Tester")

# 1. TEST BUTTON
if st.button("🧪 Test Last 2 Days"):
    st.warning("Running test for last 2 working days... Check Telegram!")
    tv = TvDatafeed()
    test_processed = set()
    # Get last 2 dates
    for i in range(1, 4): # Check last 3 days to find 2 working days
        test_date = (datetime.now() - timedelta(days=i)).date()
        for symbol in SYMBOLS:
            try:
                df = tv.get_hist(symbol=symbol, exchange="NSE", interval=Interval.in_15_minute, n_bars=200)
                process_logic(symbol, df, test_date, test_processed)
            except: pass
    st.success("Test Completed!")

# 2. START BOT BUTTON
if st.sidebar.button("🚀 Start Live Bot"):
    if 'bg_running' not in st.session_state:
        t = threading.Thread(target=monitor_market, daemon=True)
        t.start()
        st.session_state.bg_running = True
        send_msg("📟 *Bot Started Manually!* Monitoring Live NSE Breakouts.")
        st.sidebar.success("Bot is now Running!")
    else:
        st.sidebar.info("Bot is already active.")

st.divider()
st.write("### Symbols Monitored:", SYMBOLS)
if 'bg_running' in st.session_state:
    st.write("**Status:** 🟢 Live Monitoring Active")
else:
    st.write("**Status:** ⚪ Standing By (Click Start Bot)")
