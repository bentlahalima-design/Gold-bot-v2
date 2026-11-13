import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime

st.set_page_config(page_title="SMC/ICT Pro", page_icon="⚡", layout="wide")
st.title("⚡ SMC/ICT Multi-Confluence Engine")
st.markdown("---")

symbol = st.sidebar.text_input("رمز العملة", "GC=F")
timeframe = st.sidebar.selectbox("الفريم الزمني", ["5m", "15m", "1h"], index=1)

st.sidebar.markdown("---")
pip_size = st.sidebar.number_input("حجم النقطة", value=0.1, step=0.1, format="%.1f")
sl_pips = st.sidebar.number_input("الستوب لوز (نقطة)", value=100, step=10)
tp1_pips = st.sidebar.number_input("الهدف 1 (نقطة)", value=50, step=10)
tp2_pips = st.sidebar.number_input("الهدف 2 (نقطة)", value=50, step=10)
tp3_pips = st.sidebar.number_input("الهدف 3 (نقطة)", value=50, step=10)

@st.cache_data(ttl=60)
def get_data(symbol, period, interval):
    data = yf.download(tickers=symbol, period=period, interval=interval, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data.dropna()

def calculate_smc(df):
    df = df.copy()
    # 1. الاتجاه العام (Trend)
    df['EMA50'] = df['Close'].rolling(window=50).mean()
    df['EMA200'] = df['Close'].rolling(window=200).mean()
    
    # 2. RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # 3. هيكل السوق (BOS/CHoCH) - قمم وقيعان
    df['Swing_High'] = df['High'].rolling(window=5).max()
    df['Swing_Low'] = df['Low'].rolling(window=5).min()
    df['Prev_High'] = df['Swing_High'].shift(1)
    df['Prev_Low'] = df['Swing_Low'].shift(1)
    
    # 4. كسر الهيكل (BOS)
    df['BOS_Bull'] = df['Close'] > df['Prev_High']
    df['BOS_Bear'] = df['Close'] < df['Prev_Low']
    
    # 5. الفجوات (FVG)
    df['FVG_Bull'] = df['Low'] > df['High'].shift(2)
    df['FVG_Bear'] = df['High'] < df['Low'].shift(2)
    
    # 6. Order Blocks (OB)
    df['OB_Bull'] = (df['Close'].shift(1) < df['Open'].shift(1)) & (df['Close'] > df['Open']) & (df['Close'] > df['High'].shift(1))
    df['OB_Bear'] = (df['Close'].shift(1) > df['Open'].shift(1)) & (df['Close'] < df['Open']) & (df['Close'] < df['Low'].shift(1))
    
    # 7. Breaker Blocks (كسر OB)
    df['Breaker_Bull'] = (df['Close'].shift(1) > df['Open'].shift(1)) & (df['Close'] > df['High'].shift(1)) & (df['High'].shift(1) < df['High'].shift(2))
    
    # 8. المناطق الرئيسية (Key Levels) - أعلى وأدنى سعر لـ 50 شمعة
    df['Key_Res'] = df['High'].rolling(window=50).max()
    df['Key_Sup'] = df['Low'].rolling(window=50).min()
    
    return df

if st.sidebar.button("🚀 تحليل السوق الآن", use_container_width=True):
    with st.spinner('جاري تحليل هيكل السوق والسيولة...'):
        try:
            df = get_data(symbol, "60d", timeframe)
            df = calculate_smc(df)
            
            if len(df) > 200:
                last = df.iloc[-1]
                entry_price = float(last['Close'])
                signal_time = last.name # وقت الإشارة
                
                # شروط الشراء (Confluence)
                buy_cond = (
                    (last['Close'] > last['EMA200']) and 
                    (last['RSI'] > 50) and 
                    (last['BOS_Bull'] or last['Breaker_Bull']) and 
                    (last['FVG_Bull'] or last['OB_Bull']) and
                    (last['Close'] < last['Key_Res'] * 1.01) # قريب من منطقة مقاومة
                )
                
                # شروط البيع (Confluence)
                sell_cond = (
                    (last['Close'] < last['EMA200']) and 
                    (last['RSI'] < 50) and 
                    (last['BOS_Bear']) and 
                    (last['FVG_Bear'] or last['OB_Bear']) and
                    (last['Close'] > last['Key_Sup'] * 0.99)
                )
                
                signal, color = "WAITING", "gray"
                if buy_cond:
                    signal, color = "BUY", "#00FF00"
                    sl = entry_price - (sl_pips * pip_size)
                    tp1 = entry_price + (tp1_pips * pip_size)
                    tp2 = entry_price + ((tp1_pips+tp2_pips) * pip_size)
                    tp3 = entry_price + ((tp1_pips+tp2_pips+tp3_pips) * pip_size)
                elif sell_cond:
                    signal, color = "SELL", "#FF0000"
                    sl = entry_price + (sl_pips * pip_size)
                    tp1 = entry_price - (tp1_pips * pip_size)
                    tp2 = entry_price - ((tp1_pips+tp2_pips) * pip_size)
                    tp3 = entry_price - ((tp1_pips+tp2_pips+tp3_pips) * pip_size)

                if signal != "WAITING":
                    st.markdown(f"<h1 style='text-align: center; color: {color}; font-size: 60px;'>{signal}</h1>", unsafe_allow_html=True)
                    st.markdown(f"<h4 style='text-align: center; color: #FFD700;'>⏰ وقت الإشارة: {signal_time}</h4>", unsafe_allow_html=True)
                    st.info(f"✅ تأكيد: هيكل السوق (BOS) + منطقة (OB/FVG) + اتجاه (EMA200/RSI) + منطقة رئيسية.")
                    
                    c1, c2 = st.columns(2)
                    c1.metric("الدخول (Entry)", f"{entry_price:.2f}")
                    c2.metric("الستوب لوز (SL)", f"{sl:.2f}", delta="-خطر-", delta_color="inverse")
                    
                    st.markdown("---")
                    c3, c4, c5 = st.columns(3)
                    c3.metric(f"هدف 1 ({tp1_pips} نقطة)", f"{tp1:.2f}")
                    c4.metric(f"هدف 2 ({tp2_pips} نقطة)", f"{tp2:.2f}")
                    c5.metric(f"هدف 3 ({tp3_pips} نقطة)", f"{tp3:.2f}")
                else:
                    st.warning("⚠️ السوق غير واضح حالياً. البوت ينتظر توافق الشروط (BOS + OB/FVG + اتجاه).")

                # --- محرك الباك تست ---
                st.markdown("---")
                st.subheader(f"📊 نتائج الاختبار التاريخي ({timeframe})")
                
                wins, losses, total = 0, 0, 0
                in_trade = False
                trade_type = None
                
                # حلقة تكرارية بسيطة للباك تست
                for i in range(200, len(df) - 20):
                    row = df.iloc[i]
                    if not in_trade:
                        b_cond = (row['Close'] > row['EMA200']) and (row['RSI'] > 50) and (row['BOS_Bull'] or row['Breaker_Bull']) and (row['FVG_Bull'] or row['OB_Bull']) and (row['Close'] < row['Key_Res'] * 1.01)
                        s_cond = (row['Close'] < row['EMA200']) and (row['RSI'] < 50) and (row['BOS_Bear']) and (row['FVG_Bear'] or row['OB_Bear']) and (row['Close'] > row['Key_Sup'] * 0.99)
                        
                        if b_cond:
                            in_trade = True; trade_type = "BUY"
                            entry = row['Close']; sl_price = entry - (sl_pips * pip_size); tp_price = entry + (tp1_pips * pip_size)
                        elif s_cond:
                            in_trade = True; trade_type = "SELL"
                            entry = row['Close']; sl_price = entry + (sl_pips * pip_size); tp_price = entry - (tp1_pips * pip_size)
                    else:
                        total += 1
                        if trade_type == "BUY":
                            if row['Low'] <= sl_price: losses += 1; in_trade = False
                            elif row['High'] >= tp_price: wins += 1; in_trade = False
                        elif trade_type == "SELL":
                            if row['High'] >= sl_price: losses += 1; in_trade = False
                            elif row['Low'] <= tp_price: wins += 1; in_trade = False
                            
                if total > 0:
                    wr = (wins / total * 100)
                    col_a, col_b, col_c, col_d = st.columns(4)
                    col_a.metric("إجمالي الصفقات", total)
                    col_b.metric("ناجحة (TP1)", wins)
                    col_c.metric("خاسرة (SL)", losses)
                    col_d.metric("نسبة النجاح", f"{wr:.1f}%")
                else:
                    st.error("ماكاينش صفقات كافية فالفترة المحددة.")
            else:
                st.error("الداتا غير كافية.")
        except Exception as e:
            st.error(f"وقع خطأ: {e}")
