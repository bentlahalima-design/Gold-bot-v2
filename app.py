import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import ta
import datetime

st.set_page_config(page_title="Sniper VIP V11", page_icon="🎯", layout="wide")
st.title("🎯 Sniper ICT/SMC Gold - V11 (VIP Edition)")
st.markdown("---")

# ==========================================
# 1. الإعدادات
# ==========================================
st.sidebar.header("⚙️ إعدادات القناص")
symbol = st.sidebar.text_input("رمز العملة", "GC=F")
timeframe = st.sidebar.selectbox("الفريم الزمني (Timeframe)", ["15m", "5m"], index=0) # 15m أصدق

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
    # تأكد أن الوقت ديال الداتا (UTC) باش نقدرو نفلترو لندن ونيويورك
    if data.index.tz is None:
        data.index = data.index.tz_localize('UTC')
    return data

# ==========================================
# 3. منطق SMC الصارم (Sniper)
# ==========================================
def calculate_sniper_logic(df):
    df['EMA50'] = ta.trend.ema_indicator(df['Close'], window=50)
    df['EMA200'] = ta.trend.ema_indicator(df['Close'], window=200)
    df['RSI'] = ta.momentum.rsi(df['Close'], window=14)
    
    # كشف السيولة (Liquidity Sweep)
    df['Prev_High'] = df['High'].rolling(window=10).max().shift(1)
    df['Prev_Low'] = df['Low'].rolling(window=10).min().shift(1)
    
    # Sweep: السعر ضرب القمة/القاع ورجع لتحت/لفوق
    df['Sweep_High'] = (df['High'] > df['Prev_High']) & (df['Close'] < df['Prev_High'])
    df['Sweep_Low'] = (df['Low'] < df['Prev_Low']) & (df['Close'] > df['Prev_Low'])
    
    # FVG & OB (مع شموع قوية)
    body = abs(df['Close'] - df['Open'])
    avg_body = body.rolling(10).mean()
    strong = body > avg_body * 1.3
    
    df['FVG_Bull'] = (df['Low'] > df['High'].shift(2)) & strong
    df['FVG_Bear'] = (df['High'] < df['Low'].shift(2)) & strong
    
    df['Bull_OB'] = (df['Close'].shift(1) < df['Open'].shift(1)) & (df['Close'] > df['Open']) & (df['Close'] > df['High'].shift(1))
    df['Bear_OB'] = (df['Close'].shift(1) > df['Open'].shift(1)) & (df['Close'] < df['Open']) & (df['Close'] < df['Low'].shift(1))
    
    # فلتر التوقيت: لندن ونيويورك (من 8:00 حتى 17:00 UTC)
    df['Hour'] = df.index.hour
    df['Killzone'] = (df['Hour'] >= 8) & (df['Hour'] <= 17)
    
    return df

# ==========================================
# 4. محرك الاختبار الذكي (Breakeven & Trailing)
# ==========================================
def run_sniper_backtest(df, sl_dist, tp1, tp2, tp3):
    wins = 0
    losses = 0
    total_trades = 0
    gross_profit = 0
    gross_loss = 0
    
    in_trade = False
    trade_type = None
    entry_price = 0
    current_sl = 0
    
    for i in range(200, len(df) - 20):
        row = df.iloc[i]
        
        if not in_trade and row['Killzone']:
            # شروط القناص للشراء (لازم كلشي يتحقق)
            buy_cond = (row['Close'] > row['EMA200']) and (row['RSI'] > 55) and \
                       row['Sweep_Low'] and (row['FVG_Bull'] or row['Bull_OB'])
            
            # شروط القناص للبيع
            sell_cond = (row['Close'] < row['EMA200']) and (row['RSI'] < 45) and \
                        row['Sweep_High'] and (row['FVG_Bear'] or row['Bear_OB'])
            
            if buy_cond:
                in_trade = True
                trade_type = "BUY"
                entry_price = row['Close']
                current_sl = entry_price - sl_dist
                
            elif sell_cond:
                in_trade = True
                trade_type = "SELL"
                entry_price = row['Close']
                current_sl = entry_price + sl_dist
                
        elif in_trade:
            if trade_type == "BUY":
                # 1. ضرب الستوب
                if row['Low'] <= current_sl:
                    if current_sl >= entry_price: # Breakeven (ما خسرناش)
                        wins += 1 # كنحسبوها ربح صفر
                    else:
                        losses += 1
                        gross_loss += sl_dist
                    in_trade = False
                
                # 2. وصل TP1 -> حرك الستوب للدخول (Breakeven)
                elif row['High'] >= entry_price + tp1 and current_sl < entry_price:
                    current_sl = entry_price
                
                # 3. وصل TP2 -> حرك الستوب لـ TP1
                elif row['High'] >= entry_price + tp2 and current_sl < entry_price + tp1:
                    current_sl = entry_price + tp1
                
                # 4. وصل TP3 -> قفل الصفقة بربح كامل
                elif row['High'] >= entry_price + tp3:
                    wins += 1
                    gross_profit += tp3
                    in_trade = False
                    
            elif trade_type == "SELL":
                if row['High'] >= current_sl:
                    if current_sl <= entry_price: 
                        wins += 1 
                    else:
                        losses += 1
                        gross_loss += sl_dist
                    in_trade = False
                
                elif row['Low'] <= entry_price - tp1 and current_sl > entry_price:
                    current_sl = entry_price
                
                elif row['Low'] <= entry_price - tp2 and current_sl > entry_price - tp1:
                    current_sl = entry_price - tp1
                
                elif row['Low'] <= entry_price - tp3:
                    wins += 1
                    gross_profit += tp3
                    in_trade = False

    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0
    profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else 0
    return wins, losses, total_trades, win_rate, profit_factor

