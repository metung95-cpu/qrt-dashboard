import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json

st.set_page_config(page_title="검역량 & 오퍼가 대시보드", layout="wide")

# --- 비밀번호 체크 ---
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

# --- 데이터 로딩 (캐시 시간 4시간으로 연장하여 속도 향상) ---
@st.cache_data(ttl=14400)
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

@st.cache_data(ttl=14400)
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

@st.cache_data(ttl=14400)
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

df = load_data()
df_raw = load_raw_data()
df_offer = load_offer_data()

# --- 화면 구성 ---
st.sidebar.markdown("### 🚀 빠른 이동")
st.sidebar.markdown('<a href="#quarantine" style="text-decoration:none; font-size:18px;">🥩 검역량 대시보드</a>', unsafe_allow_html=True)
st.sidebar.markdown('<a href="#offer" style="text-decoration:none; font-size:18px;">💵 오퍼가 분석</a>', unsafe_allow_html=True)

st.markdown('<div id="quarantine"></div>', unsafe_allow_html=True) 
st.title("🥩 검역량 통합 대시보드")

tab1, tab2, tab3 = st.tabs(["📊 조건별 통합 조회", "📈 월별 검역량 비교", "⚡ 실시간 검역 비교"])

# --- Tab 1: 조건별 통합 조회 ---
with tab1:
    st.subheader("조건별 검역량 요약표")
    sorted_years = sorted(df['연'].unique(), key=lambda x: int(x) if str(x).isdigit() else str(x))
    sorted_months = sorted(df['월'].unique(), key=lambda x: int(x) if str(x).isdigit() else str(x))

    col1, col2, col3 = st.columns(3)
    with col1: s_year = st.selectbox("연도 선택", ['전체'] + sorted_years, key="t1_y")
    with col2: s_month = st.selectbox("월 선택", ['전체'] + sorted_months, key="t1_m")
    with col3: s_cat = st.selectbox("세부구분 선택", ['전체'] + sorted(df['세부구분'].unique()), key="t1_c")

    col4, col5, col6 = st.columns(3)
    with col4: s_item = st.selectbox("품목 선택", ['전체'] + sorted(df['품목'].unique()), key="t1_i")
    with col5: s_part = st.selectbox("부위 선택", ['전체'] + sorted(df['부위'].unique()), key="t1_p")
    with col6: s_country = st.selectbox("국가별 선택", ['전체'] + sorted(df['국가별'].unique()), key="t1_ct")

    f_df = df.copy()
    if s_year != '전체': f_df = f_df[f_df['연'] == s_year]
    if s_month != '전체': f_df = f_df[f_df['월'] == s_month]
    if s_cat != '전체': f_df = f_df[f_df['세부구분'] == s_cat]
    if s_item != '전체': f_df = f_df[f_df['품목'] == s_item]
    if s_part != '전체': f_df = f_df[f_df['부위'] == s_part]
    if s_country != '전체': f_df = f_df[f_df['국가별'] == s_country]

    if not f_df.empty:
        pivot = pd.pivot_table(f_df, values='검역량', index=['연', '월', '세부구분', '품목', '부위', '국가별'], aggfunc='sum').reset_index()
        pivot['검역량'] = pivot['검역량'].apply(lambda x: f"{x:,.2f}")
        st.dataframe(pivot, use_container_width=True, hide_index=True)
    else:
        st.warning("데이터가 없습니다.")

