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

# [핵심 수정] 정확한 구글 드라이브 파일명 및 탭 이름 매핑
SPREADSHEET_NAME = "기억 박물관 발표 채점 및 관찰기록표(최종)"
EVAL_WORKSHEET = "발표 채점 및 관찰기록표 V4"
REFLECTION_WORKSHEET = "학생소감"
