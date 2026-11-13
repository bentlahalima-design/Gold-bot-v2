import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import ta
from datetime import datetime

st.set_page_config(page_title="Gold AI MTF", page_icon="🥇", layout="centered")
st.title("🥇 Gold AI Trader - MTF (1H/15m/5m)")
st.markdown("---")

symbol = st.text_input("أدخل رمز العملة (GC=F للدهب)", "GC=F")

# دوال جلب الداتا
@st.cache_data(ttl=60)
def get_data(symbol, period, interval):
    data = yf.download(tickers=symbol, period=period, interval=interval, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data.dropna()

if st.button("تحليل السوق (Get MTF Signal)"):
    with st.spinner('جاري تحليل الفريمات (1H -> 15M -> 5M)...'):
        try:
            # 1. فريم 1H
            df_1h = get_data(symbol, "30d", "1h")
            df_1h['RSI'] = ta.momentum.rsi(df_1h['Close'], window=14)
            rsi_1h = df_1h['RSI'].iloc[-1]
            trend_1h = "UP" if rsi_1h > 50 else "DOWN"
            
            # 2. فريم 15m
            df_15m = get_data(symbol, "10d", "15m")
            df_15m['FVG_Bull'] = df_15m['Low'] > df_15m['High'].shift(2)
            df_15m['FVG_Bear'] = df_15m['High'] < df_15m['Low'].shift(2)
            df_15m['OB_Bull'] = (df_15m['Close'].shift(1) < df_15m['Open'].shift(1)) & (df_15m['Close'] > df_15m['Open']) & (df_15m['Close'] > df_15m['High'].shift(1))
            df_15m['OB_Bear'] = (df_15m['Close'].shift(1) > df_15m['Open'].shift(1)) & (df_15m['Close'] < df_15m['Open']) & (df_15m['Close'] < df_15m['Low'].shift(1))
            
            recent_fvg_bull = df_15m['FVG_Bull'].tail(5).any()
            recent_fvg_bear = df_15m['FVG_Bear'].tail(5).any()
            recent_ob_bull = df_15m['OB_Bull'].tail(5).any()
            recent_ob_bear = df_15m['OB_Bear'].tail(5).any()
            
            setup_15m = "NEUTRAL"
            if (recent_fvg_bull or recent_ob_bull): setup_15m = "BUY_SETUP"
            elif (recent_fvg_bear or recent_ob_bear): setup_15m = "SELL_SETUP"

            # 3. فريم 5m
            df_5m = get_data(symbol, "5d", "5m")
            last_5m = df_5m.iloc[-1]
            
            buy_signal = (trend_1h == "UP") and (setup_15m == "BUY_SETUP") and (last_5m['Close'] > last_5m['Open'])
            sell_signal = (trend_1h == "DOWN") and (setup_15m == "SELL_SETUP") and (last_5m['Close'] < last_5m['Open'])

            last_close = float(last_5m['Close'])
            
            sl_dist = 100 * 0.1
            tp1_dist = 100 * 0.1
            tp2_dist = 200 * 0.1
            tp3_dist = 300 * 0.1

            st.markdown(f"### الأصل: `{symbol}`")
            
            col1, col2 = st.columns(2)
            col1.info(f"📊 **ترند 1H:** {trend_1h} (RSI: {rsi_1h:.1f})")
            col2.info(f"🎯 **منطقة 15M:** {setup_15m}")
            
            st.markdown("---")

            # === هادي هي الساعة اللي بغيتي ===
            # كنجيبو الوقت ديال الشمعة ديال 5 دقايق اللي عطات الإشارة
            signal_time = last_5m.name
            
            if buy_signal or sell_signal:
                color = "#00FF00" if buy_signal else "#FF0000"
                signal_text = "BUY" if buy_signal else "SELL"
                
                st.markdown(f"<h1 style='text-align: center; color: {color};'>{signal_text}</h1>", unsafe_allow_html=True)
                
                # عرض وقت الإشارة (الساعة ديال الشمعة)
                st.markdown(f"<h3 style='text-align: center; color: #FFD700;'>⏰ وقت الإشارة (Signal Time): {signal_time}</h3>", unsafe_allow_html=True)
                
                if buy_signal:
                    sl = last_close - sl_dist
                    tp1, tp2, tp3 = last_close + tp1_dist, last_close + tp2_dist, last_close + tp3_dist
                else:
                    sl = last_close + sl_dist
                    tp1, tp2, tp3 = last_close - tp1_dist, last_close - tp2_dist, last_close - tp3_dist
                
                col_e, col_sl = st.columns(2)
                col_e.metric("الدخول (Entry)", f"{last_close:.2f}")
                col_sl.metric("الستوب لوز (SL)", f"{sl:.2f}", delta="-خطر-", delta_color="inverse")
                
                st.markdown("#### 🎯 الأهداف")
                col_tp1, col_tp2, col_tp3 = st.columns(3)
                col_tp1.metric("هدف 1", f"{tp1:.2f}")
                col_tp2.metric("هدف 2", f"{tp2:.2f}")
                col_tp3.metric("هدف 3", f"{tp3:.2f}")
            else:
                # حتى إلا ماكانش إشارة، كيبين ليك وقت آخر تحليل
                st.warning("⚠️ لا توجد إشارة حالياً. البوت ينتظر توافق الفريمات.")
                st.info(f"⏰ آخر شمعة 5M تم تحليلها: {signal_time}")
                
        except Exception as e:
            st.error(f"وقع خطأ: {e}")
