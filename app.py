import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import ta
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="MTF Sniper V22", page_icon="🎯", layout="wide")

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
    .wait-color { color: #f1c40f; }
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

st.markdown("<h2 style='text-align: center; color: white;'>🎯 MTF Sniper (15M + 5M)</h2>", unsafe_allow_html=True)
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

# ==========================================
# 4. الواجهة الرئيسية
# ==========================================
if st.button(f"🚀 تحليل {asset_choice} الآن", use_container_width=True):
    with st.spinner(f'جاري تحليل الفريمات...'):
        try:
            # --- 1. تحليل الفريم الكبير (15M) ---
            df_15m = get_data(symbol, "30d", "15m")
            df_15m['EMA200'] = ta.trend.ema_indicator(df_15m['Close'], window=200)
            last_15m = df_15m.iloc[-1]
            
            # تحديد الاتجاه العام
            if last_15m['Close'] > last_15m['EMA200']:
                trend_15m = "UP"
                trend_text = "Strong Uptrend (15m)"
                trend_color = "#00ff88"
            else:
                trend_15m = "DOWN"
                trend_text = "Strong Downtrend (15m)"
                trend_color = "#ff3366"

            # --- 2. تحليل فريم الدخول (5M) ---
            df_5m = get_data(symbol, "10d", "5m")
            df_5m['RSI'] = ta.momentum.rsi(df_5m['Close'], window=14)
            
            # كشف السيولة (Sweep) و FVG
            df_5m['Sweep_Low'] = (df_5m['Low'] < df_5m['Low'].rolling(10).min().shift(1)) & (df_5m['Close'] > df_5m['Low'].rolling(10).min().shift(1))
            df_5m['Sweep_High'] = (df_5m['High'] > df_5m['High'].rolling(10).max().shift(1)) & (df_5m['Close'] < df_5m['High'].rolling(10).max().shift(1))
            df_5m['FVG_Bull'] = df_5m['Low'] > df_5m['High'].shift(2)
            df_5m['FVG_Bear'] = df_5m['High'] < df_5m['Low'].shift(2)
            
            last_5m = df_5m.iloc[-1]
            entry = last_5m['Close']

            # --- 3. منطق القناص (Top-Down) ---
            signal = "WAITING"
            confidence = 0
            sig_color = "wait-color"
            
            # إلا كان ترند 15m صاعد، كنقلبو غير على شراء فـ 5m
            if trend_15m == "UP":
                if last_5m['Sweep_Low'] and (last_5m['FVG_Bull'] or last_5m['RSI'] > 45):
                    signal = "BUY"
                    confidence = 90
                    sig_color = "buy-color"
                elif last_5m['Close'] > last_5m['Open']: # إشارة استمرارية الترند
                    signal = "BUY"
                    confidence = 65
                    sig_color = "buy-color"
                    
            # إلا كان ترند 15m هابط، كنقلبو غير على بيع فـ 5m
            elif trend_15m == "DOWN":
                if last_5m['Sweep_High'] and (last_5m['FVG_Bear'] or last_5m['RSI'] < 55):
                    signal = "SELL"
                    confidence = 90
                    sig_color = "sell-color"
                elif last_5m['Close'] < last_5m['Open']: # إشارة استمرارية الترند
                    signal = "SELL"
                    confidence = 65
                    sig_color = "sell-color"

            # الوقت الحالي
            tz_ma = timezone(timedelta(hours=1))
            current_time = datetime.now(tz_ma).strftime("%H:%M")

            # حساب الستوب والأهداف
            if signal == "BUY":
                sl = entry - (sl_pips * pip_size)
                tp1, tp2, tp3 = entry + (tp1_pips * pip_size), entry + (tp2_pips * pip_size), entry + (tp3_pips * pip_size)
            elif signal == "SELL":
                sl = entry + (sl_pips * pip_size)
                tp1, tp2, tp3 = entry - (tp1_pips * pip_size), entry - (tp2_pips * pip_size), entry - (tp3_pips * pip_size)
            else:
                sl, tp1, tp2, tp3 = 0, 0, 0, 0

            # ==========================================
            # عرض الكارت (بلا مسافات)
            # ==========================================
            html_content = f"""
<div class="signal-card">
<div style="display: flex; justify-content: space-between; align-items: center;">
<span class="title-text">🎯 AI MTF Signal - {asset_choice}</span>
<span style="color: #2ecc71; font-size: 14px;">● LIVE</span>
</div>
<div class="big-signal {sig_color}">
{signal}
</div>
<div style="background-color: #2d303e; border-radius: 10px; height: 10px; margin-bottom: 20px;">
<div style="background-color: {'#00ff88' if signal == 'BUY' else '#ff3366' if signal == 'SELL' else '#f1c40f'}; width: {confidence}%; height: 10px; border-radius: 10px;"></div>
</div>
<div style="text-align: right; color: { '#00ff88' if signal == 'BUY' else '#ff3366' if signal == 'SELL' else '#f1c40f' }; font-weight: bold; margin-bottom: 20px;">
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
<div>15M Trend: <span style="color: {trend_color};">{trend_text}</span></div>
</div>
<div style="display: flex; justify-content: space-between; margin-top: 10px; color: #a0a5b1; font-size: 14px;">
<div>5M Setup: <span style="color: white;">{'Sweep + FVG' if confidence == 90 else 'Trend Continuation' if confidence == 65 else 'No Setup'}</span></div>
<div>RSI (5m): <span style="color: white;">{last_5m['RSI']:.1f}</span></div>
</div>
<div style="margin-top: 20px; text-align: center; color: #555; font-size: 12px;">
Last signal: {signal} at {current_time}<br>
Mode: MTF Sniper (15M Direction + 5M Entry)
</div>
</div>
"""
            st.markdown(html_content, unsafe_allow_html=True)

        except Exception as e:
            st.error(f"وقع خطأ: {e}")
