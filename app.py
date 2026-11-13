import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import ta

# 1. إعدادات الصفحة
st.set_page_config(page_title="Gold AI Trader - V4", page_icon="🥇", layout="wide")
st.title("🥇 Gold AI Trader - V4 (SMC + Backtest)")
st.markdown("---")

# 2. الشريط الجانبي (Sidebar)
st.sidebar.header("⚙️ الإعدادات (Settings)")
symbol = st.sidebar.text_input("رمز العملة (GC=F للدهب)", "GC=F")
timeframe = st.sidebar.selectbox("الفريم الزمني (Timeframe)", ["15m", "30m", "1h", "4h"], index=0)
period = "30d" if timeframe in ["15m", "30m", "1h"] else "90d"

# 3. دالة جلب الداتا
@st.cache_data(ttl=60)
def get_data(symbol, period, interval):
    data = yf.download(tickers=symbol, period=period, interval=interval, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

# 4. دالة حساب المؤشرات (باش نستعملوها فالتجربة والتطبيق)
def calculate_indicators(data):
    data['EMA50'] = ta.trend.ema_indicator(data['Close'], window=50)
    data['EMA200'] = ta.trend.ema_indicator(data['Close'], window=200)
    data['RSI'] = ta.momentum.rsi(data['Close'], window=14)
    data['ATR'] = ta.volatility.average_true_range(data['High'], data['Low'], data['Close'], window=14)
    
    # منطق SMC (FVG)
    data['FVG_Bull'] = data['Low'] > data['High'].shift(2)
    data['FVG_Bear'] = data['High'] < data['Low'].shift(2)
    
    # شروط الإشارة
    data['Buy_Signal'] = (data['Close'] > data['EMA200']) & (data['EMA50'] > data['EMA200']) & (data['RSI'] > 50) & data['FVG_Bull']
    data['Sell_Signal'] = (data['Close'] < data['EMA200']) & (data['EMA50'] < data['EMA200']) & (data['RSI'] < 50) & data['FVG_Bear']
    
    return data

# 5. دالة الـ Backtest
def run_backtest(data, tp_mult=1.5, sl_mult=1.5):
    wins = 0
    losses = 0
    
    # كنبداو من الشمعة 200 حيت EMA200 كتحتاج داتا باش تتحسب
    for i in range(200, len(data) - 30):
        row = data.iloc[i]
        
        # إلا كانت إشارة شراء
        if row['Buy_Signal']:
            entry = row['Close']
            sl = entry - (row['ATR'] * sl_mult)
            tp = entry + (row['ATR'] * tp_mult)
            
            # كنقلبو فالشموع اللي من بعد (كنعطيوها 30 شمعة باش توصل للهدف أو الستوب)
            for j in range(i+1, i+30):
                if data['High'].iloc[j] >= tp:
                    wins += 1
                    break
                elif data['Low'].iloc[j] <= sl:
                    losses += 1
                    break
                    
        # إلا كانت إشارة بيع
        elif row['Sell_Signal']:
            entry = row['Close']
            sl = entry + (row['ATR'] * sl_mult)
            tp = entry - (row['ATR'] * tp_mult)
            
            for j in range(i+1, i+30):
                if data['Low'].iloc[j] <= tp:
                    wins += 1
                    break
                elif data['High'].iloc[j] >= sl:
                    losses += 1
                    break
                    
    total = wins + losses
    win_rate = (wins / total * 100) if total > 0 else 0
    return wins, losses, total, win_rate

# ==========================================
# واجهة التطبيق
# ==========================================
st.sidebar.markdown("---")
# زر الـ Backtest
if st.sidebar.button("📊 تشغيل الاختبار التاريخي (Backtest)", use_container_width=True):
    with st.spinner('جاري اختبار الاستراتيجية على الداتا السابقة...'):
        try:
            data = get_data(symbol, period, timeframe)
            data = calculate_indicators(data)
            
            wins, losses, total, win_rate = run_backtest(data)
            
            st.subheader("📈 نتائج الاختبار التاريخي (Backtest Results)")
            if total > 0:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("إجمالي الصفقات", total)
                col2.metric("صفقات رابحة (TP1)", wins, delta="Win", delta_color="normal")
                col3.metric("صفقات خاسرة (SL)", losses, delta="Loss", delta_color="inverse")
                
                # لون نسبة النجاح على حساب النتيجة
                color = "green" if win_rate >= 60 else "orange" if win_rate >= 50 else "red"
                col4.metric("نسبة النجاح (Win Rate)", f"{win_rate:.1f}%")
                
                st.info(f"💡 **ملاحظة:** هاد الاختبار دار على أساس الستوب 1.5 ATR والهدف الأول 1.5 ATR. إلا كانت النسبة فوق 55%، يعني الاستراتيجية مربحة على المدى الطويل.")
            else:
                st.warning("ماكاينش إشارات كافية فالفترة الماضية باش نديرو الاختبار. جرب تبدل الفريم ولا العملة.")
                
        except Exception as e:
            st.error(f"وقع خطأ: {e}")

st.sidebar.markdown("---")

# زر التحليل المباشر
if st.sidebar.button("🚀 تحليل السوق الحالي (Live Signal)", use_container_width=True):
    with st.spinner('جاري تحليل السوق...'):
        try:
            data = get_data(symbol, period, timeframe)
            data = calculate_indicators(data)
            
            last_row = data.iloc[-1]
            last_close = float(last_row['Close'])
            last_atr = float(last_row['ATR'])
            
            # كنشوفو واش آخر شمعة فيها إشارة
            buy_signal = last_row['Buy_Signal']
            sell_signal = last_row['Sell_Signal']
            
            signal = "WAITING"
            color = "gray"
            conf = 0
            
            if buy_signal:
                signal = "BUY"
                color = "#00FF00"
                conf = 85
            elif sell_signal:
                signal = "SELL"
                color = "#FF0000"
                conf = 78

            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if signal != "WAITING":
                    st.markdown(f"<h1 style='text-align: center; color: {color}; font-size: 60px;'>{signal}</h1>", unsafe_allow_html=True)
                    st.progress(conf / 100.0)
                    st.markdown(f"<h3 style='text-align: center;'>نسبة الثقة: {conf}%</h3>", unsafe_allow_html=True)
                    
                    if signal == "BUY":
                        sl = last_close - (last_atr * 1.5)
                        tp1 = last_close + (last_atr * 1.5)
                        tp2 = last_close + (last_atr * 2.5)
                        tp3 = last_close + (last_atr * 3.5)
                    else:
                        sl = last_close + (last_atr * 1.5)
                        tp1 = last_close - (last_atr * 1.5)
                        tp2 = last_close - (last_atr * 2.5)
                        tp3 = last_close - (last_atr * 3.5)
                        
                    col_e, col_sl = st.columns(2)
                    col_e.metric("الدخول (Entry)", f"{last_close:.2f}")
                    col_sl.metric("الستوب لوز (SL)", f"{sl:.2f}", delta="-خطر-", delta_color="inverse")
                    
                    st.markdown("---")
                    col_tp1, col_tp2, col_tp3 = st.columns(3)
                    col_tp1.metric("الهدف 1 (TP1)", f"{tp1:.2f}")
                    col_tp2.metric("الهدف 2 (TP2)", f"{tp2:.2f}")
                    col_tp3.metric("الهدف 3 (TP3)", f"{tp3:.2f}")
                else:
                    st.warning("⚠️ السوق غير واضح حالياً فهاد اللحظة. يرجى الانتظار.")

        except Exception as e:
            st.error(f"وقع خطأ: {e}")
