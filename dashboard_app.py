import streamlit as st # Streamlit 라이브러리 임포트
import pandas as pd # Pandas 라이브러리 임포트
import numpy as np # Numpy 라이브러리 임포트
import requests # HTTP 요청을 위한 Requests 라이브러리 임포트
import os # 운영체제 리소스 접근을 위한 OS 라이브러리 임포트
import time # 시간 지연 기능을 위한 Time 라이브러리 임포트
from datetime import datetime, timedelta # 날짜 및 시간 계산을 위한 모듈 임포트
from dotenv import load_dotenv # .env 파일 로드를 위한 dotenv 임포트
import plotly.express as px # Plotly 고수준 시각화 도구 임포트
import plotly.graph_objects as go # Plotly 저수준 시각화 객체 임포트
import koreanize_matplotlib # Matplotlib 한글 폰트 설정 라이브러리 임포트

# 1. 초기 설정 및 보안
load_dotenv() # .env 파일 로드 (로컬 개발용)

# Streamlit Secrets 우선 사용, 없으면 환경 변수(.env)에서 가져옴
# 배포 시에는 share.streamlit.io 관리 화면에서 설정 필요
CLIENT_ID = st.secrets.get("NAVER_CLIENT_ID", os.getenv("NAVER_CLIENT_ID")) # 클라이언트 ID 로드
CLIENT_SECRET = st.secrets.get("NAVER_CLIENT_SECRET", os.getenv("NAVER_CLIENT_SECRET")) # 클라이언트 시크릿 로드

st.set_page_config( # 웹 페이지 기본 설정 시작
    page_title="네이버 실시간 다중 시장 분석 대시보드", # 브라우저 탭 제목 설정
    page_icon="📊", # 브라우저 탭 아이콘 설정
    layout="wide", # 페이지 레이아웃을 넓게 설정
    initial_sidebar_state="expanded" # 사이드바를 기본적으로 펼침 상태로 설정
) # 웹 페이지 기본 설정 종료