# --- Tab 2: 월별 검역량 비교 ---
with tab2:
    st.subheader("기준월 vs 비교월 차이 분석")
    col_t2_1, col_t2_2 = st.columns(2)
    with col_t2_1: s_cat_t2 = st.selectbox("세부구분 선택", ['전체'] + sorted(df['세부구분'].unique()), key="t2_c")
    with col_t2_2: s_item_t2 = st.selectbox("품목 선택", ['전체'] + sorted(df['품목'].unique()), key="t2_i")
    
    col_t2_3, col_t2_4 = st.columns(2)
    with col_t2_3: s_part_t2 = st.selectbox("부위 선택", ['전체'] + sorted(df['부위'].unique()), key="t2_p")
    with col_t2_4: s_country_t2 = st.selectbox("국가별 선택", ['전체'] + sorted(df['국가별'].unique()), key="t2_ct")

    sorted_ym = sorted(df['연월'].unique())
    c_b, c_t = st.columns(2)
    with c_b: b_month = st.selectbox("기준월 (A)", sorted_ym, index=0, key="t2_base")
    with c_t: t_month = st.selectbox("비교월 (B)", sorted_ym, index=len(sorted_ym)-1, key="t2_target")

    f_df_t2 = df.copy()
    if s_cat_t2 != '전체': f_df_t2 = f_df_t2[f_df_t2['세부구분'] == s_cat_t2]
    if s_item_t2 != '전체': f_df_t2 = f_df_t2[f_df_t2['품목'] == s_item_t2]
    if s_part_t2 != '전체': f_df_t2 = f_df_t2[f_df_t2['부위'] == s_part_t2]
    if s_country_t2 != '전체': f_df_t2 = f_df_t2[f_df_t2['국가별'] == s_country_t2]

    if not f_df_t2.empty:
        comp_pivot = pd.pivot_table(f_df_t2, values='검역량', index=['세부구분', '품목', '부위', '국가별'], columns='연월', aggfunc='sum', fill_value=0).reset_index()
        st.dataframe(comp_pivot, use_container_width=True)
    else:
        st.warning("데이터가 없습니다.")

# --- Tab 3: 실시간 검역 비교 ---
with tab3:
    st.subheader("⚡ 실시간 vs 과거 실적 비교")
    comp_m = st.selectbox("비교할 과거 월 선택", sorted(df['연월'].unique(), reverse=True), key="t3_m")
    
    f_raw = df_raw.copy()
    f_hist = df[df['연월'] == comp_m].copy()

    if not f_raw.empty:
        merge_on = ['세부구분', '품목', '국가별']
        raw_grp = f_raw.groupby(merge_on)['당월누계(Ton)'].sum().reset_index().rename(columns={'당월누계(Ton)': '실시간'})
        hist_grp = f_hist.groupby(merge_on)['검역량'].sum().reset_index().rename(columns={'검역량': '과거'})
        merged = pd.merge(raw_grp, hist_grp, on=merge_on, how='outer').fillna(0)
        merged['차이'] = merged['실시간'] - merged['과거']
        
        for col in ['실시간', '과거', '차이']:
            merged[col] = merged[col].apply(lambda x: f"{x:,.2f}")
        st.dataframe(merged, use_container_width=True, hide_index=True)
    else:
        st.warning("실시간 데이터가 없습니다.")

# --- 오퍼가 분석 ---
st.markdown("<br><br>", unsafe_allow_html=True)
st.markdown("---") 
st.markdown('<div id="offer"></div>', unsafe_allow_html=True) 
st.title("💵 오퍼가 분석")

if not df_offer.empty:
    o1, o2, o3 = st.columns(3)
    with o1: o_y = st.selectbox("연 선택", ['전체'] + sorted(df_offer['연'].unique()), key="o_y")
    with o2: o_m = st.selectbox("월 선택", ['전체'] + sorted(df_offer['월'].unique()), key="o_m")
    with o3: o_c = st.selectbox("대분류 선택", ['전체'] + sorted(df_offer['대분류'].unique()), key="o_c")

    o4, o5, o6 = st.columns(3)
    with o4: o_o = st.selectbox("원산지 선택", ['전체'] + sorted(df_offer['원산지'].unique()), key="o_o")
    with o5: o_i = st.selectbox("품목명 선택", ['전체'] + sorted(df_offer['품목명'].unique()), key="o_i")
    with o6: o_g = st.selectbox("등급 선택", ['전체'] + sorted(df_offer['등급'].unique()), key="o_g")

    f_offer = df_offer.copy()
    if o_y != '전체': f_offer = f_offer[f_offer['연'] == o_y]
    if o_m != '전체': f_offer = f_offer[f_offer['월'] == o_m]
    if o_c != '전체': f_offer = f_offer[f_offer['대분류'] == o_c]
    if o_o != '전체': f_offer = f_offer[f_offer['원산지'] == o_org]
    if o_i != '전체': f_offer = f_offer[f_offer['품목명'] == o_itm]
    if o_g != '전체': f_offer = f_offer[f_offer['등급'] == o_grd]

    st.dataframe(f_offer, use_container_width=True, hide_index=True)