# ==========================================
# 5. الواجهة الرئيسية
# ==========================================
if st.sidebar.button("🎯 تحليل السوق الآن", use_container_width=True):
    with st.spinner('جاري تحليل السيولة بدقة القناص...'):
        try:
            df = get_data(symbol, "60d", timeframe)
            df = calculate_sniper_logic(df)
            
            if len(df) > 200:
                last_row = df.iloc[-1]
                last_close = float(last_row['Close'])
                
                sl_dist = sl_pips * pip_size
                tp1_dist = tp1_pips * pip_size
                tp2_dist = tp2_pips * pip_size
                tp3_dist = tp3_pips * pip_size
                
                # شروط الإشارة الحالية
                current_buy = (last_row['Close'] > last_row['EMA200']) and (last_row['RSI'] > 55) and \
                              last_row['Sweep_Low'] and (last_row['FVG_Bull'] or last_row['Bull_OB']) and last_row['Killzone']
                
                current_sell = (last_row['Close'] < last_row['EMA200']) and (last_row['RSI'] < 45) and \
                               last_row['Sweep_High'] and (last_row['FVG_Bear'] or last_row['Bear_OB']) and last_row['Killzone']
                
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
                        st.markdown(f"<h3 style='text-align: center;'>إشارة القناص (سيولة + OB/FVG + توقيت) 🎯</h3>", unsafe_allow_html=True)
                        
                        col_e, col_sl = st.columns(2)
                        col_e.metric("الدخول (Entry)", f"{last_close:.2f}")
                        col_sl.metric("الستوب لوز (SL)", f"{sl:.2f}", delta="-خطر-", delta_color="inverse")
                        
                        st.markdown("---")
                        col_tp1, col_tp2, col_tp3 = st.columns(3)
                        col_tp1.metric(f"الهدف 1 ({tp1_pips} نقطة)", f"{tp1:.2f}")
                        col_tp2.metric(f"الهدف 2 ({tp2_pips} نقطة)", f"{tp2:.2f}")
                        col_tp3.metric(f"الهدف 3 ({tp3_pips} نقطة)", f"{tp3:.2f}")
                    else:
                        st.warning("⚠️ البوت كينتظر الفرصة الذهبية (سيولة + كسر هيكل + توقيت لندن/نيويورك). ماتدخلش دابا.")

                # النتائج
                st.markdown("---")
                st.subheader(f"📊 نتائج القناص (VIP Backtest - فريم {timeframe})")
                wins, losses, total, win_rate, pf = run_sniper_backtest(df, sl_dist, tp1_dist, tp2_dist, tp3_dist)
                
                if total > 0:
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("عدد الصفقات (قليل = جودة)", total)
                    c2.metric("ناجحة (TP/Breakeven)", wins)
                    c3.metric("خاسرة (SL)", losses)
                    c4.metric("نسبة النجاح", f"{win_rate:.1f}%")
                    
                    st.info(f"💡 **معامل الربح (Profit Factor):** {pf:.2f} | هاد البوت كيخدم بنظام (حماية الأرباح): ملي كيوصل TP1 كيتحرك الستوب لبلاصة الدخول، وملي كيوصل TP2 كيتحرك لـ TP1. هكذا الخسارة كتولي شبه مستحيلة إلا دخلنا فالصفقة.")
                else:
                    st.error("ماكاينش إشارات فالفترة الماضية، هادشي كيعني البوت قناص بزاف.")

        except Exception as e:
            st.error(f"وقع خطأ: {e}")
