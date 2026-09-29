import streamlit as st
import pandas as pd
import gspread
import plotly.graph_objects as go
from datetime import datetime

# ---------------------------------------------------------
# 1. Page Config
# ---------------------------------------------------------
st.set_page_config(
    page_title="말하기 수행평가 피드백 & 소감 제출",
    page_icon="🎤",
    layout="wide"
)

# ---------------------------------------------------------
# 2. Google Sheets 연동 및 데이터 처리 함수
# ---------------------------------------------------------
@st.cache_resource
def get_gspread_client():
    credentials = dict(st.secrets["gcp_service_account"])
    gc = gspread.service_account_from_dict(credentials)
    return gc

# 구글 시트 파일 ID 입력 (URL /d/ 와 /edit 사이의 문자열)
SPREADSHEET_ID = "YOUR_SPREADSHEET_KEY" 

# 탭 이름 설정
EVAL_TAB_NAME = "발표 채점 및 관찰기록표 V4"
REFLECTION_TAB_NAME = "학생소감"

def load_evaluation_data():
    try:
        gc = get_gspread_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet(EVAL_TAB_NAME)
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"평가 데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return pd.DataFrame()

def save_reflection_data(row_data):
    try:
        gc = get_gspread_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet(REFLECTION_TAB_NAME)
        worksheet.append_row(row_data)
        return True
    except Exception as e:
        st.error(f"소감 제출 중 오류가 발생했습니다: {e}")
        return False

# 안전하게 숫자로 변환하는 헬퍼 함수
def safe_float(val, default=0.0):
    try:
        if pd.isna(val) or val == '':
            return default
        return float(val)
    except ValueError:
        return default

# ---------------------------------------------------------
# 3. Main App Layout
# ---------------------------------------------------------
st.title("🎤 말하기 수행평가 결과 확인 및 소감 작성")
st.write("학번, 이름, 비밀번호를 입력하여 본인의 평가 피드백을 확인하고, 성찰 소감을 작성해 제출해 주세요.")

# 평가 데이터 로드
df_eval = load_evaluation_data()

# 로그인 및 정보 검색 사이드바
with st.sidebar:
    st.header("👤 학생 로그인")
    student_id = st.text_input("학번 (예: 10101)", "").strip()
    student_name = st.text_input("이름 (예: 홍길동)", "").strip()
    student_pw = st.text_input("비밀번호", type="password").strip()
    search_btn = st.button("조회하기", type="primary")

