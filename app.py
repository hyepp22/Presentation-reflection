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
    # Streamlit Secrets에서 secrets.json 정보를 읽어옵니다.
    credentials = dict(st.secrets["gcp_service_account"])
    gc = gspread.service_account_from_dict(credentials)
    return gc

# 동일한 구글 시트 파일 ID 하나만 입력합니다.
SPREADSHEET_ID = "1NxN6L57-Lr3ee-5HVf0duexlxAy0R6TiVsawnRjB58s" 

# 탭 이름 설정 (실제 시트 탭 이름과 정확히 일치해야 합니다)
EVAL_TAB_NAME = "발표 채점 및 관찰기록표 V4"     # 평가 점수/피드백이 있는 탭 이름
REFLECTION_TAB_NAME = "학생소감" # 소감을 기록할 탭 이름

def load_evaluation_data():
    try:
        gc = get_gspread_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet(EVAL_TAB_NAME) # 지정한 탭에서 데이터 불러오기
        data = worksheet.get_all_records()
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"평가 데이터를 불러오는 중 오류가 발생했습니다: {e}")
        return pd.DataFrame()

def save_reflection_data(row_data):
    try:
        gc = get_gspread_client()
        sh = gc.open_by_key(SPREADSHEET_ID)
        worksheet = sh.worksheet(REFLECTION_TAB_NAME) # 소감제출 탭으로 지정
        worksheet.append_row(row_data)
        return True
    except Exception as e:
        st.error(f"소감 제출 중 오류가 발생했습니다: {e}")
        return False

# ---------------------------------------------------------
# 3. Main App Layout
# ---------------------------------------------------------
st.title("🎤 말하기 수행평가 결과 확인 및 소감 작성")
st.write("학번과 이름을 입력하여 본인의 평가 피드백을 확인하고, 성찰 소감을 작성해 제출해 주세요.")

# 평가 데이터 로드
df_eval = load_evaluation_data()

# 학생 로그인 및 조회
with st.sidebar:
    st.header("👤 학생 정보 입력")
    student_id = st.text_input("학번 (예: 10101)", "").strip()
    student_name = st.text_input("이름", "").strip()
    search_btn = st.button("조회하기", type="primary")

if search_btn or (student_id and student_name):
    if df_eval.empty:
        st.warning("평가 데이터가 없습니다. 구글 시트 연동 및 탭 이름을 확인해 주세요.")
    else:
        # 데이터 검색 ('학번', '이름' 열 기준)
        student_data = df_eval[(df_eval['학번'].astype(str) == student_id) & (df_eval['이름'] == student_name)]
        
        if student_data.empty:
            st.error("입력한 학번과 이름에 해당하는 평가 결과가 없습니다. 다시 확인해 주세요.")
        else:
            student_info = student_data.iloc[0]
            st.success(f"**{student_info['이름']}** 학생의 평가 결과를 성공적으로 불러왔습니다!")
            
            st.divider()

            # ---------------------------------------------------------
            # 4. 점수 시각화 (레이더 차트 & 표)
            # ---------------------------------------------------------
            col1, col2 = st.columns([1, 1])

            # 점수 항목 가져오기
            score_context = float(student_info.get('맥락 및 구성&매체 활용', 0))
            score_speaking = float(student_info.get('말하기', 0))
            score_audience = float(student_info.get('청중', 0))

            categories = ['맥락 및 구성&매체 활용', '말하기', '청중']
            scores = [score_context, score_speaking, score_audience]

            with col1:
                st.subheader("📊 영역별 점수 시각화")
                fig = go.Figure()
                fig.add_trace(go.Scatterpolar(
                    r=scores + [scores[0]],  # 레이더 차트 폐곡선 처리
                    theta=categories + [categories[0]],
                    fill='toself',
                    name='내 점수',
                    line_color='#1f77b4'
                ))
                fig.update_layout(
                    polar=dict(
                        radialaxis=dict(visible=True, range=[0, 100]) # 평가 만점에 맞추어 상한값 조정 가능
                    ),
                    showlegend=False,
                    margin=dict(l=40, r=40, t=40, b=40)
                )
                st.plotly_chart(fig, use_container_width=True)

            with col2:
                st.subheader("📝 영역별 평가 수치")
                score_df = pd.DataFrame({
                    "평가 항목": categories,
                    "점수": scores
                })
                st.dataframe(score_df, use_container_width=True, hide_index=True)

            st.divider()

            # ---------------------------------------------------------
            # 5. 피드백 확인 영역
            # ---------------------------------------------------------
            st.subheader("💡 평가 피드백 확인")
            
            tab1, tab2, tab3 = st.tabs(["📋 루브릭 기준 피드백", "✏️ 교사 직접 피드백", "🤖 AI 보완 피드백"])

            with tab1:
                st.markdown("##### 평가 루브릭에 근거한 상세 피드백")
                st.info(student_info.get('루브릭 피드백', '루브릭 피드백이 없습니다.'))

            with tab2:
                st.markdown("##### 담당 교사 피드백")
                st.write(student_info.get('교사 피드백', '교사 피드백이 없습니다.'))

            with tab3:
                st.markdown("##### AI 다듬은 피드백")
                st.success(student_info.get('AI 피드백', 'AI 피드백이 없습니다.'))

            st.divider()

            # ---------------------------------------------------------
            # 6. 학생 성찰 소감 작성 폼
            # ---------------------------------------------------------
            st.subheader("✍️ 나의 발표 성찰 소감 작성하기")
            st.caption("피드백을 바탕으로 자신의 발표를 되돌아보고 소감을 작성해 주세요.")

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
    st.info("왼쪽 사이드바에서 학번과 이름을 입력한 후 [조회하기]를 눌러주세요.")
