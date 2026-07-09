# 코드 최상단에 추가
import streamlit as st

이격도(Disparity) 기반 주가 반등 전략 — 통계적 검증 프레임워크
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
  pip install FinanceDataReader pandas numpy scipy scikit-learn
"""

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
            계수가 데이터에서 나오고, out-of-sample 정확도까지 확인 가능.

    시계열이므로 train/test를 무작위 셔플이 아니라 '시간 순서'로 분리 (미래 데이터 누설 방지).
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
    baseline_acc = max(y_test.mean(), 1 - y_test.mean())  # 항상 다수클래스 예측했을 때 정확도

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
# 7. Streamlit 실행 및 시각화 화면 구성
# ----------------------------------------------------------------------
def run_full_analysis_streamlit(ticker: str = None, start="2015-01-01", end=None, threshold=95.0):
    st.title("📈 이격도 기반 주가 반등 전략 검증")
    
    if ticker:
        st.subheader(f"🔍 종목: {ticker} (기간: {start} ~ {end or '오늘'})")
        df = load_price_data(ticker, start, end)
    else:
        st.subheader("🤖 검증용 합성 데이터 분석")
        df = generate_synthetic_data()

    df = compute_indicators(df)
    df = add_forward_returns(df)

    st.info(f"**총 관측일수:** {len(df)}일 (이동평균 계산으로 앞 20일 제외)")

    # [1] 임계값 전략 백테스트 결과
    st.markdown("### [1] 이격도 미만 신호의 실제 성과 (벤치마크 대비 유의성 검정)")
    bt = backtest_threshold_strategy(df, threshold=threshold)
    st.dataframe(bt) # 웹 화면에 깔끔한 테이블로 출력

    # [2] Walk-forward 검증 결과
    st.markdown("### [2] Walk-forward 검증 (20일 보유 기준, 5개 구간)")
    wf = walk_forward_validation(df, threshold=threshold, horizon=20, n_folds=5)
    st.dataframe(wf)

    # [3] 로지스틱 회귀 리포트
    st.markdown("### [3] 로지스틱 회귀 기반 반등확률 모형 결과")
    model_report = fit_rebound_probability_model(df, horizon=20)
    
    for k, v in model_report.items():
        st.write(f"- **{k}**: {v}")

    # 주의사항 경고창
    st.warning("""
    **⚠️ 해석 시 주의 사항**
    - `win_rate`나 평균수익률이 벤치마크보다 높아도 `p_value >= 0.05`면 우연일 가능성을 배제할 수 없습니다.
    - `test_accuracy`가 `naive_baseline`보다 낮으면 모형의 예측 가치가 없는 상태입니다.
    - 신뢰구간(CI)이 너무 넓다면 확정적인 숫자로 맹신해서는 안 됩니다.
    """)

if __name__ == "__main__":
    # 사이드바에서 모드 선택 가능하도록 간단한 UI 추가
    st.sidebar.header("설정")
    mode = st.sidebar.radio("데이터 선택", ["합성 데이터 테스트", "실제 종목 분석(삼성전자)"])
    
    if mode == "합성 데이터 테스트":
        run_full_analysis_streamlit()
    else:
        # FinanceDataReader가 정상 설치되어 있어야 작동합니다.
        run_full_analysis_streamlit(ticker="005930", start="2015-01-01", threshold=95.0)
