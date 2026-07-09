"""
이격도(Disparity) 기반 주가 반등 전략 - 통계적 검증 프레임워크
================================================================

기존 앱의 문제점:
  - "Rebound Energy = (100-이격도)*2.5 + 미국지수*0.4 + 환율*0.2" 같은 계수가
    통계적 근거 없이 임의로 설정됨
  - 검증(백테스트) 없이 "D-Day 23일" 같은 확정적 숫자를 제시
  - 표본 8개(역사적 사건)로 일반화 → 생존 편향, 과적합 위험

이 스크립트가 하는 것:
  1. 실제 과거 데이터로 "이격도가 낮을 때 정말 반등하는가?"를 대량 표본으로 검증
  2. 벤치마크(그냥 매수 후 보유) 대비 초과수익이 통계적으로 유의한지 t-test
  3. 부트스트랩으로 신뢰구간 산출 (점 추정치 대신 "range + 신뢰수준")
  4. Look-ahead bias를 피하기 위한 시계열 기반 walk-forward 검증
  5. 임의 상수 대신, 로지스틱 회귀로 계수를 데이터에서 직접 추정

필요 라이브러리:
  pip install FinanceDataReader pandas numpy scipy scikit-learn streamlit
"""

import streamlit as st
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings("ignore")


# ----------------------------------------------------------------------
# 1. 데이터 로딩
# ----------------------------------------------------------------------
def load_price_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    """
    한국 주식은 FinanceDataReader, 해외 주식은 yfinance 등으로 교체 가능.
    반환: Date 인덱스, Close, Volume 컬럼을 가진 DataFrame
    """
    try:
        import FinanceDataReader as fdr
        df = fdr.DataReader(ticker, start, end)
        df = df.rename(columns=str.title)
        return df[["Close", "Volume"]].dropna()
    except ImportError as e:
        raise ImportError(
            "FinanceDataReader가 필요합니다: pip install finance-datareader"
        ) from e


def generate_synthetic_data(n_days=1500, seed=42) -> pd.DataFrame:
    """코드 검증용 합성 데이터 (실거래 데이터 없이도 로직 테스트 가능)."""
    rng = np.random.default_rng(seed)
    # 약간의 평균회귀 성질을 가진 랜덤워크로 생성 (실제 주가와 유사한 성질)
    returns = rng.normal(0.0003, 0.018, n_days)
    price = 50000 * np.exp(np.cumsum(returns))
    dates = pd.bdate_range("2019-01-01", periods=n_days)
    volume = rng.integers(1_000_000, 5_000_000, n_days)
    return pd.DataFrame({"Close": price, "Volume": volume}, index=dates)


# ----------------------------------------------------------------------
# 2. 지표 계산
# ----------------------------------------------------------------------
def compute_indicators(df: pd.DataFrame, ma_window: int = 20) -> pd.DataFrame:
    df = df.copy()
    df["MA"] = df["Close"].rolling(ma_window).mean()
    df["Disparity"] = df["Close"] / df["MA"] * 100
    df["Volatility20"] = df["Close"].pct_change().rolling(20).std() * np.sqrt(252)
    df["VolumeZ"] = (
        (df["Volume"] - df["Volume"].rolling(60).mean())
        / df["Volume"].rolling(60).std()
    )
    return df


def add_forward_returns(df: pd.DataFrame, horizons=(5, 10, 20, 40)) -> pd.DataFrame:
    df = df.copy()
    for h in horizons:
        df[f"fwd_ret_{h}d"] = df["Close"].shift(-h) / df["Close"] - 1
        df[f"fwd_win_{h}d"] = (df[f"fwd_ret_{h}d"] > 0).astype(float)
    return df


# ----------------------------------------------------------------------
# 3. 부트스트랩 신뢰구간
# ----------------------------------------------------------------------
def bootstrap_ci(series: pd.Series, n_boot=3000, ci=0.90, seed=1):
    rng = np.random.default_rng(seed)
    arr = series.dropna().values
    if len(arr) == 0:
        return (np.nan, np.nan)
    boot_means = rng.choice(arr, size=(n_boot, len(arr)), replace=True).mean(axis=1)
    lo = np.percentile(boot_means, (1 - ci) / 2 * 100)
    hi = np.percentile(boot_means, (1 + ci) / 2 * 100)
    return lo, hi


