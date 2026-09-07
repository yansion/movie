import datetime
import requests
import pandas as pd
import streamlit as st

# 1. 페이지 제목 및 전체 화면 레이아웃 설정
st.set_page_config(page_title="어제 박스오피스 순위", layout="wide")
st.title("🎬 어제 일별 박스오피스 순위")

# 2. 비밀 정보 vault(secrets)에서 KOBIS API 키 불러오기
try:
    API_KEY = st.secrets["KOBIS_KEY"]
except Exception:
    st.error("🔑 API 키를 찾을 수 없습니다.")
    st.info(
        "💡 **확인 방법:**\n"
        "- Streamlit Cloud 설정 페이지의 **Secrets** 탭에 `KOBIS_KEY = '발급받은키'` 형식으로 설정해 주세요.\n"
        "- 로컬 실행 시에는 `.streamlit/secrets.toml` 파일에 키를 저장했는지 확인해 주세요."
    )
    st.stop()

# 3. 한국 시간(KST, UTC+9) 기준으로 '어제' 날짜 계산 (YYYYMMDD 포맷)
kst_timezone = datetime.timezone(datetime.timedelta(hours=9))
now_in_kst = datetime.datetime.now(kst_timezone)
yesterday = now_in_kst - datetime.timedelta(days=1)
target_dt = yesterday.strftime("%Y%m%d")

st.caption(f"📅 조회 기준 날짜 (어제): {yesterday.strftime('%Y년 %m월 %d일')}")

# 4. API 데이터 요청 및 1시간 데이터 캐싱 (같은 날짜 재요청 방지)
@st.cache_data(ttl=3600)
def fetch_box_office(api_key, target_date):
    url = "http://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"
    params = {
        "key": api_key,
        "targetDt": target_date
    }
    try:
        response = requests.get(url, params=params, timeout=10)
        
        # HTTP 요청 상태 검사
        if response.status_code != 200:
            return None, f"서버 응답 실패 (응답 코드: {response.status_code})"
            
        data = response.json()
        
        # API 오류 메세지(faultInfo) 반환 여부 검사
        if "faultInfo" in data:
            error_msg = data["faultInfo"].get("message", "API 키가 올바르지 않거나 권한이 없습니다.")
            return None, f"KOBIS API 오류: {error_msg}"
            
        daily_list = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])
        
        # 영화 데이터 목록 검사
        if not daily_list:
            return None, "해당 날짜의 영화 목록 데이터가 비어 있습니다."
            
        return daily_list, None
        
    except Exception as e:
        return None, f"네트워크 통신 오류가 발생했습니다: {str(e)}"

# 데이터 로드 실행
box_office_data, error_message = fetch_box_office(API_KEY, target_dt)

# 5. 예외 발생 시 안내 화면 처리
if error_message:
    st.error(f"❌ 데이터 로드 실패: {error_message}")
    st.warning(
        "💡 **문제 해결 가이드:**\n"
        "1. KOBIS 개발자 센터에서 발급받은 API 키가 활성화 상태인지 확인하세요.\n"
        "2. Streamlit Cloud의 Secrets 이름이 `KOBIS_KEY`로 오탈자 없이 등록되었는지 확인하세요.\n"
        "3. KOBIS 서버 일시 점검 중일 수 있으니 잠시 후 다시 시도해 주세요."
    )
else:
    # 6. 데이터프레임 변환 및 수치형 데이터 형변환 (정렬 및 그래프용)
    df = pd.DataFrame(box_office_data)
    
    # 텍스트로 들어오는 숫자를 정수(int) 타입으로 변환
    numeric_columns = ["rank", "audiCnt", "audiAcc", "scrnCnt"]
    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
        
    # 순위(rank) 기준 오름차순 정렬 (1위 -> 10위)
    df = df.sort_values(by="rank", ascending=True)

    # 7. 1위 영화 핵심 지표 카드 3장
    st.subheader("🏆 어제의 박스오피스 1위")
    top_movie = df.iloc[0]
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric(label="🎬 영화명", value=top_movie["movieNm"])
    with col2:
        st.metric(label="🍿 어제 관객 수", value=f"{top_movie['audiCnt']:,} 명")
    with col3:
        st.metric(label="👥 누적 관객 수", value=f"{top_movie['audiAcc']:,} 명")

    st.divider()

    # 8. 관객 수 상위 5편 막대그래프 (순위 순 정렬)
    st.subheader("📊 관객 수 상위 5개 영화 (1위 ~ 5위 순)")
    top_5_df = df.head(5).copy()
    
    # X축에 '1위: 영화명' 형태로 명확히 표시
    top_5_df["순위_영화명"] = top_5_df["rank"].astype(str) + "위: " + top_5_df["movieNm"]

    # sort=False 옵션을 통해 가나다 순 자동 정렬을 끄고, 순위 데이터 순서를 유지합니다.
    st.bar_chart(
        top_5_df,
        x="순위_영화명",
        y="audiCnt",
        x_label="순위 및 영화명",
        y_label="어제 관객 수 (명)",
        sort=False
    )

    st.divider()

    # 9. 전체 순위 표 출력 (순위·영화명·개봉일·관객수·누적관객·스크린수)
    st.subheader("📋 전체 박스오피스 순위 표")
    
    # 지정된 컬럼만 선택 및 명칭 변경
    display_df = df[["rank", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]].copy()
    display_df.columns = ["순위", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]

    # 순위 순으로 정렬되어 보여지는 정갈한 테이블
    st.dataframe(
        display_df,
        use_container_width=True,
        hide_index=True,
        column_config={
            "순위": st.column_config.NumberColumn(format="%d 위"),
            "관객수": st.column_config.NumberColumn(format="%d 명"),
            "누적관객": st.column_config.NumberColumn(format="%d 명"),
            "스크린수": st.column_config.NumberColumn(format="%d 개"),
        }
    )
