import streamlit as st
import pandas as pd
import gspread
import plotly.graph_objects as go
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

# 구글 드라이브 파일명 및 워크시트(탭) 이름 설정
SPREADSHEET_NAME = "기억 박물관 발표 채점 및 관찰기록표(최종)"  # 구글 드라이브 파일명
EVAL_WORKSHEET = "발표 채점 및 관찰기록표 V4"                  # 채점표 탭 이름
REFLECTION_WORKSHEET = "학생소감"                              # 학생소감 탭 이름

# ---------------------------------------------------------
# 2. 구글 시트 데이터 로드 및 저장 함수
# ---------------------------------------------------------
def load_sheet_data(spreadsheet_title, worksheet_title):
    """구글 시트에서 데이터를 안전하게 로드하고 전처리 수행"""
    if gc is None:
        return pd.DataFrame()
    
    try:
        sh = gc.open(spreadsheet_title)
        ws = sh.worksheet(worksheet_title)
        data = ws.get_all_values()
    except Exception as e:
        try:
            sh = gc.open(spreadsheet_title)
            ws = sh.worksheet(worksheet_title)
            data = ws.get_all_values()
        except Exception:
            st.error(f"'{worksheet_title}' 시트를 로드하는 중 오류 발생: {e}")
            return pd.DataFrame()

    if not data or len(data) < 2:
        return pd.DataFrame()

    headers = [str(h).strip() for h in data[0]]
    df = pd.DataFrame(data[1:], columns=headers)
    return df

def save_reflection(student_id, student_name, good_point, regret_point, learned_point, action_point):
    """학생 소감을 구글 시트 '학생소감' 탭의 6개 컬럼에 맞춰 저장"""
    try:
        sh = gc.open(SPREADSHEET_NAME)
        ws = sh.worksheet(REFLECTION_WORKSHEET)
        
        # [학번, 이름, 잘한 점, 아쉬웠던 점, 새롭게 알게 된 점, 다음 발표에서 실천할 점] 순서로 저장
        row_data = [
            student_id, 
            student_name, 
            good_point, 
            regret_point, 
            learned_point, 
            action_point
        ]
        ws.append_row(row_data)
        return True
    except Exception as e:
        st.error(f"소감 저장 중 오류가 발생했습니다: {e}")
        return False

# ---------------------------------------------------------
# 3. Gemini API 기반 피드백 생성 함수
# ---------------------------------------------------------
def generate_growth_feedback(teacher_comment, student_name):
    """선생님의 관찰기록을 성장 중심 언어로 재가공"""
    if not teacher_comment or str(teacher_comment).strip() == "":
        return "선생님의 관찰 기록이 아직 작성되지 않았습니다."
    
    prompt = f"""
    당신은 따뜻하고 격려를 아끼지 않는 친절한 학교 교사입니다.
    아래는 학생 '{student_name}'의 발표에 대한 선생님의 원본 관찰 기록 및 피드백입니다.
    
    [선생님 원본 피드백]:
    "{teacher_comment}"
    
    위 내용을 바탕으로 학생이 잘한 점을 다정하게 칭찬하고, 앞으로 발전할 수 있는 방향을 성장 중심의 언어로 다정하게 재가공해 주세요.
    - 3~4문장 이내로 작성해 주세요.
    - 학생 이름을 부르며 따뜻한 말투로 전달해 주세요.
    """
    try:
        model = genai.GenerativeModel('gemini-1.5-flash-latest')
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        try:
            model = genai.GenerativeModel('gemini-2.5-flash')
            response = model.generate_content(prompt)
            return response.text
        except Exception:
            return f"피드백 생성 중 오류 발생: {e}"

# ---------------------------------------------------------
# 4. 세션 상태 초기화
# ---------------------------------------------------------
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'student_info' not in st.session_state:
    st.session_state.student_info = None

# ---------------------------------------------------------
# 5. 메인 UI 및 로그인/조회
# ---------------------------------------------------------
st.title("📝 발표 결과 조회 및 소감 작성 시스템")

