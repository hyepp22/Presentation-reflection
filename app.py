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

@st.cache_resource
def get_gspread_client():
    """GCP 서비스 계정 인증 후 gspread 클라이언트 반환"""
    try:
        gcp_dict = dict(st.secrets["gcp_service_account"])
        gc = gspread.service_account_from_dict(gcp_dict)
        return gc
    except Exception as e:
        st.error("구글 시트 연동 설정을 확인해주세요.")
        return None

init_gemini()
gc = get_gspread_client()

# 구글 드라이브 파일명 및 워크시트(탭) 이름 설정
SPREADSHEET_NAME = "기억 박물관 발표 채점 및 관찰기록표(최종)"
EVAL_WORKSHEET = "발표 채점 및 관찰기록표 V4"
REFLECTION_WORKSHEET = "학생소감"

# ---------------------------------------------------------
# 이미지 기반 루브릭(채점 기준) 데이터 정의
# ---------------------------------------------------------
RUBRIC_DATA = {
    '맥락/구성': [
        (10, "청중과 상황 맥락을 잘 이해하고 내용을 구성함(5점) / 활동지 1~5관 및 음악/메시지가 매우 구체적이고 진정성 있게 완성됨(5점)"),
        (6, "맥락 이해가 다소 부족하거나 일부 활동지 내용이 추상적임(3점) / 활동지 1~5관 및 음악/메시지의 구체성, 진정성이 다소 미흡함(3점)"),
        (4, "맥락 이해가 거의 나타나지 않음(2점) / 활동지 작성 항목이 5회 이상 누락되거나 내용이 단순함(2점)")
    ],
    '매체활용': [
        (10, "내용에 적합하고 맥락을 고려한 시청각 자료를 활용하였음."),
        (5, "내용에 적합하나 맥락 고려가 미흡함. 또는 유기성이 떨어지는 시청각 자료를 활용함.")
    ],
    '전달력': [
        (20, "교실 전체에 명확히 전달되는 성량과 알맞은 속도, 완급 조절로 전달력이 매우 뛰어남."),
        (15, "목소리 크기와 말하는 속도가 적절하여 발표 내용을 듣는 데 무리가 없음."),
        (10, "목소리가 다소 작거나 속도가 약간 빠르고 눌려 전달력이 일부 떨어짐."),
        (5, "목소리가 거의 들리지 않거나 기어 들어가는 발음으로 소통이 불가능함.")
    ],
    '반/비언어': [
        (10, "슬라이드 전환과 어우러지는 자연스러운 손짓, 바른 자세, 시선을 사용함."),
        (8, "발표 자세가 바르고 내용에 어울리는 적절한 시선과 동작을 사용함."),
        (6, "자세는 바르나 비언어적 표현이 다소 어색하거나 대본, PPT 화면을 자주 바라봄."),
        (4, "불필요한 동작을 반복하거나 불안정한 자세로 발표에 집중하기 어려움.")
    ],
    '내용숙지': [
        (20, "원고나 PPT 화면에 의존하지 않고 내용을 완전히 숙지하여 청중과 눈을 맞추며 유연하게 발표함."),
        (15, "내용 숙지가 다소 부족하여 원고나 PPT 화면을 대본처럼 자주 읽음. 청중과 눈맞춤이 적음."),
        (10, "내용 숙지가 미흡하여 발표 내내 원고나 PPT 화면만 그대로 읽어 내려감. 눈맞춤이 거의 없음."),
        (5, "내용을 전혀 숙지하지 못하여 발표 진행이 어려움.")
    ],
    '맥락고려': [
        (10, "주어진 시간 내에 분량을 배분하거나 맥락을 고려해 능동적으로 발표를 마침."),
        (8, "주어진 시간에 거의 맞추거나 맥락을 고려해 조절하며 안정적으로 발표를 끝마침."),
        (6, "시간 배분이 약간 부족하거나 맥락 고려가 미흡하여 급하게 마무리하거나 시간이 약간 초과됨."),
        (4, "시간 조절에 실패하여 내용을 상당 부분 생략하거나 크게 초과함.")
    ]
}

def get_rubric_description(item_name, score):
    """학생 점수에 해당 루브릭 설명 반환"""
    if item_name not in RUBRIC_DATA:
        return "채점 기준 정보가 없습니다."
    
    rubric_list = RUBRIC_DATA[item_name]
    best_match = None
    min_diff = float('inf')
    
    for level_score, desc in rubric_list:
        diff = abs(score - level_score)
        if diff < min_diff:
            min_diff = diff
            best_match = desc
            
    return best_match if best_match else "채점 기준 정보가 없습니다."