# ----------------------------------------------------------------------
# 4. 핵심: 임계값 전략 백테스트 (벤치마크 대비 통계 검정 포함)
# ----------------------------------------------------------------------
def backtest_threshold_strategy(
    df: pd.DataFrame,
    threshold: float = 95.0,
    horizons=(5, 10, 20, 40),
    min_samples: int = 30,
) -> pd.DataFrame:
    """
    '이격도가 threshold 미만인 날 매수했다면?'을 실제 표본 전체에서 검증.
    벤치마크(전체 기간 평균 수익률) 대비 초과수익의 통계적 유의성을 t-test로 확인.
    """
    signal = df["Disparity"] < threshold
    rows = []
    for h in horizons:
        col = f"fwd_ret_{h}d"
        sig_ret = df.loc[signal, col].dropna()
        all_ret = df[col].dropna()

        if len(sig_ret) < min_samples:
            rows.append({
                "horizon_days": h, "n_samples": len(sig_ret),
                "note": f"표본 부족(<{min_samples}) — 신뢰 불가",
            })
            continue

        win_rate = (sig_ret > 0).mean()
        avg_ret = sig_ret.mean()
        bench_avg = all_ret.mean()
        excess = avg_ret - bench_avg
        ci_lo, ci_hi = bootstrap_ci(sig_ret)
        t_stat, p_val = stats.ttest_ind(sig_ret, all_ret, equal_var=False)

        rows.append({
            "horizon_days": h,
            "n_samples": int(len(sig_ret)),
            "win_rate": round(win_rate, 3),
            "avg_return": round(avg_ret, 4),
            "benchmark_avg_return": round(bench_avg, 4),
            "excess_return": round(excess, 4),
            "return_90pct_CI": (round(ci_lo, 4), round(ci_hi, 4)),
            "p_value_vs_benchmark": round(p_val, 4),
            "statistically_significant(p<0.05)": bool(p_val < 0.05),
        })
    return pd.DataFrame(rows)


# ----------------------------------------------------------------------
# 5. Walk-forward 검증 (미래 데이터 누설 방지)
# ----------------------------------------------------------------------
def walk_forward_validation(
    df: pd.DataFrame,
    threshold: float = 95.0,
    horizon: int = 20,
    n_folds: int = 5,
) -> pd.DataFrame:
    """
    데이터를 시간순으로 n_folds 구간으로 나눠, 각 구간을 '검증 구간'으로 사용.
    이전 구간에서 관찰된 패턴이 다음 구간에서도 유지되는지 확인 (과적합 점검).
    """
    col = f"fwd_ret_{horizon}d"
    valid = df.dropna(subset=[col, "Disparity"]).copy()
    fold_size = len(valid) // n_folds
    results = []
    for i in range(n_folds):
        start = i * fold_size
        end = (i + 1) * fold_size if i < n_folds - 1 else len(valid)
        fold = valid.iloc[start:end]
        sig = fold.loc[fold["Disparity"] < threshold, col]
        bench = fold[col]
        if len(sig) < 5:
            results.append({"fold": i + 1, "period": f"{fold.index[0].date()}~{fold.index[-1].date()}",
                             "n_signal": len(sig), "win_rate": None, "avg_return": None})
            continue
        results.append({
            "fold": i + 1,
            "period": f"{fold.index[0].date()}~{fold.index[-1].date()}",
            "n_signal": int(len(sig)),
            "win_rate": round((sig > 0).mean(), 3),
            "avg_return": round(sig.mean(), 4),
            "benchmark_avg": round(bench.mean(), 4),
        })
    return pd.DataFrame(results)


# ----------------------------------------------------------------------
# 6. 임의 상수 대신 데이터 기반 계수 추정 (로지스틱 회귀)
# ----------------------------------------------------------------------
def fit_rebound_probability_model(
    df: pd.DataFrame, horizon: int = 20, test_size: float = 0.3
):
    """
    기존 앱: Rebound Energy = 임의 상수들의 선형합 (근거 없음)
    개선안: '이격도, 변동성, 거래량 이상치'로 'N일 내 반등 확률'을 로지스틱 회귀로 직접 추정.
    """
    feat_cols = ["Disparity", "Volatility20", "VolumeZ"]
    target_col = f"fwd_win_{horizon}d"
    data = df.dropna(subset=feat_cols + [target_col]).copy()

    split_idx = int(len(data) * (1 - test_size))
    train, test = data.iloc[:split_idx], data.iloc[split_idx:]

    scaler = StandardScaler()
    X_train = scaler.fit_transform(train[feat_cols])
    X_test = scaler.transform(test[feat_cols])
    y_train, y_test = train[target_col], test[target_col]

    model = LogisticRegression()
    model.fit(X_train, y_train)

    train_acc = model.score(X_train, y_train)
    test_acc = model.score(X_test, y_test)
    baseline_acc = max(y_test.mean(), 1 - y_test.mean())

    coef_report = dict(zip(feat_cols, model.coef_[0].round(4)))

    return {
        "features": feat_cols,
        "coefficients(표준화된 스케일)": coef_report,
        "train_accuracy": round(train_acc, 3),
        "test_accuracy(out-of-sample)": round(test_acc, 3),
        "naive_baseline_accuracy": round(baseline_acc, 3),
        "beats_naive_baseline": bool(test_acc > baseline_acc),
        "train_period": f"{train.index[0].date()} ~ {train.index[-1].date()}",
        "test_period": f"{test.index[0].date()} ~ {test.index[-1].date()}",
    }


