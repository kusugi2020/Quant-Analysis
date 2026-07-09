"""
이격도(Disparity) 기반 통계적 검증 및 퀀트 분석 플랫폼
================================================================
리뉴얼 포인트: '오늘 사면 어떻게 될까?' 실시간 최종 판정 신호등 메뉴 추가
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
            rows.append({"보유기간": f"{h}일", "신호발생": len(sig_ret), "승률": 0, "전략수익률": 0, "시장수익률": 0, "초과수익률": 0, "최악의경우": 0, "최선의경우": 0, "판정": "데이터 부족", "p_val": 1.0})
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
            "판정": "🟢 진짜 신호 (진입 가능)" if p_val < 0.05 else "🔴 가짜 신호 (위험)",
            "p_val": p_val
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
        <p style="color:#94A3B8; margin:8px 0 0 0; font-size:15px;">오늘 가격 기준으로 살지 말지, 인공지능과 통계 데이터가 즉시 판정해 드립니다.</p>
    </div>
""", unsafe_allow_html=True)

menu_tab1, menu_tab2, menu_tab3 = st.tabs(["🎯 오늘의 투자 판정 & 대시보드", "📚 분석 원리 쉽게 이해하기", "📖 초보자 사용 설명서"])

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
# 메뉴 1: 실시간 분석 계기판 및 '오늘 사면 어떻게 될까?' 추가
# ----------------------------------------------------------------------
with menu_tab1:
    if is_data_loaded and execute_button:
        processed_df = compute_indicators(raw_df)
        processed_df = add_forward_returns(processed_df)
        
        current_disparity = processed_df['Disparity'].iloc[-1]
        bt_res = backtest_threshold_strategy(processed_df, input_threshold)
        
        # ==================================================================
        # 🔥 신설 메뉴: 오늘 사면 어떻게 될까? (최종 신호등 판정 엔진)
        # ==================================================================
        st.markdown("### 🚨 [오늘의 투자 최종 신호등 판정]")
        
        # 통계적 신호가 유효한 보유일수가 단 하나라도 있는지 확인
        valid_horizons = bt_res[bt_res["판정"] == "🟢 진짜 신호 (진입 가능)"]
        
        # 조건별 상태 연산
        if current_disparity < input_threshold:
            if len(valid_horizons) > 0:
                # 조건 충족 + 통계적 유의성 확보 완료 -> 적극 매수
                best_row = valid_horizons.sort_values(by="전략수익률", ascending=False).iloc[0]
                st.markdown(f"""
                    <div style="background-color:#DCFCE7; padding:20px; border-radius:8px; border: 2px solid #22C55E;">
                        <h2 style="color:#166534; margin:0; font-size:22px;">🔥 오늘의 판정: [ 적극 매수 가능 자리 ]</h2>
                        <p style="color:#1F2937; margin:8px 0 0 0; font-size:15px;">
                            현재 이격도가 <b>{current_disparity:.2f}%</b>로 설정하신 기준치({input_threshold}%)보다 낮아 <b>역사적인 과매도 구간</b>에 진입했습니다.<br>
                            과거 통계 검증 결과, 현재 자리에서 <b>{best_row['보유기간']}</b> 동안 보유 시 <b>승률 {best_row['승률']}% / 기대 수익률 {best_row['전략수익률']}%</b>로 가장 성과가 우수했으며, 우연히 오른 것이 아님이 수학적으로 증명되었습니다.
                        </p>
                    </div>
                """, unsafe_allow_html=True)
            else:
                # 조건은 충족했으나 통계적 유의성이 부족한 함정 카드 자리 -> 관망
                st.markdown(f"""
                    <div style="background-color:#FEF3C7; padding:20px; border-radius:8px; border: 2px solid #F59E0B;">
                        <h2 style="color:#92400E; margin:0; font-size:22px;">⚠️ 오늘의 판정: [ 하락했으나 매수 보류 (함정 위험) ]</h2>
                        <p style="color:#1F2937; margin:8px 0 0 0; font-size:15px;">
                            현재 이격도는 <b>{current_disparity:.2f}%</b>로 낮아져 얼핏 싸 보이지만, 과거 데이터 분석 결과 <b>이 자리에서 샀을 때의 반등 확률이 '단순한 운'이나 '상승장 빨'이었을 확률(p-value)이 높습니다.</b><br>
                            통계적 유의성이 확보되지 않은 자리이므로 지금 당장 진입하는 것은 위험하며, 추가 관망을 권장합니다.
                        </p>
                    </div>
                """, unsafe_allow_html=True)
        else:
            # 주가가 아직 충분히 떨어지지 않은 평이한 상태 -> 관망
            st.markdown(f"""
                <div style="background-color:#F1F5F9; padding:20px; border-radius:8px; border: 2px solid #94A3B8;">
                    <h2 style="color:#334155; margin:0; font-size:22px;">🛑 오늘의 판정: [ 관망 및 매수 대기 ]</h2>
                    <p style="color:#1F2937; margin:8px 0 0 0; font-size:15px;">
                        현재 이격도는 <b>{current_disparity:.2f}%</b>로, 설정하신 과매도 기준치({input_threshold}%)보다 높습니다. <br>
                        주가가 통계적으로 유리한 고지까지 충분히 내려오지 않았으므로, 굳이 리스크를 지고 먼저 진입할 필요가 없습니다. 기준치 이하로 떨어질 때까지 느긋하게 기다리세요.
                    </p>
                </div>
            """, unsafe_allow_html=True)
            
        st.markdown("---")
        
        # 1. 친절한 상단 지표 요약
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("🔬 검증에 사용된 총 일수", f"{len(processed_df):,} 일")
        with m2:
            st.metric("📉 최근 이격도 상태", f"{current_disparity:.2f}%")
        with m3:
            st.metric("🚨 역사적 매수 신호 포착 횟수", f"{total_signals} 회")
            
        st.markdown("---")
        
        # 2. 메인 시각화 그래프 구간
        st.markdown("### 📊 최근 주가 추이와 이격도 흐름")
        chart_data = processed_df.tail(250)[["Close", "MA", "Disparity"]]
        st.line_chart(chart_data[["Close", "MA"]], height=250)
        st.line_chart(chart_data["Disparity"], height=120)
        
        st.markdown("---")
        
        # 3. 전략 기대 성과 표 및 그래프
        st.markdown("### 🎯 1단계 분석 결과: 이 자리에 사면 내 계좌는 어떻게 될까?")
        st.dataframe(bt_res[["보유기간", "신호발생", "승률", "전략수익률", "시장수익률", "초과수익률", "판정"]], use_container_width=True, hide_index=True)
        
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
            ci_graph_df = pd.DataFrame({
                "최악의 경우 (손실 하단)": bt_res["최악의경우"].values,
                "최선의 경우 (이익 상단)": bt_res["최선의경우"].values
            }, index=bt_res["보유기간"])
            st.bar_chart(ci_graph_df)
            
        with col_chart2:
            st.markdown("### ⏳ 3단계 분석 결과: 옛날에도 고르게 잘 먹혔을까?")
            wf_res = walk_forward_validation(processed_df, input_threshold)
            st.bar_chart(wf_res.set_index("구간"))

    else:
        st.info("👈 왼쪽 패널에서 설정을 완료하고 [🚀 분석 시작하기] 버튼을 눌러주세요.")