if search_btn or (student_id and student_name and student_pw):
    if df_eval.empty:
        st.warning("평가 데이터가 없습니다. 구글 시트 연동 및 탭 이름을 확인해 주세요.")
    else:
        # '학번이름' 형태로 결합하여 검색 (시트 헤더: '학번이름')
        target_name_id = f"{student_id}{student_name}"
        
        # 데이터 검색
        student_data = df_eval[
            (df_eval['학번이름'].astype(str).str.replace(" ", "") == target_name_id) & 
            (df_eval['비밀번호'].astype(str) == student_pw)
        ]
        
        if student_data.empty:
            st.error("입력한 학번, 이름 또는 비밀번호가 일치하지 않습니다. 다시 확인해 주세요.")
        else:
            student_info = student_data.iloc[0]
            st.success(f"**{student_name}** 학생의 평가 결과를 성공적으로 불러왔습니다!")
            st.caption(f"발표 날짜: {student_info.get('발표 날짜', '미입력')}")
            
            st.divider()

            # ---------------------------------------------------------
            # 4. 점수 시각화 및 세부 항목 표
            # ---------------------------------------------------------
            # 점수 항목 추출
            s_context1 = safe_float(student_info.get('맥락 및 구성(10점)'))
            s_media = safe_float(student_info.get('매체 활용(10점)'))
            s_delivery = safe_float(student_info.get('전달력(20점)'))
            s_nonverbal = safe_float(student_info.get('반/비언어(10점)'))
            s_mastery = safe_float(student_info.get('내용 숙지(20점)'))
            s_context2 = safe_float(student_info.get('맥락고려(10점)'))
            s_audience = safe_float(student_info.get('청중 점수(20점)'))
            s_total = safe_float(student_info.get('최종 총점(100점)'))

            # 3가지 대분류 항목으로 합산
            sum_context = s_context1 + s_media + s_context2  # 만점 30점
            sum_speaking = s_delivery + s_nonverbal + s_mastery  # 만점 50점
            sum_audience = s_audience                          # 만점 20점

            # 백분율 환산 (레이더 차트용)
            rate_context = (sum_context / 30.0) * 100 if 30 else 0
            rate_speaking = (sum_speaking / 50.0) * 100 if 50 else 0
            rate_audience = (sum_audience / 20.0) * 100 if 20 else 0

            categories = ['맥락 및 구성&매체 활용\n(30점 만점)', '말하기\n(50점 만점)', '청중\n(20점 만점)']
            rates = [rate_context, rate_speaking, rate_audience]

            col1, col2 = st.columns([1.1, 0.9])

            with col1:
                st.subheader("📊 영역별 성취도 시각화 (100% 환산)")
                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(
                    r=rates + [rates[0]],
                    theta=categories + [categories[0]],
                    fill='toself',
                    name='달성률 (%)',
                    line_color='#2b5c8f'
                ))
                fig.update_layout(
                    polar=dict(
                        radialaxis=dict(visible=True, range=[0, 100])
                    ),
                    showlegend=False,
                    margin=dict(l=50, r=50, t=30, b=30)
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.subheader("📝 세부 점수 내역")
                
                score_details = pd.DataFrame([
                    {"영역": "맥락 및 구성 (10점)", "점수": f"{s_context1} 점"},
                    {"영역": "매체 활용 (10점)", "점수": f"{s_media} 점"},
                    {"영역": "맥락 고려 (10점)", "점수": f"{s_context2} 점"},
                    {"영역": "전달력 (20점)", "점수": f"{s_delivery} 점"},
                    {"영역": "반/비언어 (10점)", "점수": f"{s_nonverbal} 점"},
                    {"영역": "내용 숙지 (20점)", "점수": f"{s_mastery} 점"},
                    {"영역": "청중 점수 (20점)", "점수": f"{s_audience} 점"},
                ])
                st.dataframe(score_details, use_container_width=True, hide_index=True)
                st.metric(label="🏆 최종 총점", value=f"{s_total} / 100 점")

            st.divider()

            # ---------------------------------------------------------
            # 5. 피드백 확인 영역
            # ---------------------------------------------------------
            st.subheader("💡 평가 피드백")
            feedback_text = student_info.get('관찰 기록 및 교사 피드백', '작성된 피드백이 없습니다.')
            st.info(feedback_text)

            st.divider()

            # ---------------------------------------------------------
            # 6. 학생 성찰 소감 작성 폼
            # ---------------------------------------------------------
            st.subheader("✍️ 나의 발표 성찰 소감 작성하기")
            st.caption("선생님의 피드백과 점수를 바탕으로 성찰 소감을 작성해 제출해 주세요.")

            with st.form("reflection_form"):
                good_point = st.text_area("1. 이번 발표에서 내가 잘한 점", placeholder="자신감 있게 목소리를 낸 점, 매체를 효과적으로 활용한 점 등...")
                bad_point = st.text_area("2. 아쉬웠던 점", placeholder="시선 처리가 부족했던 점, 시간 조절이 아쉬웠던 점 등...")
                learned_point = st.text_area("3. 새롭게 알게 된 점", placeholder="발표 구성 방법, 청중을 사로잡는 말하기 팁 등...")
                action_plan = st.text_area("4. 다음 발표에서 실천할 점", placeholder="다음번에는 대본을 외워서 시선 교환을 늘리겠다 등...")

                submit_btn = st.form_submit_button("소감 제출하기", type="primary")

                if submit_btn:
                    if not (good_point and bad_point and learned_point and action_plan):
                        st.warning("모든 항목을 작성해야 제출이 가능합니다.")
                    else:
                        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        new_row = [
                            current_time,
                            student_id,
                            student_name,
                            good_point,
                            bad_point,
                            learned_point,
                            action_plan
                        ]

                        if save_reflection_data(new_row):
                            st.balloons()
                            st.success("소감이 성공적으로 제출되었습니다!")
else:
    st.info("왼쪽 사이드바에서 학번, 이름, 비밀번호를 입력한 후 [조회하기] 버튼을 눌러주세요.")
