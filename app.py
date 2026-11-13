import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="SMC Pro V4", page_icon="⚡", layout="wide")
st.title("⚡ SMC/ICT Active Bot V4 (Real Time)")
st.markdown("---")

symbol = st.sidebar.text_input("رمز العملة", "GC=F")
timeframe = st.sidebar.selectbox("الفريم الزمني (يفضل 15m)", ["15m", "1h", "5m"], index=0)

st.sidebar.markdown("---")
pip_size = st.sidebar.number_input("حجم النقطة", value=0.1, step=0.1, format="%.1f")
sl_pips = st.sidebar.number_input("الستوب لوز (نقطة)", value=100, step=10)
tp1_pips = st.sidebar.number_input("الهدف 1 (نقطة)", value=150, step=10)

@st.cache_data(ttl=60)
def get_data(symbol, period, interval):
    data = yf.download(tickers=symbol, period=period, interval=interval, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data.dropna()

def calculate_smc(df):
    df = df.copy()
    df['EMA50'] = df['Close'].rolling(window=50).mean()
    df['EMA200'] = df['Close'].rolling(window=200).mean()
    
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # FVG و OB
    df['FVG_Bull'] = df['Low'] > df['High'].shift(2)
    df['FVG_Bear'] = df['High'] < df['Low'].shift(2)
    df['OB_Bull'] = (df['Close'].shift(1) < df['Open'].shift(1)) & (df['Close'] > df['Open']) & (df['Close'] > df['High'].shift(1))
    df['OB_Bear'] = (df['Close'].shift(1) > df['Open'].shift(1)) & (df['Close'] < df['Open']) & (df['Close'] < df['Low'].shift(1))
    
    return df

if st.sidebar.button("🚀 تحليل السوق الآن", use_container_width=True):
    with st.spinner('جاري تحليل السوق...'):
        try:
            df = get_data(symbol, "60d", timeframe)
            df = calculate_smc(df)
            
            if len(df) > 200:
                last = df.iloc[-1]
                entry_price = float(last['Close'])
                
                # --- الوقت الحقيقي ديال الإشارة (بتوقيتك) ---
                tz_ma = timezone(timedelta(hours=1)) # توقيت المغرب UTC+1
                current_time = datetime.now(tz_ma).strftime("%Y-%m-%d %H:%M:%S")
                
                # شروط الدخول (مبسطة باش تعطي إشارات)
                recent_fvg_bull = df['FVG_Bull'].tail(5).any()
                recent_fvg_bear = df['FVG_Bear'].tail(5).any()
                recent_ob_bull = df['OB_Bull'].tail(5).any()
                recent_ob_bear = df['OB_Bear'].tail(5).any()
                
                buy_cond = (last['Close'] > last['EMA200']) and (last['RSI'] > 45) and (recent_fvg_bull or recent_ob_bull)
                sell_cond = (last['Close'] < last['EMA200']) and (last['RSI'] < 55) and (recent_fvg_bear or recent_ob_bear)
                
                signal, color = "WAITING", "gray"
                if buy_cond:
                    signal, color = "BUY", "#00FF00"
                    sl = entry_price - (sl_pips * pip_size)
                    tp1 = entry_price + (tp1_pips * pip_size)
                elif sell_cond:
                    signal, color = "SELL", "#FF0000"
                    sl = entry_price + (sl_pips * pip_size)
                    tp1 = entry_price - (tp1_pips * pip_size)

                if signal != "WAITING":
                    st.markdown(f"<h1 style='text-align: center; color: {color}; font-size: 60px;'>{signal}</h1>", unsafe_allow_html=True)
                    # وقت الإشارة الحقيقي
                    st.markdown(f"<h4 style='text-align: center; color: #FFD700;'>⏰ وقت التحليل (المغرب): {current_time}</h4>", unsafe_allow_html=True)
                    
                    c1, c2 = st.columns(2)
                    c1.metric("سعر الإغلاق (Entry)", f"{entry_price:.2f}")
                    c2.metric("الستوب (SL)", f"{sl:.2f}")
                    
                    st.markdown("---")
                    c3 = st.columns(1)[0]
                    c3.metric(f"هدف 1 ({tp1_pips} نقطة)", f"{tp1:.2f}")
                    
                    st.info("💡 **ملاحظة مهمة**: هاد السعر ديال الإغلاق (yfinance). ملي تدخل فـ MT5، دخل بالسعر الحي، وطرح 10 دولار للستوب و 15 دولار للهدف.")
                else:
                    st.warning(f"⚠️ السوق غير واضح حالياً. الترند: {'صاعد' if last['Close'] > last['EMA200'] else 'هابط'}، ولكن مازال ماكاينش تأكيد من الفجوات.")
                    st.info(f"⏰ وقت التحليل: {current_time}")

                # --- محرك الباك تست ---
                st.markdown("---")
                st.subheader(f"📊 نتائج الاختبار التاريخي ({timeframe})")
                
                wins, losses, total_trades = 0, 0, 0
                in_trade = False
                trade_type = None
                
                for i in range(200, len(df) - 20):
                    row = df.iloc[i]
                    
                    if not in_trade:
                        r_fvg_b = df['FVG_Bull'].iloc[i-5:i].any()
                        r_fvg_s = df['FVG_Bear'].iloc[i-5:i].any()
                        r_ob_b = df['OB_Bull'].iloc[i-5:i].any()
                        r_ob_s = df['OB_Bear'].iloc[i-5:i].any()
                        
                        b_cond = (row['Close'] > row['EMA200']) and (row['RSI'] > 45) and (r_fvg_b or r_ob_b)
                        s_cond = (row['Close'] < row['EMA200']) and (row['RSI'] < 55) and (r_fvg_s or r_ob_s)
                        
                        if b_cond:
                            in_trade = True; trade_type = "BUY"
                            entry = row['Close']; sl_price = entry - (sl_pips * pip_size); tp_price = entry + (tp1_pips * pip_size)
                        elif s_cond:
                            in_trade = True; trade_type = "SELL"
                            entry = row['Close']; sl_price = entry + (sl_pips * pip_size); tp_price = entry - (tp1_pips * pip_size)
                    else:
                        trade_closed = False
                        if trade_type == "BUY":
                            if row['Low'] <= sl_price: losses += 1; trade_closed = True
                            elif row['High'] >= tp_price: wins += 1; trade_closed = True
                        elif trade_type == "SELL":
                            if row['High'] >= sl_price: losses += 1; trade_closed = True
                            elif row['Low'] <= tp_price: wins += 1; trade_closed = True
                        
                        if trade_closed:
                            total_trades += 1
                            in_trade = False
                            
                if total_trades > 0:
                    wr = (wins / total_trades * 100)
                    col_a, col_b, col_c, col_d = st.columns(4)
                    col_a.metric("إجمالي الصفقات", total_trades)
                    col_b.metric("ناجحة (TP1)", wins)
                    col_c.metric("خاسرة (SL)", losses)
                    col_d.metric("نسبة النجاح", f"{wr:.1f}%")
                else:
                    st.error("ماكاينش صفقات كافية.")
            else:
                st.error("الداتا غير كافية.")
        except Exception as e:
            st.error(f"وقع خطأ: {e}")