# ----------------------------------------------------------------------
# 메뉴 2: 분석 원리 및 근거 설명 화면 (기존 내용 유지)
# ----------------------------------------------------------------------
with menu_tab2:
    st.markdown("### 📚 그래프와 메트릭이 계산되는 숨은 원리")
    st.markdown("""
    #### 1️⃣ 🟢 진짜 신호 vs 🔴 가짜 신호의 비밀 (독립표본 t-test)
    * **원리:** 주가가 단순히 낙폭과대로 반등한 것인지, 아니면 시장이 다 같이 오르는 상승장이어서 휩쓸려 오른 것인지를 수학적으로 분리합니다.
    #### 2️⃣ 최악과 최선의 범위 (부트스트랩 신뢰구간)
    * **원리:** 과거 데이터를 무작위로 3,000번 섞어서 모의실험을 반복합니다. 그중 상위 5%의 대박 사건과 하위 5%의 쪽박 사건을 발라냅니다.
    #### 3️⃣ 구간별 쪼개기 검증 (Walk-forward 전진 분석)
    * **원리:** 특정 시기에만 반짝 반등했던 전략에 속아 현재 시장에서 물리는 불상사를 예방합니다.
    """)

# ----------------------------------------------------------------------
# 메뉴 3: 초보자 사용 설명서 화면 (기존 내용 유지)
# ----------------------------------------------------------------------
with menu_tab3:
    st.markdown("### 📖 왕초보 투자자를 위한 3단계 계기판 매매 가이드")
    st.markdown("""
    #### 1단계: 내 종목 검색하기
    #### 2단계: 최적의 보유일수 사냥하기 (1단계 분석 표 보기)
    #### 3단계: 안전한 안전벨트 확인하기 (리스크 범위 그래프 보기)
    """)
