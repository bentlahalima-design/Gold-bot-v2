import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="Confluence Dashboard", page_icon="🎯", layout="wide")
st.title("🎯 VIP Confluence Dashboard (24/5 SMC)")
st.markdown("---")

# ==========================================
# 1. الإعدادات
# ==========================================
symbol = st.sidebar.text_input("رمز العملة", "GC=F")
timeframe = st.sidebar.selectbox("فريم الدخول", ["15m", "5m", "1h"], index=0)

st.sidebar.markdown("---")
pip_size = st.sidebar.number_input("حجم النقطة", value=0.1, step=0.1, format="%.1f")
sl_pips = st.sidebar.number_input("الستوب لوز (نقطة)", value=50, step=10)
tp1_pips = st.sidebar.number_input("الهدف (نقطة)", value=100, step=10)

# ==========================================
# 2. جلب الداتا
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

# ==========================================
# 3. المؤشرات (SMC)
# ==========================================
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

# ==========================================
# 4. الواجهة الرئيسية
# ==========================================
if st.sidebar.button("🚀 تحليل السوق الآن", use_container_width=True):
    with st.spinner('جاري تحليل السوق...'):
        try:
            df = get_data(symbol, "60d", timeframe)
            df = calculate_smc_logic(df)
            
            last = df.iloc[-1]
            entry_price = float(last['Close'])
            last_time = last.name
            
            # توقيت المغرب
            tz_ma = timezone(timedelta(hours=1))
            current_time = datetime.now(tz_ma).strftime("%Y-%m-%d %H:%M:%S")
            
            # الشروط (بلا فلتر الوقت)
            buy_cond = last['Sweep_Low'] and (last['OB_Bull'] or last['FVG_Bull']) and (last['RSI'] > 45)
            sell_cond = last['Sweep_High'] and (last['OB_Bear'] or last['FVG_Bear']) and (last['RSI'] < 55)

            st.markdown("---")
            st.markdown(f"### ⏰ وقت التحليل (بتوقيت المغرب): `{current_time}`")
            st.markdown("---")

            if buy_cond or sell_cond:
                signal, color = ("BUY", "#00FF00") if buy_cond else ("SELL", "#FF0000")
                sl = entry_price - (sl_pips * pip_size) if buy_cond else entry_price + (sl_pips * pip_size)
                tp1 = entry_price + (tp1_pips * pip_size) if buy_cond else entry_price - (tp1_pips * pip_size)
                
                st.markdown(f"<h1 style='text-align: center; color: {color}; font-size: 60px;'>{signal}</h1>", unsafe_allow_html=True)
                st.success("✅ تم التأكيد: ضربة سيولة (Sweep) + منطقة (OB/FVG).")
                
                c1, c2, c3 = st.columns(3)
                c1.metric("سعر الدخول (Entry)", f"{entry_price:.2f}")
                c2.metric("الستوب (SL)", f"{sl:.2f}")
                c3.metric("الهدف (TP)", f"{tp1:.2f}")
            else:
                st.warning("⚠️ لا توجد إشارة حالياً. البوت ينتظر ضربة سيولة (Sweep) مع تأكيد من OB/FVG.")
                
                # عرض تفاصيل إضافية باش تعرف علاش ماعطاش إشارة
                st.info(f"📝 تحليل سريع: RSI = {last['RSI']:.1f} | Sweep Low = {last['Sweep_Low']} | Sweep High = {last['Sweep_High']}")

        except Exception as e:
            st.error(f"وقع خطأ: {e}")
