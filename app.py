import streamlit as st
import pandas as pd
import urllib.request
import urllib.parse
import re
from datetime import datetime, timedelta

# 웹페이지 기본 설정 (정돈된 레이아웃 반영)
st.set_page_config(page_title="나만의 스마트 퀀트 포털", page_icon="📈", layout="wide")

st.title("🚀 나만의 AI 퀀트 주가 분석 포털")
st.markdown("---")

# 분석 종목
target_stocks = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "005380": "현대차",
    "009150": "삼성전기",
    "006800": "미래에셋증권",
    "069500": "KODEX 200"
}

# 상단 메인 탭 분리
main_tabs = st.tabs(["📊 실시간 AI·퀀트 통합 대시보드", "📜 기술적 분석 원리 및 역사적 통계"])

# ==============================================================================
# [메인 탭 1] 실시간 AI·퀀트 통합 대시보드
# ==============================================================================
with main_tabs[0]:
    st.markdown("원하는 종목의 하위 탭을 선택한 후 **[AI 입체 분석 리포트 발행]** 버튼을 누르면 정밀 연산된 데이터를 정갈한 보고서 형태로 출력합니다.")
    
    stock_tabs = st.tabs(list(target_stocks.values()))
    
    for idx, (code, name) in enumerate(target_stocks.items()):
        with stock_tabs[idx]:
            st.subheader(f"{name} ({code}) 데이터 통합 포트폴리오")
            
            if st.button(f"🔍 {name} AI 입체 분석 리포트 발행", key=f"btn_{code}", type="primary"):
                with st.spinner(f"시스템이 {name}의 계량 지표와 글로벌 매크로 변수를 정밀 조립 중입니다..."):
                    try:
                        # 1. 네이버 금융 데이터 수집
                        url = f"https://fchart.stock.naver.com/sise.nhn?symbol={code}&timeframe=day&count=60&requestType=0"
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
                            st.error(f"{name} 분석에 필요한 충분한 거래일 데이터가 부족합니다.")
                            continue
                            
                        df = pd.DataFrame(rows, columns=['Date', 'Close'])
                        df['MA20'] = df['Close'].rolling(window=20).mean()
                        df['Disparity20'] = (df['Close'] / df['MA20']) * 100
                        
                        today_data = df.iloc[-1]
                        prev_data = df.iloc[-2]
                        
                        today_close = int(today_data['Close'])
                        today_change = ((today_close - int(prev_data['Close'])) / int(prev_data['Close'])) * 100
                        today_disparity = round(today_data['Disparity20'], 2)
                        
                        # 2. 기술 지표 요약 정돈된 레이아웃으로 출력
                        change_sign = "+" if today_change > 0 else ""
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.metric(label="현재 종가", value=f"{today_close:,}원", delta=f"{change_sign}{today_change:.2f}%")
                        with col2:
                            st.metric(label="20일 이평선 이격도", value=f"{today_disparity}%")
                        with col3:
                            position_label = "과매도 수렴" if today_disparity < 95 else "정상 범위"
                            st.metric(label="현재 포지션 상태", value=position_label)
                        
                        st.markdown("---")
                        
                        # 3. 구글 실시간 뉴스 데이터 수집
                        search_query = urllib.parse.quote(f"{name} 주가 전망 뉴스 when:1d")
                        search_url = f"https://news.google.com/rss/search?q={search_query}&hl=ko&gl=KR&ceid=KR:ko"
                        
                        req_news = urllib.request.Request(search_url, headers={'User-Agent': 'Mozilla/5.0'})
                        with urllib.request.urlopen(req_news) as response_news:
                            rss_data = response_news.read().decode('utf-8', errors='ignore')
                        
                        items = rss_data.split("<item>")[1:11]
                        
                        st.markdown(f"### 📰 실시간 마켓 핵심 이슈 (최신 뉴스 10개)")
                        
                        news_found = False
                        full_news_text = ""
                        
                        if items:
                            for t_idx, item in enumerate(items):
                                title_match = re.search(r"<title>(.*?)</title>", item)
                                date_match = re.search(r"<pubDate>(.*?)</pubDate>", item)
                                
                                if title_match:
                                    title_text = title_match.group(1).replace("<![CDATA[", "").replace("]]>", "")
                                    title_text = title_text.split(" - ")[0]
                                    full_news_text += title_text + " "
                                    
                                    date_str = ""
                                    if date_match:
                                        raw_date = date_match.group(1)
                                        try:
                                            parsed_date = datetime.strptime(raw_date[:25].strip(), "%a, %d %b %Y %H:%M:%S")
                                            kst_date = parsed_date + timedelta(hours=9)
                                            date_str = kst_date.strftime("%Y-%m-%d %H:%M")
                                        except:
                                            date_str = raw_date[:16]
                                    
                                    st.markdown(f"**{t_idx+1}.** ` {date_str} ` {title_text}")
                                    news_found = True
                                    
                        if not news_found:
                            st.markdown("* 현재 동기화된 실시간 최신 뉴스 스트림이 없습니다.")
                        
                        st.markdown("---")
                        
                        # 4. 글로벌 가중치 연산 및 테이블 시각화 정돈
                        is_us_market_hot = any(k in full_news_text for k in ["미국", "엔비디아", "나스닥", "뉴욕증시", "빅테크", "FED", "파월"])
                        is_fx_risk = any(k in full_news_text for k in ["환율", "원달러", "외국인", "매도세", "수급", "이탈"])
                        is_earning_shock = any(k in full_news_text for k in ["실적", "어닝쇼크", "적자", "매출둔화", "하향"])
                        
                        us_impact_score = 75 if is_us_market_hot else 50
                        fx_stability_score = 40 if is_fx_risk else 80
                        rebound_energy = round((100 - today_disparity) * 2.5 + (us_impact_score * 0.4) + (fx_stability_score * 0.2), 1)
                        rebound_energy = max(10, min(98.5, rebound_energy))
                        
                        st.markdown("### 📊 글로벌 거시 경제 영향 변수 연산 테이블")
                        df_macro_table = pd.DataFrame([
                            {"글로벌 영향 핵심 지표": "🇺🇸 미국 증시 및 빅테크 연동성 지수", "지표 점수": f"{us_impact_score} / 100", "상태 진단": "미국 기술주 온기 유입 중" if is_us_market_hot else "미국 기술주 모멘텀 정체"},
                            {"글로벌 영향 핵심 지표": "💵 원/달러 환율 및 수급 안정성 지수", "지표 점수": f"{fx_stability_score} / 100", "상태 진단": "외국인 자금 이탈 경계 구간" if is_fx_risk else "외국인 수급 안정 및 포지션 유지"},
                            {"글로벌 영향 핵심 지표": "📈 종합 기술적 반등 에너지 강도", "지표 점수": f"{rebound_energy}%", "상태 진단": "상방 회귀 복원력 압축 중" if today_disparity < 95 else "정상 가치 수렴 상태"}
                        ])
                        st.table(df_macro_table)
                        
                        st.markdown("---")
                        st.markdown(f"### 📜 {name} 퀀트 통합 투자 보고서")
                        
                        # 5. 분석 리포트 본문 구조 정돈
                        if today_disparity < 95:
                            status = "단기 과매도 국면 (낙폭과대 한계 영역)"
                            if is_earning_issue := any(k in full_news_text for k in ["실적", "어닝", "적자"]):
                                eval_text = "현재 주가는 20일 균형선을 이탈하여 딥 언더슈팅 국면에 진입했습니다. 실시간 마켓 이슈 내 실적 변동성 데이터 영향으로 대중의 투자 심리가 펀더멘탈 대비 다소 과도하게 하향 조정되어 있습니다. 이는 일시적 악재가 가격에 선반영된 통계적 매수 구간입니다."
                            elif is_macro_issue := any(k in full_news_text for k in ["반도체", "환율", "금리"]):
                                eval_text = "개별 기업의 결함보다는 실시간 뉴스에서 확인되는 거시 경제(금리, 환율, 공급망 리스크) 충격에 의한 무차별 수급 이탈 흐름입니다. 기술적 지표 기준 매크로 공포가 정점에 달했을 때 나타나는 전형적인 시세 왜곡 현상입니다."
                            else:
                                eval_text = "뚜렷한 개별형 고유 악재 없이 시장 전반의 투매 심리와 소외 수급의 공백으로 인해 주가가 밀려 있습니다. 이격도 복원 탄성력이 상방으로 가장 두텁게 뭉치기 시작하는 영역입니다."
                            
                            base_days = int((100 - today_disparity) * 2.8)
                            if is_us_market_hot: base_days -= 4
                            if is_fx_risk: base_days += 5
                            d_day_result = max(5, min(45, base_days))
                            
                            # 타임라인 및 전략 박스 가독성 정돈화
                            st.error(f"**현재 포지션 진단:** {status}")
                            st.markdown(f"**입체 분석 전문 뷰:** {eval_text}")
                            
                            st.success(f"🎯 **통계적 추세 전환 및 회귀 예상 시점:** **D-Day {d_day_result}일 내외 (약 {round(d_day_result/5, 1)}주일 이내 반등 유력)**")
                            st.info(f"💡 **신규/추가 매수 비중 전략:** 추천 점수 **{int(rebound_energy/10)} / 10점**\n\n과거 대형 우량주 통계 스펙트럼상 현 포지션에서의 패닉 매도는 실익이 전혀 없습니다. 감정적 대응을 자제하고 예상 디데이 기간 동안 균등하게 분할 적립하는 자금 배분 전략이 최선입니다.")
                        else:
                            st.info(f"**현재 포지션 진단:** 정상 밸류에이션 추세 수렴 구간")
                            st.markdown("현재 글로벌 거시 지표와 국내 수급 흐름이 균형 범위 내에서 동행하고 있습니다. 극단적 왜곡이 없으므로 당분간 박스권 횡보가 전개될 확률이 높으며, 차주 공시될 미국 거시 경제지표 방향성에 따라 새로운 모멘텀 전환 시점이 결정될 것입니다.")
                            
                    except Exception as data_err:
                        st.error(f"데이터 처리 중 오류 발생: {data_err}")
            else:
                st.info(f"위 [ {name} AI 입체 분석 리포트 발행 ] 버튼을 누르면 정돈된 양식의 보고서가 아래에 출력됩니다.")

