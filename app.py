# ---------------------------------------------------------
# 2. 구글 시트 데이터 로드 및 저장 함수 (방어 로직 보완)
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
        # <Response [200]> 예외가 터지더라도 실제로는 성공한 상태이므로 다시 강제 조회
        try:
            sh = gc.open(spreadsheet_title)
            ws = sh.worksheet(worksheet_title)
            # get_all_values 대신 cell 범위 전체 가져오기 방식 활용
            data = ws.get_all_values()
        except Exception:
            # 예외 메시지에 200이 포함되어 있다면 이미 데이터를 정상으로 취급 가능
            if "200" in str(e):
                st.warning("시트 응답 상태는 정상(200)이나 형식을 다시 확인 중입니다.")
            else:
                st.error(f"'{worksheet_title}' 시트를 로드하는 중 오류 발생: {e}")
            return pd.DataFrame()

    if not data or len(data) < 2:
        st.warning(f"'{worksheet_title}' 시트에 데이터(행)가 없거나 비어 있습니다.")
        return pd.DataFrame()

    # 첫 번째 행(헤더) 공백 제거 및 데이터프레임 생성
    headers = [str(h).strip() for h in data[0]]
    df = pd.DataFrame(data[1:], columns=headers)
    return df
