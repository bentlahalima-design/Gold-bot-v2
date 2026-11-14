import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="Ultimate Sniper V7", page_icon="🎯", layout="wide")
st.title("🎯 Ultimate Sniper V7 (Range Filter + SMC/ICT)")
st.markdown("---")

# ==========================================
# 1. الإعدادات
# ==========================================
symbol = st.sidebar.text_input("رمز العملة", "GC=F")
timeframe = st.sidebar.selectbox("الفريم الزمني", ["15m", "1h", "5m"], index=0)

st.sidebar.markdown("---")
st.sidebar.subheader("🎯 إدارة المخاطر (بالنقط)")
pip_size = st.sidebar.number_input("حجم النقطة (Pip Size)", value=0.1, step=0.1, format="%.1f")
sl_pips = st.sidebar.number_input("الستوب لوز (نقطة)", value=100, step=10)
tp1_pips = st.sidebar.number_input("الهدف 1 (نقطة)", value=150, step=10)

# إعدادات مؤشر Range Filter
st.sidebar.markdown("---")
st.sidebar.subheader("⚙️ Range Filter Settings")
rf_period = st.sidebar.number_input("Swing Period", value=20, step=1)
rf_multiplier = st.sidebar.number_input("Swing Multiplier", value=3.5, step=0.1)

