import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="Ultimate Sniper V10", page_icon="🏆", layout="wide")
st.title("🏆 Ultimate Sniper V10 (Breakeven & Trailing)")
st.markdown("---")

symbol = st.sidebar.text_input("رمز العملة", "GC=F")
timeframe = st.sidebar.selectbox("فريم الدخول", ["15m", "5m", "1h"], index=0)

st.sidebar.markdown("---")
pip_size = st.sidebar.number_input("حجم النقطة", value=0.1, step=0.1, format="%.1f")
sl_pips = st.sidebar.number_input("الستوب لوز", value=100, step=10)
tp1_pips = st.sidebar.number_input("الهدف 1", value=50, step=10)
tp2_pips = st.sidebar.number_input("الهدف 2", value=100, step=10)
tp3_pips = st.sidebar.number_input("الهدف 3", value=150, step=10)

@st.cache_data(ttl=60)
def get_data(symbol, period, interval):
    data = yf.download(tickers=symbol, period=period, interval=interval, progress=False)
    if isinstance(data.columns, pd.MultiIndex):
        data.columns = data.columns.get_level_values(0)
    return data.dropna()

def calculate_range_filter_trend(df, rng_per=20, rng_qty=3.5):
    source = df['Close']
    wper = (rng_per * 2) - 1
    avrng = source.diff().abs().ewm(span=rng_per, adjust=False).mean()
    AC = avrng.ewm(span=wper, adjust=False).mean() * rng_qty
    filt = np.zeros(len(source))
    filt[0] = source.iloc[0]
    for i in range(1, len(source)):
        x, r, prev_filt = source.iloc[i], AC.iloc[i], filt[i-1]
        if x - r > prev_filt: filt[i] = x - r
        elif x + r < prev_filt: filt[i] = x + r
        else: filt[i] = prev_filt
    filt_series = pd.Series(filt, index=df.index)
    fdir = np.zeros(len(source))
    for i in range(1, len(source)):
        if filt_series.iloc[i] > filt_series.iloc[i-1]: fdir[i] = 1
        elif filt_series.iloc[i] < filt_series.iloc[i-1]: fdir[i] = -1
        else: fdir[i] = fdir[i-1]
    return fdir 

def calculate_algo_alpha_zones(df, plen=200, res=40, tolerance=0.93):
    recent_df = df.tail(plen)
    if len(recent_df) < plen: return []
    max_p = recent_df['High'].max()
    min_p = recent_df['Low'].min()
    step = (max_p - min_p) / res
    if step == 0: return []
    bin_volumes = np.zeros(res)
    for i in range(len(recent_df)):
        c_low, c_high, vol = recent_df['Low'].iloc[i], recent_df['High'].iloc[i], recent_df['Volume'].iloc[i]
        for j in range(res):
            b_bot = min_p + (j * step)
            b_top = min_p + ((j + 1) * step)
            if c_high >= b_bot and c_low <= b_top: bin_volumes[j] += vol
    key_zones = []
    for j in range(res):
        is_key = True
        if j > 0 and bin_volumes[j] >= bin_volumes[j-1] * tolerance: is_key = False
        if j < res - 1 and bin_volumes[j] >= bin_volumes[j+1] * tolerance: is_key = False
        if is_key and bin_volumes[j] > 0:
            key_zones.append((min_p + (j * step), min_p + ((j + 1) * step)))
    return key_zones

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