# 커스텀 CSS (프리미엄 디자인 적용)
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; } /* 메인 배경색 설정 */
    .stMetric {
        background-color: #ffffff; /* 지표 카드 배경색 설정 */
        padding: 15px; /* 지표 카드 안쪽 여백 설정 */
        border-radius: 10px; /* 지표 카드 모서리 둥글게 설정 */
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); /* 지표 카드 그림자 효과 설정 */
    }
    h1, h2, h3 { color: #1e3a8a; } /* 헤더 텍스트 색상 설정 */
    </style>
    """, unsafe_allow_html=True) # HTML/CSS 스타일 적용

# 2. API 호출 함수 정의
def get_header(): # API 호출 헤더 생성 함수 시작
    return { # 헤더 딕셔너리 반환
        "X-Naver-Client-Id": CLIENT_ID, # 네이버 클라이언트 ID 포함
        "X-Naver-Client-Secret": CLIENT_SECRET, # 네이버 클라이언트 시크릿 포함
        "Content-Type": "application/json" # 콘텐츠 타입을 JSON으로 설정
    } # 헤더 딕셔너리 반환 종료

@st.cache_data(ttl=3600) # 데이터를 1시간 동안 캐싱하여 중복 호출 방지
def fetch_trend_data(keywords, start_date, end_date): # 다중 키워드 트렌드 수집 함수 시작
    """실시간 다중 검색어 트렌드 데이터 수집"""
    url = "https://openapi.naver.com/v1/datalab/search" # 네이버 데이터랩 검색 트렌드 API URL
    keyword_groups = [{"groupName": kw, "keywords": [kw]} for kw in keywords] # 각 키워드를 개별 그룹으로 생성
    
    body = { # API 요청 바디 구성 시작
        "startDate": start_date.strftime("%Y-%m-%d"), # 시작 날짜 형식 지정
        "endDate": end_date.strftime("%Y-%m-%d"), # 종료 날짜 형식 지정
        "timeUnit": "date", # 시간 단위를 '일' 단위로 설정
        "keywordGroups": keyword_groups # 생성된 키워드 그룹 할당
    } # API 요청 바디 구성 종료
    try: # 예외 처리 구문 시작
        response = requests.post(url, headers=get_header(), json=body) # API POST 요청 실행
        if response.status_code == 200: # 응답 성공 시
            data = response.json() # 결과 데이터를 JSON으로 변환
            all_trend_data = [] # 전체 데이터를 담을 리스트 초기화
            for result in data['results']: # 각 키워드별 결과 순회 시작
                group_name = result['title'] # 키워드 그룹 이름 추출
                df_group = pd.DataFrame(result['data']) # 데이터 리스트를 데이터프레임으로 변환
                df_group['keyword'] = group_name # 데이터프레임에 키워드 열 추가
                all_trend_data.append(df_group) # 리스트에 개별 데이터프레임 추가
            
            final_df = pd.concat(all_trend_data, ignore_index=True) # 모든 데이터프레임을 하나로 병합
            final_df['period'] = pd.to_datetime(final_df['period']) # 기간 열을 날짜 형식으로 변환
            return final_df # 최종 데이터프레임 반환
        else: # 응답 실패 시
            st.error(f"Trend API Error: {response.status_code}") # 에러 메시지 출력
            return None # None 반환
    except Exception as e: # 예외 발생 시
        st.error(f"Trend Connection Error: {e}") # 연결 에러 메시지 출력
        return None # None 반환

@st.cache_data(ttl=3600) # 데이터를 1시간 동안 캐싱하여 중복 호출 방지
def fetch_search_results(keyword, category): # 개별 검색 결과 수집 함수 시작
    """실시간 단일 검색어 결과 수집 (shop, blog, cafearticle, news)"""
    url = f"https://openapi.naver.com/v1/search/{category}.json" # 카테고리별 검색 API URL 생성
    params = {"query": keyword, "display": 100, "start": 1, "sort": "sim"} # 요청 파라미터(100건, 정확도순) 설정
    try: # 예외 처리 구문 시작
        response = requests.get(url, headers=get_header(), params=params) # API GET 요청 실행
        if response.status_code == 200: # 응답 성공 시
            items = response.json().get('items', []) # 결과 아이템 리스트 추출
            if not items: # 아이템이 없을 경우
                return pd.DataFrame() # 빈 데이터프레임 반환
            df = pd.DataFrame(items) # 아이템 리스트를 데이터프레임으로 변환
            df['category'] = category # 데이터프레임에 카테고리 열 추가
            df['query_keyword'] = keyword # 데이터프레임에 검색 키워드 열 추가
            
            if 'lprice' in df.columns: # 가격(최저가) 열이 있는 경우
                df['lprice'] = pd.to_numeric(df['lprice'], errors='coerce') # 숫자로 변환하고 에러 시 결측치 처리
            
            if 'title' in df.columns: # 제목 열이 있는 경우
                df['title_clean'] = df['title'].str.replace('<b>', '', regex=False).str.replace('</b>', '', regex=False) # HTML 태그 제거
            
            return df # 최종 데이터프레임 반환
        else: # 응답 실패 시
            st.error(f"Search API Error ({category} - {keyword}): {response.status_code}") # 에러 메시지 출력
            return pd.DataFrame() # 빈 데이터프레임 반환
    except Exception as e: # 예외 발생 시
        st.error(f"Search Connection Error ({category} - {keyword}): {e}") # 연결 에러 메시지 출력
        return pd.DataFrame() # 빈 데이터프레임 반환

# 3. 사이드바 구성 시작
st.sidebar.title("🔍 분석 설정") # 사이드바 제목 출력
raw_keywords = st.sidebar.text_input("검색어 입력 (쉼표로 구분, 최대 5개)", value="스포츠브라, 레깅스, 요가매트") # 검색어 입력창 생성
search_keywords = [k.strip() for k in raw_keywords.split(",") if k.strip()][:5] # 입력을 쉼표로 나누고 공백 제거 후 5개로 제한

today = datetime.now() # 현재 날짜 및 시간 가져오기
one_year_ago = today - timedelta(days=365) # 현재로부터 1년 전 날짜 계산
date_range = st.sidebar.date_input("조회 기간", [one_year_ago, today]) # 날짜 범위 입력창 생성

st.sidebar.markdown("---") # 사이드바 구분선 추가
st.sidebar.info(f"현재 분석 키워드: {', '.join(search_keywords)}") # 현재 분석 중인 키워드 목록 정보창 출력

# 4. 데이터 수집 실행 시작
if CLIENT_ID and CLIENT_SECRET and search_keywords: # API 정보와 키워드 존재 여부 확인
    with st.spinner(f"다중 키워드 데이터 수집 중..."): # 데이터 로딩 애니메이션 표시
        # 트렌드 데이터 수집 (모든 키워드 그룹을 한 번에 요청)
        if len(date_range) == 2: # 시작일과 종료일이 모두 선택된 경우
            trend_df = fetch_trend_data(search_keywords, date_range[0], date_range[1]) # 트렌드 데이터 수집 함수 호출
        else: # 날짜 범위가 미완성인 경우
            trend_df = None # 트렌드 데이터 없음으로 처리
            
        # 통합 검색 데이터 수집 (키워드 및 카테고리별로 순회하며 수집)
        all_dfs = [] # 모든 데이터프레임을 담을 리스트 초기화
        for kw in search_keywords: # 입력된 각 키워드별로 순회 시작
            for cat in ['shop', 'blog', 'cafearticle', 'news']: # 4개 주요 카테고리별로 순회 시작
                res_df = fetch_search_results(kw, cat) # 개별 검색 결과 수집 함수 호출
                if not res_df.empty: # 수집된 데이터가 있으면
                    all_dfs.append(res_df) # 수집 데이터 리스트에 추가
                time.sleep(0.05) # 네이버 API 호출 간격 제한(Rate Limit) 방지
            
        combined_df = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame() # 모든 데이터를 하나의 데이터프레임으로 통합

    # 5. 메인 대시보드 레이아웃 시작
    st.title(f"🚀 다중 키워드 시장 분석 리포트") # 대시보드 메인 제목 출력
    
    # 상단 요약 지표 (KPI - 키워드별 분석 요약) 영역
    if not combined_df.empty: # 통합 데이터가 존재하는 경우
        st.subheader("📌 주요 지표 요약") # 소제목 출력
        kpi_cols = st.columns(len(search_keywords)) # 입력된 키워드 개수만큼 열 생성
        for i, kw in enumerate(search_keywords): # 각 키워드별 메트릭 카드 생성 순회 시작
            with kpi_cols[i]: # 각 열 내부에서 작업
                kw_data = combined_df[combined_df['query_keyword'] == kw] # 해당 키워드의 데이터만 필터링
                st.markdown(f"**{kw}**") # 키워드 이름 강조 표시
                st.metric("수집 데이터", f"{len(kw_data)} 건") # 수집된 총 검색 결과 건수 표시
                if 'lprice' in kw_data.columns: # 쇼핑 데이터(가격)가 포함된 경우
                    avg_p = kw_data[kw_data['category'] == 'shop']['lprice'].mean() # 쇼핑 카테고리 평균 가격 계산
                    if not np.isnan(avg_p): # 유효한 평균 가격이 있으면
                        st.write(f"평균가: {int(avg_p):,}원") # 포맷팅하여 가격 표시
    
    # 분석 탭 메뉴 구성
    tab_trend, tab_shop, tab_content, tab_profiling, tab_raw = st.tabs([ # 5개의 탭 버튼 정의
        "📊 트렌드 비교", "🛒 쇼핑 비교", "💬 채널 반응", "📄 프로파일링", "📁 원본 데이터"
    ]) # 탭 메뉴 생성 종료

    # 트렌드 비교 탭 영역
    with tab_trend: # '📊 트렌드 비교' 탭 내부 시작
        st.subheader("🗓 키워드별 검색 트렌드 비교") # 탭 소제목 출력
        if trend_df is not None: # 트렌드 데이터가 있는 경우
            fig_trend = px.line(trend_df, x='period', y='ratio', color='keyword', # 날짜별 검색 비율 선 그래프 생성
                               title="기간별 상대적 검색 트렌드 비교", # 차트 제목 설정
                               labels={'period': '날짜', 'ratio': '검색 비율 (상대치)'}, # 축 레이블 설정
                               line_shape='spline') # 곡선 형태로 보간
            fig_trend.update_layout(hovermode="x unified") # 마우스 호버 시 통합 정보 표시
            st.plotly_chart(fig_trend, use_container_width=True) # 대시보드 화면 너비에 맞춰 차트 출력
            
            st.write("**[해석]**") # 분석 해석 제목 출력
            st.info("여러 키워드를 동시에 시각화하여 관심도의 계절성과 키워드 간의 상대적 규모를 파악할 수 있습니다.") # 자동 해석 안내문 출력
        else: # 데이터가 없는 경우
            st.warning("트렌드 데이터를 불러올 수 없습니다.") # 경고 메시지 출력

    # 쇼핑 비교 탭 영역
    with tab_shop: # '🛒 쇼핑 비교' 탭 내부 시작
        st.subheader("🛒 키워드별 쇼핑 시장 분석") # 탭 소제목 출력
        shop_df = combined_df[combined_df['category'] == 'shop'] if not combined_df.empty else pd.DataFrame() # 쇼핑 데이터만 필터링
        
        if not shop_df.empty: # 쇼핑 데이터가 존재하는 경우
            col_s1, col_s2 = st.columns(2) # 2단 레이아웃 생성
            with col_s1: # 첫 번째 열 내부
                # 키워드별 평균 최저가 비교 바 차트 생성
                avg_price_df = shop_df.groupby('query_keyword')['lprice'].mean().reset_index() # 키워드별 평균가 집계
                fig_price = px.bar(avg_price_df, x='query_keyword', y='lprice', color='query_keyword', # 막대 그래프 객체 생성
                                  title="키워드별 평균 최저가 비교", labels={'lprice': '평균 가격', 'query_keyword': '키워드'}) # 차트 제목 및 레이블 설정
                st.plotly_chart(fig_price, use_container_width=True) # 대시보드에 차트 출력
            
            with col_s2: # 두 번째 열 내부
                # 키워드 및 쇼핑몰 점유율 트리맵 생성
                fig_tree = px.treemap(shop_df, path=['query_keyword', 'mallName'], # 계층 구조(키워드 -> 쇼핑몰) 지정
                                     title="키워드 및 쇼핑몰별 노출 구성(Treemap)") # 차트 제목 설정
                st.plotly_chart(fig_tree, use_container_width=True) # 대시보드에 차트 출력
            
            # 박스 플롯을 활용한 가격 분포 비교 차트 생성
            fig_box = px.box(shop_df, x='query_keyword', y='lprice', color='query_keyword', # 박스 플롯 객체 생성
                            title="키워드별 가격 분포 및 아웃라이어 분석") # 차트 제목 설정
            st.plotly_chart(fig_box, use_container_width=True) # 대시보드에 차트 출력
        else: # 쇼핑 데이터가 없는 경우
            st.write("쇼핑 데이터가 없습니다.") # 안내 텍스트 출력

    # 채널 반응 분석 탭 영역
    with tab_content: # '💬 채널 반응' 탭 내부 시작
        st.subheader("💬 키워드/채널별 소비자 반응") # 탭 소제목 출력
        content_df = combined_df[combined_df['category'].isin(['blog', 'cafearticle', 'news'])] if not combined_df.empty else pd.DataFrame() # 소셜 채널 데이터 필터링
        
        if not content_df.empty: # 데이터가 존재하는 경우
            # 키워드별 채널 데이터 수집 비중 비교 막대 차트 생성
            cat_counts = combined_df.groupby(['query_keyword', 'category']).size().reset_index(name='count') # 키워드/카테고리별 건수 집계
            fig_cat = px.bar(cat_counts, x='query_keyword', y='count', color='category', barmode='group', # 그룹형 막대 차트 생성
                            title="키워드별 채널 데이터 수집 비중") # 차트 제목 설정
            st.plotly_chart(fig_cat, use_container_width=True) # 대시보드에 차트 출력
            
            # 키워드별 상위 토근 정보를 하위 탭으로 개별 표시
            st.write("**키워드별 상위 20개 빈출 단어**") # 텍스트 안내 출력
            kw_tabs = st.tabs(search_keywords) # 각 키워드별로 탭 객체 생성
            for i, kw in enumerate(search_keywords): # 생성된 하위 탭을 키워드별로 순회
                with kw_tabs[i]: # 개별 키워드 탭 내부
                    sub_df = content_df[content_df['query_keyword'] == kw] # 해당 키워드의 소셜 데이터 필터링
                    if not sub_df.empty: # 데이터가 있으면
                        all_txt = " ".join(sub_df['title_clean'].astype(str)) # 전체 제목을 하나의 문장으로 합침
                        words = [w for w in all_txt.split() if len(w) > 1] # 2글자 이상의 단어만 추출
                        top_words = pd.Series(words).value_counts().head(20).reset_index() # 빈도수 상위 20개 추출
                        top_words.columns = ['단어', '빈도'] # 열 이름 변경
                        fig_kw = px.bar(top_words, x='빈도', y='단어', orientation='h', title=f"'{kw}' 주요 키워드", # 가로 막대 그래프 생성
                                       color='빈도', color_continuous_scale='Plasma') # 색상 스케일 적용
                        st.plotly_chart(fig_kw, use_container_width=True) # 대시보드에 차트 출력
                    else: # 데이터가 부족한 경우
                        st.write("데이터가 부족합니다.") # 안내 텍스트 출력
        else: # 데이터가 존재하지 않는 경우
            st.write("채널별 반응 데이터가 없습니다.") # 안내 텍스트 출력

    # 데이터 프로파일링 탭 영역
    with tab_profiling: # '📄 프로파일링' 탭 내부 시작
        st.subheader("📄 수집 데이터 품질 리포트") # 탭 소제목 출력
        if not combined_df.empty: # 데이터가 존재하는 경우
            st.write("**전체 데이터 구조 요약**") # 소제목 출력
            st.write(combined_df.describe(include='all').T) # 모든 열에 대한 요약 통계량 전치 행렬로 출력
            
            st.write("**키워드별 결측치 현황**") # 소제목 출력
            null_info = combined_df.groupby('query_keyword').apply(lambda x: x.isnull().sum()).T # 키워드별 결측치 합계 집계
            st.dataframe(null_info) # 표 형태로 결과 출력
        else: # 데이터가 없는 경우
            st.info("데이터가 없습니다.") # 정보 안내창 출력

    # 원본 데이터 조회 탭 영역
    with tab_raw: # '📁 원본 데이터' 탭 내부 시작
        st.subheader("📁 원본 데이터 조회 및 필터링") # 탭 소제목 출력
        if not combined_df.empty: # 데이터가 존재하는 경우
            # 사용자가 직접 조회할 키워드를 선택할 수 있는 멀티 셀렉트 박스 생성
            filter_kw = st.multiselect("조회할 키워드 선택", search_keywords, default=search_keywords) # 멀티 셀렉트 위젯
            filtered_view = combined_df[combined_df['query_keyword'].isin(filter_kw)] # 선택된 키워드만 필터링한 뷰 생성
            st.dataframe(filtered_view, use_container_width=True) # 통합 데이터프레임 표 형태로 출력
            
            csv = filtered_view.to_csv(index=False, encoding='utf-8-sig').encode('utf-8-sig') # 엑셀 깨짐 방지를 위한 인코딩 후 CSV로 변환
            st.download_button(label="필터링된 데이터 CSV 다운로드", data=csv, # 다운로드 버튼 생성
                               file_name=f"multi_search_{datetime.now().strftime('%Y%m%d')}.csv") # 현재 날짜가 포함된 파일 이름 설정
        else: # 데이터가 없는 경우
            st.info("데이터가 없습니다.") # 정보 안내창 출력

# 네이버 API 키가 없거나 키워드가 입력되지 않은 경우의 처리
else: # 설정 조건 불충분 시
    st.error("API 키 설정 확인 및 최소 하나 이상의 키워드를 입력해 주세요.") # 에러 메시지 출력창 표시