if not st.session_state.authenticated:
    st.subheader("🔑 학생 본인 인증")
    st.caption("학번, 이름, 비밀번호를 정확히 입력해 주세요.")

    col1, col2, col3 = st.columns(3)
    with col1:
        input_student_id = st.text_input("학번", placeholder="예: 10101")
    with col2:
        input_name = st.text_input("이름", placeholder="예: 홍길동")
    with col3:
        input_password = st.text_input("비밀번호", type="password", placeholder="비밀번호 입력")

    search_button = st.button("🔍 조회하기", type="primary", use_container_width=True)

    if search_button:
        if not input_student_id.strip() or not input_name.strip() or not input_password.strip():
            st.warning("학번, 이름, 비밀번호를 모두 입력해 주세요.")
        else:
            df_eval = load_sheet_data(SPREADSHEET_NAME, EVAL_WORKSHEET)
            
            if df_eval.empty:
                st.error("평가 시트 데이터를 불러오지 못했거나 데이터가 비어있습니다.")
            else:
                s_id = input_student_id.strip()
                s_name = input_name.strip()
                s_pw = input_password.strip()

                required_cols = ['학번', '이름', '비밀번호']
                missing_cols = [c for c in required_cols if c not in df_eval.columns]

                if missing_cols:
                    st.error(f"시트에 다음 필수 열이 없습니다: {', '.join(missing_cols)}")
                else:
                    match_mask = (
                        (df_eval['학번'].astype(str).str.strip() == s_id) &
                        (df_eval['이름'].astype(str).str.strip() == s_name) &
                        (df_eval['비밀번호'].astype(str).str.strip() == s_pw)
                    )
                    result_df = df_eval[match_mask]

                    if not result_df.empty:
                        st.session_state.authenticated = True
                        st.session_state.student_info = result_df.iloc[0].to_dict()
                        st.rerun()
                    else:
                        st.error("입력하신 학번, 이름 또는 비밀번호가 일치하지 않습니다.")

# ---------------------------------------------------------
# 6. 인증 성공 후 화면 (결과 조회 & 소감 제출)
# ---------------------------------------------------------
else:
    student = st.session_state.student_info
    student_id = student.get('학번', '')
    student_name = student.get('이름', '')

    col_head, col_logout = st.columns([4, 1])
    with col_head:
        st.success(f"🎉 환영합니다, **{student_id} {student_name}** 학생!")
    with col_logout:
        if st.button("🚪 로그아웃", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.student_info = None
            st.rerun()

    st.divider()

    # --- Section A: 점수 레이더 차트 & 피드백 ---
    col_chart, col_ai = st.columns([1, 1])

    with col_chart:
        st.subheader("📊 항목별 발표 평가 점수")
        
        score_info = [
            ('맥락 및 구성(10점)', 10),
            ('매체 활용(10점)', 10),
            ('전달력(20점)', 20),
            ('반/비언어(10점)', 10),
            ('내용 숙지(20점)', 20),
            ('맥락고려(10점)', 10)
        ]
        
        categories = []
        scores = []
        
        for col_name, max_val in score_info:
            if col_name in student:
                categories.append(col_name.split('(')[0])
                try:
                    scores.append(float(student[col_name]))
                except ValueError:
                    scores.append(0.0)

        if scores:
            fig = go.Figure(data=go.Scatterpolar(
                r=scores + [scores[0]],
                theta=categories + [categories[0]],
                fill='toself',
                line_color='#2b5c8f'
            ))

            fig.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 20])),
                showlegend=False,
                height=380
            )
            st.plotly_chart(fig, use_container_width=True)
            
            st.metric(label="🏆 최종 총점 (100점 만점)", value=f"{student.get('최종 총점(100점)', '-')} 점")
        else:
            st.info("평가 점수 데이터가 존재하지 않습니다.")

    with col_ai:
        st.subheader("💬 선생님의 피드백")
        teacher_comment = student.get('관찰 기록 및 교사 피드백', '')
        
        with st.spinner("피드백을 정돈하는 중입니다..."):
            ai_feedback = generate_growth_feedback(teacher_comment, student_name)
        
        st.info(ai_feedback)

    st.divider()

    # --- Section B: 학생 소감 작성 및 제출 (시트 컬럼과 1:1 매핑) ---
    st.subheader("✍️ 나의 발표 소감 작성하기")
    st.caption("발표를 마치며 느낀 점을 4가지 항목에 따라 솔직하게 작성해 주세요.")

    col_f1, col_f2 = st.columns(2)
    with col_f1:
        good_point = st.text_area("1. 잘한 점", height=100, placeholder="이번 발표에서 스스로 칭찬하고 싶은 부분은 무엇인가요?")
        learned_point = st.text_area("3. 새롭게 알게 된 점", height=100, placeholder="발표를 준비하고 진행하며 새롭게 깨달은 점은 무엇인가요?")

    with col_f2:
        regret_point = st.text_area("2. 아쉬웠던 점", height=100, placeholder="조금 더 보완했으면 좋았을 아쉬운 부분은 무엇인가요?")
        action_point = st.text_area("4. 다음 발표에서 실천할 점", height=100, placeholder="다음 발표에서는 어떤 점을 더욱 노력할 것인가요?")

    if st.button("📤 소감 제출하기", type="primary", use_container_width=True):
        if not good_point.strip() or not regret_point.strip() or not learned_point.strip() or not action_point.strip():
            st.warning("4가지 항목을 모두 작성한 후 제출해 주세요.")
        else:
            with st.spinner("구글 시트에 소감을 저장하는 중입니다..."):
                success = save_reflection(
                    student_id, 
                    student_name, 
                    good_point.strip(), 
                    regret_point.strip(), 
                    learned_point.strip(), 
                    action_point.strip()
                )
                if success:
                    st.balloons()
                    st.success("소감이 성공적으로 제출되었습니다! 수고하셨습니다.")
