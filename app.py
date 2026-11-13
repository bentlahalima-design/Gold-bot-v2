import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import ta

st.set_page_config(page_title="SMC Scalper V8", page_icon="⚡", layout="wide")
st.title("⚡ SMC/ICT Gold Scalper - V8 (Advanced)")
st.markdown("---")

# ==========================================
# 1. الشريط الجانبي (Settings)
# ==========================================
st.sidebar.header("⚙️ إعدادات السكالبينغ")
symbol = st.sidebar.text_input("رمز العملة", "GC=F")
timeframe = st.sidebar.selectbox("الفريم (Timeframe)", ["5m", "15m"], index=0)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 إدارة المخاطر (بالنقط)")
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
# 3. منطق SMC/ICT المتقدم
# ==========================================
def calculate_smc_logic(df):
    # مؤشرات الترند
    df['EMA50'] = ta.trend.ema_indicator(df['Close'], window=50)
    df['EMA200'] = ta.trend.ema_indicator(df['Close'], window=200)
    df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
    
    # كشف القمم والقيعان (Liquidity) والقمم السابقة
    df['Swing_High'] = df['High'].rolling(window=10).max()
    df['Swing_Low'] = df['Low'].rolling(window=10).min()
    df['Prev_Swing_High'] = df['Swing_High'].shift(1)
    df['Prev_Swing_Low'] = df['Swing_Low'].shift(1)
    
    # كشف FVG مع شمعة قوية (Displacement)
    body_size = abs(df['Close'] - df['Open'])
    avg_body = body_size.rolling(10).mean()
    strong_candle = body_size > avg_body * 1.5
    
    df['FVG_Bull'] = (df['Low'] > df['High'].shift(2)) & strong_candle
    df['FVG_Bear'] = (df['High'] < df['Low'].shift(2)) & strong_candle
    
    # Order Block بسيط (Engulfing)
    df['Bull_OB'] = (df['Close'].shift(1) < df['Open'].shift(1)) & (df['Close'] > df['Open']) & (df['Close'] > df['High'].shift(1))
    df['Bear_OB'] = (df['Close'].shift(1) > df['Open'].shift(1)) & (df['Close'] < df['Open']) & (df['Close'] < df['Low'].shift(1))
    
    return df

# ==========================================
# 4. محرك الاختبار التاريخي (دقيق)
# ==========================================
def run_backtest(df, sl_dist, tp1_dist):
    wins = 0
    losses = 0
    gross_profit = 0
    gross_loss = 0
    total_trades = 0
    
    in_trade = False
    trade_type = None
    
    for i in range(200, len(df) - 20):
        row = df.iloc[i]
        
        if not in_trade:
            # شرط الشراء: ترند صاعد + (FVG أو OB) + كسر سيولة سابقة
            buy_cond = (row['Close'] > row['EMA200']) and (row['RSI'] > 50) and (row['FVG_Bull'] or row['Bull_OB']) and (row['Close'] > row['Prev_Swing_High'])
            
            # شرط البيع: ترند هابط + (FVG أو OB) + كسر سيولة سابقة
            sell_cond = (row['Close'] < row['EMA200']) and (row['RSI'] < 50) and (row['FVG_Bear'] or row['Bear_OB']) and (row['Close'] < row['Prev_Swing_Low'])
            
            if buy_cond:
                in_trade = True
                trade_type = "BUY"
                entry = row['Close']
                sl = entry - sl_dist
                tp1 = entry + tp1_dist
            elif sell_cond:
                in_trade = True
                trade_type = "SELL"
                entry = row['Close']
                sl = entry + sl_dist
                tp1 = entry - tp1_dist
                
        else:
            # إلا كنا فصفقة، كنقلبو واش ضربت الستوب ولا الهدف
            if trade_type == "BUY":
                if row['Low'] <= sl:
                    losses += 1
                    gross_loss += sl_dist
                    in_trade = False
                elif row['High'] >= tp1:
                    wins += 1
                    gross_profit += tp1_dist
                    in_trade = False
            elif trade_type == "SELL":
                if row['High'] >= sl:
                    losses += 1
                    gross_loss += sl_dist
                    in_trade = False
                elif row['Low'] <= tp1:
                    wins += 1
                    gross_profit += tp1_dist
                    in_trade = False

    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
    return wins, losses, total_trades, win_rate, profit_factor