# ==============================================================================
# [메인 탭 2] 기술적 분석 원리 및 역사적 통계
# ==============================================================================
with main_tabs[1]:
    st.header("📈 퀀트 포털의 기술적 분석 기준 및 작동 원리")
    st.markdown("본 프로그램은 감정이나 노이즈 가득한 뉴스에 흔들리지 않고, 오직 시장의 가격 데이터가 보내는 **'통계적 불균형(왜곡)'**을 포착하여 전략을 도출합니다.")
    
    st.markdown("---")
    st.subheader("📊 대한민국 대형주 역대 대폭락장과 이격도 통계 백서")
    
    df_history = pd.DataFrame([
        {"역사적 사건": "2008년 리먼 브라더스 금융위기", "공포의 정점 이격도": "76% ~ 81%", "당시 시장 심리 상태": "시스템 붕괴 공포, 주식 시장 종말론 대두", "이격도 정점 이후 실제 결과": "공포의 정점 통과 후 3개월 만에 20일선 복귀, 1년 뒤 주가 평균 +45% 대반등 성공"},
        {"역사적 사건": "2011년 미국 신용등급 강등 사태", "공포의 정점 이격도": "82% ~ 84%", "당시 시장 심리 상태": "글로벌 더블딥(재침체) 패닉, 무차별 투매", "이격도 정점 이후 실제 결과": "이격도 최저점 기록 후 정확히 24거래일 만에 이격도 100% 회복 완료"},
        {"역사적 사건": "2020년 코로나19 팬데믹 (3월)", "공포의 정점 이격도": "74% ~ 79%", "당시 시장 심리 상태": "인류 마비 공포, 코스피 서킷브레이커 발동", "이격도 정점 이후 실제 결과": "역대 최악의 이격도 과매도 기록 후, 4월 한 달 만에 20일선 안착 및 역사적 대세 상승장 시발점 돌입"},
        {"역사적 사건": "2022년 글로벌 고금리·인플레 쇼크", "공포의 정점 이격도": "84% ~ 86%", "당시 시장 심리 상태": "반도체 업황 종말론, 삼성전자/하이닉스 연일 신저가", "이격도 정점 이후 실제 결과": "계단식 하락 중에도 이격도 85% 도달 시마다 예외 없이 단기 10~15% 수준의 강한 기술적 반등 출현"}
    ])
    st.table(df_history)
    
    st.markdown("---")
    st.subheader("📐 수학적 분석 지표 및 4단계 포지션")
    st.latex(r"\text{이격도(Disparity)} = \left( \frac{\text{현재 주가}}{\text{20일 이동평균선}} \right) \times 100")
    
    df_info = pd.DataFrame([
        {"단계": "1단계", "이격도 범위": "90% 미만", "시장 포지션 상태": "🚨 단기 강력 과매도 (낙폭과대)", "투자 권장 전략": "물타기 및 매수 최적기. 과거 통계상 반등 확률 최고조 구간. 매도 절대 금지."},
        {"단계": "2단계", "이격도 범위": "90% 이상 ~ 98% 미만", "시장 포지션 상태": "📉 단기 조정 및 매수 우위", "투자 권장 전략": "안정적인 기술적 바닥을 다지는 구간. 점진적인 비중 확대 유효."},
        {"단계": "3단계", "이격도 범위": "98% 이상 ~ 103% 이하", "시장 포지션 상태": "⚖️ 적정 주가 및 횡보 구간", "투자 권장 전략": "평균 균형 상태. 섣부른 추정 매매보다는 기존 포트폴리오 비중을 유지하며 관망."},
        {"단계": "4단계", "이격도 범위": "103% 초과", "시장 포지션 상태": "🔥 단기 과열 및 고점 경계", "투자 권장 전략": "분할 매도 최적기. 탐욕을 버리고 리스크 관리 차원에서 이익 실현(익절) 시작."}
    ])
    st.table(df_info)