if st.sidebar.button("🚀 تحليل السوق الآن", use_container_width=True):
    with st.spinner('جاري تحليل (1H Trend + S&D + OB)...'):
        try:
            df_1h = get_data(symbol, "60d", "1h")
            trend_1h_series = calculate_range_filter_trend(df_1h)
            current_trend_1h = trend_1h_series[-1]
            
            df = get_data(symbol, "60d", timeframe)
            df = calculate_sonarlab_obs(df)
            
            last = df.iloc[-1]
            entry_price = float(last['Close'])
            tz_ma = timezone(timedelta(hours=1))
            current_time = datetime.now(tz_ma).strftime("%Y-%m-%d %H:%M:%S")
            
            key_zones = calculate_algo_alpha_zones(df)
            in_demand = False
            in_supply = False
            if key_zones:
                for z_b, z_t in key_zones:
                    if z_b <= entry_price <= z_t:
                        if entry_price > df['Close'].rolling(200).mean().iloc[-1]: in_demand = True
                        else: in_supply = True
                        
            buy_cond = (current_trend_1h == 1) and (in_demand or last['In_Bull_OB'])
            sell_cond = (current_trend_1h == -1) and (in_supply or last['In_Bear_OB'])

            signal, color = "WAITING", "gray"
            if buy_cond:
                signal, color = "BUY", "#00FF00"
                sl = entry_price - (sl_pips * pip_size)
                tp1 = entry_price + (tp1_pips * pip_size)
                tp2 = entry_price + (tp2_pips * pip_size)
                tp3 = entry_price + (tp3_pips * pip_size)
            elif sell_cond:
                signal, color = "SELL", "#FF0000"
                sl = entry_price + (sl_pips * pip_size)
                tp1 = entry_price - (tp1_pips * pip_size)
                tp2 = entry_price - (tp2_pips * pip_size)
                tp3 = entry_price - (tp3_pips * pip_size)

            if signal != "WAITING":
                st.markdown(f"<h1 style='text-align: center; color: {color}; font-size: 60px;'>{signal}</h1>", unsafe_allow_html=True)
                st.markdown(f"<h4 style='text-align: center; color: #FFD700;'>⏰ وقت الإشارة: {current_time}</h4>", unsafe_allow_html=True)
                st.success(f"✅ ترند 1H: {'صاعد' if current_trend_1h == 1 else 'هابط'} | السعر داخل منطقة قوية")
                
                c1, c2 = st.columns(2)
                c1.metric("سعر الدخول (Entry)", f"{entry_price:.2f}")
                c2.metric("الستوب (SL)", f"{sl:.2f}")
                
                st.markdown("---")
                c3, c4, c5 = st.columns(3)
                c3.metric(f"هدف 1 ({tp1_pips}ن)", f"{tp1:.2f}")
                c4.metric(f"هدف 2 ({tp2_pips}ن)", f"{tp2:.2f}")
                c5.metric(f"هدف 3 ({tp3_pips}ن)", f"{tp3:.2f}")
            else:
                st.warning("⚠️ السوق غير واضح. كينتظر توافق ترند 1H مع مناطق العرض/الطلب.")

            # ==========================================
            # 6. الباك تست (مع Breakeven & Trailing)
            # ==========================================
            st.markdown("---")
            st.subheader(f"📊 نتائج الاختبار التاريخي (مع حماية الأرباح) - ({timeframe})")
            
            wins, losses, total_trades = 0, 0, 0
            in_trade = False
            trade_type = None
            
            bt_zones = calculate_algo_alpha_zones(df)
            ema200 = df['Close'].rolling(200).mean()
            
            for i in range(200, len(df) - 20):
                row = df.iloc[i]
                trend_bt = 1 if row['Close'] > ema200.iloc[i] else -1
                
                if not in_trade:
                    in_z = False
                    if bt_zones:
                        for z_b, z_t in bt_zones:
                            if z_b <= row['Close'] <= z_t: in_z = True; break
                    
                    b_cond = (trend_bt == 1) and (in_z or row['In_Bull_OB'])
                    s_cond = (trend_bt == -1) and (in_z or row['In_Bear_OB'])
                    
                    if b_cond:
                        in_trade = True; trade_type = "BUY"
                        entry = row['Close']; sl_price = entry - (sl_pips * pip_size)
                        tp1 = entry + (tp1_pips * pip_size); tp2 = entry + (tp2_pips * pip_size); tp3 = entry + (tp3_pips * pip_size)
                        current_sl = sl_price
                    elif s_cond:
                        in_trade = True; trade_type = "SELL"
                        entry = row['Close']; sl_price = entry + (sl_pips * pip_size)
                        tp1 = entry - (tp1_pips * pip_size); tp2 = entry - (tp2_pips * pip_size); tp3 = entry - (tp3_pips * pip_size)
                        current_sl = sl_price
                else:
                    trade_closed = False
                    if trade_type == "BUY":
                        # 1. ضرب الستوب
                        if row['Low'] <= current_sl:
                            if current_sl >= entry: wins += 1 # Breakeven (ربح صفر)
                            else: losses += 1
                            trade_closed = True
                        # 2. وصل TP1 -> حرك الستوب للدخول
                        elif row['High'] >= tp1 and current_sl < entry:
                            current_sl = entry
                        # 3. وصل TP2 -> حرك الستوب لـ TP1
                        elif row['High'] >= tp2 and current_sl < tp1:
                            current_sl = tp1
                        # 4. وصل TP3 -> قفل الصفقة
                        elif row['High'] >= tp3:
                            wins += 1; trade_closed = True
                            
                    elif trade_type == "SELL":
                        if row['High'] >= current_sl:
                            if current_sl <= entry: wins += 1 
                            else: losses += 1
                            trade_closed = True
                        elif row['Low'] <= tp1 and current_sl > entry:
                            current_sl = entry
                        elif row['Low'] <= tp2 and current_sl > tp1:
                            current_sl = tp1
                        elif row['Low'] <= tp3:
                            wins += 1; trade_closed = True
                    
                    if trade_closed:
                        total_trades += 1
                        in_trade = False
                        
            if total_trades > 0:
                wr = (wins / total_trades * 100)
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("إجمالي الصفقات", total_trades)
                col_b.metric("ناجحة (TP/Breakeven)", wins)
                col_c.metric("خاسرة (SL)", losses)
                col_d.metric("نسبة النجاح", f"{wr:.1f}%")
            else:
                st.error("ماكاينش صفقات كافية فالفترة المحددة.")
                
        except Exception as e:
            st.error(f"وقع خطأ: {e}")
