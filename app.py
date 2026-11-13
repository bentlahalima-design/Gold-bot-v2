import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import ta

# 1. إعدادات الصفحة
st.set_page_config(page_title="Gold AI Trader - V5", page_icon="🥇", layout="wide")
st.title("🥇 Gold AI Trader - V5 (Trend Filter + Fixed Pips)")
st.markdown("---")

# 2. الشريط الجانبي (Sidebar)
st.sidebar.header("⚙️ الإعدادات (Settings)")
symbol = st.sidebar.text_input("رمز العملة (GC=F للدهب)", "GC=F")
timeframe = st.sidebar.selectbox("الفريم الزمني للدخول", ["15m", "30m", "1h"], index=0)
period = "30d"

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 إدارة المخاطر (بالنقط)")
pip_size = st.sidebar.number_input("حجم البيب الواحد (Pip Size)", value=0.1, step=0.01, help="فالدهب غالباً 0.1 كتعني 1 بيب.")
sl_pips = st.sidebar.number_input("الستوب لوز (SL Pips)", value=50, step=10)
tp1_pips = st.sidebar.number_input("الهدف الأول (TP1 Pips)", value=100, step=10)
tp2_pips = st.sidebar.number_input("الهدف الثاني (TP2 Pips)", value=200, step=10)

