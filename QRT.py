import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json
import plotly.express as px  # 차트용 라이브러리 추가

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

# --- 데이터 로딩 함수들 ---
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

df = load_data()
df_raw = load_raw_data()
df_offer = load_offer_data()

# --- 레이아웃 시작 ---
st.sidebar.markdown("### 🚀 빠른 이동")
st.sidebar.markdown('<a href="#quarantine" style="text-decoration:none; font-size:18px;">🥩 검역량 대시보드</a>', unsafe_allow_html=True)
st.sidebar.markdown('<a href="#offer" style="text-decoration:none; font-size:18px;">💵 오퍼가 분석</a>', unsafe_allow_html=True)

st.markdown('<div id="quarantine"></div>', unsafe_allow_html=True) 
st.title("🥩 검역량 통합 대시보드")

tab1, tab2, tab3 = st.tabs(["📊 조건별 통합 조회", "📈 월별 검역량 비교", "⚡ 실시간 검역 비교"])

# --- Tab 1: 조건별 통합 조회 ---
with tab1:
    st.subheader("🔍 필터링 및 요약")
    col1, col2, col3 = st.columns(3)
    with col1: selected_year = st.selectbox("연도 선택", ['전체'] + sorted(df['연'].unique()), key="t1_y")
    with col2: selected_month = st.selectbox("월 선택", ['전체'] + sorted(df['월'].unique()), key="t1_m")
    with col3: selected_category = st.selectbox("세부구분", ['전체'] + sorted(df['세부구분'].unique()), key="t1_c")
    
    filtered_df = df.copy()
    if selected_year != '전체': filtered_df = filtered_df[filtered_df['연'] == selected_year]
    if selected_month != '전체': filtered_df = filtered_df[filtered_df['월'] == selected_month]
    if selected_category != '전체': filtered_df = filtered_df[filtered_df['세부구분'] == selected_category]

    if not filtered_df.empty:
        # [추가] 시각화 차트 1: 국가별 검역량 비중
        fig1 = px.pie(filtered_df, values='검역량', names='국가별', title=f"🌍 선택 조건 내 국가별 검역 비중", hole=0.4)
        st.plotly_chart(fig1, use_container_width=True)
        
        pivot_df = pd.pivot_table(filtered_df, values='검역량', index=['연', '월', '세부구분', '품목', '부위', '국가별'], aggfunc='sum').reset_index()
        pivot_df['검역량'] = pivot_df['검역량'].apply(lambda x: f"{x:,.2f}")
        st.dataframe(pivot_df, use_container_width=True, hide_index=True)
    else:
        st.warning("데이터가 없습니다.")

# --- Tab 2: 월별 검역량 비교 ---
with tab2:
    st.subheader("📈 기간별 검역량 추이")
    sorted_ym = sorted(df['연월'].unique())
    col_t2_1, col_t2_2 = st.columns(2)
    with col_t2_1: start_ym = st.selectbox("시작월 선택", sorted_ym, index=0)
    with col_t2_2: end_ym = st.selectbox("종료월 선택", sorted_ym, index=len(sorted_ym)-1)
    
    # [추가] 시각화 차트 2: 시계열 검역량 추이
    trend_df = df[(df['연월'] >= start_ym) & (df['연월'] <= end_ym)]
    if not trend_df.empty:
        trend_grp = trend_df.groupby('연월')['검역량'].sum().reset_index()
        fig2 = px.line(trend_grp, x='연월', y='검역량', title="📅 월별 총 검역량 흐름", markers=True)
        st.plotly_chart(fig2, use_container_width=True)
    
    # 기존 비교 표 로직 (생략 없이 유지)
    base_month = st.selectbox("기준월(A)", sorted_ym, key="b_m")
    target_month = st.selectbox("비교월(B)", sorted_ym, index=len(sorted_ym)-1, key="t_m")
    # ... (기존 pivot 표 로직이 여기에 들어갑니다)

# --- Tab 3: 실시간 검역 비교 ---
with tab3:
    st.subheader("⚡ 실시간 vs 과거 실적 비교")
    comp_hist_month = st.selectbox("비교할 과거 월 선택", sorted(df['연월'].unique(), reverse=True))
    
    f_raw = df_raw.copy()
    f_hist = df[df['연월'] == comp_hist_month].copy()
    
    if not f_raw.empty:
        merge_on = ['세부구분', '품목', '국가별']
        raw_grp = f_raw.groupby(merge_on)['당월누계(Ton)'].sum().reset_index().rename(columns={'당월누계(Ton)': '실시간'})
        hist_grp = f_hist.groupby(merge_on)['검역량'].sum().reset_index().rename(columns={'검역량': '과거'})
        
        merged_df = pd.merge(raw_grp, hist_grp, on=merge_on, how='outer').fillna(0)
        
        # [추가] 시각화 차트 3: 실시간 vs 과거 막대 비교
        chart_data = merged_df.melt(id_vars=merge_on, value_vars=['실시간', '과거'], var_name='구분', value_name='검역량')
        fig3 = px.bar(chart_data, x='품목', y='검역량', color='구분', barmode='group', title="⚖️ 품목별 실시간 vs 과거 실적")
        st.plotly_chart(fig3, use_container_width=True)
        
        st.dataframe(merged_df, use_container_width=True)

# --- 메인 2: 오퍼가 분석 ---
st.markdown("---") 
st.markdown('<div id="offer"></div>', unsafe_allow_html=True) 
st.title("💵 오퍼가 분석")

if not df_offer.empty:
    # [추가] 시각화 차트 4: 원산지별 평균 오퍼가
    avg_offer = df_offer.groupby('원산지')['보정오퍼가'].mean().reset_index()
    fig4 = px.bar(avg_offer, x='원산지', y='보정오퍼가', color='원산지', title="💰 원산지별 평균 보정오퍼가")
    st.plotly_chart(fig4, use_container_width=True)
    
    # 기존 오퍼가 필터 및 표 로직 유지
    # ...