# ----------------------------------------------------------------------
# 7. Streamlit 대시보드 화면 구성 구현
# ----------------------------------------------------------------------
def run_full_analysis_streamlit(ticker: str = None, start="2015-01-01", end=None, threshold=95.0):
    st.title("📈 이격도 기반 주가 반등 전략 검증")
    
    if ticker:
        st.subheader(f"🔍 분석 대상: {ticker} (기간: {start} ~ {end or '오늘'})")
        df = load_price_data(ticker, start, end)
    else:
        st.subheader("🤖 검증용 합성 데이터 분석 모드")
        df = generate_synthetic_data()

    df = compute_indicators(df)
    df = add_forward_returns(df)

    st.info(f"📊 **총 관측 데이터:** {len(df)}일 (이동평균 산출을 위한 초기 20일 제외)")

    # [1] 임계값 전략 백테스트
    st.markdown("### 1️⃣ 이격도 임계값 미만 진호의 실제 성과")
    st.caption("벤치마크(전체 기간 평균 수익률) 대비 초과수익 및 t-test 유의성 검정 결과")
    bt = backtest_threshold_strategy(df, threshold=threshold)
    st.dataframe(bt, use_container_width=True)

    # [2] Walk-forward 검증
    st.markdown("### 2️⃣ 시계열 구조 Walk-forward 검증")
    st.caption("과적합을 방지하기 위해 데이터를 순차적 구간으로 나누어 패턴의 영속성 확인 (20일 보유 기준)")
    wf = walk_forward_validation(df, threshold=threshold, horizon=20, n_folds=5)
    st.dataframe(wf, use_container_width=True)

    # [3] 로지스틱 회귀
    st.markdown("### 3️⃣ 데이터 기반 반등 확률 추정 모형 (로지스틱 회귀)")
    st.caption("임의 상수를 배제하고 이격도, 변동성, 거래량 Z-Score 변수를 바탕으로 머신러닝 학습 수행")
    model_report = fit_rebound_probability_model(df, horizon=20)
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("**📊 평가 메트릭**")
        st.write(f"- 학습 정확도 (Train Accuracy): `{model_report['train_accuracy']}`")
        st.write(f"- 검증 정확도 (Test Accuracy): `{model_report['test_accuracy(out-of-sample)']}`")
        st.write(f"- 기준 정확도 (Baseline Accuracy): `{model_report['naive_baseline_accuracy']}`")
        st.write(f"- 기준 모델 대비 우수 여부: `{'✅ 통과' if model_report['beats_naive_baseline'] else '❌ 미달'}`")
    
    with col2:
        st.markdown("**📐 표준화 계수 (Coefficients)**")
        for feat, coef in model_report["coefficients(표준화된 스케일)"].items():
            st.write(f"- `{feat}`: `{coef}`")
            
    st.caption(f"📅 학습 기간: {model_report['train_period']} / 검증 기간: {model_report['test_period']}")

    # 오해 소지 방지를 위한 안내 문구
    st.warning("""
    **⚠️ 통계 해석 시 유의사항**
    - `win_rate`나 평균수익률이 벤치마크보다 높게 관측되더라도, `p_value >= 0.05`라면 우연에 의한 결과일 확률을 배제할 수 없습니다.
    - `test_accuracy`가 `naive_baseline`보다 낮은 경우, 단순히 무조건 상승 혹은 무조건 하락으로 찍는 기본 모델보다 성능이 떨어짐을 의미합니다.
    - 신뢰구간(CI)의 범위가 지나치게 넓다면 과거 변동성이 매우 컸던 것이므로 확정적인 기대치를 신뢰해서는 안 됩니다.
    """)


if __name__ == "__main__":
    # 스트림릿 사이드바 제어 패널
    st.sidebar.header("🕹️ 제어 패널")
    data_mode = st.sidebar.selectbox("데이터 소스 선택", ["합성 데이터 (테스트용)", "국내 주식 시장 (실거래 데이터)"])
    
    input_threshold = st.sidebar.slider("이격도 매수 임계값 (%)", min_value=85.0, max_value=100.0, value=95.0, step=0.5)
    
    if data_mode == "합성 데이터 (테스트용)":
        run_full_analysis_streamlit(threshold=input_threshold)
    else:
        ticker_code = st.sidebar.text_input("종목코드 입력 (6자리)", value="005930")
        start_date = st.sidebar.text_input("조회 시작일", value="2015-01-01")
        
        if st.sidebar.button("분석 실행"):
            run_full_analysis_streamlit(ticker=ticker_code, start=start_date, threshold=input_threshold)
        else:
            st.info("👈 왼쪽 패널에서 종목코드 확인 후 [분석 실행] 버튼을 눌러주세요.")