# 3. دالة جلب الداتا
@st.cache_data(ttl=60)
def get_data(symbol, period, interval):
    data = yf.download(tickers=symbol, period=period, interval=interval, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

# 4. دالة حساب المؤشرات
def calculate_indicators(data):
    data['EMA50'] = ta.trend.ema_indicator(data['Close'], window=50)
    data['EMA200'] = ta.trend.ema_indicator(data['Close'], window=200)
    data['RSI'] = ta.momentum.rsi(data['Close'], window=14)
    data['ATR'] = ta.volatility.average_true_range(data['High'], data['Low'], data['Close'], window=14)
    
    # SMC FVG
    data['FVG_Bull'] = data['Low'] > data['High'].shift(2)
    data['FVG_Bear'] = data['High'] < data['Low'].shift(2)
    
    return data

# 5. دالة الـ Backtest (مطورة)
def run_backtest(data, htf_trend, sl_dist, tp1_dist, tp2_dist):
    wins_tp1 = 0
    wins_tp2 = 0
    losses = 0
    gross_profit = 0
    gross_loss = 0
    
    for i in range(200, len(data) - 30):
        row = data.iloc[i]
        
        # شرط الشراء (مع فلتر الترند)
        if row['Close'] > row['EMA200'] and row['EMA50'] > row['EMA200'] and row['RSI'] > 50 and row['FVG_Bull'] and htf_trend == "UP":
            entry = row['Close']
            sl = entry - sl_dist
            tp1 = entry + tp1_dist
            tp2 = entry + tp2_dist
            
            for j in range(i+1, i+50): # كنعطيوه 50 شمعة باش يوصل
                if data['Low'].iloc[j] <= sl:
                    losses += 1
                    gross_loss += sl_dist
                    break
                elif data['High'].iloc[j] >= tp2:
                    wins_tp2 += 1
                    gross_profit += tp2_dist
                    break
                elif data['High'].iloc[j] >= tp1:
                    wins_tp1 += 1
                    gross_profit += tp1_dist
                    break
                    
        # شرط البيع (مع فلتر الترند)
        elif row['Close'] < row['EMA200'] and row['EMA50'] < row['EMA200'] and row['RSI'] < 50 and row['FVG_Bear'] and htf_trend == "DOWN":
            entry = row['Close']
            sl = entry + sl_dist
            tp1 = entry - tp1_dist
            tp2 = entry - tp2_dist
            
            for j in range(i+1, i+50):
                if data['High'].iloc[j] >= sl:
                    losses += 1
                    gross_loss += sl_dist
                    break
                elif data['Low'].iloc[j] <= tp2:
                    wins_tp2 += 1
                    gross_profit += tp2_dist
                    break
                elif data['Low'].iloc[j] <= tp1:
                    wins_tp1 += 1
                    gross_profit += tp1_dist
                    break
                    
    total_wins = wins_tp1 + wins_tp2
    total = total_wins + losses
    win_rate = (total_wins / total * 100) if total > 0 else 0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
    return total_wins, wins_tp1, wins_tp2, losses, total, win_rate, profit_factor

# ==========================================
# واجهة التطبيق
# ==========================================
st.sidebar.markdown("---")

# زر التحليل
if st.sidebar.button("🚀 تحليل السوق (Get Signal)", use_container_width=True):
    with st.spinner('جاري جلب الداتا وتحليل الترند...'):
        try:
            # جلب داتا الفريم ديال الدخول
            data = get_data(symbol, period, timeframe)
            data = calculate_indicators(data)
            
            # جلب داتا فريم الساعة (1H) باش نفلترو الترند
            data_htf = get_data(symbol, "30d", "1h")
            data_htf = calculate_indicators(data_htf)
            
            # تحديد اتجاه الترند فالساعة
            htf_trend = "UP" if data_htf['Close'].iloc[-1] > data_htf['EMA200'].iloc[-1] else "DOWN"
            
            last_row = data.iloc[-1]
            last_close = float(last_row['Close'])
            
            # القيم بالنقط
            sl_dist = sl_pips * pip_size
            tp1_dist = tp1_pips * pip_size
            tp2_dist = tp2_pips * pip_size
            
            # الشروط
            buy_signal = last_row['Close'] > last_row['EMA200'] and last_row['EMA50'] > last_row['EMA200'] and last_row['RSI'] > 50 and last_row['FVG_Bull'] and htf_trend == "UP"
            sell_signal = last_row['Close'] < last_row['EMA200'] and last_row['EMA50'] < last_row['EMA200'] and last_row['RSI'] < 50 and last_row['FVG_Bear'] and htf_trend == "DOWN"
            
            signal = "WAITING"
            color = "gray"
            
            if buy_signal:
                signal = "BUY"
                color = "#00FF00"
                sl = last_close - sl_dist
                tp1 = last_close + tp1_dist
                tp2 = last_close + tp2_dist
            elif sell_signal:
                signal = "SELL"
                color = "#FF0000"
                sl = last_close + sl_dist
                tp1 = last_close - tp1_dist
                tp2 = last_close - tp2_dist

            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                st.info(f"📊 **ترند الساعة (1H):** {htf_trend}")
                
                if signal != "WAITING":
                    st.markdown(f"<h1 style='text-align: center; color: {color}; font-size: 60px;'>{signal}</h1>", unsafe_allow_html=True)
                    st.markdown(f"<h3 style='text-align: center;'>الإشارة مدعومة بالترند ✅</h3>", unsafe_allow_html=True)
                    
                    col_e, col_sl = st.columns(2)
                    col_e.metric("الدخول (Entry)", f"{last_close:.2f}")
                    col_sl.metric("الستوب لوز (SL)", f"{sl:.2f}", delta="-خطر-", delta_color="inverse")
                    
                    st.markdown("---")
                    col_tp1, col_tp2 = st.columns(2)
                    col_tp1.metric(f"الهدف 1 ({tp1_pips} بيب)", f"{tp1:.2f}")
                    col_tp2.metric(f"الهدف 2 ({tp2_pips} بيب)", f"{tp2:.2f}")
                else:
                    st.warning("⚠️ السوق غير واضح حالياً، ولا الترند فالساعة ماكيدعمش الإشارة. ماتدخلش.")

            # تشغيل الباك تست أوتوماتيكيا فتحت الواجهة
            st.markdown("---")
            st.subheader("📈 نتائج الاختبار التاريخي (Backtest) مع فلتر الترند")
            
            # هنا كنستعملو ترند ثابت للتبسيط فالباك تست (ولا تقدر تبرمجو يتغير)
            total_wins, wins_tp1, wins_tp2, losses, total, win_rate, pf = run_backtest(data, "UP", sl_dist, tp1_dist, tp2_dist)
            total_wins_down, wins_tp1_dn, wins_tp2_dn, losses_dn, total_dn, win_rate_dn, pf_dn = run_backtest(data, "DOWN", sl_dist, tp1_dist, tp2_dist)
            
            # دمج النتائج
            final_wins = total_wins + total_wins_down
            final_losses = losses + losses_dn
            final_total = final_wins + final_losses
            final_wr = (final_wins / final_total * 100) if final_total > 0 else 0
            final_pf = ((wins_tp1 + wins_tp2)*tp1_dist) / (final_losses * sl_dist) if final_losses > 0 else 0
            
            if final_total > 0:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("إجمالي الصفقات", final_total)
                c2.metric("أرباح (TP1+TP2)", final_wins)
                c3.metric("خسائر (SL)", final_losses)
                c4.metric("نسبة النجاح", f"{final_wr:.1f}%")
                
                st.success(f"💡 **معامل الربح (Profit Factor):** {final_pf:.2f} | إلا كان فوق 1.5 فهو ممتاز.")
                
        except Exception as e:
            st.error(f"وقع خطأ: {e}")
