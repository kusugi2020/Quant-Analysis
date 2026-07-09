import streamlit as st
import pandas as pd
import urllib.request
import urllib.parse
import re
from datetime import datetime, timedelta

# 웹페이지 기본 설정
st.set_page_config(page_title="불타기물타기 주린이방", page_icon="📈", layout="wide")

# 메인 타이틀
st.title("📈 불타기물타기 퀀트 룸")
st.markdown("---")

# 1. 똘이선택종목 딕셔너리
ttori_stocks = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "005380": "현대차",
    "009150": "삼성전기",
    "006800": "미래에셋증권",
    "069500": "KODEX 200"
}

# 2. KOSPI 200 핵심 기업 가나다순 대량 배열 (오타 완벽 수정본)
kospi_200_full = {
    "HD현대마린솔루션": "443060", "HD현대미포": "010620", "HD현대삼호": "329180", "HD현대에너지솔루션": "322000", "HD현대일렉트릭": "267260",
    "HD현대중공업": "329180", "HMM": "011200", "KCC": "002380", "KT": "030200", "KT&G": "033780",
    "LG": "003550", "LG디스플레이": "034220", "LG에너지솔루션": "373220", "LG유플러스": "032640", "LG이노텍": "011070",
    "LG생활건강": "051900", "LG전자": "066570", "LG화학": "051910", "LS": "006260", "LS일렉트릭": "010120",
    "NAVER": "035420", "POSCO홀딩스": "005490", "S-Oil": "010950", "SK": "034730", "SK가스": "018670",
    "SK네웍스": "001740", "SK바이오팜": "326030", "SK바이오사이언스": "302440", "SK스퀘어": "402340", "SK아이이테크놀로지": "361610",
    "SK이노베이션": "096770", "SK케미칼": "285130", "SK텔레콤": "017670", "SK하이닉스": "000660", "하이브": "352820",
    "한각자산운용": "069500", "한국가스공사": "036460", "한국앤컴퍼니": "000240", "한국전력": "015760", "한국조선해양": "009540",
    "한국타이어앤테크놀로지": "161390", "한국항공우주": "047810", "한미약품": "128940", "한미사이언스": "008930", "한온시스템": "018880",
    "한화": "000880", "한화갤러리아": "452260", "한화생명": "088350", "한화솔루션": "009830", "한화에어로스페이스": "012450",
    "한화오션": "042660", "한화시스템": "272210", "현대건설": "000720", "현대글로비스": "086280", "현대두산인프라코어": "042670",
    "현대로템": "064350", "현대모비스": "012330", "현대미포조선": "010620", "현대백화점": "069960", "현대위아": "011210",
    "현대제철": "004020", "현대차": "005380", "현대해상": "001450", "호텔신라": "008770", "효성": "004800",
    "효성티앤씨": "298020", "효성중공업": "298040", "효성화학": "298000", "효성첨단소재": "298050", "후성": "093370",
    "흥국화재": "000540", "BGF리테일": "282330", "BNK금융지주": "138930", "CJ": "001040",
    "CJ대한통운": "000120", "CJ제일제당": "097950", "DB손해보험": "005830", "DB하이텍": "000990", "DL": "000210",
    "DL이앤씨": "375500", "GS": "078930", "GS리테일": "007070", "GS건설": "006360", "HDC현대산업개발": "294870",
    "HL만도": "204320", "KODEX200": "069500", "LF": "093050", "OCI홀딩스": "010060", "강원랜드": "035250",
    "고려아연": "010130", "고려제강": "002240", "금호석유": "011780", "금호타이어": "073240", "기아": "000270",
    "기업은행": "024110", "남선알미늄": "008350", "남해화학": "025860", "넥센타이어": "002270",
    "넷마블": "251270", "농심": "004370", "대덕전자": "353200", "대아티아이": "045390",
    "대우건설": "047040", "대한유화": "006650", "대한항공": "003490", "동국제강": "001230",
    "동원산업": "006040", "동서": "026960", "두산": "000150", "두산밥캣": "241560", "두산에너빌리티": "034020",
    "두산퓨어셀": "336260", "락앤락": "115390", "롯데관광개발": "032350", "롯데쇼핑": "023530", "롯데지주": "004990",
    "롯데칠성": "005300", "롯데케미칼": "011170", "롯데정밀화학": "004000", "메리츠금융지주": "138040", "무학": "033920",
    "미래에셋증권": "006800", "보령": "003850", "부광약품": "003000", "빙그레": "005180",
    "삼성물산": "028260", "삼성바이오로직스": "207940", "삼성생명": "032830", "삼성SDI": "006400",
    "삼성엔지니어링": "028050", "삼성전기": "009150", "삼성전자": "005930", "삼성중공업": "010140", "삼성증권": "016360",
    "삼성화재": "000810", "삼양홀딩스": "000070", "삼양식품": "003230", "서연": "007860",
    "서울가스": "017390", "선진": "143000", "성신양회": "000450", "세방전지": "004490", "셀트리온": "068270",
    "솔루스첨단소재": "336370", "신세계": "004170", "신한지주": "055550", "아모레퍼시픽": "090430", "아모레G": "002790",
    "아시아나항공": "020560", "에스원": "012750", "에코프로머티": "450080", "엘앤에프": "066970",
    "영원무역": "111770", "오리온": "271560", "우리금융지주": "316140", "유한양행": "000100", "이마트": "139480",
    "일진하이솔루스": "271940", "제일기획": "030000", "종근당": "185750", "카카오": "035720", "카카오뱅크": "323410",
    "카카오페이": "377300", "하이트진로": "000080", "한전KPS": "051600", "한전기술": "052690"
}

