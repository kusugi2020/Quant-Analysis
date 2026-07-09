"""
이격도(Disparity) 기반 통계적 검증 및 퀀트 분석 플랫폼
================================================================
리뉴얼 포인트: 투자자 맞춤형 이격도 설정 가이드 및 시각화 강화
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
input_threshold = st.sidebar.slider("📉 얼마나 과매도 되었을 때 살까요? (이격도 %)", min_value=85.0, max_value=100.0, value=93.0, step=0.5)

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
# 메뉴 1: 실시간 분석 계기판
# ----------------------------------------------------------------------
with menu_tab1:
    if is_data_loaded and execute_button:
        processed_df = compute_indicators(raw_df)
        processed_df = add_forward_returns(processed_df)
        
        current_disparity = processed_df['Disparity'].iloc[-1]
        total_signals = (processed_df['Disparity'] < input_threshold).sum()
        bt_res = backtest_threshold_strategy(processed_df, input_threshold)
        
        # ==================================================================
        # 1. 오늘의 투자 최종 신호등 판정
        # ==================================================================
        st.markdown("### 🚨 [오늘의 투자 최종 신호등 판정]")
        
        valid_horizons = bt_res[bt_res["판정"] == "🟢 진짜 신호 (진입 가능)"]
        
        if current_disparity < input_threshold:
            if len(valid_horizons) > 0:
                best_row = valid_horizons.sort_values(by="전략수익률", ascending=False).iloc[0]
                st.markdown(f"""
                    <div style="background-color:#DCFCE7; padding:20px; border-radius:8px; border: 2px solid #22C55E;">
                        <h2 style="color:#166534; margin:0; font-size:22px;">🔥 오늘의 판정: [ 적극 매수 가능 자리 ]</h2>
                        <p style="color:#1F2937; margin:8px 0 0 0; font-size:15px;">
                            현재 이격도가 <b>{current_disparity:.2f}%</b>로 설정하신 기준치({input_threshold}%)보다 낮아 <b>역사적인 과매도 구간</b>에 진입했습니다.<br>
                            과거 통계 검증 결과, 현재 자리에서 <b>{best_row['보유기간']}</b> 동안 보유 시 <b>승률 {best_row['승률']}% / 기대 수익률 {best_row['전략수익률']}%</b>로 성과가 우수했으며, 우연이 아님이 수학적으로 증명되었습니다.
                        </p>
                    </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                    <div style="background-color:#FEF3C7; padding:20px; border-radius:8px; border: 2px solid #F59E0B;">
                        <h2 style="color:#92400E; margin:0; font-size:22px;">⚠️ 오늘의 판정: [ 하락했으나 매수 보류 (함정 위험) ]</h2>
                        <p style="color:#1F2937; margin:8px 0 0 0; font-size:15px;">
                            현재 이격도는 <b>{current_disparity:.2f}%</b>로 낮아져 얼핏 싸 보이지만, 과거 데이터 분석 결과 <b>이 자리에서 샀을 때의 반등 확률이 '단순한 운'이었을 확률이 높습니다.</b><br>
                            통계적 유의성이 확보되지 않은 자리이므로 지금 당장 진입하는 것은 위험하며, 추가 관망을 권장합니다.
                        </p>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown(f"""
                <div style="background-color:#F1F5F9; padding:20px; border-radius:8px; border: 2px solid #94A3B8;">
                    <h2 style="color:#334155; margin:0; font-size:22px;">🛑 오늘의 판정: [ 관망 및 매수 대기 ]</h2>
                    <p style="color:#1F2937; margin:8px 0 0 0; font-size:15px;">
                        현재 이격도는 <b>{current_disparity:.2f}%</b>로, 설정하신 과매도 기준치({input_threshold}%)보다 높습니다. <br>
                        주가가 유리한 고지까지 충분히 내려오지 않았으므로, 기준치 이하로 떨어질 때까지 느긋하게 기다리세요.
                    </p>
                </div>
            """, unsafe_allow_html=True)
            
        # ==================================================================
        # 🔥 신설 메뉴: 투자자 맞춤형 슬라이더 가이드 문구
        # ==================================================================
        st.markdown("")
        with st.expander("💡 <b>왼쪽 '이격도 매수 임계값' 슬라이더 조절은 어떤 의미인가요? (필독)</b>", expanded=True):
            st.markdown(f"""
            * **마음대로 기준을 정해보세요:** 슬라이더를 **{input_threshold}%**로 두셨다는 건, *"나는 20일 평균 가격보다 **-{100-input_threshold:.1f}% 이상 폭락한 공포의 자리**에서만 살래"*라고 나만의 커트라인을 선언하신 것입니다.
            * **현재 상태 해석:** 지금 이 종목의 실시간 이격도는 **{current_disparity:.2f}%**입니다. 즉, 평균보다 **-{100-current_disparity:.1f}%** 하락해 있습니다. 투자자님이 정한 커트라인보다 주가가 낮기 때문에 시스템이 과거 데이터를 뒤져 '살지 말지'를 주황색/초록색 창으로 채점해 준 것입니다.
            * **어떻게 활용하나요?:** 슬라이더 숫자를 높이면(예: 96%) 매수 기회는 자주 오지만 위험한 자리일 수 있고, 숫자를 낮추면(예: 90%) 기회는 매우 드물게 오지만 엄청나게 안전한 자리가 됩니다. 정답은 없습니다! 슬라이더를 바꿔가며 아래 표의 **[판정]**에 초록불이 켜지는 나만의 최적의 황금 커트라인을 탐색해 보세요.
            """)
        
        st.markdown("---")
        
        # 2. 상단 지표 요약
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("🔬 검증에 사용된 총 일수", f"{len(processed_df):,} 일")
        with m2:
            st.metric("📉 최근 이격도 상태", f"{current_disparity:.2f}%")
        with m3:
            st.metric("🚨 역사적 매수 신호 포착 횟수", f"{total_signals} 회")
            
        st.markdown("---")
        
        # 3. 메인 시각화 그래프 구간
        st.markdown("### 📊 최근 주가 추이와 이격도 흐름")
        chart_data = processed_df.tail(250)[["Close", "MA", "Disparity"]]
        st.line_chart(chart_data[["Close", "MA"]], height=250)
        st.line_chart(chart_data["Disparity"], height=120)
        
        st.markdown("---")
        
        # 4. 전략 기대 성과 표 및 그래프
        st.markdown("### 🎯 1단계 분석 결과: 이 자리에 사면 내 계좌는 어떻게 될까?")
        st.dataframe(bt_res[["보유기간", "신호발생", "승률", "전략수익률", "시장수익률", "초과수익률", "판정"]], use_container_width=True, hide_index=True)
        
        st.markdown("#### 📈 무작위로 살 때 vs 과매도 신호에 살 때 수익률 비교 그래프")
        graph_df = pd.DataFrame({
            "시장 그냥 보유 시 (벤치마크)": bt_res["시장수익률"].values,
            "이격도 과매도 전략 사용 시": bt_res["전략수익률"].values
        }, index=bt_res["보유기간"])
        st.bar_chart(graph_df)

        st.markdown("---")
        
        # 5. 리스크 관리 차트 및 과거 영속성 검증
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

# ... (이하 메뉴 2, 메뉴 3 코드는 기존과 동일) ...