# ---------------------------------------------------------
# 2. 구글 시트 데이터 로드 및 저장 함수
# ---------------------------------------------------------
def load_sheet_data(spreadsheet_title, worksheet_title):
    """구글 시트 데이터 로드"""
    if gc is None:
        return pd.DataFrame()
    
    try:
        sh = gc.open(spreadsheet_title)
        ws = sh.worksheet(worksheet_title)
        data = ws.get_all_values()
    except Exception:
        return pd.DataFrame()

    if not data or len(data) < 2:
        return pd.DataFrame()

    headers = [str(h).strip() for h in data[0]]
    df = pd.DataFrame(data[1:], columns=headers)
    return df

def save_reflection(student_id, student_name, good_point, regret_point, learned_point, action_point):
    """학생 소감을 구글 시트에 저장"""
    try:
        sh = gc.open(SPREADSHEET_NAME)
        ws = sh.worksheet(REFLECTION_WORKSHEET)
        
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
    except Exception:
        return False

# ---------------------------------------------------------
# 3. 피드백 다듬기 함수 (오류 메시지 노출 완전 방지)
# ---------------------------------------------------------
def format_feedback(teacher_comment, student_name):
    """피드백 다듬기 (API 실패 시 원본 자연스럽게 제공)"""
    if not teacher_comment or str(teacher_comment).strip() == "":
        return f"{student_name} 학생의 발표 피드백을 작성 중입니다."
    
    clean_comment = str(teacher_comment).strip()

    prompt = f"""
    아래는 교사가 작성한 발표 평가 메모입니다.
    이 내용을 {student_name} 학생에게 직접 다정하게 전하는 말로 다듬어주세요.
    
    [평가 메모]:
    "{clean_comment}"
    
    - 학생의 이름을 부르며 친절하고 다정한 말투로 작성하세요.
    - 잘한 점과 성장 포인트를 다정하게 다듬어 3문장 안팎으로 작성하세요.
    - 시스템이나 AI가 가공했다는 언급은 절대 하지 마세요.
    """
    
    candidate_models = ['gemini-1.5-flash', 'gemini-1.5-pro']
    
    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(prompt)
            if response and response.text:
                return response.text.strip()
        except Exception:
            continue
            
    # API 호출에 실패할 경우 에러 메시지 대신 원본 메시지 그대로 전달
    return f"{student_name} 학생, {clean_comment}"

# ---------------------------------------------------------
# 4. 세션 상태 초기화
# ---------------------------------------------------------
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'student_info' not in st.session_state:
    st.session_state.student_info = None

# ---------------------------------------------------------
# 5. 메인 UI - 본인 인증
# ---------------------------------------------------------
st.title("📝 발표 결과 조회 및 소감 작성")

if not st.session_state.authenticated:
    st.subheader("🔑 학생 본인 인증")
    st.caption("학번, 이름, 비밀번호를 정확히 입력해 주세요.")

    col1, col2, col3 = st.columns([1, 1, 1])
    with col1:
        input_student_id = st.text_input("학번", placeholder="예: 10101")
    with col2:
        input_name = st.text_input("이름", placeholder="예: 홍길동")
    with col3:
        input_password = st.text_input("비밀번호", type="password", placeholder="비밀번호 입력")

    st.markdown("---")
    search_button = st.button("🔍 발표 결과 조회하기", type="primary", use_container_width=True)

    if search_button:
        if not input_student_id.strip() or not input_name.strip() or not input_password.strip():
            st.warning("학번, 이름, 비밀번호를 모두 입력해 주세요.")
        else:
            df_eval = load_sheet_data(SPREADSHEET_NAME, EVAL_WORKSHEET)
            
            if df_eval.empty:
                st.error("평가 데이터를 불러오지 못했습니다. 잠시 후 다시 시도해 주세요.")
            else:
                s_id = input_student_id.strip()
                s_name = input_name.strip()
                s_pw = input_password.strip()

                required_cols = ['학번', '이름', '비밀번호']
                missing_cols = [c for c in required_cols if c not in df_eval.columns]

                if missing_cols:
                    st.error("시트 양식을 확인해주세요.")
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
                        st.error("입력하신 정보가 일치하지 않습니다. 다시 확인해 주세요.")

