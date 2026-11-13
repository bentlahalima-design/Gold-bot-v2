import streamlit as st
import yfinance as yf
import pandas as pd
import ta

st.set_page_config(page_title="Gold AI Trader", page_icon="🥇", layout="centered")
st.title("🥇 Gold AI Trader - V2")
st.markdown("---")

symbol = st.text_input("أدخل رمز العملة (GC=F للدهب، BTC-USD للبيتكوين)", "GC=F")

if st.button("تحليل السوق (Get Signal)"):
    with st.spinner('جاري تحليل السوق...'):
        try:
            data = yf.download(tickers=symbol, period="5d", interval="15m", progress=False)
            
            if data.empty:
                st.error("لم يتم العثور على بيانات لهذه العملة.")
            else:
                # إصلاح مشكل الأعمدة (MultiIndex) باش ما يعطيش الخطأ
                if isinstance(data.columns, pd.MultiIndex):
                    data.columns = data.columns.get_level_values(0)

                # حساب المؤشرات
                data['EMA50'] = ta.trend.ema_indicator(data['Close'], window=50)
                data['EMA200'] = ta.trend.ema_indicator(data['Close'], window=200)
                data['RSI'] = ta.momentum.rsi(data['Close'], window=14)
                data['ATR'] = ta.volatility.average_true_range(data['High'], data['Low'], data['Close'], window=14)

                # جلب آخر القيم
                last_close = float(data['Close'].iloc[-1])
                last_ema50 = float(data['EMA50'].iloc[-1])
                last_ema200 = float(data['EMA200'].iloc[-1])
                last_rsi = float(data['RSI'].iloc[-1])
                last_atr = float(data['ATR'].iloc[-1])

                signal = "WAITING"
                confidence = 0
                color = "gray"

                # شروط الإشارة
                if last_close > last_ema200 and last_ema50 > last_ema200 and last_rsi > 50:
                    signal = "BUY"
                    confidence = 85
                    color = "green"
                elif last_close < last_ema200 and last_ema50 < last_ema200 and last_rsi < 50:
                    signal = "SELL"
                    confidence = 78
                    color = "red"

                # حساب الستوب والأهداف
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

                # عرض النتائج
                st.markdown(f"### الأصل: `{symbol}`")
                if signal != "WAITING":
                    st.markdown(f"<h1 style='text-align: center; color: {color};'>{signal}</h1>", unsafe_allow_html=True)
                    st.progress(confidence / 100.0)
                    st.write(f"**نسبة الثقة:** {confidence}%")
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric(label="الدخول (Entry)", value=f"{last_close:.2f}")
                        st.metric(label="الستوب لوز", value=f"{sl:.2f}")
                    with col2:
                        st.metric(label="الهدف 1", value=f"{tp1:.2f}")
                        st.metric(label="الهدف 2", value=f"{tp2:.2f}")
                    st.metric(label="الهدف 3", value=f"{tp3:.2f}")
                else:
                    st.warning("السوق غير واضح حالياً. لا توجد إشارة.")
        except Exception as e:
            st.error(f"وقع خطأ: {e}")
