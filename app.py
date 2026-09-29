# ---------------------------------------------------------
# 2. 구글 시트 데이터 로드 및 저장 함수 (보완)
# ---------------------------------------------------------
def load_sheet_data(spreadsheet_title, worksheet_title):
    """구글 시트에서 데이터를 안전하게 로드하고 전처리 수행"""
    if gc is None:
        return pd.DataFrame()
    
    try:
        sh = gc.open(spreadsheet_title)
        ws = sh.worksheet(worksheet_title)
        
        # 전체 데이터 가져오기
        data = ws.get_all_values()
        
        if not data:
            return pd.DataFrame()
        
        # 첫 번째 행을 컬럼 헤더로 사용하고 양끝 공백 제거
        headers = [str(h).strip() for h in data[0]]
        df = pd.DataFrame(data[1:], columns=headers)
        return df

    except Exception as e:
        # <Response [200]> 예외가 발생한 경우 수동으로 셀 데이터를 재시도하여 가져오기
        if "200" in str(e):
            try:
                sh = gc.open(spreadsheet_title)
                ws = sh.worksheet(worksheet_title)
                data = ws.get_all_values()
                if data:
                    headers = [str(h).strip() for h in data[0]]
                    return pd.DataFrame(data[1:], columns=headers)
            except Exception:
                pass
        
        st.error(f"'{worksheet_title}' 시트를 로드하는 중 오류 발생: {e}")
        return pd.DataFrame()
