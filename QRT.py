import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json 

st.set_page_config(page_title="검역량 & 오퍼가 대시보드", layout="wide")

def check_password():
    password = st.sidebar.text_input("🔒 비밀번호 입력", type="password")
    if password == "0348":
        return True
    elif password != "":
        st.sidebar.error("비밀번호가 틀렸습니다.")
    return False

if not check_password():
    st.info("왼쪽 사이드바에 비밀번호를 입력해야 데이터를 볼 수 있습니다.")
    st.stop()

# --- 구글 인증 통합 함수 ---
def get_gspread_client():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    if "google_key" in st.secrets:
        creds_dict = json.loads(st.secrets["google_key"])
        credentials = Credentials.from_service_account_info(creds_dict, scopes=scope)
    else:
        credentials = Credentials.from_service_account_file('key.json', scopes=scope)
    return gspread.authorize(credentials)


# --- 1. 과거 데이터(Qrt) 불러오기 ---
@st.cache_data(ttl=7200)
def load_data():
    gc = get_gspread_client()
    doc = gc.open('전략데이터 원본데이터') 
    worksheet = doc.worksheet('Qrt')
    data = worksheet.get_all_values()
    df = pd.DataFrame(data[1:], columns=data[0])
    df.columns = df.columns.str.strip()
    df = df.loc[:, df.columns != '']
    df['검역량'] = pd.to_numeric(df['검역량'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    df['연월'] = df['연'].astype(str) + "-" + df['월'].astype(str).str.zfill(2)
    return df

# --- 2. 실시간 데이터(RAW) 불러오기 ---
@st.cache_data(ttl=3600)
def load_raw_data():
    gc = get_gspread_client()
    doc = gc.open_by_url('https://docs.google.com/spreadsheets/d/1lSMxR62Qes09fKqmWUya2jFuEG0U4ScqsfjKlFJudnk/edit?gid=1705869223#gid=1705869223') 
    worksheet = doc.worksheet('RAW')
    data = worksheet.get_all_values()
    df_raw = pd.DataFrame(data[1:], columns=data[0])
    df_raw.columns = df_raw.columns.str.strip()
    df_raw.rename(columns={'품명': '품목', '구분': '세부구분', '국가명': '국가별'}, inplace=True)
    if '당월누계(kg)' in df_raw.columns:
        df_raw['당월누계(kg)'] = pd.to_numeric(df_raw['당월누계(kg)'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        df_raw['당월누계(Ton)'] = df_raw['당월누계(kg)'] / 1000.0
    return df_raw

# --- 3. 오퍼가 데이터 불러오기 ---
@st.cache_data(ttl=3600)
def load_offer_data():
    gc = get_gspread_client()
    doc = gc.open_by_url('https://docs.google.com/spreadsheets/d/1Ke8Q5BHqeeZUZ90Pe7WSWIlppndtebqsq0yoApek1go/edit?gid=1724697100#gid=1724697100') 
    worksheet = next((ws for ws in doc.worksheets() if ws.id == 1724697100), doc.sheet1)
    data = worksheet.get_all_values()
    df_offer = pd.DataFrame(data[1:], columns=data[0])
    df_offer.columns = df_offer.columns.str.strip()
    df_offer = df_offer.loc[:, df_offer.columns != '']
    if '보정오퍼가' in df_offer.columns:
        df_offer['보정오퍼가'] = pd.to_numeric(df_offer['보정오퍼가'].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
    return df_offer

# 데이터 로딩
df = load_data()
df_raw = load_raw_data()
df_offer = load_offer_data()


# ==========================================
# 좌측 사이드바
# ==========================================
st.sidebar.markdown("### 🚀 빠른 이동")
st.sidebar.markdown('<a href="#quarantine" style="text-decoration:none; font-size:18px;">🥩 검역량 대시보드</a>', unsafe_allow_html=True)
st.sidebar.markdown("<br>", unsafe_allow_html=True)
st.sidebar.markdown('<a href="#offer" style="text-decoration:none; font-size:18px;">💵 오퍼가 분석</a>', unsafe_allow_html=True)


# ==========================================
# 메인 화면 1: 검역량 대시보드
# ==========================================
st.markdown('<div id="quarantine"></div>', unsafe_allow_html=True) 
st.title("🥩 검역량 통합 대시보드")

tab1, tab2, tab3 = st.tabs(["📊 조건별 통합 조회", "📈 월별 검역량 비교", "⚡ 실시간 검역 비교"])

with tab1:
    st.subheader("조건별 검역량 요약표")
    sorted_years = sorted(df['연'].unique(), key=lambda x: int(x) if str(x).isdigit() else str(x))
    sorted_months = sorted(df['월'].unique(), key=lambda x: int(x) if str(x).isdigit() else str(x))

    col1, col2, col3 = st.columns(3)
    with col1: selected_year = st.selectbox("연도 선택", ['전체'] + sorted_years, key="tab1_year")
    with col2: selected_month = st.selectbox("월 선택", ['전체'] + sorted_months, key="tab1_month")
    with col3: selected_category = st.selectbox("세부구분 선택", ['전체'] + sorted(df['세부구분'].unique()), key="tab1_cat")

    col4, col5, col6 = st.columns(3)
    with col4: selected_item = st.selectbox("품목 선택", ['전체'] + sorted(df['품목'].unique()), key="tab1_item")
    with col5: selected_part = st.selectbox("부위 선택", ['전체'] + sorted(df['부위'].unique()), key="tab1_part")
    with col6: selected_country = st.selectbox("국가별 선택", ['전체'] + sorted(df['국가별'].unique()), key="tab1_country")

    filtered_df = df.copy()
    if selected_year != '전체': filtered_df = filtered_df[filtered_df['연'] == selected_year]
    if selected_month != '전체': filtered_df = filtered_df[filtered_df['월'] == selected_month]
    if selected_category != '전체': filtered_df = filtered_df[filtered_df['세부구분'] == selected_category]
    if selected_item != '전체': filtered_df = filtered_df[filtered_df['품목'] == selected_item]
    if selected_part != '전체': filtered_df = filtered_df[filtered_df['부위'] == selected_part]
    if selected_country != '전체': filtered_df = filtered_df[filtered_df['국가별'] == selected_country]

    if not filtered_df.empty:
        pivot_df = pd.pivot_table(filtered_df, values='
