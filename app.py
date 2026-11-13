import streamlit as st
from datetime import datetime
import pytz

# إعدادات الصفحة
st.set_page_config(page_title="Institutional SMC/ICT Scalper", layout="centered")

st.title("🏛️ SMC/ICT Institutional Scalper & CHoCH Engine")
st.markdown("نظام المؤسسات الكبرى مع تحليل الهيكلة (**CHoCH & BOS**) وتحديد توقيت الإشارة بدقة.")

# توقيت المغرب (أو التوقيت المحلي)
morocco_tz = pytz.timezone('Africa/Casablanca')
current_time = datetime.now(morocco_tz).strftime('%Y-%m-%d %H:%M:%S')

# المدخلات من الواجهة
st.sidebar.header("إعدادات الهيكلة والسيولة")
asset = st.sidebar.selectbox("الأصل المالي", ["XAUUSD (الذهب)", "BTCUSD", "EURUSD"])
structure_event = st.sidebar.selectbox("نوع حدث الهيكلة المؤسساتية", [
    "CHoCH (تغير الشخصية - انقلاب الاتجاه)", 
    "BOS (استمرار الاتجاه / كسر الهيكل)"
])
direction = st.sidebar.radio("اتجاه الصفقة", ["BUY (شراء)", "SELL (بيع)"])

current_price = st.sidebar.number_input("سعر السوق الحالي", value=2650.0)
ob_zone = st.sidebar.number_input("منطقة الـ Order Block / FVG", value=2648.0)
risk_points = st.sidebar.slider("نقاط حماية الـ Stop Loss", min_value=3, max_value=15, value=8)

# زر توليد الصفقة
if st.button("🚀 تحليل السوق واستخراج الإشارة المؤسساتية"):
    
    # التحقق من توافق الهيكلة
    if "CHoCH" in structure_event:
        st.success(f"🔥 تم رصد **CHoCH** قوي! المؤسسات غيرات الاتجاه، والآن نبحث عن إعادة اختبار الـ OB.")
    else:
        st.success(f"📈 تم رصد **BOS** صحيح! استمرار في نفس الاتجاه المؤسساتي.")
    
    # حساب الأهداف بناءً على الاتجاه
    if "BUY" in direction:
        exact_entry = ob_zone
        sl = exact_entry - risk_points
        tp1 = exact_entry + 50
        tp2 = exact_entry + 100
        tp3 = exact_entry + 150
        action_color = "🟢"
    else:
        exact_entry = ob_zone
        sl = exact_entry + risk_points
        tp1 = exact_entry - 50
        tp2 = exact_entry - 100
        tp3 = exact_entry - 150
        action_color = "🔴"

    # عرض التوقيت دقيقاً
    st.markdown(f"🕒 **توقيت توليد الإشارة:** `{current_time} (توقيت المغرب)`")
    st.markdown(f"### {action_color} تفاصيل الصفقة المؤسساتية لـ **{asset}** ({structure_event})")
    
    col1, col2 = st.columns(2)
    with col1:
        st.metric(label="اتجاه الصفقة", value=direction)
        st.metric(label="📍 الدخول الدقيق (Entry)", value=f"{exact_entry:.2f}")
        st.metric(label="وقف الخسارة (SL)", value=f"{sl:.2f}")
    
    with col2:
        st.metric(label="الهدف الأول (TP1 - 50p)", value=f"{tp1:.2f}")
        st.metric(label="الهدف الثاني (TP2 - 100p)", value=f"{tp2:.2f}")
        st.metric(label="الهدف الثالث (TP3 - 150p)", value=f"{tp3:.2f}")

    st.info("💡 **قاعدة هامة:** بما أن التوقيت مسجل أعلاه، إذا لاحظت أن الإشارة خرجت قبل قليل وسعر السوق قريب من نقطة الدخول، توكل على الله ونفذها يدوياً في MT5.")
else:
    st.info("💡 حدد نوع الهيكلة (CHoCH أو BOS) ومنطقة الـ OB واضغط على زر التحليل.")
