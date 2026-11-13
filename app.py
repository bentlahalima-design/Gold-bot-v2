import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import ta

st.set_page_config(page_title="VIP Scalper V13", page_icon="⚡", layout="wide")
st.title("⚡ VIP Scalper V13 (ICT/SMC + S&D + 150 Pips Total)")
st.markdown("---")

# ==========================================
# 1. الإعدادات (مصلحة باش تقبل الأرقام بلا مشاكل)
# ==========================================
st.sidebar.header("⚙️ إعدادات السكالبينغ")
symbol = st.sidebar.text_input("رمز العملة", "GC=F")
timeframe = st.sidebar.selectbox("الفريم الزمني (Timeframe)", ["5m", "15m"], index=0)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 إدارة المخاطر (بالنقط)")
pip_size = st.sidebar.number_input("قيمة النقطة (Pip Size)", value=0.1, step=0.1, format="%.1f")
sl_pips = st.sidebar.number_input("الستوب لوز (نقطة)", value=50, step=10)
tp1_pips = st.sidebar.number_input("الهدف 1 (نقطة)", value=50, step=10)
tp2_pips = st.sidebar.number_input("الهدف 2 (نقطة)", value=50, step=10)
tp3_pips = st.sidebar.number_input("الهدف 3 (نقطة)", value=50, step=10)

