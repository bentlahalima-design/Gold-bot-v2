import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta

st.set_page_config(page_title="V17 - High Win Rate SMC", page_icon="🛡️", layout="wide")
st.title("🛡️ V17 - High Win Rate SMC (VIP Edition)")
st.markdown("---")

# ==========================================
# 1. الإعدادات
# ==========================================
symbol = st.sidebar.text_input("رمز العملة", "GC=F")
timeframe = st.sidebar.selectbox("فريم الدخول", ["15m", "5m", "1h"], index=0)

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
# 3. المؤشرات (Range Filter, AlgoAlpha, Sonarlab, RSI, Sweep)
# ==========================================
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

def calculate_algo_alpha_zones(df, plen=100, res=40, tolerance=0.93):
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

def calculate_sonarlab_obs(df, sens=20):
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

def calculate_sweep_rsi(df):
    # RSI
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # Sweep (السيولة على 5 شموع)
    df['Prev_Low_5'] = df['Low'].rolling(window=5).min().shift(1)
    df['Prev_High_5'] = df['High'].rolling(window=5).max().shift(1)
    df['Sweep_Low'] = (df['Low'] < df['Prev_Low_5']) & (df['Close'] > df['Prev_Low_5'])
    df['Sweep_High'] = (df['High'] > df['Prev_High_5']) & (df['Close'] < df['Prev_High_5'])
    return df

# ==========================================
# 4. الواجهة الرئيسية
# ==========================================
if st.sidebar.button("🚀 تحليل السوق الآن", use_container_width=True):
    with st.spinner('جاري القنص (High Win Rate)...'):
        try:
            df_1h = get_data(symbol, "60d", "1h")
            trend_1h_series = calculate_range_filter_trend(df_1h)
            current_trend_1h = trend_1h_series[-1]
            
            df = get_data(symbol, "60d", timeframe)
            df = calculate_sweep_rsi(df)
            df = calculate_sonarlab_obs(df)
            
            st.markdown("---")
            st.subheader(f"📊 نتائج الاختبار (High Win Rate) - ({timeframe})")
            
            wins, losses, total_trades = 0, 0, 0
            net_pips = 0
            in_trade = False
            trade_type = None
            
            bt_zones = calculate_algo_alpha_zones(df)
            ema200 = df['Close'].rolling(200).mean()
            
            current_date = None
            trades_today = 0
            
            for i in range(200, len(df) - 20):
                row = df.iloc[i]
                row_date = row.name.date()
                
                if row_date != current_date:
                    current_date = row_date
                    trades_today = 0
                
                trend_bt = 1 if row['Close'] > ema200.iloc[i] else -1
                time_ok = is_in_session(row.name, sessions)
                
                if not in_trade and time_ok and trades_today < 3: # Max 3 trades
                    in_z = False
                    if bt_zones:
                        for z_b, z_t in bt_zones:
                            if z_b <= row['Close'] <= z_t: in_z = True; break
                    
                    # شروط قوية (Sweep + OB/Zone + RSI + Trend)
                    b_cond = (trend_bt == 1) and (in_z or row['In_Bull_OB']) and row['Sweep_Low'] and (row['RSI'] > 45)
                    s_cond = (trend_bt == -1) and (in_z or row['In_Bear_OB']) and row['Sweep_High'] and (row['RSI'] < 55)
                    
                    if b_cond:
                        in_trade = True; trade_type = "BUY"
                        trades_today += 1
                        entry = row['Close']; sl_price = entry - (sl_pips * pip_size); tp_price = entry + (tp1_pips * pip_size)
                    elif s_cond:
                        in_trade = True; trade_type = "SELL"
                        trades_today += 1
                        entry = row['Close']; sl_price = entry + (sl_pips * pip_size); tp_price = entry - (tp1_pips * pip_size)
                
                elif in_trade:
                    trade_closed = False
                    if trade_type == "BUY":
                        if row['Low'] <= sl_price: 
                            losses += 1; net_pips -= sl_pips; trade_closed = True
                        elif row['High'] >= tp_price: 
                            wins += 1; net_pips += tp1_pips; trade_closed = True
                    elif trade_type == "SELL":
                        if row['High'] >= sl_price: 
                            losses += 1; net_pips -= sl_pips; trade_closed = True
                        elif row['Low'] <= tp_price: 
                            wins += 1; net_pips += tp1_pips; trade_closed = True
                    
                    if trade_closed:
                        total_trades += 1
                        in_trade = False
                        
            if total_trades > 0:
                wr = (wins / total_trades * 100)
                col_a, col_b, col_c, col_d = st.columns(4)
                col_a.metric("إجمالي الصفقات", total_trades)
                col_b.metric("ناجحة", wins)
                col_c.metric("خاسرة", losses)
                col_d.metric("نسبة النجاح", f"{wr:.1f}%")
                
                if net_pips > 0:
                    st.success(f"💰 **صافي الربح (Net Profit): +{net_pips} نقطة**")
                else:
                    st.error(f"📉 **صافي الخسارة (Net Loss): {net_pips} نقطة**")
            else:
                st.error("ماكاينش صفقات كافية.")

            # عرض الإشارة الحالية
            st.markdown("---")
            st.subheader("🔴 الإشارة الحالية (Live)")
            last = df.iloc[-1]
            entry_price = float(last['Close'])
            in_time = is_in_session(last.name, sessions)
            
            key_zones = calculate_algo_alpha_zones(df)
            in_demand = False; in_supply = False
            if key_zones:
                for z_b, z_t in key_zones:
                    if z_b <= entry_price <= z_t:
                        if entry_price > ema200.iloc[-1]: in_demand = True
                        else: in_supply = True
                        
            live_buy = (current_trend_1h == 1) and (in_demand or last['In_Bull_OB']) and last['Sweep_Low'] and (last['RSI'] > 45) and in_time
            live_sell = (current_trend_1h == -1) and (in_supply or last['In_Bear_OB']) and last['Sweep_High'] and (last['RSI'] < 55) and in_time

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
                st.warning(f"⚠️ السوق غير واضح حالياً. البوت ينتظر ضربة سيولة + OB/FVG + تأكيد الاتجاه.")

        except Exception as e:
            st.error(f"وقع خطأ: {e}")
