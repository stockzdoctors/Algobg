import streamlit as st
import pandas as pd
from nsepython import *

st.set_page_config(page_title="Nifty 200 Top Gainers", layout="wide")

st.title("📈 Nifty 200 Top Gainers")

# Get Nifty 200 stock list
def get_nifty200_stocks():
    try:
        data = nse_quote_ltp("NIFTY 200")  # fallback trigger
    except:
        pass

    # Static list (you can later replace with live scrape if needed)
    url = "https://archives.nseindia.com/content/indices/ind_nifty200list.csv"
    df = pd.read_csv(url)
    return df['Symbol'].tolist()

# Fetch stock data
def get_top_gainers():
    symbols = get_nifty200_stocks()
    gainers = []

    for symbol in symbols:
        try:
            quote = nse_eq(symbol)
            change = quote['priceInfo']['pChange']
            price = quote['priceInfo']['lastPrice']

            gainers.append({
                "Symbol": symbol,
                "Price": price,
                "% Change": change
            })
        except:
            continue

    df = pd.DataFrame(gainers)

    # Sort by % Change descending
    df = df.sort_values(by="% Change", ascending=False)

    return df

# Button to fetch data
if st.button("Get Top Gainers"):
    with st.spinner("Fetching data..."):
        df = get_top_gainers()

        st.success("Data Loaded Successfully!")

        st.dataframe(df.head(20), use_container_width=True)

        # Download option
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download CSV",
            data=csv,
            file_name='nifty200_top_gainers.csv',
            mime='text/csv',
        )