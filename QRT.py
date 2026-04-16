import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import json 
from datetime import datetime
import calendar
import time

st.set_page_config(page_title="검역량 & 오퍼가 & 재고 대시보드", layout="wide")

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

# --- 4. AZ광주 재고 데이터 불러오기 ---
@st.cache_data(ttl=60) # 수정을 자주 하므로 캐시 시간을 짧게 1분으로 설정
def load_inventory_data():
    try:
        gc = get_gspread_client()
        doc = gc.open_by_url('https://docs.google.com/spreadsheets/d/1XTZIZQsyeTi4s82G1zdDvtsddSBpPcAXeBA9iuRd87Y/edit#gid=1809836868')
        worksheet = doc.worksheet('총재고')
        data = worksheet.get_all_values()
        if not data: return pd.DataFrame()
        
        df_inv = pd.DataFrame(data[1:], columns=data[0])
        df_inv.columns = df_inv.columns.str.strip()
        df_inv = df_inv.loc[:, df_inv.columns != ''] # 빈 열 제거
        
        # 💡 [핵심 수정 1] 처음 만들 때부터 데이터 타입을 빡세게 고정 (TypeError 방지)
        if '판매 계획' not in df_inv.columns: df_inv['판매 계획'] = ""
        if '구매 계획' not in df_inv.columns: df_inv['구매 계획'] = ""
        
        if '적정재고' not in df_inv.columns:
            if '판매 계획' in df_inv.columns:
                idx = df_inv.columns.get_loc('판매 계획')
                df_inv.insert(idx, '적정재고', 0) # 빈칸("")이 아니라 숫자(0)으로 초기화
            else:
                df_inv['적정재고'] = 0
                
        # 무조건 숫자는 숫자, 문자는 문자로 형변환 쾅! 박아버리기
        df_inv['적정재고'] = pd.to_numeric(df_inv['적정재고'].astype(str).str.replace(',', ''), errors='coerce').fillna(0).astype(int)
        df_inv['판매 계획'] = df_inv['판매 계획'].astype(str).fillna("")
        df_inv['구매 계획'] = df_inv['구매 계획'].astype(str).fillna("")
                
        return df_inv
    except Exception as e:
        st.error(f"재고 데이터를 불러오는 중 오류 발생: {e}")
        return pd.DataFrame()

# 데이터 로딩
df = load_data()
df_raw = load_raw_data()
df_offer = load_offer_data()
df_inv = load_inventory_data()


# ==========================================
# 좌측 사이드바
# ==========================================
st.sidebar.markdown("### 🚀 빠른 이동")
st.sidebar.markdown('<a href="#quarantine" style="text-decoration:none; font-size:18px;">🥩 검역량 대시보드</a>', unsafe_allow_html=True)
st.sidebar.markdown('<a href="#offer" style="text-decoration:none; font-size:18px;">💵 오퍼가 분석</a>', unsafe_allow_html=True)
st.sidebar.markdown('<a href="#inventory" style="text-decoration:none; font-size:18px;">📦 AZ광주 재고관리</a>', unsafe_allow_html=True)


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
        pivot_df = pd.pivot_table(filtered_df, values='검역량', index=['연', '월', '세부구분', '품목', '부위', '국가별'], aggfunc='sum').reset_index()
        st.markdown("---")
        sort_t1 = st.radio("⬇️ 표 정렬 방식", ["기본", "검역량 내림차순 (큰 수부터)", "검역량 오름차순 (작은 수부터)"], horizontal=True, key="t1_sort")
        if "내림차순" in sort_t1: pivot_df = pivot_df.sort_values('검역량', ascending=False)
        elif "오름차순" in sort_t1: pivot_df = pivot_df.sort_values('검역량', ascending=True)
        pivot_df['검역량'] = pd.to_numeric(pivot_df['검역량'], errors='coerce').fillna(0).round(0).apply(lambda x: f"{x:,.0f}")
        st.dataframe(pivot_df, use_container_width=True, hide_index=True)
    else: st.warning("선택한 조건에 맞는 데이터가 없습니다.")

