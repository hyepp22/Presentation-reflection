import streamlit as st
import pandas as pd
import gspread
import json
import google.generativeai as genai

st.set_page_config(
    page_title="발표 소감 및 평가 시스템",
    page_icon="📝",
    layout="wide"
)

# ---------------------------------------------------------
# 1. Secrets 및 API 인증 설정
# ---------------------------------------------------------
@st.cache_resource
def init_gemini():
    """Gemini API 설정"""
    if "GEMINI_API_KEY" in st.secrets:
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    else:
        st.error("Secrets에 GEMINI_API_KEY가 설정되어 있지 않습니다.")

@st.cache_resource
def get_gspread_client():
    """GCP 서비스 계정 인증 후 gspread 클라이언트 반환"""
    try:
        # Secrets의 [gcp_service_account] dictionary 가져오기
        gcp_dict = dict(st.secrets["gcp_service_account"])
        gc = gspread.service_account_from_dict(gcp_dict)
        return gc
    except Exception as e:
        st.error(f"구글 서비스 계정 인증 실패: {e}")
        return None

init_gemini()
gc = get_gspread_client()

# ---------------------------------------------------------
# 2. 구글 시트 데이터 로드 및 데이터 전처리 함수
# ---------------------------------------------------------
def load_sheet_data(spreadsheet_title, worksheet_title):
    """구글 시트에서 데이터를 로드하고 '학번' + '이름' 컬럼 결합 전처리 수행"""
    if gc is None:
        return pd.DataFrame()
    
    try:
        sh = gc.open(spreadsheet_title)
        ws = sh.worksheet(worksheet_title)
        data = ws.get_all_records()
        df = pd.DataFrame(data)
        
        if df.empty:
            return df

        # 컬럼명의 앞뒤 공백 제거
        df.columns = df.columns.str.strip()

        # [핵심] '학번이름' 컬럼이 없고, '학번'과 '이름'이 따로 존재하는 경우 자동 결합
        if '학번이름' not in df.columns:
            if '학번' in df.columns and '이름' in df.columns:
                df['학번이름'] = df['학번'].astype(str).str.strip() + df['이름'].astype(str).str.strip()
            elif '이름' in df.columns:
                df['학번이름'] = df['이름'].astype(str).str.strip()
            elif '학번' in df.columns:
                df['학번이름'] = df['학번'].astype(str).str.strip()
            else:
                df['학번이름'] = ""
                
        return df
    except Exception as e:
        st.error(f"'{worksheet_title}' 시트를 로드하는 중 오류 발생: {e}")
        return pd.DataFrame()

# ---------------------------------------------------------
# 3. 메인 UI 및 데이터 조회
# ---------------------------------------------------------
st.title("📝 발표 소감 및 평가 시스템")

# 시트 이름과 워크시트(탭) 이름을 본인 구글 시트에 맞게 확인해 주세요.
SPREADSHEET_NAME = "발표소감"  # 구글 시트 파일명
WORKSHEET_NAME = "학생소감"    # 탭 이름

# 데이터 로드
df_eval = load_sheet_data(SPREADSHEET_NAME, WORKSHEET_NAME)

st.subheader("🔍 학생 조회")
search_input = st.text_input("검색할 학번/이름 또는 학번이름을 입력하세요 (예: 10101홍길동 또는 홍길동)")

if search_input:
    target_name_id = search_input.replace(" ", "").strip()
    
    if not df_eval.empty and '학번이름' in df_eval.columns:
        # 기존 89행 오프셋 부분: 안전하게 결합된 '학번이름' 컬럼 사용
        search_mask = (
            df_eval['학번이름'].astype(str).str.replace(" ", "").str.contains(target_name_id, case=False, na=False)
        )
        result_df = df_eval[search_mask]
        
        if not result_df.empty:
            st.success(f"총 {len(result_df)}건의 기록을 찾았습니다.")
            st.dataframe(result_df, use_container_width=True)
        else:
            st.warning("일치하는 학생 데이터가 없습니다.")
    else:
        st.error("시트 데이터를 정상적으로 불러오지 못했거나 '학번이름' 검색 대상을 생성할 수 없습니다.")
