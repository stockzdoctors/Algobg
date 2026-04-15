import streamlit as st
import pandas as pd
import requests
import time
import os

st.set_page_config(
    page_title="Stock Screener",
    page_icon="📊",
    layout="wide"
)

# Custom CSS to remove branding
st.markdown("""
    <style>
        [data-testid="stHeader"] { display: none !important; }
        [data-testid="stFooter"], footer { display: none !important; }
        [data-testid="stToolbar"] { display: none !important; }
        .viewerBadge_container__1QSob, .stAppDeployButton { display: none !important; }
        .main .block-container { padding-top: 2rem !important; }
    </style>
""", unsafe_allow_html=True)

st.title("📊 NIFTY 200 Stock Screener")
st.markdown("---")

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
        time.sleep(2)  # Increased delay
        
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
        st.error(f"Error: {str(e)}")
        return pd.DataFrame()

# Sidebar filters
st.sidebar.header("🔍 Filter Criteria")
min_change = st.sidebar.number_input("Min Change %", 0.0, 100.0, 2.0, 0.5)
max_change = st.sidebar.number_input("Max Change %", 0.0, 100.0, 5.0, 0.5)
min_ltp = st.sidebar.number_input("Min LTP (₹)", 0, 10000, 500, 100)
max_ltp = st.sidebar.number_input("Max LTP (₹)", 0, 50000, 3000, 100)

# Main content
col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    if st.button("🚀 FETCH NIFTY 200 DATA", type="primary", use_container_width=True):
        with st.spinner("Fetching NIFTY 200 stocks from NSE..."):
            df_stocks = fetch_nifty200_stocks()
            
            if not df_stocks.empty:
                st.session_state['stock_data'] = df_stocks
                st.session_state['last_update'] = time.time()
                st.success(f"✅ Successfully fetched {len(df_stocks)} NIFTY 200 stocks!")
            else:
                st.error("❌ Failed to fetch data. Try again in a few minutes.")
                st.session_state['stock_data'] = pd.DataFrame()

# Display and filter data
if 'stock_data' in st.session_state and not st.session_state['stock_data'].empty:
    df = st.session_state['stock_data']
    
    # Apply filters
    filtered_df = df[
        (df['Change %'] >= min_change) & 
        (df['Change %'] <= max_change) & 
        (df['LTP'] > min_ltp) & 
        (df['LTP'] < max_ltp)
    ].sort_values('Change %', ascending=False)
    
    # Metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Total NIFTY 200", len(df))
    with col2:
        st.metric("Filtered Stocks", len(filtered_df))
    with col3:
        if not filtered_df.empty:
            st.metric("Max Change %", f"{filtered_df['Change %'].max():.2f}%")
    with col4:
        if not filtered_df.empty:
            st.metric("Avg LTP", f"₹{filtered_df['LTP'].mean():.0f}")
    
    st.markdown("---")
    
    if not filtered_df.empty:
        st.subheader(f"📋 Filtered Stocks ({len(filtered_df)} stocks)")
        
        # Display table
        display_df = filtered_df.copy()
        display_df['LTP'] = display_df['LTP'].apply(lambda x: f"₹{x:,.2f}")
        display_df['Change %'] = display_df['Change %'].apply(lambda x: f"{x:+.2f}%")
        display_df['Volume'] = display_df['Volume'].apply(lambda x: f"{int(x):,}")
        
        st.dataframe(display_df[['Symbol', 'Company Name', 'LTP', 'Change %', 'Volume']], 
                    use_container_width=True, height=400)
        
        # Save button
        col1, col2 = st.columns(2)
        with col1:
            if st.button("💾 SAVE FOR TRADING BOT", type="primary", use_container_width=True):
                # Save to session state for trading bot
                st.session_state['saved_stocks'] = filtered_df['Symbol'].tolist()
                st.session_state['saved_stocks_df'] = filtered_df
                st.success(f"✅ Saved {len(filtered_df)} stocks! Go to Trading Bot page.")
                
        with col2:
            # Download CSV
            csv = filtered_df.to_csv(index=False)
            st.download_button("📥 Download CSV", csv, "nifty200_filtered.csv", "text/csv", use_container_width=True)
        
        # Top gainers
        st.subheader("🏆 Top 5 Gainers")
        top_stocks = filtered_df.nlargest(5, 'Change %')[['Company Name', 'LTP', 'Change %']]
        top_stocks['LTP'] = top_stocks['LTP'].apply(lambda x: f"₹{x:,.2f}")
        top_stocks['Change %'] = top_stocks['Change %'].apply(lambda x: f"{x:+.2f}%")
        st.dataframe(top_stocks, use_container_width=True)
        
    else:
        st.warning("No stocks match the filter criteria. Try adjusting the filters.")

st.markdown("---")
st.caption("Data refreshes every 5 minutes | NSE India - NIFTY 200 Index")
