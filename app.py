import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import ta

# 1. إعدادات الصفحة
st.set_page_config(page_title="Gold AI Trader - V3 SMC", page_icon="🥇", layout="wide")
st.title("🥇 Gold AI Trader - V3 (SMC & ICT)")
st.markdown("---")

# 2. الشريط الجانبي (Sidebar) للإعدادات
st.sidebar.header("⚙️ الإعدادات (Settings)")
symbol = st.sidebar.text_input("رمز العملة (GC=F للدهب)", "GC=F")
timeframe = st.sidebar.selectbox("الفريم الزمني (Timeframe)", ["15m", "30m", "1h", "4h"], index=0)
period = "30d" if timeframe in ["15m", "30m", "1h"] else "90d"

# 3. دالة لجلب الداتا وحساب المؤشرات
@st.cache_data(ttl=60) # كيخزن الداتا دقيقة باش ما يعلقش
def get_data(symbol, period, interval):
    data = yf.download(tickers=symbol, period=period, interval=interval, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

# 4. زر التحليل
if st.sidebar.button("🚀 تحليل السوق (Get Signal)", use_container_width=True):
    with st.spinner('جاري تحليل هيكل السوق والسيولة...'):
        try:
            data = get_data(symbol, period, timeframe)
            
            if data.empty:
                st.error("لم يتم العثور على بيانات. تأكد من رمز العملة.")
            else:
                # --- حساب المؤشرات الأساسية ---
                data['EMA50'] = ta.trend.ema_indicator(data['Close'], window=50)
                data['EMA200'] = ta.trend.ema_indicator(data['Close'], window=200)
                data['RSI'] = ta.momentum.rsi(data['Close'], window=14)
                data['ATR'] = ta.volatility.average_true_range(data['High'], data['Low'], data['Close'], window=14)

                # --- منطق SMC المبسط (Swing Highs / Lows) ---
                # كنديرو لوك باك ديال 5 شموع باش نلقاو القمم والقيعان
                data['Swing_High'] = data['High'].rolling(window=5).max()
                data['Swing_Low'] = data['Low'].rolling(window=5).min()

                # آخر القيم
                last_close = float(data['Close'].iloc[-1])
                last_ema50 = float(data['EMA50'].iloc[-1])
                last_ema200 = float(data['EMA200'].iloc[-1])
                last_rsi = float(data['RSI'].iloc[-1])
                last_atr = float(data['ATR'].iloc[-1])
                
                # اكتشاف FVG (Fair Value Gap) مبسط
                # الفجوة الصاعدة: قاع الشمعة الحالية فوق قمة الشمعة اللي قبل جوج
                bullish_fvg = data['Low'].iloc[-1] > data['High'].iloc[-3]
                bearish_fvg = data['High'].iloc[-1] < data['Low'].iloc[-3]

                # --- حساب نسبة الثقة (Confluence) ---
                signal = "WAITING"
                confidence = 0
                color = "gray"
                trend_text = ""
                momentum_text = ""

                # شرط الشراء (BUY): ترند صاعد + RSI فوق 50 + دعم من SMC
                if last_close > last_ema200 and last_ema50 > last_ema200:
                    trend_text = "Strong Uptrend"
                    if last_rsi > 50:
                        confidence += 30
                        momentum_text = "Bullish"
                    if bullish_fvg:
                        confidence += 20 # FVG صاعدة
                    
                    # إلا جمعنا 50% ولا أكثر كنعطيو إشارة
                    if confidence >= 50:
                        signal = "BUY"
                        color = "#00FF00" # أخضر نيون
                        confidence += 20 # تعزيز إضافي

                # شرط البيع (SELL): ترند هابط + RSI تحت 50 + دعم من SMC
                elif last_close < last_ema200 and last_ema50 < last_ema200:
                    trend_text = "Strong Downtrend"
                    if last_rsi < 50:
                        confidence += 30
                        momentum_text = "Bearish"
                    if bearish_fvg:
                        confidence += 20 # FVG هابطة
                    
                    if confidence >= 50:
                        signal = "SELL"
                        color = "#FF0000" # أحمر
                        confidence += 20

                # --- حساب الستوب والأهداف ---
                if signal == "BUY":
                    sl = last_close - (last_atr * 1.5)
                    tp1 = last_close + (last_atr * 1.5)
                    tp2 = last_close + (last_atr * 2.5)
                    tp3 = last_close + (last_atr * 3.5)
                elif signal == "SELL":
                    sl = last_close + (last_atr * 1.5)
                    tp1 = last_close - (last_atr * 1.5)
                    tp2 = last_close - (last_atr * 2.5)
                    tp3 = last_close - (last_atr * 3.5)
                else:
                    sl = tp1 = tp2 = tp3 = 0

                # ==========================================
                # 5. عرض الواجهة (Dashboard UI)
                # ==========================================
                col1, col2, col3 = st.columns([1, 2, 1])
                
                with col2:
                    if signal != "WAITING":
                        # عرض الإشارة بلون كبير
                        st.markdown(f"<h1 style='text-align: center; color: {color}; font-size: 60px;'>{signal}</h1>", unsafe_allow_html=True)
                        st.progress(min(confidence, 100) / 100.0)
                        st.markdown(f"<h3 style='text-align: center;'>نسبة الثقة: {min(confidence, 100)}%</h3>", unsafe_allow_html=True)
                        
                        # عرض المعلومات فـ بلوكات
                        st.info(f"📊 **الترند:** {trend_text} | **الزخم:** {momentum_text}")
                        
                        # جدول الأسعار
                        col_e, col_sl = st.columns(2)
                        col_e.metric("الدخول (Entry)", f"{last_close:.2f}")
                        col_sl.metric("الستوب لوز (SL)", f"{sl:.2f}", delta="-خطر-", delta_color="inverse")
                        
                        st.markdown("---")
                        st.markdown("#### 🎯 الأهداف (Take Profits)")
                        col_tp1, col_tp2, col_tp3 = st.columns(3)
                        col_tp1.metric("الهدف 1 (TP1)", f"{tp1:.2f}")
                        col_tp2.metric("الهدف 2 (TP2)", f"{tp2:.2f}")
                        col_tp3.metric("الهدف 3 (TP3)", f"{tp3:.2f}")
                        
                    else:
                        st.warning("⚠️ السوق غير واضح حالياً (لا يوجد توافق بين الترند و SMC). يرجى الانتظار.")

        except Exception as e:
            st.error(f"وقع خطأ: {e}")
