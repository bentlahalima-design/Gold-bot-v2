import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import ta

st.set_page_config(page_title="SMC Scalper V7", page_icon="⚡", layout="wide")
st.title("⚡ SMC/ICT Gold Scalper - V7")
st.markdown("---")

# ==========================================
# 1. الشريط الجانبي (Settings)
# ==========================================
st.sidebar.header("⚙️ إعدادات السكالبينغ")
symbol = st.sidebar.text_input("رمز العملة", "GC=F")
timeframe = st.sidebar.selectbox("الفريم (Timeframe)", ["5m", "15m"], index=0)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 إدارة المخاطر (بالنقط)")
# فـ الدهب، النقطة = 0.1 دولار. 100 نقطة = 10 دولار
pip_size = st.sidebar.number_input("قيمة النقطة (Pip Size)", value=0.1, step=0.01, format="%.2f")
sl_pips = st.sidebar.number_input("الستوب لوز (نقطة)", value=100, step=10)
tp1_pips = st.sidebar.number_input("الهدف 1 (نقطة)", value=100, step=10)
tp2_pips = st.sidebar.number_input("الهدف 2 (نقطة)", value=200, step=10)
tp3_pips = st.sidebar.number_input("الهدف 3 (نقطة)", value=300, step=10)

# ==========================================
# 2. جلب الداتا
# ==========================================
@st.cache_data(ttl=60)
def get_data(symbol, period, interval):
    data = yf.download(tickers=symbol, period=period, interval=interval, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data

# ==========================================
# 3. المؤشرات ومنطق SMC/ICT
# ==========================================
def calculate_smc_logic(df):
    # المؤشرات الأساسية
    df['EMA50'] = ta.trend.ema_indicator(df['Close'], window=50)
    df['EMA200'] = ta.trend.ema_indicator(df['Close'], window=200)
    df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
    
    # كشف FVG (Fair Value Gap)
    # الفجوة الصاعدة: قاع الشمعة الحالية أعلى من قمة الشمعة اللي قبل جوج
    df['FVG_Bull'] = df['Low'] > df['High'].shift(2)
    # الفجوة الهابطة: قمة الشمعة الحالية أقل من قاع الشمعة اللي قبل جوج
    df['FVG_Bear'] = df['High'] < df['Low'].shift(2)
    
    # تقريب Order Block / Supply & Demand (شمعة قوية عكس الاتجاه قبل الحركة)
    df['Bull_OB'] = (df['Close'].shift(1) < df['Open'].shift(1)) & (df['Close'] > df['Open']) & (df['Close'] > df['High'].shift(1))
    df['Bear_OB'] = (df['Close'].shift(1) > df['Open'].shift(1)) & (df['Close'] < df['Open']) & (df['Close'] < df['Low'].shift(1))
    
    return df

# ==========================================
# 4. محرك الاختبار التاريخي (Backtest)
# ==========================================
def run_backtest(df, sl_dist, tp1_dist, tp2_dist, tp3_dist):
    wins = 0
    losses = 0
    gross_profit = 0
    gross_loss = 0
    total_trades = 0
    
    for i in range(200, len(df) - 20):
        row = df.iloc[i]
        
        # شرط الشراء (SMC Confluence)
        buy_signal = (row['Close'] > row['EMA200']) and (row['EMA50'] > row['EMA200']) and (row['RSI'] > 50) and (row['FVG_Bull'] or row['Bull_OB'])
        
        # شرط البيع
        sell_signal = (row['Close'] < row['EMA200']) and (row['EMA50'] < row['EMA200']) and (row['RSI'] < 50) and (row['FVG_Bear'] or row['Bear_OB'])
        
        if buy_signal:
            total_trades += 1
            entry = row['Close']
            sl = entry - sl_dist
            tp1 = entry + tp1_dist
            tp2 = entry + tp2_dist
            tp3 = entry + tp3_dist
            
            # كنقلبو على النتيجة فـ 15 شمعة القادمة
            for j in range(i+1, min(i+15, len(df))):
                if df['Low'].iloc[j] <= sl:
                    losses += 1
                    gross_loss += sl_dist
                    break
                elif df['High'].iloc[j] >= tp1: # كنحسبو النجاح ملي كيوصل TP1
                    wins += 1
                    gross_profit += tp1_dist
                    break
                    
        elif sell_signal:
            total_trades += 1
            entry = row['Close']
            sl = entry + sl_dist
            tp1 = entry - tp1_dist
            tp2 = entry - tp2_dist
            tp3 = entry - tp3_dist
            
            for j in range(i+1, min(i+15, len(df))):
                if df['High'].iloc[j] >= sl:
                    losses += 1
                    gross_loss += sl_dist
                    break
                elif df['Low'].iloc[j] <= tp1:
                    wins += 1
                    gross_profit += tp1_dist
                    break
                    
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
    return wins, losses, total_trades, win_rate, profit_factor

# ==========================================
# 5. واجهة التطبيق الرئيسية
# ==========================================
if st.sidebar.button("🚀 تحليل السوق الآن", use_container_width=True):
    with st.spinner('جاري تحليل السيولة والهيكل...'):
        try:
            df = get_data(symbol, "30d", timeframe)
            df = calculate_smc_logic(df)
            
            last_row = df.iloc[-1]
            last_close = float(last_row['Close'])
            
            sl_dist = sl_pips * pip_size
            tp1_dist = tp1_pips * pip_size
            tp2_dist = tp2_pips * pip_size
            tp3_dist = tp3_pips * pip_size
            
            # شروط الإشارة الحالية
            current_buy = (last_row['Close'] > last_row['EMA200']) and (last_row['EMA50'] > last_row['EMA200']) and (last_row['RSI'] > 50) and (last_row['FVG_Bull'] or last_row['Bull_OB'])
            current_sell = (last_row['Close'] < last_row['EMA200']) and (last_row['EMA50'] < last_row['EMA200']) and (last_row['RSI'] < 50) and (last_row['FVG_Bear'] or last_row['Bear_OB'])
            
            signal = "WAITING"
            color = "gray"
            
            if current_buy:
                signal, color = "BUY", "#00FF00"
                sl = last_close - sl_dist
                tp1 = last_close + tp1_dist
                tp2 = last_close + tp2_dist
                tp3 = last_close + tp3_dist
            elif current_sell:
                signal, color = "SELL", "#FF0000"
                sl = last_close + sl_dist
                tp1 = last_close - tp1_dist
                tp2 = last_close - tp2_dist
                tp3 = last_close - tp3_dist

            col1, col2, col3 = st.columns([1, 2, 1])
            with col2:
                if signal != "WAITING":
                    st.markdown(f"<h1 style='text-align: center; color: {color}; font-size: 60px;'>{signal}</h1>", unsafe_allow_html=True)
                    st.markdown(f"<h3 style='text-align: center;'>إشارة SMC/ICT مؤكدة ✅</h3>", unsafe_allow_html=True)
                    
                    col_e, col_sl = st.columns(2)
                    col_e.metric("الدخول (Entry)", f"{last_close:.2f}")
                    col_sl.metric("الستوب لوز (SL)", f"{sl:.2f}", delta="-خطر-", delta_color="inverse")
                    
                    st.markdown("---")
                    col_tp1, col_tp2, col_tp3 = st.columns(3)
                    col_tp1.metric(f"الهدف 1 ({tp1_pips} نقطة)", f"{tp1:.2f}")
                    col_tp2.metric(f"الهدف 2 ({tp2_pips} نقطة)", f"{tp2:.2f}")
                    col_tp3.metric(f"الهدف 3 ({tp3_pips} نقطة)", f"{tp3:.2f}")
                else:
                    st.warning("⚠️ السوق غير واضح حالياً. البوت كينتظر تكون فجوة سعرية (FVG) ولا Order Block مع تأكيد الترند. ماتدخلش دابا.")

            # النتائج
            st.markdown("---")
            st.subheader("📊 نتائج الاختبار التاريخي (SMC Backtest)")
            wins, losses, total, win_rate, pf = run_backtest(df, sl_dist, tp1_dist, tp2_dist, tp3_dist)
            
            if total > 0:
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("إجمالي الإشارات", total)
                c2.metric("ناجحة (وصلت TP1)", wins)
                c3.metric("خاسرة (ضربت SL)", losses)
                
                # لون النسبة
                wr_color = "green" if win_rate > 50 else "red"
                c4.metric("نسبة النجاح", f"{win_rate:.1f}%")
                
                st.info(f"💡 **معامل الربح (Profit Factor):** {pf:.2f} | هاد البوت كيعتمد على السكالبينغ عكس الاتجاه ولا مع الاتجاه، تأكد من رسم الشارت بعينك قبل الدخول.")
            else:
                st.error("ماكاينش إشارات فالفترة الماضية، جرب تبدل الفريم ولا العملة.")
                
        except Exception as e:
            st.error(f"وقع خطأ: {e}")