@st.cache_data(ttl=60)
def get_data(symbol, period, interval):
    data = yf.download(tickers=symbol, period=period, interval=interval, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data.dropna()

# ==========================================
# 2. مؤشر Range Filter (مترجم من Pine Script)
# ==========================================
def calculate_range_filter(df, rng_per, rng_qty):
    source = df['Close']
    wper = (rng_per * 2) - 1
    
    # حساب التذبذب
    avrng = source.diff().abs().ewm(span=rng_per, adjust=False).mean()
    AC = avrng.ewm(span=wper, adjust=False).mean() * rng_qty

    # حساب الفلتر (Recursive)
    filt = np.zeros(len(source))
    filt[0] = source.iloc[0]

    for i in range(1, len(source)):
        x = source.iloc[i]
        r = AC.iloc[i]
        prev_filt = filt[i-1]

        if x - r > prev_filt:
            filt[i] = x - r
        elif x + r < prev_filt:
            filt[i] = x + r
        else:
            filt[i] = prev_filt

    filt_series = pd.Series(filt, index=df.index)

    # تحديد الاتجاه
    fdir = np.zeros(len(source))
    for i in range(1, len(source)):
        if filt_series.iloc[i] > filt_series.iloc[i-1]:
            fdir[i] = 1
        elif filt_series.iloc[i] < filt_series.iloc[i-1]:
            fdir[i] = -1
        else:
            fdir[i] = fdir[i-1]

    longCond = (source > filt_series) & (fdir == 1)
    shortCond = (source < filt_series) & (fdir == -1)

    # تحديد إشارات الدخول
    CondIni = np.zeros(len(source))
    for i in range(1, len(source)):
        if longCond.iloc[i]:
            CondIni[i] = 1
        elif shortCond.iloc[i]:
            CondIni[i] = -1
        else:
            CondIni[i] = CondIni[i-1]

    CondIni_prev = np.roll(CondIni, 1)
    CondIni_prev[0] = 0

    df['RF_Long_Signal'] = longCond & (CondIni_prev == -1)
    df['RF_Short_Signal'] = shortCond & (CondIni_prev == 1)
    
    return df

# ==========================================
# 3. مؤشر Sonarlab Order Blocks
# ==========================================
def calculate_sonarlab_obs(df, sens=28):
    df = df.copy()
    sens = sens / 100
    df['pc'] = (df['Open'] - df['Open'].shift(4)) / df['Open'].shift(4) * 100
    
    in_bull_ob = [False] * len(df)
    in_bear_ob = [False] * len(df)
    active_bull_obs = []
    active_bear_obs = []
    
    for i in range(15, len(df)):
        if df['pc'].iloc[i-1] < -sens and df['pc'].iloc[i] >= -sens:
            for j in range(4, 16):
                if df['Close'].iloc[i-j] > df['Open'].iloc[i-j]:
                    active_bear_obs.append({'top': df['High'].iloc[i-j], 'bottom': df['Low'].iloc[i-j]})
                    break
                    
        if df['pc'].iloc[i-1] > sens and df['pc'].iloc[i] <= sens:
            for j in range(4, 16):
                if df['Close'].iloc[i-j] < df['Open'].iloc[i-j]:
                    active_bull_obs.append({'top': df['High'].iloc[i-j], 'bottom': df['Low'].iloc[i-j]})
                    break
                    
        active_bear_obs = [ob for ob in active_bear_obs if df['Close'].iloc[i] <= ob['top']]
        active_bull_obs = [ob for ob in active_bull_obs if df['Close'].iloc[i] >= ob['bottom']]
        
        c_low, c_high = df['Low'].iloc[i], df['High'].iloc[i]
        for ob in active_bull_obs:
            if c_low <= ob['top'] and c_high >= ob['bottom']: in_bull_ob[i] = True; break
        for ob in active_bear_obs:
            if c_high >= ob['bottom'] and c_low <= ob['top']: in_bear_ob[i] = True; break
                
    df['In_Bull_OB'] = in_bull_ob
    df['In_Bear_OB'] = in_bear_ob
    return df

# ==========================================
# 4. FVG
# ==========================================
def calculate_fvg(df):
    df['FVG_Bull'] = df['Low'] > df['High'].shift(2)
    df['FVG_Bear'] = df['High'] < df['Low'].shift(2)
    return df

# ==========================================
# 5. الواجهة الرئيسية
# ==========================================
if st.sidebar.button("🚀 تحليل السوق الآن", use_container_width=True):
    with st.spinner('جاري تحليل Range Filter + SMC...'):
        try:
            df = get_data(symbol, "60d", timeframe)
            
            if len(df) > 200:
                # حساب المؤشرات
                df = calculate_range_filter(df, rf_period, rf_multiplier)
                df = calculate_sonarlab_obs(df)
                df = calculate_fvg(df)
                
                last = df.iloc[-1]
                entry_price = float(last['Close'])
                
                tz_ma = timezone(timedelta(hours=1))
                current_time = datetime.now(tz_ma).strftime("%Y-%m-%d %H:%M:%S")
                
                # الشروط (Sniper Logic)
                # Buy: إشارة Range Filter + (OB صاعد أو FVG صاعدة)
                buy_cond = last['RF_Long_Signal'] and (last['In_Bull_OB'] or last['FVG_Bull'])
                # Sell: إشارة Range Filter + (OB هابط أو FVG هابطة)
                sell_cond = last['RF_Short_Signal'] and (last['In_Bear_OB'] or last['FVG_Bear'])

                signal, color = "WAITING", "gray"
                if buy_cond:
                    signal, color = "BUY", "#00FF00"
                    sl = entry_price - (sl_pips * pip_size)
                    tp1 = entry_price + (tp1_pips * pip_size)
                elif sell_cond:
                    signal, color = "SELL", "#FF0000"
                    sl = entry_price + (sl_pips * pip_size)
                    tp1 = entry_price - (tp1_pips * pip_size)

                # عرض النتائج
                if signal != "WAITING":
                    st.markdown(f"<h1 style='text-align: center; color: {color}; font-size: 60px;'>{signal}</h1>", unsafe_allow_html=True)
                    st.markdown(f"<h4 style='text-align: center; color: #FFD700;'>⏰ وقت التحليل: {current_time}</h4>", unsafe_allow_html=True)
                    
                    st.success("✅ تم التأكيد: إشارة Range Filter + Order Block/FVG")
                    
                    c1, c2, c3 = st.columns(3)
                    c1.metric("سعر الدخول (Entry)", f"{entry_price:.2f}")
                    c2.metric("الستوب (SL)", f"{sl:.2f}")
                    c3.metric(f"هدف 1 ({tp1_pips} نقطة)", f"{tp1:.2f}")
                else:
                    st.warning("⚠️ السوق غير واضح حالياً. البوت كينتظر إشارة Range Filter متزامنة مع Order Block/FVG.")

                # ==========================================
                # 6. الباك تست
                # ==========================================
                st.markdown("---")
                st.subheader(f"📊 نتائج الاختبار التاريخي ({timeframe})")
                
                wins, losses, total_trades = 0, 0, 0
                in_trade = False
                trade_type = None
                
                for i in range(200, len(df) - 20):
                    row = df.iloc[i]
                    
                    if not in_trade:
                        # نفس شروط القناص
                        b_cond = row['RF_Long_Signal'] and (row['In_Bull_OB'] or row['FVG_Bull'])
                        s_cond = row['RF_Short_Signal'] and (row['In_Bear_OB'] or row['FVG_Bear'])
                        
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