with tab2:
    st.subheader("기준월 vs 비교월 검역량 차이 분석")
    col_t2_1, col_t2_2 = st.columns(2)
    with col_t2_1: selected_cat_t2 = st.selectbox("세부구분 선택", ['전체'] + sorted(df['세부구분'].unique()), key="t2_cat")
    with col_t2_2: selected_item_t2 = st.selectbox("품목 선택", ['전체'] + sorted(df['품목'].unique()), key="t2_item")
    col_t2_3, col_t2_4 = st.columns(2)
    with col_t2_3: selected_part_t2 = st.selectbox("부위 선택", ['전체'] + sorted(df['부위'].unique()), key="t2_part")
    with col_t2_4: selected_country_t2 = st.selectbox("국가별 선택", ['전체(개별)', '전국가 합계'] + sorted(df['국가별'].unique()), key="t2_country")
    f_df_t2 = df.copy()
    if selected_cat_t2 != '전체': f_df_t2 = f_df_t2[f_df_t2['세부구분'] == selected_cat_t2]
    if selected_item_t2 != '전체': f_df_t2 = f_df_t2[f_df_t2['품목'] == selected_item_t2]
    if selected_part_t2 != '전체': f_df_t2 = f_df_t2[f_df_t2['부위'] == selected_part_t2]
    if selected_country_t2 not in ['전체(개별)', '전국가 합계']: f_df_t2 = f_df_t2[f_df_t2['국가별'] == selected_country_t2]
    sorted_ym = sorted(df['연월'].unique())
    col3, col4, col5 = st.columns(3)
    try: default_a_idx = sorted_ym.index('2025-01')
    except ValueError: default_a_idx = 0
    with col3: start_month_a = st.selectbox("시작월 (A) 선택", sorted_ym, index=default_a_idx, key="t2_base")
    default_b_idx = len(sorted_ym) - 1 if len(sorted_ym) > 0 else 0
    with col4: end_month_b = st.selectbox("마지막월 (B) 선택", sorted_ym, index=default_b_idx, key="t2_target")
    default_c_idx = len(sorted_ym) - 1 if len(sorted_ym) > 0 else 0
    with col5: target_month_c = st.selectbox("비교월 선택", sorted_ym, index=default_c_idx, key="t2_target_c")
    if not f_df_t2.empty:
        idx_cols = ['세부구분', '품목', '부위'] if selected_country_t2 == '전국가 합계' else ['세부구분', '품목', '부위', '국가별']
        comp_pivot_full = pd.pivot_table(f_df_t2, values='검역량', index=idx_cols, columns='연월', aggfunc='sum', fill_value=0)
        start_m, end_m = min(start_month_a, end_month_b), max(start_month_a, end_month_b)
        range_months = [m for m in sorted_ym if start_m <= m <= end_m]
        ordered_cols = []
        years_in_range = sorted(list(set([m.split('-')[0] for m in range_months])))
        for y in years_in_range:
            y_months = [m for m in range_months if m.startswith(y) and m in comp_pivot_full.columns]
            ordered_cols.extend(y_months)
            if y_months:
                comp_pivot_full[f'{y}년 합계'] = comp_pivot_full[y_months].sum(axis=1)
                comp_pivot_full[f'{y}년 평균'] = comp_pivot_full[y_months].mean(axis=1).fillna(0)
                ordered_cols.extend([f'{y}년 합계', f'{y}년 평균'])
        c_year, c_month = map(int, target_month_c.split('-'))
        prev_month_str = f"{c_year-1}-12" if c_month == 1 else f"{c_year}-{c_month-1:02d}"
        last_year_same_month = f"{c_year-1}-{c_month:02d}"
        this_year_cols = [m for m in sorted_ym if m.startswith(str(c_year)) and m <= target_month_c and m in comp_pivot_full.columns]
        last_year_cols = [m for m in sorted_ym if m.startswith(str(c_year-1)) and m in comp_pivot_full.columns]
        val_c = comp_pivot_full.get(target_month_c, 0)
        val_prev = comp_pivot_full.get(prev_month_str, 0)
        val_same_last = comp_pivot_full.get(last_year_same_month, 0)
        this_year_avg = comp_pivot_full[this_year_cols].mean(axis=1).fillna(0) if this_year_cols else 0
        last_year_avg = comp_pivot_full[last_year_cols].mean(axis=1).fillna(0) if last_year_cols else 0
        c_col_name = f"비교월({target_month_c})"
        comp_pivot_full[c_col_name] = val_c
        comp_pivot_full['올해평균 - 비교월'] = this_year_avg - val_c
        comp_pivot_full['비교월 - 직전월'] = val_c - val_prev
        comp_pivot_full['작년평균 - 비교월'] = last_year_avg - val_c
        comp_pivot_full['작년동월 - 비교월'] = val_same_last - val_c
        calc_cols = [c_col_name, '올해평균 - 비교월', '비교월 - 직전월', '작년평균 - 비교월', '작년동월 - 비교월']
        final_cols = ordered_cols + calc_cols
        comp_pivot = comp_pivot_full[final_cols].reset_index()
        if selected_country_t2 == '전국가 합계': comp_pivot.insert(3, '국가별', '전국가 합계')
        for col in final_cols: comp_pivot[col] = pd.to_numeric(comp_pivot[col], errors='coerce').fillna(0).round(0).apply(lambda x: f"{x:,.0f}")
        def color_tab2_cells(row):
            styles = [''] * len(row)
            month_vals = []
            for col in range_months:
                if col in row.index:
                    try: month_vals.append(float(str(row[col]).replace(',', '')))
                    except: pass
            r_max = max(month_vals) if month_vals else None
            non_zero_vals = [v for v in month_vals if v > 0]
            r_min = min(non_zero_vals) if non_zero_vals else None
            for i, col_name in enumerate(row.index):
                col_str = str(col_name)
                try: val = float(str(row[col_name]).replace(',', ''))
                except: val = 0.0
                if col_str in range_months:
                    if r_max is not None and val == r_max and val > 0 and r_max != r_min: styles[i] = 'background-color: #E3F2FD; color: #1565C0; font-weight: bold;'
                    elif r_min is not None and val == r_min and r_max != r_min: styles[i] = 'background-color: #FFEBEE; color: #C62828; font-weight: bold;'
                elif '합계' in col_str: styles[i] = 'background-color: #616161; color: #FFFFFF; font-weight: bold;'
                elif '평균' in col_str and '비교월' not in col_str: styles[i] = 'background-color: #F5F5F5; color: #212121; font-weight: bold;'
                elif col_str in calc_cols:
                    bg_color = 'background-color: #424242;'
                    text_color = 'color: #FFFFFF;'
                    if col_str == '비교월 - 직전월':
                        if val > 0: text_color = 'color: #81D4FA;'
                        elif val < 0: text_color = 'color: #EF9A9A;'
                    elif col_str in ['올해평균 - 비교월', '작년평균 - 비교월', '작년동월 - 비교월']:
                        if val < 0: text_color = 'color: #81D4FA;'
                        elif val > 0: text_color = 'color: #EF9A9A;'
                    styles[i] = f'{bg_color} {text_color} font-weight: bold;'
            return styles
        st.markdown("---")
        sort_c1, sort_c2 = st.columns(2)
        with sort_c1: sort_col_t2 = st.selectbox("⬇️ 표 정렬 기준 열", final_cols, index=len(final_cols)-1, key="t2_sort_col")
        with sort_c2: sort_ord_t2 = st.radio("정렬 방식", ["내림차순 (큰 수부터)", "오름차순 (작은 수부터)"], horizontal=True, key="t2_sort_ord")
        comp_pivot_numeric = comp_pivot.copy()
        if sort_col_t2 in final_cols:
            comp_pivot_numeric['_temp_sort'] = pd.to_numeric(comp_pivot_numeric[sort_col_t2].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
            comp_pivot_numeric = comp_pivot_numeric.sort_values('_temp_sort', ascending=("오름차순" in sort_ord_t2)).drop(columns=['_temp_sort'])
        st.dataframe(comp_pivot_numeric.style.apply(color_tab2_cells, axis=1), use_container_width=True, hide_index=True)
    else: st.warning("데이터가 없습니다.")

with tab3:
    st.subheader("⚡ 실시간 당월(Ton) vs 과거 특정월 비교")
    sorted_ym_desc = sorted(df['연월'].unique(), reverse=True)
    comp_hist_month = st.selectbox("비교할 과거 월 선택", sorted_ym_desc, index=0, key="t3_comp_month")
    col_t3_1, col_t3_2 = st.columns(2)
    with col_t3_1: sel_cat_t3 = st.selectbox("세부구분 선택", ['전체'] + sorted([x for x in df_raw['세부구분'].unique() if x]), key="t3_cat")
    with col_t3_2: sel_item_t3 = st.selectbox("품목 선택", ['전체'] + sorted([x for x in df_raw['품목'].unique() if x]), key="t3_item")
    col_t3_3, col_t3_4 = st.columns(2)
    part_list = sorted([x for x in df_raw.get('부위', pd.Series()).unique() if x]) if '부위' in df_raw.columns else []
    with col_t3_3: sel_part_t3_1 = st.selectbox("부위 선택 1", ['전체'] + part_list, key="t3_part1")
    with col_t3_4: sel_part_t3_2 = st.selectbox("부위 선택 2 (선택안함)", ['선택안함'] + part_list, key="t3_part2")
    col_t3_5, col_t3_6 = st.columns(2)
    with col_t3_5: sel_country_t3 = st.selectbox("국가별 선택", ['전체(개별)', '전국가 합계'] + sorted([x for x in df_raw['국가별'].unique() if x]), key="t3_country")
    with col_t3_6: view_mode_t3 = st.selectbox("표시 방식", ["국가별 상세 보기", "전국가 합계 보기"], key="t3_view")
    f_raw, f_hist, f_hist_25 = df_raw.copy(), df[df['연월'] == comp_hist_month].copy(), df[df['연'].astype(str).str[:4] == '2025'].copy()
    if sel_cat_t3 != '전체':
        for d in [f_raw, f_hist, f_hist_25]: d.query("세부구분 == @sel_cat_t3", inplace=True)
    if sel_item_t3 != '전체':
        for d in [f_raw, f_hist, f_hist_25]: d.query("품목 == @sel_item_t3", inplace=True)
    if sel_country_t3 not in ['전체(개별)', '전국가 합계']:
        for d in [f_raw, f_hist, f_hist_25]: d.query("국가별 == @sel_country_t3", inplace=True)
    if '부위' in df_raw.columns:
        parts = [sel_part_t3_1] if sel_part_t3_1 != '전체' else []
        if sel_part_t3_2 != '선택안함': parts.append(sel_part_t3_2)
        if parts:
            f_raw, f_hist, f_hist_25 = [d[d['부위'].isin(parts)].copy() for d in [f_raw, f_hist, f_hist_25]]
            if len(parts) > 1:
                cname = f"{parts[0]} + {parts[1]}"
                for d in [f_raw, f_hist, f_hist_25]: d['부위'] = cname
    if not f_raw.empty:
        merge_on = ['세부구분', '품목', '부위'] if sel_country_t3 == "전국가 합계" else ['세부구분', '품목', '부위', '국가별']
        raw_grp = f_raw.groupby(merge_on)['당월누계(Ton)'].sum().reset_index().rename(columns={'당월누계(Ton)': '실시간 당월 (Ton)'})
        hist_grp = f_hist.groupby(merge_on)['검역량'].sum().reset_index().rename(columns={'검역량': f'과거 {comp_hist_month} (Ton)'})
        avg_grp = f_hist_25.groupby(merge_on + ['연월'])['검역량'].sum().reset_index().groupby(merge_on)['검역량'].mean().reset_index().rename(columns={'검역량': '25년 월평균'})
        merged_df = pd.merge(raw_grp, hist_grp, on=merge_on, how='outer').fillna(0)
        merged_df = pd.merge(merged_df, avg_grp, on=merge_on, how='left').fillna(0)
        merged_df = merged_df[merged_df[f'과거 {comp_hist_month} (Ton)'] > 0]
        if not merged_df.empty:
            merged_df['차이 (실시간 - 과거)'] = merged_df['실시간 당월 (Ton)'] - merged_df[f'과거 {comp_hist_month} (Ton)']
            pacing = calendar.monthrange(datetime.now().year, datetime.now().month)[1] / datetime.now().day
            def get_status(row):
                proj = row['실시간 당월 (Ton)'] * pacing
                past = row[f'과거 {comp_hist_month} (Ton)']
                return 1 if proj > past else (-1 if proj < past else 0)
            merged_df['_pacing_status'] = merged_df.apply(get_status, axis=1)
            st.markdown("---")
            t3_num_cols = ['실시간 당월 (Ton)', f'과거 {comp_hist_month} (Ton)', '25년 월평균', '차이 (실시간 - 과거)']
            s1, s2 = st.columns(2)
            with s1: sort_col_t3 = st.selectbox("⬇️ 표 정렬 기준 열", t3_num_cols + ["색상 정렬"], key="t3_sort_col")
            with s2: sort_ord_t3 = st.radio("정렬 방식", ["내림차순", "오름차순", "파란색(미달예상)", "빨간색(초과예상)"], horizontal=True, key="t3_sort_ord")
            if "파란색" in sort_ord_t3: merged_df.sort_values('_pacing_status', ascending=True, inplace=True)
            elif "빨간색" in sort_ord_t3: merged_df.sort_values('_pacing_status', ascending=False, inplace=True)
            elif sort_col_t3 != "색상 정렬":
                merged_df['_tmp'] = pd.to_numeric(merged_df[sort_col_t3].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
                merged_df.sort_values('_tmp', ascending=("오름차순" in sort_ord_t3), inplace=True)
            for c in t3_num_cols: merged_df[c] = pd.to_numeric(merged_df[c]).round(0).apply(lambda x: f"{x:,.0f}")
            def color_t3(df_to_style):
                style_df = pd.DataFrame('', index=df_to_style.index, columns=df_to_style.columns)
                for i in range(len(df_to_style)):
                    status = merged_df.iloc[i]['_pacing_status']
                    if status == 1: style_df.iloc[i, :] = 'color: #D32F2F; font-weight: bold;'
                    elif status == -1: style_df.iloc[i, :] = 'color: #1976D2; font-weight: bold;'
                return style_df
            st.dataframe(merged_df.drop(columns=['_pacing_status','_tmp'], errors='ignore').style.apply(color_t3, axis=None), use_container_width=True, hide_index=True)
        else: st.info("비교할 과거 데이터 내역이 없습니다.")
    else: st.warning("실시간 검역 데이터가 없습니다.")


# ==========================================
# 메인 화면 2: 오퍼가 분석
# ==========================================
st.markdown("<br><br><br>", unsafe_allow_html=True) 
st.markdown("---") 
st.markdown('<div id="offer"></div>', unsafe_allow_html=True) 
st.title("💵 오퍼가 분석")
if not df_offer.empty and '보정오퍼가' in df_offer.columns:
    col_o1, col_o2, col_o3, col_o4 = st.columns(4)
    def extract_num(v):
        d = ''.join(filter(str.isdigit, str(v)))
        return int(d) if d else 0
    with col_o1: off_year = st.selectbox("연 선택", ['전체'] + sorted(df_offer['연'].unique(), key=extract_num))
    with col_o2: off_month = st.selectbox("월 선택", ['전체'] + sorted(df_offer['월'].unique(), key=extract_num))
    with col_o3: off_cat = st.selectbox("대분류 선택", ['전체'] + sorted(df_offer['대분류'].unique()))
    with col_o4: off_item = st.selectbox("품목명 선택", ['전체'] + sorted(df_offer['품목명'].unique()))
    filtered_offer = df_offer.copy()
    if off_year != '전체': filtered_offer = filtered_offer[filtered_offer['연'] == off_year]
    if off_month != '전체': filtered_offer = filtered_offer[filtered_offer['월'] == off_month]
    if off_cat != '전체': filtered_offer = filtered_offer[filtered_offer['대분류'] == off_cat]
    if off_item != '전체': filtered_offer = filtered_offer[filtered_offer['품목명'] == off_item]
    idx_cols = [c for c in ['대분류', '연', '월', '원산지', '품목명', '브랜드', 'EST', '등급'] if c in filtered_offer.columns]
    if idx_cols and not filtered_offer.empty:
        offer_pivot = pd.pivot_table(filtered_offer, values='보정오퍼가', index=idx_cols, aggfunc='mean').reset_index()
        offer_pivot['보정오퍼가'] = pd.to_numeric(offer_pivot['보정오퍼가']).round(0).apply(lambda x: f"{x:,.0f}")
        st.dataframe(offer_pivot, use_container_width=True, hide_index=True)
    else: st.warning("데이터가 없습니다.")


# ==========================================
# 메인 화면 3: AZ광주 재고관리 (양방향 편집 가능)
# ==========================================
st.markdown("<br><br><br>", unsafe_allow_html=True) 
st.markdown("---") 
st.markdown('<div id="inventory"></div>', unsafe_allow_html=True) 
st.title("📦 AZ광주 재고 판매계획")

if not df_inv.empty:
    st.subheader("🔍 재고 검색 및 필터")
    col_s1, col_s2, col_s3 = st.columns(3)
    with col_s1:
        search_query = st.text_input("🔍 품명 / 브랜드 검색 (일부 키워드 입력)", "")
    with col_s2:
        brand_col = next((c for c in df_inv.columns if '브랜드' in c or 'BRAND' in c.upper()), None)
        if brand_col:
            selected_brand = st.selectbox("🏷️ 브랜드 필터", ['전체'] + sorted(df_inv[brand_col].astype(str).unique().tolist()))
        else:
            selected_brand = '전체'
    with col_s3:
        offer_col = next((c for c in df_inv.columns if '오퍼구매' in c.replace(' ', '')), None)
        if offer_col:
            offer_opts = [x for x in df_inv[offer_col].unique() if str(x).strip() != '']
            selected_offer = st.selectbox("🛒 오퍼/구매 필터", ['전체'] + sorted(offer_opts))
        else:
            selected_offer = '전체'

    display_inv = df_inv.copy()
    
    if search_query:
        mask = display_inv.apply(lambda row: row.astype(str).str.contains(search_query, case=False).any(), axis=1)
        display_inv = display_inv[mask]
    if selected_brand != '전체' and brand_col:
        display_inv = display_inv[display_inv[brand_col] == selected_brand]
    if selected_offer != '전체' and offer_col:
        display_inv = display_inv[display_inv[offer_col] == selected_offer]

    st.markdown(f"**현재 조회된 항목:** {len(display_inv)}건 (표 안에서 직접 숫자를 적고 메모를 남길 수 있습니다.)")
    
    editor_config = {
        "적정재고": st.column_config.NumberColumn("적정재고", width="medium", format="%d"),
        "판매 계획": st.column_config.TextColumn("판매 계획 (메모)", width="large"),
        "구매 계획": st.column_config.TextColumn("구매 계획 (메모)", width="large")
    }
    disabled_cols = [c for c in display_inv.columns if c not in ["적정재고", "판매 계획", "구매 계획"]]

    edited_display = st.data_editor(
        display_inv,
        column_config=editor_config,
        disabled=disabled_cols,
        use_container_width=True,
        hide_index=True,
        height=int((len(display_inv) + 1) * 35) + 40
    )

    # 💡 [핵심 수정 2] .update() 대신 열별로 콕 찝어 수동으로 값 밀어넣기 (에러 완벽 차단)
    for col in ["적정재고", "판매 계획", "구매 계획"]:
        if col in edited_display.columns:
            df_inv.loc[edited_display.index, col] = edited_display[col]

    st.markdown("---")
    col_btn, _ = st.columns([1, 3])
    with col_btn:
        if st.button("💾 변경된 계획 구글 시트에 저장하기", use_container_width=True, type="primary"):
            with st.spinner("구글 시트에 데이터를 덮어쓰는 중입니다..."):
                try:
                    gc = get_gspread_client()
                    doc = gc.open_by_url('https://docs.google.com/spreadsheets/d/1XTZIZQsyeTi4s82G1zdDvtsddSBpPcAXeBA9iuRd87Y/edit#gid=1809836868')
                    worksheet = doc.worksheet('총재고')

                    save_df = df_inv.copy()
                    save_df.fillna("", inplace=True)
                    
                    update_data = [save_df.columns.values.tolist()] + save_df.values.tolist()
                    worksheet.clear()
                    worksheet.update('A1', update_data)
                    
                    st.success("✅ 구글 시트에 성공적으로 저장되었습니다!")
                    load_inventory_data.clear()
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"🚨 저장 실패! 오류 메시지: {e}")

else:
    st.warning("재고 데이터를 불러오지 못했습니다. 구글 시트의 권한이나 시트 이름을 확인해주세요.")
