import streamlit as st
import pandas as pd
import urllib.request

st.set_page_config(page_title="AI 퀀트 투자 리포트", page_icon="📈", layout="wide")

st.title("🚀 JJM 퀀트지표 분석기(매수매도타이밍)")
st.markdown("원하는 종목의 탭을 선택한 후 [투자 분석 리포트 발행] 버튼을 누르면 알고리즘이 기술적 지표를 분석합니다. 네이버증권의 실시간 주가를 가져옵니다.")
st.markdown("---")

target_stocks = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "005380": "현대차",
    "069500": "KODEX 200",
    "005380": "현대차",
    "495850": "KODEX 코리아밸류업",
    "006800": "미래에셋증권"
}

tabs = st.tabs(list(target_stocks.values()))

for idx, (code, name) in enumerate(target_stocks.items()):
    with tabs[idx]:
        st.subheader(f"📊 {name} ({code}) 기술 지표 및 전략")
        
        if st.button(f"🔍 {name} 투자 분석 리포트 발행", key=f"btn_{code}", type="primary"):
            with st.spinner(f"{name} 데이터를 분석하는 중..."):
                try:
                    url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=60&requestType=0"
                    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req) as response:
                        xml_data = response.read().decode('utf-8', errors='ignore')
                    
                    rows = []
                    for item in xml_data.split('<item data="')[1:]:
                        data_str = item.split('"')[0]
                        values = data_str.split('|')
                        if len(values) >= 5:
                            rows.append([values[0], int(values[4])])
                    
                    if not rows:
                        st.error(f"{name} 데이터를 가져오지 못했습니다.")
                        continue
                        
                    df = pd.DataFrame(rows, columns=['Date', 'Close'])
                    df['MA20'] = df['Close'].rolling(window=20).mean()
                    df['Disparity20'] = (df['Close'] / df['MA20']) * 100
                    
                    today_data = df.iloc[-1]
                    prev_data = df.iloc[-2]
                    
                    today_close = int(today_data['Close'])
                    today_change = ((today_close - int(prev_data['Close'])) / int(prev_data['Close'])) * 100
                    today_disparity = round(today_data['Disparity20'], 2)
                    
                    change_sign = "+" if today_change > 0 else ""
                    st.markdown(f"""
                    > 📌 **{name} 실시간 기술 지표 요약**
                    > * **현재 종가:** `{today_close:,}원` ({change_sign}{today_change:.2f}%)
                    > * **20일 이동평균선 이격도:** `{today_disparity}%`
                    """)
                    
                    if today_disparity < 90:
                        status = "🚨 **단기 강력 과매도 (낙폭과대 구간)**"
                        buy_score = "⭐⭐⭐⭐⭐ (5 / 5)"
                        buy_reason = "20일 이동평균선 대비 주가가 과도하게 하락하여 기술적 반등 가능성이 매우 높은 매력적인 저가 매수 타이밍입니다. 분할 매수(물타기) 전략이 유효합니다."
                        sell_score = "⭐ (1 / 5)"
                        sell_reason = "현재 구간에서 패닉 셀(손절)을 감행하는 것은 실익이 적습니다. 단기 저점을 확인한 후 반등을 기다리는 전략을 권장합니다."
                    elif today_disparity < 98:
                        status = "📉 **단기 조정 및 매수 우위 구간**"
                        buy_score = "⭐⭐⭐⭐ (4 / 5)"
                        buy_reason = "주가가 이평선 아래에서 안정적인 지지선을 탐색 중입니다. 장기 보유 관점이라면 비중을 점진적으로 늘려가기 좋은 구간입니다."
                        sell_score = "⭐⭐ (2 / 5)"
                        sell_reason = "추가 하락 우려가 일부 남아있으나, 기 보유 물량을 급하게 매도할 이유가 없는 관망 구간입니다."
                    elif today_disparity <= 103:
                        status = "⚖️ **적정 주가 및 횡보 구간**"
                        buy_score = "⭐⭐⭐ (3 / 5)"
                        buy_reason = "현재 주가가 20일 평균선 근처에서 수렴하고 있습니다. 방향성이 모호하므로 공격적인 추가 매수보다는 기존 비중을 유지하는 것이 좋습니다."
                        sell_score = "⭐⭐⭐ (3 / 5)"
                        sell_reason = "포트폴리오 리밸런싱 차원에서의 소량 분할 매도는 가능하나, 뚜렷한 추세 전환 전까지는 보유가 유리합니다."
                    else:
                        status = "🔥 **단기 과열 및 고점 경계 구간**"
                        buy_score = "⭐ (1 / 5)"
                        buy_reason = "20일 이동평균선과의 이격이 벌어져 단기 고점 신호가 켜졌습니다. 지금 추격 매수(물타기)에 나서는 것은 리스크가 매우 큽니다."
                        sell_score = "⭐⭐⭐⭐⭐ (5 / 5)"
                        sell_reason = "단기 이익을 실현하기에 아주 좋은 타이밍입니다. 욕심을 버리고 리스크 관리 차원에서 분할 익절을 시작하는 것을 추천합니다."

                    st.markdown(f"""
                    ### 📜 {name} 정밀 퀀트 투자 보고서
                    
                    #### 1. 단기 위치 평가
                    * 현재 시장 포지션: {status}
                    * 기술적 분석: 현재 20일 이동평균선 대비 주가 위치가 {today_disparity}% 수준에 머물러 있어, 자산의 단기 추세 왜곡 현상을 나타내고 있습니다.
                    
                    #### 2. 추가 매수 (물타기) 추천 점수: {buy_score}
                    * **구체적인 이유:** {buy_reason}
                    
                    #### 3. 분할 매도 (익절/손절) 추천 점수: {sell_score}
                    * **구체적인 이유:** {sell_reason}
                    
                    #### 4. 변동성 장세 멘탈 조언
                    > 💡 *“투자의 본질은 확률 게임입니다. 공포와 탐욕에 흔들리지 않고 오직 차가운 데이터적 지표에 기반하여 나만의 분할 매매 원칙을 고수하는 자가 결국 승리합니다.”*
                    """)
                    
                except Exception as data_err:
                    st.error(f"데이터 처리 중 오류 발생: {data_err}")
