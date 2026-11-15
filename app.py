import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="Gold & BTC Confluence", page_icon="🎯", layout="wide")
st.title("🎯 VIP Confluence Dashboard (Gold & BTC)")
st.markdown("---")

# ==========================================
# 1. الإعدادات
# ==========================================
timeframe = st.sidebar.selectbox("فريم الدخول", ["15m", "5m", "1h"], index=0)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 إعدادات إدارة المخاطر")
pip_size = st.sidebar.number_input("حجم النقطة (للدهب 0.1 | للبيتكوين 1.0)", value=0.1, step=0.1, format="%.1f")
sl_pips = st.sidebar.number_input("الستوب لوز (نقطة)", value=50, step=10)
tp1_pips = st.sidebar.number_input("الهدف (نقطة)", value=100, step=10)

# ==========================================
# 2. دوال مساعدة
# ==========================================
@st.cache_data(ttl=60)
def get_data(symbol, period, interval):
    data = yf.download(tickers=symbol, period=period, interval=interval, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    if data.index.tz is None:
        data.index = data.index.tz_localize('UTC')
    else:
        data.index = data.index.tz_convert('UTC')
    return data.dropna()

def calculate_smc_logic(df):
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # Sweep (السيولة على 10 شموع)
    df['Prev_Low_10'] = df['Low'].rolling(window=10).min().shift(1)
    df['Prev_High_10'] = df['High'].rolling(window=10).max().shift(1)
    df['Sweep_Low'] = (df['Low'] < df['Prev_Low_10']) & (df['Close'] > df['Prev_Low_10'])
    df['Sweep_High'] = (df['High'] > df['Prev_High_10']) & (df['Close'] < df['Prev_High_10'])
    
    # FVG و OB
    df['FVG_Bull'] = df['Low'] > df['High'].shift(2)
    df['FVG_Bear'] = df['High'] < df['Low'].shift(2)
    df['OB_Bull'] = (df['Close'].shift(1) < df['Open'].shift(1)) & (df['Close'] > df['Open']) & (df['Close'] > df['High'].shift(1))
    df['OB_Bear'] = (df['Close'].shift(1) > df['Open'].shift(1)) & (df['Close'] < df['Open']) & (df['Close'] < df['Low'].shift(1))
    
    return df

def analyze_asset(symbol, name, pip_size, sl_pips, tp1_pips):
    try:
        df = get_data(symbol, "60d", timeframe)
        df = calculate_smc_logic(df)
        
        last = df.iloc[-1]
        entry_price = float(last['Close'])
        
        buy_cond = last['Sweep_Low'] and (last['OB_Bull'] or last['FVG_Bull']) and (last['RSI'] > 45)
        sell_cond = last['Sweep_High'] and (last['OB_Bear'] or last['FVG_Bear']) and (last['RSI'] < 55)

        if buy_cond:
            signal, color = "BUY", "#00FF00"
            sl = entry_price - (sl_pips * pip_size)
            tp1 = entry_price + (tp1_pips * pip_size)
        elif sell_cond:
            signal, color = "SELL", "#FF0000"
            sl = entry_price + (sl_pips * pip_size)
            tp1 = entry_price - (tp1_pips * pip_size)
        else:
            signal, color = "WAITING", "gray"
            sl, tp1 = 0, 0

        return {
            "name": name, "signal": signal, "color": color, 
            "entry": entry_price, "sl": sl, "tp1": tp1, "rsi": last['RSI']
        }
    except Exception as e:
        return {"name": name, "signal": "ERROR", "color": "red", "entry": 0, "sl": 0, "tp1": 0, "rsi": 0}

# ==========================================
# 3. الواجهة الرئيسية
# ==========================================
if st.sidebar.button("🚀 تحليل الذهب والبيتكوين الآن", use_container_width=True):
    with st.spinner('جاري تحليل السوق...'):
        
        # توقيت المغرب
        tz_ma = timezone(timedelta(hours=1))
        current_time = datetime.now(tz_ma).strftime("%Y-%m-%d %H:%M:%S")
        st.markdown(f"### ⏰ وقت التحليل (بتوقيت المغرب): `{current_time}`")
        st.markdown("---")
        
        # تحليل الجوج
        gold_res = analyze_asset("GC=F", "الذهب (Gold)", pip_size, sl_pips, tp1_pips)
        btc_res = analyze_asset("BTC-USD", "البيتكوين (BTC)", 1.0, sl_pips * 10, tp1_pips * 10) # ضربنا فـ 10 حيت البيتكوين حركتو كبيرة

        # عرض النتائج فـ جوج أعمدة
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader(f"🥇 {gold_res['name']}")
            if gold_res['signal'] in ["BUY", "SELL"]:
                st.markdown(f"<h1 style='text-align: center; color: {gold_res['color']}; font-size: 50px;'>{gold_res['signal']}</h1>", unsafe_allow_html=True)
                st.metric("الدخول", f"{gold_res['entry']:.2f}")
                st.metric("الستوب", f"{gold_res['sl']:.2f}")
                st.metric("الهدف", f"{gold_res['tp1']:.2f}")
            else:
                st.warning("⚠️ لا توجد إشارة حالياً (ينتظر Sweep + OB/FVG).")
            st.caption(f"RSI: {gold_res['rsi']:.1f}")

        with col2:
            st.subheader(f"₿ {btc_res['name']}")
            if btc_res['signal'] in ["BUY", "SELL"]:
                st.markdown(f"<h1 style='text-align: center; color: {btc_res['color']}; font-size: 50px;'>{btc_res['signal']}</h1>", unsafe_allow_html=True)
                st.metric("الدخول", f"{btc_res['entry']:.2f}")
                st.metric("الستوب", f"{btc_res['sl']:.2f}")
                st.metric("الهدف", f"{btc_res['tp1']:.2f}")
            else:
                st.warning("⚠️ لا توجد إشارة حالياً (ينتظر Sweep + OB/FVG).")
            st.caption(f"RSI: {btc_res['rsi']:.1f}")
