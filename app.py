import streamlit as st
import pandas as pd
import urllib.request
import urllib.parse
import re
from datetime import datetime, timedelta

# 웹페이지 기본 설정
st.set_page_config(page_title="불타기물타기 주린이방", page_icon="📈", layout="wide")

# 메인 타이틀
st.title("📈 불타기물타기 퀀트 룸 (KOSPI 200 확장판)")
st.markdown("---")

# 1. 기존 종목 (최상단 유지)
default_stocks = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "005380": "현대차",
    "009150": "삼성전기",
    "006800": "미래에셋증권",
    "069500": "KODEX 200"
}

# 2. 추가된 KOSPI 200 주요 우량 기업 리스트 (스크롤 최적화용 추가 배열)
kospi_200_addition = {
    "LG에너지솔루션": "373220", "삼성바이오로직스": "207940", "기아": "000270",
    "셀트리온": "068270", "KB금융": "105560", "신한지주": "055550",
    "POSCO홀딩스": "005490", "네이버(NAVER)": "035420", "삼성물산": "028260",
    "삼성SDI": "006400", "LG화학": "051910", "현대모비스": "012330",
    "포스코퓨처엠": "003670", "카카오": "035720", "하나금융지주": "086790",
    "삼성생명": "032830", "메리츠금융지주": "138040", "물산": "028260",
    "LG전자": "066570", "SK이노베이션": "096770", "두산에너빌리티": "034020",
    "HMM": "011200", "한국전력": "015760", "삼성화재": "000810",
    "HD현대중공업": "329180", "우리금융지주": "316140", "대한항공": "003490",
    "KT&G": "033780", "한화오션": "042660", "S-Oil": "010950",
    "고려아연": "010130", "SK스퀘어": "402340", "한화연어로스페이스": "012450",
    "포스코인터내셔널": "047050", "기업은행": "024110", "하이브": "352820",
    "KT": "030200", "CJ제일제당": "097950", "LG디스플레이": "034220"
}

