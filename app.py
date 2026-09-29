import streamlit as st
import pandas as pd
import gspread
import google.generativeai as genai

st.set_page_config(
    page_title="발표 결과 및 소감 작성",
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
        gcp_dict = dict(st.secrets["gcp_service_account"])
        gc = gspread.service_account_from_dict(gcp_dict)
        return gc
    except Exception as e:
        st.error(f"구글 서비스 계정 인증 실패: {e}")
        return None

init_gemini()
gc = get_gspread_client()

# ---------------------------------------------------------
# 2. 구글 시트 데이터 로드 함수
# ---------------------------------------------------------
def load_sheet_data(spreadsheet_title, worksheet_title):
    """구글 시트에서 데이터를 로드하고 전처리 수행"""
    if gc is None:
        return pd.DataFrame()
    
    try:
        sh = gc.open(spreadsheet_title)
        ws = sh.worksheet(worksheet_title)
        
        # get_all_records() 문제 발생 시 get_all_values()로 안전하게 불러오기
        data = ws.get_all_values()
        if not data:
            return pd.DataFrame()
        
        # 첫 번째 행을 컬럼 헤더로 사용
        headers = [str(h).strip() for h in data[0]]
        df = pd.DataFrame(data[1:], columns=headers)
        return df
    except Exception as e:
        st.error(f"'{worksheet_title}' 시트를 로드하는 중 오류 발생: {e}")
        return pd.DataFrame()

# ---------------------------------------------------------
# 3. 메인 UI - 학생 본인 인증 및 조회
# ---------------------------------------------------------
st.title("📝 발표 소감 및 평가 시스템")

# 시트 이름과 워크시트(탭) 이름 설정
SPREADSHEET_NAME = "발표소감"  # 구글 시트 파일명
WORKSHEET_NAME = "학생소감"    # 탭 이름

# 데이터 로드
df_eval = load_sheet_data(SPREADSHEET_NAME, WORKSHEET_NAME)

st.subheader("🔑 학생 본인 조회")
st.caption("학번, 이름, 비밀번호를 정확히 입력해 주세요.")

# 3개 개별 입력 칸 구성
col1, col2, col3 = st.columns(3)

with col1:
    input_student_id = st.text_input("학번", placeholder="예: 10101")
with col2:
    input_name = st.text_input("이름", placeholder="예: 홍길동")
with col3:
    input_password = st.text_input("비밀번호", type="password", placeholder="비밀번호 입력")

search_button = st.button("🔍 조회하기", type="primary", use_container_width=True)

# 조회 버튼 클릭 시 검증 로직 실행
if search_button:
    # 1. 필수 입력 필드 확인
    if not input_student_id.strip() or not input_name.strip() or not input_password.strip():
        st.warning("학번, 이름, 비밀번호를 모두 입력해 주세요.")
    elif df_eval.empty:
        st.error("시트 데이터를 불러오지 못했거나 데이터가 비어 있습니다.")
    else:
        s_id = input_student_id.strip()
        s_name = input_name.strip()
        s_pw = input_password.strip()

        # 필수 열(Header) 존재 여부 확인
        required_cols = ['학번', '이름', '비밀번호']
        missing_cols = [c for c in required_cols if c not in df_eval.columns]

        if missing_cols:
            st.error(f"구글 시트에 다음 필수 열이 없습니다: {', '.join(missing_cols)}")
            st.info("구글 시트 첫 번째 행에 '학번', '이름', '비밀번호'가 컬럼명으로 기재되어 있는지 확인해 주세요.")
        else:
            # 2. 학번, 이름, 비밀번호 일치 조건 확인
            match_mask = (
                (df_eval['학번'].astype(str).str.strip() == s_id) &
                (df_eval['이름'].astype(str).str.strip() == s_name) &
                (df_eval['비밀번호'].astype(str).str.strip() == s_pw)
            )

            result_df = df_eval[match_mask]

            if not result_df.empty:
                st.success(f"✅ 인증 성공! {s_name} 학생의 기록을 불러왔습니다.")
                
                # 비밀번호 열은 화면 표시에서 제외
                display_cols = [col for col in result_df.columns if col != '비밀번호']
                st.dataframe(result_df[display_cols], use_container_width=True)
            else:
                st.error("입력하신 학번, 이름 또는 비밀번호가 일치하지 않습니다.")
