import streamlit as st
from datetime import datetime
import pytz

# إعدادات الصفحة
st.set_page_config(page_title="Gold Scalper Pro - SMC/ICT", layout="centered")

st.title("⚡ Gold Scalper Pro (Precision & Speed)")
st.markdown("بوت السكالبينغ المؤسساتي: إشارات سريعة وأهداف لاصقة (TP1 قريب للتنفيذ الفوري).")

# توقيت المغرب
morocco_tz = pytz.timezone('Africa/Casablanca')
current_time = datetime.now(morocco_tz).strftime('%Y-%m-%d %H:%M:%S')

st.sidebar.header("إعدادات السوق الحية")
# هنا كتدخل الثمن الحقيقي اللي كيبان ليك في المنصة دابا باش ما يبقاش يغالطك البوت
market_price = st.sidebar.number_input("ثمن الذهب الحالي في منصتك (الواقعي)", value=3881.0, step=0.1)

signal_type = st.sidebar.selectbox("اختر نوع الصفقة المطلوبة", [
    "SELL (بيع من السيولة العليا - سكالبينغ)", 
    "BUY (شراء من السيولة السفلى - سكالبينغ)"
])

scalp_risk = st.sidebar.slider("نقاط حماية الـ Stop Loss", min_value=3, max_value=10, value=5)

# زر توليد الإشارة الدقيقة
if st.button("🚀 اعطيني صفقة سكالبينغ لاصقة"):
    
    # حساب الأهداف بطريقة السكالبينغ المؤسساتي (أهداف قريبة ولاصقة)
    if "SELL" in signal_type:
        exact_entry = market_price
        sl = exact_entry + scalp_risk      # وقف خسارة صغير ومحمي
        tp1 = exact_entry - 12             # TP1 قريب جداً ولاصق للسكالبينغ السريع
        tp2 = exact_entry - 25             # TP2 متوسط
        tp3 = exact_entry - 50             # TP3 للهدف الكبير
        action_color = "🔴"
    else:
        exact_entry = market_price
        sl = exact_entry - scalp_risk
        tp1 = exact_entry + 12
        tp2 = exact_entry + 25
        tp3 = exact_entry + 50
        action_color = "🟢"

    st.markdown(f"🕒 **توقيت الإشارة:** `{current_time} (توقيت المغرب)`")
    st.markdown(f"### {action_color} تفاصيل صفقة السكالبينغ لـ **XAUUSD**")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="نوع الصفقة", value=signal_type.split(" ")[0])
        st.metric(label="📍 سعر الدخول (Entry)", value=f"{exact_entry:.2f}")
        st.metric(label="وقف الخسارة (SL)", value=f"{sl:.2f}")
    
    with col2:
        st.metric(label="الهدف الأول (TP1 - لاصق وسريع)", value=f"{tp1:.2f}")
        st.metric(label="الهدف الثاني (TP2)", value=f"{tp2:.2f}")
        st.metric(label="الهدف الثالث (TP3)", value=f"{tp3:.2f}")

    st.info("💡 **طريقة العمل:** بما أنك طلبت TP1 يكون لاصق، هاد الكود كيحسب ليك أهداف قريبة باش تخطف الأرباح بسرعة وتأمين الصفقة!")
else:
    st.info("💡 أدخل ثمن الذهب الحقيقي اللي عندك فالمصة، واختار نوع الصفقة، واضغط على الزر لتوليد الأهداف اللاصقة.")