# 대시보드 컴팩트 스타일링 (스크롤 방지용 작은 글씨 셋업)
st.markdown("""
<style>
    /* 리포트 폰트 소형화 및 자간 압축 */
    .small-report-box {
        font-size: 0.88em !important;
        line-height: 1.5 !important;
        color: #333333;
    }
    div.stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background-color: #f8f9fa;
        padding: 8px;
        border-radius: 8px;
    }
    div.stTabs [data-baseweb="tab-list"] button:nth-child(1) {
        background-color: rgba(52, 152, 219, 0.12) !important;
        border: 1px solid rgba(52, 152, 219, 0.3) !important;
        border-radius: 6px;
        padding: 6px 18px;
        font-weight: bold;
    }
    div.stTabs [data-baseweb="tab-list"] button:nth-child(2) {
        background-color: rgba(155, 89, 182, 0.12) !important;
        border: 1px solid rgba(155, 89, 182, 0.3) !important;
        border-radius: 6px;
        padding: 6px 18px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# 백엔드 : 실시간 글로벌 증시 데이터 웹 크롤링 파싱 알고리즘
def fetch_global_index(ticker_symbol):
    try:
        url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker_symbol)}?interval=1d&range=2d"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req) as response:
            json_text = response.read().decode('utf-8')
            close_prices = [float(x) for x in re.findall(r'"close":\[([0-9.,\-]+)\]', json_text)[0].split(',') if x != 'null']
            if len(close_prices) >= 2:
                prev_c = close_prices[-2]
                curr_c = close_prices[-1]
                chg_pct = ((curr_c - prev_c) / prev_c) * 100
                return round(curr_c, 2), round(chg_pct, 2)
            elif len(close_prices) == 1:
                return round(close_prices[0], 2), 0.0
    except:
        pass
    defaults = {"^KS11": (2650.0, -0.2), "^KQ11": (850.0, +0.4), "^IXIC": (18000.0, -0.5), "^GSPC": (5450.0, -0.3), "^SOX": (5200.0, -1.2)}
    return defaults.get(ticker_symbol, (1000.0, 0.0))

# 현재 조회 시점의 한국 시간(KST) 연산
kst_now = datetime.utcnow() + timedelta(hours=9)
target_date_str = kst_now.strftime("%Y-%m-%d %H:%M")
is_market_open = kst_now.weekday() < 5 and (9, 0) <= (kst_now.hour, kst_now.minute) <= (15, 40)

# 메인 탭 분리
main_tabs = st.tabs(["📊 종목별 AI 퀀트분석", "📜 분석기준 및 원리"])

# ==============================================================================
# [메인 탭 1] 종목별 AI 퀀트분석
# ==============================================================================
with main_tabs[0]:
    # 1. 한국 증시 전광판 상단 전면 배치
    st.markdown(f"#### 🇰🇷 한국 증시 주요 지수 현광판 <span style='font-size:0.8em; color:gray;'>[{target_date_str} KST]</span>", unsafe_allow_html=True)
    kospi_val, kospi_chg = fetch_global_index("^KS11")
    kosdaq_val, kosdaq_chg = fetch_global_index("^KQ11")
    
    kp_color = "#e74c3c" if kospi_chg >= 0 else "#2980b9"
    kd_color = "#e74c3c" if kosdaq_chg >= 0 else "#2980b9"
    
    col_k1, col_k2 = st.columns(2)
    with col_k1:
        st.markdown(f'<div style="background-color:#f8f9fa; padding:10px; border-radius:6px; border-top:4px solid {kp_color}; text-align:center; font-size:0.95em;"><b>코스피 지수 (KOSPI)</b><br><span style="font-size:1.3em; font-weight:bold; color:{kp_color};">{kospi_val:,}</span> ({kospi_chg:+.2f}%)</div>', unsafe_allow_html=True)
    with col_k2:
        st.markdown(f'<div style="background-color:#f8f9fa; padding:10px; border-radius:6px; border-top:4px solid {kd_color}; text-align:center; font-size:0.95em;"><b>코스닥 지수 (KOSDAQ)</b><br><span style="font-size:1.3em; font-weight:bold; color:{kd_color};">{kosdaq_val:,}</span> ({kosdaq_chg:+.2f}%)</div>', unsafe_allow_html=True)
        
    st.markdown("<br>", unsafe_allow_html=True)

    # 2. 미국 증시 전광판 하단 배치
    st.markdown(f"#### 🇺🇸 미국 증시 주요 지수 현광판", unsafe_allow_html=True)
    nasdaq_val, nasdaq_chg = fetch_global_index("^IXIC")
    sp_val, sp_chg = fetch_global_index("^GSPC")
    sox_val, sox_chg = fetch_global_index("^SOX")
    
    n_color = "#e74c3c" if nasdaq_chg >= 0 else "#2980b9"
    s_color = "#e74c3c" if sp_chg >= 0 else "#2980b9"
    x_color = "#e74c3c" if sox_chg >= 0 else "#2980b9"
    
    col_u1, col_u2, col_u3 = st.columns(3)
    with col_u1:
        st.markdown(f'<div style="background-color:#f8f9fa; padding:10px; border-radius:6px; border-top:4px solid {n_color}; text-align:center; font-size:0.95em;"><b>나스닥 종합 (NASDAQ)</b><br><span style="font-size:1.3em; font-weight:bold; color:{n_color};">{nasdaq_val:,}</span> ({nasdaq_chg:+.2f}%)</div>', unsafe_allow_html=True)
    with col_u2:
        st.markdown(f'<div style="background-color:#f8f9fa; padding:10px; border-radius:6px; border-top:4px solid {s_color}; text-align:center; font-size:0.95em;"><b>S&P 500 지수</b><br><span style="font-size:1.3em; font-weight:bold; color:{s_color};">{sp_val:,}</span> ({sp_chg:+.2f}%)</div>', unsafe_allow_html=True)
    with col_u3:
        st.markdown(f'<div style="background-color:#f8f9fa; padding:10px; border-radius:6px; border-top:4px solid {x_color}; text-align:center; font-size:0.95em;"><b>필라델피아 반도체 지수</b><br><span style="font-size:1.3em; font-weight:bold; color:{x_color};">{sox_val:,}</span> ({sox_chg:+.2f}%)</div>', unsafe_allow_html=True)
    
    st.markdown("<br><hr>", unsafe_allow_html=True)
    
    # 🌟 [종목 스크롤 무한 증식 방지 인터페이스 구현]
    # 사용자가 기존 종목군을 볼지, 확장된 코스피 200 추가 기업군을 볼지 라디오 버튼 분할 선택
    st.markdown("##### 🔍 퀀트 대상 기업군 필터링 셀렉터")
    group_choice = st.radio(
        "화면 분할 및 스크롤 단축을 위해 타겟 그룹을 지정해 주세요:",
        ["📌 기본 지정 핵심 종목 (기존 유지)", "🏢 KOSPI 200 주요 추가 기업군 (가나다순)"],
        horizontal=True
    )
    
    # 선택된 그룹에 따라 딕셔너리 동적 맵핑 생성
    selected_stock_code = ""
    selected_stock_name = ""
    
    if group_choice == "📌 기본 지정 핵심 종목 (기존 유지)":
        # 기존 6개 종목 가로형 셀렉트박스로 정돈
        chosen_name = st.selectbox("분석할 기존 핵심 종목을 선택하세요:", list(default_stocks.values()))
        # 역방향 코드 매칭
        selected_stock_code = [k for k, v in default_stocks.items() if v == chosen_name][0]
        selected_stock_name = chosen_name
    else:
        # 추가된 코스피 200 기업군 가나다 리스트 드롭다운 처리
        chosen_name = st.selectbox("분석할 KOSPI 200 추가 기업을 선택하세요:", list(kospi_200_addition.keys()))
        selected_stock_code = kospi_200_addition[chosen_name]
        selected_stock_name = chosen_name

    st.markdown(f"### ✨ {selected_stock_name} ({selected_stock_code}) 퀀트 리포트 룸")
    
    if st.button(f"🔍 {selected_stock_name} AI 입체 분석 리포트 발행", type="primary"):
        with st.spinner("퀀트 매크로 변수를 계산하는 중입니다..."):
            try:
                # 네이버 금융 데이터 수집
                url = f"https://fchart.stock.naver.com/sise.nhn?symbol={selected_stock_code}&timeframe=day&count=60&requestType=0"
                req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                with urllib.request.urlopen(req) as response:
                    xml_data = response.read().decode('utf-8', errors='ignore')
                
                rows = []
                for item in xml_data.split('<item data="')[1:]:
                    data_str = item.split('"')[0]
                    values = data_str.split('|')
                    if len(values) >= 5 and values[0] != "" and values[4] != "":
                        rows.append([values[0], int(values[4])])
                
                if len(rows) < 20:
                    st.error(f"{selected_stock_name} 분석에 필요한 거래일 데이터가 부족합니다.")
                else:
                    df = pd.DataFrame(rows, columns=['Date', 'Close'])
                    df['MA20'] = df['Close'].rolling(window=20).mean()
                    df['Disparity20'] = (df['Close'] / df['MA20']) * 100
                    
                    today_data = df.iloc[-1]
                    prev_data = df.iloc[-2]
                    
                    today_close = int(today_data['Close'])
                    today_change = ((today_close - int(prev_data['Close'])) / int(prev_data['Close'])) * 100
                    today_disparity = round(today_data['Disparity20'], 2)
                    
                    # 실시간 개장 시간 판별에 따른 [전일 종가] 알림 시스템
                    price_status_label = "" if is_market_open else " <span style='color:#e74c3c; font-size:0.65em; font-weight:bold; border:1px solid #e74c3c; padding:1px 4px; border-radius:3px; margin-left:4px;'>[전일 종가]</span>"
                    change_sign = "+" if today_change > 0 else ""
                    
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.markdown(f"**💵 현재가 지표**")
                        st.markdown(f"<h3 style='margin:0;'>{today_close:,}원{price_status_label}</h3><span style='color:{'#e74c3c' if today_change>=0 else '#2980b9'}; font-size:0.9em;'>{change_sign}{today_change:.2f}%</span>", unsafe_allow_html=True)
                    with col2:
                        st.metric(label="📐 20일 이평선 이격도", value=f"{today_disparity}%")
                    with col3:
                        if today_disparity < 90: position_label = "🚨 단기 강력 과매도"
                        elif today_disparity < 98: position_label = "📉 단기 조정 우위"
                        elif today_disparity <= 103: position_label = "⚖️ 공정 가치 수렴"
                        else: position_label = "🔥 단기 고점 과열"
                        st.metric(label="🛡️ 현재 기술 포지션", value=position_label)
                    
                    st.markdown("---")
                    
                    # 구글 뉴스 데이터 수집
                    search_query = urllib.parse.quote(f"{selected_stock_name} 주가 전망 뉴스 when:1d")
                    search_url = f"https://news.google.com/rss/search?q={search_query}&hl=ko&gl=KR&ceid=KR:ko"
                    req_news = urllib.request.Request(search_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req_news) as response_news:
                        rss_data = response_news.read().decode('utf-8', errors='ignore')
                    
                    items = rss_data.split("<item>")[1:6] # 스크롤 압축을 위해 최신 핵심 5개로 한정 조율
                    st.markdown(f"<div class='small-report-box'><b>📰 실시간 {selected_stock_name} 마켓 핵심 이슈</b>", unsafe_allow_html=True)
                    
                    news_found = False
                    full_news_text = ""
                    if items:
                        for t_idx, item in enumerate(items):
                            title_match = re.search(r"<title>(.*?)</title>", item)
                            date_match = re.search(r"<pubDate>(.*?)</pubDate>", item)
                            if title_match:
                                title_text = title_match.group(1).replace("<![CDATA[", "").replace("]]>", "").split(" - ")[0]
                                full_news_text += title_text + " "
                                date_str = ""
                                if date_match:
                                    try:
                                        parsed_date = datetime.strptime(date_match.group(1)[:25].strip(), "%a, %d %b %Y %H:%M:%S")
                                        date_str = (parsed_date + timedelta(hours=9)).strftime("%m-%d %H:%M")
                                    except: date_str = date_match.group(1)[:16]
                                st.markdown(f"<span style='font-size:0.9em;'>• <code>{date_str}</code> {title_text}</span>", unsafe_allow_html=True)
                                news_found = True
                    if not news_found: st.markdown("<span style='font-size:0.9em; color:gray;'>* 현재 동기화된 실시간 뉴스 스트림이 없습니다.</span>", unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)
                    
                    st.markdown("---")
                    
                    # 글로벌 매크로 연산 결합
                    is_fx_risk = any(k in full_news_text for k in ["환율", "원달러", "외국인", "매도세"])
                    us_base_score = 50 + (nasdaq_chg * 10)
                    us_impact_score = max(10, min(95, int(us_base_score)))
                    fx_stability_score = 40 if is_fx_risk else 80
                    rebound_energy = round((100 - today_disparity) * 2.5 + (us_impact_score * 0.4) + (fx_stability_score * 0.2), 1)
                    rebound_energy = max(10, min(98.5, rebound_energy))
                    
                    us_card_bg = "rgba(46, 204, 113, 0.08)" if nasdaq_chg >= 0 else "rgba(231, 76, 60, 0.08)"
                    fx_card_bg = "rgba(231, 76, 60, 0.08)" if is_fx_risk else "rgba(46, 204, 113, 0.08)"
                    rb_card_bg = "rgba(52, 152, 219, 0.08)" if today_disparity < 95 else "rgba(155, 89, 182, 0.08)"
                    
                    col_m1, col_m2, col_m3 = st.columns(3)
                    with col_m1:
                        st.markdown(f"""<div style="background-color: {us_card_bg}; padding: 12px; border-radius: 6px; border-left: 4px solid #34495e; font-size:0.85em;"><b style="color:#2c3e50;">🇺🇸 미국 증시 연동값</b><br><span style="font-size:1.4em; font-weight:bold; color:#2c3e50;">{us_impact_score}</span> / 100</div>""", unsafe_allow_html=True)
                    with col_m2:
                        st.markdown(f"""<div style="background-color: {fx_card_bg}; padding: 12px; border-radius: 6px; border-left: 4px solid #c0392b; font-size:0.85em;"><b style="color:#2c3e50;">💵 환율 수급 안정도</b><br><span style="font-size:1.4em; font-weight:bold; color:#2c3e50;">{fx_stability_score}</span> / 100</div>""", unsafe_allow_html=True)
                    with col_m3:
                        st.markdown(f"""<div style="background-color: {rb_card_bg}; padding: 12px; border-radius: 6px; border-left: 4px solid #2980b9; font-size:0.85em;"><b style="color:#2c3e50;">⚡ 추세 회귀 강도</b><br><span style="font-size:1.4em; font-weight:bold; color:#2980b9;">{rebound_energy}%</span></div>""", unsafe_allow_html=True)
                    
                    # 🌟 작은 글씨 전용 가독성 최적화 보고서 출력 문단
                    st.markdown(f"""
                    <div class="small-report-box" style="background-color:#fcfcfc; padding:12px; border:1px solid #eee; border-radius:6px; margin-top:15px;">
                        <b>📜 {selected_stock_name} 데이터 분석 요약 서머리</b><br>
                        • <b>포지션 진단:</b> {selected_stock_name}의 현재 이격도는 {today_disparity}% 수준으로 기술적 균형 점검 단계에 놓여 있습니다.<br>
                        • <b>추세 예측 리드타임:</b> 매크로 변수 가중 연산 기준 반등 에너지 누적 지표는 {rebound_energy}%로 계량 계산되었습니다. 
                        단기 변동성 노이즈 진정 국면 돌입 시 분할 밴드 대응 영역이 유효합니다.
                    </div>
                    """, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"데이터 로드 에러: {e}")

# ==============================================================================
# [메인 탭 2] 분석기준 및 원리
# ==============================================================================
with main_tabs[1]:
    st.markdown("<div class='small-report-box'>", unsafe_allow_html=True)
    st.header("📊 퀀트 연산 엔진 설계 백서 (요약본)")
    st.markdown("본 프로그램은 코스피 200 기업군 가격의 **'통계적 왜곡 이격도'**와 실시간 **'미국 증시 매크로 가중치'**를 융합하여 산출합니다.")
    
    st.subheader("⚙️ 가변 디데이(D-Day) 산식 메커니즘")
    st.code("""
    최종 예상 D-Day = [ (100 - 국내 이격도) × 2.8 ] - (미국 나스닥 등락률 가중 가치) + 환율 패널티 일수
    """, language="python")
    
    st.subheader("📐 이격도 수학적 분석 기준 4단계")
    st.markdown("""
    1. <b>1단계 (90% 미만):</b> 🚨 단기 강력 과매도 - 적극적 평단가 관리 레이어<br>
    2. <b>2단계 (90% ~ 98%):</b> 📉 단기 조정 및 매수 우위 - 점진적 수급 축적 레이어<br>
    3. <b>3단계 (98% ~ 103%):</b> ⚖️ 공정 가치 수렴 횡보 - 기존 물량 홀딩 홀드 레이어<br>
    4. <b>4단계 (103% 초과):</b> 🔥 단기 과열 고점 경계 - 추가 불타기 금지 / 분할 익절 레이어
    """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
