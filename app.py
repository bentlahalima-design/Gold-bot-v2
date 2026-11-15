import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="V15 - Strict ICT Sniper", page_icon="🛡️", layout="wide")
st.title("🛡️ V15 - Strict ICT Sniper (High Win Rate)")
st.markdown("---")

# ==========================================
# 1. الإعدادات
# ==========================================
symbol = st.sidebar.text_input("رمز العملة", "GC=F")
timeframe = st.sidebar.selectbox("فريم الدخول", ["15m", "5m"], index=0)

st.sidebar.markdown("---")
st.sidebar.subheader("⏰ الجلسات (Killzones)")
sessions = st.sidebar.multiselect("اختار الجلسات:", ["London", "New York"], default=["London", "New York"])

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

def is_in_session(timestamp, selected_sessions):
    hour = timestamp.hour
    in_london = (7 <= hour < 16)
    in_ny = (12 <= hour < 21)
    if "London" in selected_sessions and in_london: return True
    if "New York" in selected_sessions and in_ny: return True
    return False

# ==========================================
# 3. المؤشرات (Trend, RSI, Sweep, OB/FVG)
# ==========================================
def calculate_indicators(df):
    # 1. الترند (EMA 200)
    df['EMA200'] = df['Close'].rolling(window=200).mean()
    
    # 2. RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))

    # 3. السيولة (Liquidity Sweep)
    df['Prev_Low'] = df['Low'].rolling(window=10).min().shift(1)
    df['Prev_High'] = df['High'].rolling(window=10).max().shift(1)
    df['Sweep_Low'] = (df['Low'] < df['Prev_Low']) & (df['Close'] > df['Prev_Low'])
    df['Sweep_High'] = (df['High'] > df['Prev_High']) & (df['Close'] < df['Prev_High'])
    
    # 4. FVG و OB
    df['FVG_Bull'] = df['Low'] > df['High'].shift(2)
    df['FVG_Bear'] = df['High'] < df['Low'].shift(2)
    df['OB_Bull'] = (df['Close'].shift(1) < df['Open'].shift(1)) & (df['Close'] > df['Open']) & (df['Close'] > df['High'].shift(1))
    df['OB_Bear'] = (df['Close'].shift(1) > df['Open'].shift(1)) & (df['Close'] < df['Open']) & (df['Close'] < df['Low'].shift(1))
    
    return df

# ==========================================
# 4. الواجهة الرئيسية
# ==========================================
if st.sidebar.button("🚀 تحليل السوق الآن", use_container_width=True):
    with st.spinner('جاري الفلترة الصارمة...'):
        try:
            df = get_data(symbol, "60d", timeframe)
            df = calculate_indicators(df)
            
            st.markdown("---")
            st.subheader(f"📊 نتائج الاختبار الصارم (V15) - ({timeframe})")
            
            wins, losses, total_trades = 0, 0, 0
            net_pips = 0
            in_trade = False
            trade_type = None
            
            current_date = None
            trades_today = 0
            
            for i in range(200, len(df) - 20):
                row = df.iloc[i]
                row_date = row.name.date()
                
                if row_date != current_date:
                    current_date = row_date
                    trades_today = 0
                
                time_ok = is_in_session(row.name, sessions)
                
                if not in_trade and time_ok and trades_today < 3:
                    # شروط قاسية جداً (Sweep + OB/FVG + Trend + RSI)
                    b_cond = (
                        row['Sweep_Low'] and (row['OB_Bull'] or row['FVG_Bull']) and 
                        (row['Close'] > row['EMA200']) and (row['RSI'] > 50)
                    )
                    s_cond = (
                        row['Sweep_High'] and (row['OB_Bear'] or row['FVG_Bear']) and 
                        (row['Close'] < row['EMA200']) and (row['RSI'] < 50)
                    )
                    
                    if b_cond:
                        in_trade = True; trade_type = "BUY"
                        trades_today += 1
                        entry = row['Close']; current_sl = entry - (sl_pips * pip_size); tp_price = entry + (tp1_pips * pip_size)
                    elif s_cond:
                        in_trade = True; trade_type = "SELL"
                        trades_today += 1
                        entry = row['Close']; current_sl = entry + (sl_pips * pip_size); tp_price = entry - (tp1_pips * pip_size)
                
                elif in_trade:
                    trade_closed = False
                    if trade_type == "BUY":
                        # Breakeven: إلا وصل 50 بيب ربح، حرك الستوب للدخول
                        if row['High'] >= entry + (50 * pip_size) and current_sl < entry:
                            current_sl = entry
                            
                        if row['Low'] <= current_sl:
                            if current_sl >= entry: wins += 1; net_pips += 0 # Breakeven
                            else: losses += 1; net_pips -= sl_pips
                            trade_closed = True
                        elif row['High'] >= tp_price:
                            wins += 1; net_pips += tp1_pips; trade_closed = True
                            
                    elif trade_type == "SELL":
                        if row['Low'] <= entry - (50 * pip_size) and current_sl > entry:
                            current_sl = entry
                            
                        if row['High'] >= current_sl:
                            if current_sl <= entry: wins += 1; net_pips += 0
                            else: losses += 1; net_pips -= sl_pips
                            trade_closed = True
                        elif row['Low'] <= tp_price:
                            wins += 1; net_pips += tp1_pips; trade_closed = True
                    
                    if trade_closed:
                        total_trades += 1
                        in_trade = False
                        
            if total_trades > 0:
                wr = (wins / total_trades * 100)
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("إجمالي الصفقات", total_trades)
                col_b.metric("ناجحة (TP/BE)", wins)
                col_c.metric("خاسرة (SL)", losses)
                col_d.metric("نسبة النجاح", f"{wr:.1f}%")
                
                if net_pips > 0:
                    st.success(f"💰 **صافي الربح (Net Profit): +{net_pips} نقطة**")
                else:
                    st.error(f"📉 **صافي الخسارة (Net Loss): {net_pips} نقطة**")
            else:
                st.error("ماكاينش صفقات كافية. (البوت ولى قناص بزاف).")

            # عرض الإشارة الحالية
            st.markdown("---")
            st.subheader("🔴 الإشارة الحالية (Live)")
            last = df.iloc[-1]
            entry_price = float(last['Close'])
            in_time = is_in_session(last.name, sessions)
            
            live_buy = last['Sweep_Low'] and (last['OB_Bull'] or last['FVG_Bull']) and (last['Close'] > last['EMA200']) and (last['RSI'] > 50) and in_time
            live_sell = last['Sweep_High'] and (last['OB_Bear'] or last['FVG_Bear']) and (last['Close'] < last['EMA200']) and (last['RSI'] < 50) and in_time

            if live_buy or live_sell:
                signal, color = ("BUY", "#00FF00") if live_buy else ("SELL", "#FF0000")
                sl = entry_price - (sl_pips * pip_size) if live_buy else entry_price + (sl_pips * pip_size)
                tp1 = entry_price + (tp1_pips * pip_size) if live_buy else entry_price - (tp1_pips * pip_size)
                
                st.markdown(f"<h1 style='text-align: center; color: {color}; font-size: 60px;'>{signal}</h1>", unsafe_allow_html=True)
                c1, c2, c3 = st.columns(3)
                c1.metric("سعر الدخول", f"{entry_price:.2f}")
                c2.metric("الستوب", f"{sl:.2f}")
                c3.metric("الهدف", f"{tp1:.2f}")
            else:
                st.warning(f"⚠️ السوق غير واضح حالياً. البوت ينتظر فرصة ذهبية (Sweep + OB + Trend + RSI).")

        except Exception as e:
            st.error(f"وقع خطأ: {e}")