# ==========================================
# 2. جلب الداتا
# ==========================================
@st.cache_data(ttl=60)
def get_data(symbol, period, interval):
    data = yf.download(tickers=symbol, period=period, interval=interval, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    data.dropna(inplace=True)
    return data

# ==========================================
# 3. منطق SMC/ICT (دقة عالية)
# ==========================================
def calculate_smc_logic(df):
    # 1. الاتجاه (Trend)
    df['EMA50'] = ta.trend.ema_indicator(df['Close'], window=50)
    df['EMA200'] = ta.trend.ema_indicator(df['Close'], window=200)
    df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
    
    # 2. السيولة (Liquidity Sweeps)
    # كنشوفو واش السعر كسر أدنى سعر ديال 10 شموع اللي فاتو ورجع
    df['Swing_Low'] = df['Low'].rolling(window=10).min().shift(1)
    df['Swing_High'] = df['High'].rolling(window=10).max().shift(1)
    
    df['Sweep_Low'] = (df['Low'] < df['Swing_Low']) & (df['Close'] > df['Swing_Low'])
    df['Sweep_High'] = (df['High'] > df['Swing_High']) & (df['Close'] < df['Swing_High'])
    
    # 3. الفجوات السعرية (FVG) والـ Order Blocks
    body = abs(df['Close'] - df['Open'])
    avg_body = body.rolling(10).mean()
    strong = body > avg_body * 1.2
    
    df['FVG_Bull'] = (df['Low'] > df['High'].shift(2)) & strong
    df['FVG_Bear'] = (df['High'] < df['Low'].shift(2)) & strong
    
    df['Bull_OB'] = (df['Close'].shift(1) < df['Open'].shift(1)) & (df['Close'] > df['Open']) & (df['Close'] > df['High'].shift(1))
    df['Bear_OB'] = (df['Close'].shift(1) > df['Open'].shift(1)) & (df['Close'] < df['Open']) & (df['Close'] < df['Low'].shift(1))
    
    # 4. الدعم والمقاومة (Support/Resistance)
    df['Resistance'] = df['High'].rolling(window=20).max()
    df['Support'] = df['Low'].rolling(window=20).min()
    
    return df

# ==========================================
# 4. محرك الاختبار التاريخي (دقيق)
# ==========================================
def run_backtest(df, sl_dist, tp1, tp2, tp3):
    wins = 0
    losses = 0
    total_trades = 0
    
    in_trade = False
    trade_type = None
    entry = 0
    sl = 0
    
    for i in range(200, len(df) - 20):
        row = df.iloc[i]
        
        if not in_trade:
            # شروط الشراء (لازم كلشي يتحقق باش البوت يدخل)
            buy_cond = (
                (row['Close'] > row['EMA200']) and 
                (row['RSI'] > 50) and 
                row['Sweep_Low'] and 
                (row['FVG_Bull'] or row['Bull_OB']) and
                (row['Close'] < row['Support'] * 1.005) # قريب من منطقة الطلب
            )
            
            # شروط البيع
            sell_cond = (
                (row['Close'] < row['EMA200']) and 
                (row['RSI'] < 50) and 
                row['Sweep_High'] and 
                (row['FVG_Bear'] or row['Bear_OB']) and
                (row['Close'] > row['Resistance'] * 0.995) # قريب من منطقة العرض
            )
            
            if buy_cond:
                in_trade = True
                trade_type = "BUY"
                entry = row['Close']
                sl = entry - sl_dist
                target1, target2, target3 = entry + tp1, entry + tp2, entry + tp3
            elif sell_cond:
                in_trade = True
                trade_type = "SELL"
                entry = row['Close']
                sl = entry + sl_dist
                target1, target2, target3 = entry - tp1, entry - tp2, entry - tp3
                
        else:
            if trade_type == "BUY":
                if row['Low'] <= sl:
                    losses += 1
                    in_trade = False
                elif row['High'] >= target3:
                    wins += 1
                    in_trade = False
                elif row['High'] >= target1: # إلا وصل TP1 كنحسبوها ربح
                    wins += 1
                    in_trade = False
                    
            elif trade_type == "SELL":
                if row['High'] >= sl:
                    losses += 1
                    in_trade = False
                elif row['Low'] <= target3:
                    wins += 1
                    in_trade = False
                elif row['Low'] <= target1: 
                    wins += 1
                    in_trade = False

    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    return wins, losses, total_trades, win_rate

# ==========================================
# 5. الواجهة الرئيسية
# ==========================================
if st.sidebar.button("🚀 تحليل السوق الآن", use_container_width=True):
    with st.spinner('جاري البحث عن أفضل الفرص...'):
        try:
            df = get_data(symbol, "30d", timeframe) # 30 يوم كافية للسكالبينغ
            df = calculate_smc_logic(df)
            
            if len(df) > 200:
                last_row = df.iloc[-1]
                last_close = float(last_row['Close'])
                
                sl_dist = sl_pips * pip_size
                tp1_dist = tp1_pips * pip_size
                tp2_dist = tp2_pips * pip_size
                tp3_dist = tp3_pips * pip_size
                
                current_buy = (
                    (last_row['Close'] > last_row['EMA200']) and 
                    (last_row['RSI'] > 50) and 
                    last_row['Sweep_Low'] and 
                    (last_row['FVG_Bull'] or last_row['Bull_OB']) and
                    (last_row['Close'] < last_row['Support'] * 1.005)
                )
                
                current_sell = (
                    (last_row['Close'] < last_row['EMA200']) and 
                    (last_row['RSI'] < 50) and 
                    last_row['Sweep_High'] and 
                    (last_row['FVG_Bear'] or last_row['Bear_OB']) and
                    (last_row['Close'] > last_row['Resistance'] * 0.995)
                )
                
                signal = "WAITING"
                color = "gray"
                
                if current_buy:
                    signal, color = "BUY", "#00FF00"
                    sl = last_close - sl_dist
                    tp1, tp2, tp3 = last_close + tp1_dist, last_close + tp2_dist, last_close + tp3_dist
                elif current_sell:
                    signal, color = "SELL", "#FF0000"
                    sl = last_close + sl_dist
                    tp1, tp2, tp3 = last_close - tp1_dist, last_close - tp2_dist, last_close - tp3_dist

                col1, col2, col3 = st.columns([1, 2, 1])
                with col2:
                    if signal != "WAITING":
                        st.markdown(f"<h1 style='text-align: center; color: {color}; font-size: 60px;'>{signal}</h1>", unsafe_allow_html=True)
                        st.markdown(f"<h3 style='text-align: center;'>إشارة السكالبينغ (سيولة + فجوة + دعم/مقاومة) ⚡</h3>", unsafe_allow_html=True)
                        
                        col_e, col_sl = st.columns(2)
                        col_e.metric("الدخول (Entry)", f"{last_close:.2f}")
                        col_sl.metric("الستوب لوز (SL)", f"{sl:.2f}", delta="-خطر-", delta_color="inverse")
                        
                        st.markdown("---")
                        col_tp1, col_tp2, col_tp3 = st.columns(3)
                        col_tp1.metric(f"الهدف 1 ({tp1_pips} نقطة)", f"{tp1:.2f}")
                        col_tp2.metric(f"الهدف 2 ({tp2_pips} نقطة)", f"{tp2:.2f}")
                        col_tp3.metric(f"الهدف 3 ({tp3_pips} نقطة)", f"{tp3:.2f}")
                    else:
                        st.warning("⚠️ السوق غير واضح حالياً. البوت كينتظر ضربة سيولة + فجوة سعرية. ماتدخلش دابا.")

                # النتائج
                st.markdown("---")
                st.subheader(f"📊 نتائج الباك تست (Scalper V13 - فريم {timeframe})")
                wins, losses, total, win_rate = run_backtest(df, sl_dist, tp1_dist, tp2_dist, tp3_dist)
                
                if total > 0:
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("إجمالي الإشارات", total)
                    c2.metric("ناجحة (وصلت TP1)", wins)
                    c3.metric("خاسرة (ضربت SL)", losses)
                    c4.metric("نسبة النجاح", f"{win_rate:.1f}%")
                    
                    st.info(f"💡 **الهدف:** البوت كيقلب على 5 صفقات فاليوم مع ستوب 50 نقطة، وأهداف (50/50/50) باش يوصل لـ 150 نقطة.")
                else:
                    st.error("ماكاينش إشارات فالفترة الماضية.")
            else:
                st.error("الداتا غير كافية.")

        except Exception as e:
            st.error(f"وقع خطأ: {e}")
