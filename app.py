import streamlit as st

st.set_page_config(
    page_title="Algo Trading System",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🎯 Algorithmic Trading System")
st.markdown("---")

st.markdown("""
## Welcome to the Trading System

### Select a page from the sidebar to get started:

1. **📊 Stock Screener** - Fetch and filter NIFTY 200 stocks
2. **🤖 Trading Bot** - Run automated trading with selected stocks

### Workflow:
1. Go to **Stock Screener** → Fetch NIFTY 200 data → Filter stocks → Click "Save for Trading"
2. Go to **Trading Bot** → Load saved stocks → Start bot

### Features:
- Real-time NIFTY 200 data from NSE
- Custom filtering by change % and price
- Automated breakout strategy
- Telegram alerts for signals
""")

st.markdown("---")
st.info("👈 **Select a page from the left sidebar to continue**")
