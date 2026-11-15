import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import ta
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="AI Signal Pro - BTC & Gold", page_icon="🎯", layout="wide")

# ==========================================
# 1. CSS باش نعطيو شكل التطبيق
# ==========================================
st.markdown("""
<style>
    .main { background-color: #0e1117; }
    .signal-card {
        background-color: #1a1c24;
        padding: 20px;
        border-radius: 15px;
        color: white;
        border: 1px solid #2d303e;
        margin-bottom: 15px;
    }
    .title-text { color: #a0a5b1; font-size: 16px; font-weight: bold; }
    .big-signal { font-size: 60px; font-weight: bold; text-align: center; margin: 10px 0; }
    .buy-color { color: #00ff88; }
    .sell-color { color: #ff3366; }
    .box-item {
        background-color: #232634;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        font-size: 18px;
        border-left: 4px solid #444;
    }
    .entry-box { border-left-color: #f39c12; }
    .sl-box { border-left-color: #e74c3c; }
    .tp-box { border-left-color: #2ecc71; }
    .text-green { color: #2ecc71; font-weight: bold; }
    .text-red { color: #e74c3c; font-weight: bold; }
    .text-gold { color: #f1c40f; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

st.markdown("<h2 style='text-align: center; color: white;'>🎯 AI Signal Dashboard</h2>", unsafe_allow_html=True)
st.markdown("---")

# ==========================================
# 2. الإعدادات
# ==========================================
asset_choice = st.sidebar.selectbox("اختار الأصل (Asset)", ["BTC-USD (بيتكوين)", "GC=F (ذهب)"], index=0)

if "BTC" in asset_choice:
    symbol = "BTC-USD"
    default_pip = 1.0
    default_sl = 500
    default_tp1 = 500
    default_tp2 = 1000
    default_tp3 = 1500
else:
    symbol = "GC=F"
    default_pip = 0.1
    default_sl = 100
    default_tp1 = 50
    default_tp2 = 100
    default_tp3 = 150

timeframe = st.sidebar.selectbox("الفريم الزمني", ["15m", "1h", "5m"], index=0)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 إدارة المخاطر (بالنقط)")
pip_size = st.sidebar.number_input("حجم النقطة", value=default_pip, step=0.1, format="%.1f")
sl_pips = st.sidebar.number_input("الستوب لوز", value=default_sl, step=10)
tp1_pips = st.sidebar.number_input("الهدف 1", value=default_tp1, step=10)
tp2_pips = st.sidebar.number_input("الهدف 2", value=default_tp2, step=10)
tp3_pips = st.sidebar.number_input("الهدف 3", value=default_tp3, step=10)

# ==========================================
# 3. جلب الداتا
# ==========================================
@st.cache_data(ttl=30)
def get_data(symbol, period, interval):
    data = yf.download(tickers=symbol, period=period, interval=interval, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    if data.index.tz is None:
        data.index = data.index.tz_localize('UTC')
    else:
        data.index = data.index.tz_convert('UTC')
    return data.dropna()

def analyze_market(df):
    df['EMA50'] = ta.trend.ema_indicator(df['Close'], window=50)
    df['EMA200'] = ta.trend.ema_indicator(df['Close'], window=200)
    df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
    df['ATR'] = ta.volatility.average_true_range(df['High'], df['Low'], df['Close'], window=14)
    
    last = df.iloc[-1]
    
    trend = "Strong Uptrend" if last['Close'] > last['EMA200'] and last['EMA50'] > last['EMA200'] else "Strong Downtrend"
    momentum = "Bullish" if last['RSI'] > 50 else "Bearish"
    volatility = "High" if last['ATR'] > df['ATR'].mean() else "Low"
    
    df['Sweep_Low'] = (df['Low'] < df['Low'].rolling(10).min().shift(1)) & (df['Close'] > df['Low'].rolling(10).min().shift(1))
    df['Sweep_High'] = (df['High'] > df['High'].rolling(10).max().shift(1)) & (df['Close'] < df['High'].rolling(10).max().shift(1))
    df['FVG_Bull'] = df['Low'] > df['High'].shift(2)
    df['FVG_Bear'] = df['High'] < df['Low'].shift(2)
    
    last = df.iloc[-1]
    
    if last['Sweep_Low'] and (last['FVG_Bull'] or momentum == "Bullish"):
        signal = "BUY"
        confidence = 85
    elif last['Sweep_High'] and (last['FVG_Bear'] or momentum == "Bearish"):
        signal = "SELL"
        confidence = 85
    elif last['Close'] > last['EMA200']:
        signal = "BUY"
        confidence = 65
    else:
        signal = "SELL"
        confidence = 65
        
    return signal, confidence, trend, momentum, volatility, last['Close'], last['RSI']

# ==========================================
# 4. الواجهة الرئيسية
# ==========================================
if st.button(f"🚀 تحليل {asset_choice} الآن", use_container_width=True):
    with st.spinner(f'جاري تحليل {asset_choice}...'):
        try:
            df = get_data(symbol, "60d", timeframe)
            signal, confidence, trend, momentum, volatility, entry, rsi = analyze_market(df)
            
            sig_color = "buy-color" if signal == "BUY" else "sell-color"
            
            if signal == "BUY":
                sl = entry - (sl_pips * pip_size)
                tp1, tp2, tp3 = entry + (tp1_pips * pip_size), entry + (tp2_pips * pip_size), entry + (tp3_pips * pip_size)
            else:
                sl = entry + (sl_pips * pip_size)
                tp1, tp2, tp3 = entry - (tp1_pips * pip_size), entry - (tp2_pips * pip_size), entry - (tp3_pips * pip_size)

            tz_ma = timezone(timedelta(hours=1))
            current_time = datetime.now(tz_ma).strftime("%H:%M")

            # ==========================================
            # عرض الكارت (بدون مسافات باش يخدم HTML)
            # ==========================================
            html_content = f"""
<div class="signal-card">
<div style="display: flex; justify-content: space-between; align-items: center;">
<span class="title-text">🎯 AI Signal - {asset_choice}</span>
<span style="color: #2ecc71; font-size: 14px;">● LIVE</span>
</div>
<div class="big-signal {sig_color}">
{signal}
</div>
<div style="background-color: #2d303e; border-radius: 10px; height: 10px; margin-bottom: 20px;">
<div style="background-color: {'#00ff88' if signal == 'BUY' else '#ff3366'}; width: {confidence}%; height: 10px; border-radius: 10px;"></div>
</div>
<div style="text-align: right; color: { '#00ff88' if signal == 'BUY' else '#ff3366' }; font-weight: bold; margin-bottom: 20px;">
{confidence}% Confidence
</div>
<div class="box-item entry-box">
<span>🎯 Entry</span>
<span class="text-gold">${entry:.2f}</span>
</div>
<div class="box-item sl-box">
<span>🔴 Stop Loss</span>
<span class="text-red">${sl:.2f}</span>
</div>
<div class="box-item tp-box">
<span>✅ TP1</span>
<span class="text-green">${tp1:.2f}</span>
</div>
<div class="box-item tp-box">
<span>✅ TP2</span>
<span class="text-green">${tp2:.2f}</span>
</div>
<div class="box-item tp-box">
<span>✅ TP3</span>
<span class="text-green">${tp3:.2f}</span>
</div>
<div style="display: flex; justify-content: space-between; margin-top: 20px; color: #a0a5b1; font-size: 14px;">
<div>Trend: <span style="color: {'#00ff88' if 'Up' in trend else '#ff3366'};">{trend}</span></div>
<div>Volatility: <span style="color: white;">{volatility}</span></div>
</div>
<div style="display: flex; justify-content: space-between; margin-top: 10px; color: #a0a5b1; font-size: 14px;">
<div>Momentum: <span style="color: white;">{momentum}</span></div>
<div>RSI: <span style="color: white;">{rsi:.1f}</span></div>
</div>
<div style="margin-top: 20px; text-align: center; color: #555; font-size: 12px;">
Last signal: {signal} at {current_time} (under 1 min ago)<br>
Mode: Quality (target 5/day)
</div>
</div>
"""
            st.markdown(html_content, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"وقع خطأ: {e}")