# ==========================================
# 5. واجهة التطبيق الرئيسية
# ==========================================
if st.sidebar.button("🚀 تحليل السوق الآن", use_container_width=True):
    with st.spinner('جاري تحليل السيولة والهيكل...'):
        try:
            df = get_data(symbol, "60d", timeframe)
            df = calculate_smc_logic(df)
            
            # التأكد من أن الداتا كافية
            if len(df) > 200:
                last_row = df.iloc[-1]
                last_close = float(last_row['Close'])
                
                sl_dist = sl_pips * pip_size
                tp1_dist = tp1_pips * pip_size
                tp2_dist = tp2_pips * pip_size
                tp3_dist = tp3_pips * pip_size
                
                # الشروط ديال آخر شمعة
                current_buy = (last_row['Close'] > last_row['EMA200']) and (last_row['RSI'] > 50) and (last_row['FVG_Bull'] or last_row['Bull_OB']) and (last_row['Close'] > last_row['Prev_Swing_High'])
                current_sell = (last_row['Close'] < last_row['EMA200']) and (last_row['RSI'] < 50) and (last_row['FVG_Bear'] or last_row['Bear_OB']) and (last_row['Close'] < last_row['Prev_Swing_Low'])
                
                signal = "WAITING"
                color = "gray"
                
                if current_buy:
                    signal, color = "BUY", "#00FF00"
                    sl, tp1, tp2, tp3 = last_close - sl_dist, last_close + tp1_dist, last_close + tp2_dist, last_close + tp3_dist
                elif current_sell:
                    signal, color = "SELL", "#FF0000"
                    sl, tp1, tp2, tp3 = last_close + sl_dist, last_close - tp1_dist, last_close - tp2_dist, last_close - tp3_dist

                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    if signal != "WAITING":
                        st.markdown(f"<h1 style='text-align: center; color: {color}; font-size: 60px;'>{signal}</h1>", unsafe_allow_html=True)
                        st.markdown(f"<h3 style='text-align: center;'>إشارة SMC/ICT (سيولة + فجوة) ✅</h3>", unsafe_allow_html=True)
                        
                        col_e, col_sl = st.columns(2)
                        col_e.metric("الدخول (Entry)", f"{last_close:.2f}")
                        col_sl.metric("الستوب لوز (SL)", f"{sl:.2f}", delta="-خطر-", delta_color="inverse")
                        
                        st.markdown("---")
                        col_tp1, col_tp2, col_tp3 = st.columns(3)
                        col_tp1.metric(f"الهدف 1 ({tp1_pips} نقطة)", f"{tp1:.2f}")
                        col_tp2.metric(f"الهدف 2 ({tp2_pips} نقطة)", f"{tp2:.2f}")
                        col_tp3.metric(f"الهدف 3 ({tp3_pips} نقطة)", f"{tp3:.2f}")
                    else:
                        st.warning("⚠️ السوق غير واضح حالياً. البوت كينتظر: كسر سيولة + فجوة سعرية قوية (FVG) + تأكيد الاتجاه. ماتدخلش دابا.")

                # النتائج
                st.markdown("---")
                st.subheader("📊 نتائج الاختبار التاريخي (SMC Backtest V8)")
                wins, losses, total, win_rate, pf = run_backtest(df, sl_dist, tp1_dist)
                
                if total > 0:
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("إجمالي الإشارات", total)
                    c2.metric("ناجحة (وصلت TP1)", wins)
                    c3.metric("خاسرة (ضربت SL)", losses)
                    
                    c4.metric("نسبة النجاح", f"{win_rate:.1f}%")
                    
                    st.info(f"💡 **معامل الربح (Profit Factor):** {pf:.2f} | الهدف ديالنا هو فوق 1.5 مع تقليل عدد الصفقات باش نتفاداو التخربيق.")
                else:
                    st.error("ماكاينش إشارات فالفترة الماضية، جرب تبدل الفريم ولا العملة.")
            else:
                st.error("الداتا غير كافية للتحليل. جرب تبدل الفريم ولا العملة.")

        except Exception as e:
            st.error(f"وقع خطأ: {e}")
