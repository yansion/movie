import datetime
import pandas as pd
import plotly.express as px
import requests
import streamlit as st

st.set_page_config(page_title="일별 박스오피스", page_icon="🎬", layout="wide")

# 인증키는 비밀 금고(secrets)에서 불러온다
API_KEY = st.secrets["KOBIS_KEY"]
URL = "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/searchDailyBoxOfficeList.json"

# 한국 시간(KST) 기준 계산 및 달력 조회 가능한 최대 날짜(어제) 설정
KST = datetime.timezone(datetime.timedelta(hours=9))
yesterday = datetime.datetime.now(KST).date() - datetime.timedelta(days=1)

st.title("🎬 일별 박스오피스")

# 달력에서 조회할 날짜 선택 (어제 날짜까지만 선택 가능)
selected_date = st.date_input(
    "📅 조회할 날짜를 선택하세요",
    value=yesterday,
    max_value=yesterday
)
target_dt = selected_date.strftime("%Y%m%d")


@st.cache_data(ttl=3600)  # 같은 날짜는 한 시간 동안 캐싱하여 API 재호출 방지
def fetch_boxoffice(date_str):
    """KOBIS API에서 해당 날짜의 일별 박스오피스를 받아 온다."""
    params = {"key": API_KEY, "targetDt": date_str}
    res = requests.get(URL, params=params, timeout=10)
    res.raise_for_status()
    return res.json()


try:
    data = fetch_boxoffice(target_dt)
except requests.RequestException:
    st.error("서버에 연결하지 못했습니다. 인터넷 연결을 확인하고 잠시 뒤 새로고침해 주세요.")
    st.stop()

# API 키 오류 등 faultInfo 예외 처리
if "faultInfo" in data:
    st.error(f"API가 오류를 돌려주었습니다: {data['faultInfo'].get('message', '')}")
    st.info("비밀 금고(secrets)의 KOBIS_KEY 값이 올바른지 확인해 주세요.")
    st.stop()

movies = data.get("boxOfficeResult", {}).get("dailyBoxOfficeList", [])

# 영화 목록이 비어 있는 경우 처리
if not movies:
    st.warning("그날은 아직 집계 전입니다.")
    st.stop()

df = pd.DataFrame(movies)

# 숫자가 글자로 오므로 수치형으로 변환
for col in ["rank", "rankInten", "audiCnt", "audiAcc", "scrnCnt"]:
    df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

# 100만 관객 돌파 영화 표기 (영화명 옆 트로피 🏆 이모지 추가)
df["movieNm"] = df.apply(
    lambda row: f"{row['movieNm']} 🏆" if row["audiAcc"] >= 1000000 else row["movieNm"],
    axis=1
)

# 전날 대비 순위 증감(rankInten) 화살표 변환
def format_rank_inten(inten):
    if inten > 0:
        return f"🔺 {inten}"
    elif inten < 0:
        return f"🔻 {abs(inten)}"
    return "-"

df["순위변동"] = df["rankInten"].apply(format_rank_inten)

# 1위 영화 핵심 지표 카드
top = df.sort_values("rank").iloc[0]
st.subheader(f"🥇 1위 — {top['movieNm']}")
c1, c2, c3 = st.columns(3)
c1.metric("일일 관객수", f"{top['audiCnt']:,}명")
c2.metric("누적 관객수", f"{top['audiAcc']:,}명")
c3.metric("스크린수", f"{top['scrnCnt']:,}개")

# 전체 순위표 (순위변동 컬럼 추가)
st.subheader("📋 전체 순위표")
table = df.sort_values("rank")[["rank", "순위변동", "movieNm", "openDt", "audiCnt", "audiAcc", "scrnCnt"]]
table.columns = ["순위", "순위변동", "영화명", "개봉일", "관객수", "누적관객", "스크린수"]
st.dataframe(table, hide_index=True, width="stretch")

# 관객수 상위 5편 막대그래프
st.subheader("📊 관객수 상위 5편")
top5 = df.sort_values("audiCnt", ascending=False).head(5)
fig = px.bar(top5, x="movieNm", y="audiCnt", labels={"movieNm": "영화명", "audiCnt": "일일 관객수"})
st.plotly_chart(fig, width="stretch")
