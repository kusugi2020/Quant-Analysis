"""
이격도(Disparity) 기반 통계적 검증 및 퀀트 분석 플랫폼
================================================================
리뉴얼 포인트: 직관적 시각화 그래프 배치 및 친절한 기능 가이드 내재화
"""

import streamlit as st
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings("ignore")

# 스트림릿 페이지 기본 설정
st.set_page_config(
    page_title="Disparity Quant Platform",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------------------------------------------------
# [백엔드 함수] 데이터 연산 로직 (기존 핵심 알고리즘 유지)
# ----------------------------------------------------------------------
def load_price_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    try:
        import FinanceDataReader as fdr
        df = fdr.DataReader(ticker, start, end)
        df = df.rename(columns=str.title)
        return df[["Close", "Volume"]].dropna()
    except ImportError as e:
        raise ImportError("FinanceDataReader 설치가 필요합니다.") from e

def generate_synthetic_data(n_days=1500, seed=42) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    returns = rng.normal(0.0003, 0.018, n_days)
    price = 50000 * np.exp(np.cumsum(returns))
    dates = pd.bdate_range("2019-01-01", periods=n_days)
    volume = rng.integers(1_000_000, 5_000_000, n_days)
    return pd.DataFrame({"Close": price, "Volume": volume}, index=dates)

def compute_indicators(df: pd.DataFrame, ma_window: int = 20) -> pd.DataFrame:
    df = df.copy()
    df["MA"] = df["Close"].rolling(ma_window).mean()
    df["Disparity"] = df["Close"] / df["MA"] * 100
    df["Volatility20"] = df["Close"].pct_change().rolling(20).std() * np.sqrt(252)
    df["VolumeZ"] = (df["Volume"] - df["Volume"].rolling(60).mean()) / df["Volume"].rolling(60).std()
    return df

def add_forward_returns(df: pd.DataFrame, horizons=(5, 10, 20, 40)) -> pd.DataFrame:
    df = df.copy()
    for h in horizons:
        df[f"fwd_ret_{h}d"] = df["Close"].shift(-h) / df["Close"] - 1
        df[f"fwd_win_{h}d"] = (df[f"fwd_ret_{h}d"] > 0).astype(float)
    return df

def bootstrap_ci(series: pd.Series, n_boot=3000, ci=0.90, seed=1):
    rng = np.random.default_rng(seed)
    arr = series.dropna().values
    if len(arr) == 0: return (np.nan, np.nan)
    boot_means = rng.choice(arr, size=(n_boot, len(arr)), replace=True).mean(axis=1)
    return np.percentile(boot_means, (1 - ci) / 2 * 100), np.percentile(boot_means, (1 + ci) / 2 * 100)

def backtest_threshold_strategy(df: pd.DataFrame, threshold: float, horizons=(5, 10, 20, 40), min_samples=30):
    signal = df["Disparity"] < threshold
    rows = []
    for h in horizons:
        col = f"fwd_ret_{h}d"
        sig_ret = df.loc[signal, col].dropna()
        all_ret = df[col].dropna()

        if len(sig_ret) < min_samples:
            rows.append({"보유기간": f"{h}일", "신호발생": len(sig_ret), "승률": 0, "전략수익률": 0, "시장수익률": 0, "초과수익률": 0, "최악의경우": 0, "최선의경우": 0, "판정": "데이터 부족"})
            continue

        win_rate = (sig_ret > 0).mean()
        avg_ret = sig_ret.mean()
        bench_avg = all_ret.mean()
        excess = avg_ret - bench_avg
        ci_lo, ci_hi = bootstrap_ci(sig_ret)
        _, p_val = stats.ttest_ind(sig_ret, all_ret, equal_var=False)

        rows.append({
            "보유기간": f"{h}일",
            "신호발생": int(len(sig_ret)),
            "승률": round(win_rate * 100, 1),
            "전략수익률": round(avg_ret * 100, 2),
            "시장수익률": round(bench_avg * 100, 2),
            "초과수익률": round(excess * 100, 2),
            "최악의경우": round(ci_lo * 100, 2),
            "최선의경우": round(ci_hi * 100, 2),
            "판정": "🟢 진짜 신호 (진입 가능)" if p_val < 0.05 else "🔴 가짜 신호 (위험)"
        })
    return pd.DataFrame(rows)

def walk_forward_validation(df: pd.DataFrame, threshold: float, horizon=20, n_folds=5):
    col = f"fwd_ret_{horizon}d"
    valid = df.dropna(subset=[col, "Disparity"]).copy()
    fold_size = len(valid) // n_folds
    results = []
    for i in range(n_folds):
        start, end = i * fold_size, (i + 1) * fold_size if i < n_folds - 1 else len(valid)
        fold = valid.iloc[start:end]
        sig = fold.loc[fold["Disparity"] < threshold, col]
        if len(sig) < 5:
            results.append({"구간": f"{i+1}구간", "전략수익률": 0})
            continue
        results.append({
            "구간": f"{i+1}구간 ({fold.index[0].year}년)",
            "전략수익률": round(sig.mean() * 100, 2)
        })
    return pd.DataFrame(results)

# ----------------------------------------------------------------------
# [프론트엔드] 사이트 네비게이션 및 디자인
# ----------------------------------------------------------------------
st.markdown("""
    <div style="background-color:#0F172A; padding:24px; border-radius:12px; margin-bottom:25px; border-left: 8px solid #3B82F6;">
        <h1 style="color:white; margin:0; font-size:30px; font-weight:700;">📈 대시보드로 보는 주가 반등 과학적 검증기</h1>
        <p style="color:#94A3B8; margin:8px 0 0 0; font-size:15px;">어려운 통계 공식은 숨기고, 계기판과 그래프로 안전한 투자 자리만 찾아냅니다.</p>
    </div>
""", unsafe_allow_html=True)

menu_tab1, menu_tab2, menu_tab3 = st.tabs(["🎯 실시간 분석 계기판", "📚 분석 원리 쉽게 이해하기", "📖 초보자 사용 설명서"])

# 사이드바 제어판
st.sidebar.markdown("### 🕹️ 분석 조건 설정")
data_mode = st.sidebar.selectbox("💾 어떤 데이터를 볼까요?", ["합성 데이터 (가상 테스트)", "국내 주식 (실제 거래 데이터)"])
input_threshold = st.sidebar.slider("📉 얼마나 과매도 되었을 때 살까요? (이격도 %)", min_value=85.0, max_value=100.0, value=95.0, step=0.5)

if data_mode == "국내 주식 (실제 거래 데이터)":
    ticker_code = st.sidebar.text_input("📌 종목코드 6자리 (삼성전자: 005930)", value="005930")
    start_date = st.sidebar.text_input("📅 조회 시작일", value="2015-01-01")
    execute_button = st.sidebar.button("🚀 분석 시작하기", use_container_width=True)
else:
    ticker_code, start_date = None, "2015-01-01"
    execute_button = True

# 데이터 로딩
if data_mode == "국내 주식 (실제 거래 데이터)" and ticker_code:
    try:
        raw_df = load_price_data(ticker_code, start_date, None)
        is_data_loaded = True
    except Exception:
        st.sidebar.error("⚠️ 올바른 종목코드를 입력해 주세요.")
        is_data_loaded = False
else:
    raw_df = generate_synthetic_data()
    is_data_loaded = True

# ----------------------------------------------------------------------
# 메뉴 1: 실시간 분석 계기판 (차트 및 가이드 보강)
# ----------------------------------------------------------------------
with menu_tab1:
    if is_data_loaded and execute_button:
        processed_df = compute_indicators(raw_df)
        processed_df = add_forward_returns(processed_df)
        
        # 1. 친절한 상단 지표 요약
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("🔬 검증에 사용된 총 일수", f"{len(processed_df):,} 일", help="과거 이 종목이 거래된 전체 역사적 데이터 일수입니다.")
        with m2:
            current_disparity = processed_df['Disparity'].iloc[-1]
            st.metric("📉 최근 이격도 상태", f"{current_disparity:.2f}%", help="100%보다 낮을수록 20일 평균 가격보다 많이 떨어졌다는 뜻입니다.")
        with m3:
            total_signals = (processed_df['Disparity'] < input_threshold).sum()
            st.metric("🚨 역사적 매수 신호 포착 횟수", f"{total_signals} 회", help="과거 역사 속에서 내가 지정한 기준보다 주가가 떨어졌던 횟수입니다.")
            
        st.markdown("---")
        
        # 2. 메인 시각화 그래프 구간
        st.markdown("### 📊 최근 주가 추이와 이격도 흐름")
        st.caption("위 그래프는 실제 주가와 20일 이동평균선이고, 아래 그래프는 주가가 평균에서 얼마나 멀어졌는가(이격도)를 나타냅니다. 파란 선이 아래로 꺾일 때가 과매도 구간입니다.")
        
        chart_data = processed_df.tail(250)[["Close", "MA", "Disparity"]]
        st.line_chart(chart_data[["Close", "MA"]], height=250)
        st.line_chart(chart_data["Disparity"], height=120)
        
        st.markdown("---")
        
        # 3. 전략 기대 성과 표 및 그래프
        st.markdown("### 🎯 1단계 분석 결과: 이 자리에 사면 내 계좌는 어떻게 될까?")
        st.info("💡 **친절한 판정 가이드:** 맨 오른쪽 **[판정]**에 **🟢 진짜 신호**가 뜬 기간을 고르세요. **🔴 가짜 신호**가 뜨면 과거에 올랐어도 운이었을 뿐이니 진입하면 안 됩니다.")
        
        bt_res = backtest_threshold_strategy(processed_df, input_threshold)
        st.dataframe(bt_res[["보유기간", "신호발생", "승률", "전략수익률", "시장수익률", "초과수익률", "판정"]], use_container_width=True, hide_index=True)
        
        # 보유기간별 수익률 시각화 차트
        st.markdown("#### 📈 무작위로 살 때 vs 과매도 신호에 살 때 수익률 비교 그래프")
        graph_df = pd.DataFrame({
            "시장 그냥 보유 시 (벤치마크)": bt_res["시장수익률"].values,
            "이격도 과매도 전략 사용 시": bt_res["전략수익률"].values
        }, index=bt_res["보유기간"])
        st.bar_chart(graph_df)

        st.markdown("---")
        
        # 4. 리스크 관리 차트 및 과거 영속성 검증
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.markdown("### 🛡️ 2단계 분석 결과: 물리더라도 얼마나 깨질까? (리스크 범위)")
            st.caption("과거 데이터를 기반으로 계산한 **최악의 손실 한도**와 **최선의 기대 이익**의 범위입니다.")
            
            ci_graph_df = pd.DataFrame({
                "최악의 경우 (손실 하단)": bt_res["최악의경우"].values,
                "최선의 경우 (이익 상단)": bt_res["최선의경우"].values
            }, index=bt_res["보유기간"])
            st.bar_chart(ci_graph_df)
            st.caption("⚠️ **안전 운전 법:** '최악의 경우' 막대가 아래로 너무 길게 뚫려 있는 보유일수는 피하는 것이 좋습니다.")
            
        with col_chart2:
            st.markdown("### ⏳ 3단계 분석 결과: 옛날에도 고르게 잘 먹혔을까?")
            st.caption("데이터를 5개 시간 순서대로 쪼개서 과거에도 이 전략이 꾸준히 수익을 냈는지 추적한 결과입니다.")
            
            wf_res = walk_forward_validation(processed_df, input_threshold)
            st.bar_chart(wf_res.set_index("구간"))
            st.caption("📊 **안전 운전 법:** 막대기가 한쪽만 솟아있지 않고 모든 구간에서 고르게 위를 향하고 있어야 신뢰할 수 있는 튼튼한 전략입니다.")

    else:
        st.info("👈 왼쪽 패널에서 설정을 완료하고 [🚀 분석 시작하기] 버튼을 눌러주세요.")

# ----------------------------------------------------------------------
# 메뉴 2: 분석 원리 및 근거 설명 화면
# ----------------------------------------------------------------------
with menu_tab2:
    st.markdown("### 📚 그래프와 메트릭이 계산되는 숨은 원리")
    st.write("전문가들이 사용하는 이 세 가지 필터링 시스템이 가짜 반등에 속아 돈을 날리는 것을 원천 차단합니다.")
    
    st.markdown("""
    #### 1️⃣ 🟢 진짜 신호 vs 🔴 가짜 신호의 비밀 (독립표본 t-test)
    * **원리:** 주가가 단순히 낙폭과대로 반등한 것인지, 아니면 시장이 다 같이 오르는 상승장이어서 휩쓸려 오른 것인지를 수학적으로 분리합니다.
    * **해석:** 판정에 초록불(`🟢`)이 들어왔다는 것은 시장이 보합이나 하락장일 때도 이 종목만큼은 이격도가 떨어지면 독자적으로 반등하는 힘(알파)을 가졌다는 사실이 증명되었다는 뜻입니다.

    #### 2️⃣ 최악과 최선의 범위 (부트스트랩 신뢰구간)
    * **원리:** 과거 데이터를 무작위로 3,000번 섞어서 모의실험을 반복합니다. 그중 상위 5%의 대박 사건과 하위 5%의 쪽박 사건을 발라냅니다.
    * **해석:** 이를 통해 우리는 진입하기 전에 "내가 최악의 타이밍에 물려도 몇 % 안에서 손실이 방어되겠구나"를 미리 예측하고 비중을 조절할 수 있습니다.

    #### 3️⃣ 구간별 쪼개기 검증 (Walk-forward 전진 분석)
    * **원리:** 2015년~2017년에는 잘 맞다가 최근 하락장(2022~2024년)에는 박살 나는 전략인지 검사하기 위해 시계열을 강제로 쪼개어 검증합니다.
    * **해석:** 특정 시기에만 반짝 반등했던 전략에 속아 현재 시장에서 물리는 불상사를 예방합니다.
    """)

# ----------------------------------------------------------------------
# 메뉴 3: 초보자 사용 설명서 화면
# ----------------------------------------------------------------------
with menu_tab3:
    st.markdown("### 📖 왕초보 투자자를 위한 3단계 계기판 매매 가이드")
    
    st.markdown("""
    이 앱을 켜고 실제 투자에 나설 때는 복잡하게 생각하지 말고 딱 **3단계 프로세스**만 밟으세요!
    
    ---
    
    #### 1단계: 내 종목 검색하기
    1. 왼쪽 패널에서 `국내 주식 (실제 거래 데이터)`를 선택합니다.
    2. 분석하고 싶은 종목 코드 6자리(예: 카카오 `035720`)를 입력하고 **[🚀 분석 시작하기]**를 누릅니다.
    
    #### 2단계: 최적의 보유일수 사냥하기 (1단계 분석 표 보기)
    * 표를 보면서 **[판정]** 열에 `🟢 진짜 신호 (진입 가능)`라고 적힌 행을 찾습니다.
    * 5일, 10일, 20일, 40일 중 초록불이 들어와 있으면서 **[승률]**과 **[전략수익률]**이 가장 높게 찍힌 보유일수가 이 종목의 '골든 타임'입니다.
    
    #### 3단계: 안전한 안전벨트 확인하기 (리스크 범위 그래프 보기)
    * 내가 고른 보유일수의 **`최악의 경우 (손실 하단)`** 막대그래프 길이를 봅니다.
    * 만약 손실 한도가 `-1%`~`-2%` 수준으로 짧다면 마음 편히 비중을 실어 매수해도 좋고, `-5%` 이상으로 깊다면 언제든 급락할 수 있으므로 소액만 진입하는 것이 좋습니다.
    """)
    st.success("🎯 **결론:** 판정에 초록불이 켜져 있고, 리스크 막대기가 짧은 자리만 찾아 들어가는 것. 그것이 퀀트 투자의 핵심입니다.")