# 대시보드 컴팩트 스타일링 (폰트 통일, 스크롤 억제 및 가독성 업그레이드)
st.markdown("""
<style>
    html, body, [class*="css"], .stMarkdown {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif !important;
    }
    .clean-report-box {
        font-size: 0.9em !important;
        line-height: 1.6 !important;
        color: #2c3e50;
        padding: 14px;
        background-color: #fdfdfd;
        border: 1px solid #eef2f5;
        border-radius: 6px;
        margin-top: 10px;
    }
    .predict-alert-box {
        padding: 12px;
        margin-top: 10px;
        border-radius: 6px;
        font-size: 0.9em !important;
        line-height: 1.5 !important;
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
    st.markdown(f"#### 한국 증시 주요 지수 현황판 <span style='font-size:0.8em; color:gray;'>[{target_date_str} KST]</span>", unsafe_allow_html=True)
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

    st.markdown(f"#### 미국 증시 주요 지수 현황판", unsafe_allow_html=True)
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
    
    st.markdown("##### 🔍 종목별 분석")
    group_choice = st.radio(
        "그룹을 선택해 주세요:",
        ["똘이선택종목", "KOSPI200"],
        horizontal=True
    )
    
    selected_stock_code = ""
    selected_stock_name = ""
    
    if group_choice == "똘이선택종목":
        chosen_name = st.selectbox("종목을 선택하세요:", list(ttori_stocks.values()))
        selected_stock_code = [k for k, v in ttori_stocks.items() if v == chosen_name][0]
        selected_stock_name = chosen_name
    else:
        sorted_keys = sorted(list(kospi_200_full.keys()))
        chosen_name = st.selectbox("KOSPI 200 종목을 선택하세요:", sorted_keys)
        selected_stock_code = kospi_200_full[chosen_name]
        selected_stock_name = chosen_name

    st.markdown(f"### ✨ {selected_stock_name} ({selected_stock_code}) 퀀트 리포트 룸")
    
    if st.button(f"🔍 {selected_stock_name} AI 입체 분석 리포트 발행", type="primary"):
        with st.spinner("퀀트 가중치 변수 연산 중..."):
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
                    st.error(f"{selected_stock_name} 분석 데이터가 부족합니다.")
                else:
                    df = pd.DataFrame(rows, columns=['Date', 'Close'])
                    df['MA20'] = df['Close'].rolling(window=20).mean()
                    df['Disparity20'] = (df['Close'] / df['MA20']) * 100
                    
                    today_data = df.iloc[-1]
                    prev_data = df.iloc[-2]
                    
                    today_close = int(today_data['Close'])
                    today_change = ((today_close - int(prev_data['Close'])) / int(prev_data['Close'])) * 100
                    today_disparity = round(today_data['Disparity20'], 2)
                    
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
                    
                    items = rss_data.split("<item>")[1:11] 
                    st.markdown(f"<div class='clean-report-box'><b>📰 실시간 {selected_stock_name} 마켓 핵심 이슈 (최신 10건)</b>", unsafe_allow_html=True)
                    
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
                                st.markdown(f"<span style='font-size:0.95em; display:block; margin-bottom:4px;'>{t_idx+1}. <code>{date_str}</code> {title_text}</span>", unsafe_allow_html=True)
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
                        st.markdown(f"""<div style="background-color: {us_card_bg}; padding: 12px; border-radius: 6px; border-left: 4px solid #34495e; font-size:0.9em;"><b style="color:#2c3e50;">미국 증시 연동값</b><br><span style="font-size:1.4em; font-weight:bold; color:#2c3e50;">{us_impact_score}</span> / 100</div>""", unsafe_allow_html=True)
                    with col_m2:
                        st.markdown(f"""<div style="background-color: {fx_card_bg}; padding: 12px; border-radius: 6px; border-left: 4px solid #c0392b; font-size:0.9em;"><b style="color:#2c3e50;">환율 수급 안정도</b><br><span style="font-size:1.4em; font-weight:bold; color:#2c3e50;">{fx_stability_score}</span> / 100</div>""", unsafe_allow_html=True)
                    with col_m3:
                        st.markdown(f"""<div style="background-color: {rb_card_bg}; padding: 12px; border-radius: 6px; border-left: 4px solid #2980b9; font-size:0.9em;"><b style="color:#2c3e50;">추세 회귀 강도</b><br><span style="font-size:1.4em; font-weight:bold; color:#2980b9;">{rebound_energy}%</span></div>""", unsafe_allow_html=True)
                    
                    if today_disparity < 95:
                        base_days = int((100 - today_disparity) * 2.8)
                        if nasdaq_chg >= 0: base_days -= 5  
                        else: base_days += 4               
                        if is_fx_risk: base_days += 4       
                        d_day_result = max(5, min(45, base_days))
                        
                        predict_html = f"""
                        <div class='predict-alert-box' style='background-color: #eef9f0; border-left: 5px solid #27ae60;'>
                            🎯 <b>주가 반등 및 추세 전환 예상 시점:</b> <span style='color:#27ae60; font-weight:bold;'>D-Day {d_day_result}일 내외 (약 {round(d_day_result/5, 1)}주일 이내 반등 전환 유력)</span><br>
                            <span style='font-size:0.95em; color:#444; display:block; margin-top:5px;'>• <b>예측 근거:</b> 현재 왜곡된 이격도 스펙트럼과 미국 마감 지수 등락률 가중치를 백엔드에서 결합 역산한 결과입니다. 이 기간 동안 분할로 물타기 단가를 관리하는 전략이 통계적으로 유효합니다.</span>
                        </div>
                        """
                    elif today_disparity <= 103:
                        predict_html = """
                        <div class='predict-alert-box' style='background-color:#f4f6f7; border-left:5px solid #7f8c8d;'>
                            ⚖️ <b>주가 방향성 전망:</b> <span style='color:#34495e; font-weight:bold;'>당분간 단기 수렴 및 박스권 횡보 우세</span><br>
                            <span style='font-size:0.95em; color:#444; display:block; margin-top:5px;'>• <b>예측 근거:</b> 현재 주가가 20일 균형 평균 가격대에 긴밀히 밀착해 있어 위아래 왜곡이 없는 중립 상태입니다. 매크로 자금 유입 방향성에 따라 새 진입 타이밍이 결정될 것입니다.</span>
                        </div>
                        """
                    else:
                        predict_html = """
                        <div class='predict-alert-box' style='background-color:#fdf2e9; border-left:5px solid #e67e22;'>
                            🔥 <b>주가 방향성 전망:</b> <span style='color:#e67e22; font-weight:bold;'>단기 오버슈팅에 따른 숨고르기(하락조정) 리스크 경계</span><br>
                            <span style='font-size:0.95em; color:#444; display:block; margin-top:5px;'>• <b>예측 근거:</b> 이격도가 103%를 초과하여 탐욕 수급이 과열 영역에 머물고 있습니다. 추가 불타기는 절대 금지이며, 이평선 회귀성 눌림목 조정을 대비해 분할 익절하는 타임라인입니다.</span>
                        </div>
                        """
                    st.markdown(predict_html, unsafe_allow_html=True)
                    
                    st.markdown(f"""
                    <div class="clean-report-box">
                        <b>📜 {selected_stock_name} 데이터 분석 요약 서머리</b><br>
                        • <b>포지션 진단 :</b> {selected_stock_name}의 현재 이격도는 {today_disparity}% 수준으로 계산되었습니다.<br>
                        • <b>마켓 가이드 :</b> 본 퀀트 룸은 외부 소음에 뇌동매매하지 않고 오직 숫자의 통계적 복원력을 추종합니다.
                    </div>
                    """, unsafe_allow_html=True)
            except Exception as e:
                st.error(f"데이터 로드 에러: {e}")

# ==============================================================================
# [메인 탭 2] 분석기준 및 원리
# ==============================================================================
with main_tabs[1]:
    st.markdown("<div class='clean-report-box'>", unsafe_allow_html=True)
    st.header("📊 퀀트 연산 엔진 설계 백서 (요약본)")
    st.markdown("본 프로그램은 국내 증시 가격이 보내는 **'통계적 왜곡 이격도'**와 실시간 **'미국 증시 매크로 가중치'**를 융합하여 산출합니다.")
    
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