# ---------------------------------------------------------
# 6. 인증 성공 후 화면
# ---------------------------------------------------------
else:
    student = st.session_state.student_info
    student_id = student.get('학번', '')
    student_name = student.get('이름', '')

    col_head, col_logout = st.columns([3, 1])
    with col_head:
        st.success(f"🎉 **{student_id} {student_name}** 학생, 환영합니다!")
    with col_logout:
        if st.button("🚪 로그아웃", use_container_width=True):
            st.session_state.authenticated = False
            st.session_state.student_info = None
            st.rerun()

    st.divider()

    # --- Section A: 점수 차트 & 선생님 피드백 ---
    col_chart, col_ai = st.columns([1, 1])

    with col_chart:
        st.subheader("📊 항목별 발표 평가 점수")
        
        score_info = [
            ('맥락 및 구성(10점)', 10, '맥락/구성'),
            ('매체 활용(10점)', 10, '매체활용'),
            ('전달력(20점)', 20, '전달력'),
            ('반/비언어(10점)', 10, '반/비언어'),
            ('내용 숙지(20점)', 20, '내용숙지'),
            ('맥락고려(10점)', 10, '맥락고려')
        ]
        
        chart_categories = []
        scores = []
        max_scores = []
        score_details = []

        for full_col, max_val, short_name in score_info:
            if full_col in student:
                try:
                    val = float(student[full_col])
                except ValueError:
                    val = 0.0
                
                chart_categories.append(f"{short_name}<br>({max_val}점 만점)")
                scores.append(val)
                max_scores.append(max_val)
                score_details.append((short_name, val, max_val))

        if scores:
            fig = go.Figure()

            fig.add_trace(go.Scatterpolar(
                r=scores + [scores[0]],
                theta=chart_categories + [chart_categories[0]],
                fill='toself',
                name='획득 점수',
                line_color='#2b5c8f'
            ))

            fig.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 20]
                    )
                ),
                showlegend=False,
                margin=dict(l=40, r=40, t=30, b=30),
                height=320
            )
            st.plotly_chart(fig, use_container_width=True)
            
            st.metric(label="🏆 최종 총점", value=f"{student.get('최종 총점(100점)', '-')} / 100 점")
            
            # --- 세부 항목별 점수 및 루브릭(채점 기준) 조회 영역 ---
            st.markdown("**📌 세부 항목별 점수 및 채점 기준**")
            
            for s_name, val, max_val in score_details:
                rubric_desc = get_rubric_description(s_name, val)
                with st.expander(f"• **{s_name}**: {val:.0f}점 / {max_val}점 만점"):
                    st.markdown(f"**📖 나의 수행 수준 기준:**")
                    st.caption(rubric_desc)

        else:
            st.info("평가 점수 데이터가 존재하지 않습니다.")

    with col_ai:
        st.subheader("💌 선생님의 발표 피드백")
        teacher_comment = student.get('관찰 기록 및 교사 피드백', '')
        
        # 피드백 다듬기 수행
        final_feedback = format_feedback(teacher_comment, student_name)
        st.info(final_feedback)

    st.divider()

    # --- Section B: 학생 소감 작성 및 제출 ---
    st.subheader("✍️ 나의 발표 소감 작성하기")
    st.caption("발표를 마치며 느낀 점을 4가지 항목에 따라 작성해 주세요.")

    col_f1, col_f2 = st.columns([1, 1])
    with col_f1:
        good_point = st.text_area("1. 잘한 점", height=110, placeholder="이번 발표에서 스스로 칭찬하고 싶은 부분은 무엇인가요?")
        learned_point = st.text_area("3. 새롭게 알게 된 점", height=110, placeholder="발표를 준비하고 진행하며 깨달은 점은 무엇인가요?")

    with col_f2:
        regret_point = st.text_area("2. 아쉬웠던 점", height=110, placeholder="조금 더 보완했으면 좋았을 아쉬운 부분은 무엇인가요?")
        action_point = st.text_area("4. 다음 발표에서 실천할 점", height=110, placeholder="다음 발표에서는 어떤 점을 더욱 노력할 것인가요?")

    st.markdown("---")
    if st.button("📤 소감 제출하기", type="primary", use_container_width=True):
        if not good_point.strip() or not regret_point.strip() or not learned_point.strip() or not action_point.strip():
            st.warning("4가지 항목을 모두 작성한 후 제출해 주세요.")
        else:
            with st.spinner("소감을 제출하는 중입니다..."):
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
