"""
이격도(Disparity) 기반 통계적 검증 및 퀀트 분석 플랫폼
================================================================
리뉴얼 포인트: 250라인 부근의 NameError(display 변수 누락 오타) 완벽 버그 수정
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
# [백엔드 함수] 데이터 연산 로직 (실거래 데이터 전용)
# ----------------------------------------------------------------------
def load_price_data(ticker: str, start: str, end: str) -> pd.DataFrame:
    try:
        import FinanceDataReader as fdr
        df = fdr.DataReader(ticker, start, end)
        df = df.rename(columns=str.title)
        return df[["Close", "Volume"]].dropna()
    except ImportError as e:
        raise ImportError("FinanceDataReader 설치가 필요합니다.") from e

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
            rows.append({"보유기간": f"{h}일", "신호발생": len(sig_ret), "승률": 0.0, "전략수익률": 0.0, "시장수익률": 0.0, "초과수익률": 0.0, "최악의경우": 0.0, "최선의경우": 0.0, "판정": "데이터 부족", "p_val": 1.0})
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
            results.append({"구간": f"{i+1}구간", "전략수익률": 0.0})
            continue
        results.append({
            "구간": f"{i+1}구간 ({fold.index[0].year}년)",
            "전략수익률": round(sig.mean() * 100, 2)
        })
    return pd.DataFrame(results)

def fit_rebound_probability_model(df: pd.DataFrame, horizon=20, test_size=0.3):
    feat_cols = ["Disparity", "Volatility20", "VolumeZ"]
    target_col = f"fwd_win_{horizon}d"
    data = df.dropna(subset=feat_cols + [target_col]).copy()
    split_idx = int(len(data) * (1 - test_size))
    train, test = data.iloc[:split_idx], data.iloc[split_idx:]
    
    scaler = StandardScaler()
    X_train = scaler.fit_transform(train[feat_cols])
    X_test = scaler.transform(test[feat_cols])
    
    model = LogisticRegression()
    model.fit(X_train, train[target_col])
    
    raw_coefs = model.coef_[0]
    formatted_coefs = {
        "이격도 (Disparity)": float(round(raw_coefs[0], 4)),
        "20일 변동성 (Volatility)": float(round(raw_coefs[1], 4)),
        "거래량 이상치 (Volume Z-score)": float(round(raw_coefs[2], 4))
    }
    
    return {
        "coef": formatted_coefs,
        "train_acc": float(model.score(X_train, train[target_col])),
        "test_acc": float(model.score(X_test, test[target_col])),
        "baseline_acc": float(max(test[target_col].mean(), 1 - test[target_col].mean())),
        "train_p": f"{train.index[0].date()}~{train.index[-1].date()}",
        "test_p": f"{test.index[0].date()}~{test.index[-1].date()}"
    }

# ----------------------------------------------------------------------
# [프론트엔드] 사이트 디자인 및 네비게이션
# ----------------------------------------------------------------------
st.markdown("""
    <div style="background-color:#0F172A; padding:24px; border-radius:12px; margin-bottom:25px; border-left: 8px solid #3B82F6;">
        <h1 style="color:white; margin:0; font-size:30px; font-weight:700;">📈 언제 사야 할지 몰라서 만든 사이트</h1>
        <p style="color:#94A3B8; margin:8px 0 0 0; font-size:15px;">오늘 가격 기준으로 살지 말지, 얼만큼 떨어질때 사야 할 지 몰라서 AI와 통계 데이터를 비벼서 만들었습니다.</p>
        <p style="color:#94A3B8; margin:8px 0 0 0; font-size:15px;">최근 20일 간 하락율이 10%면 이격도 90%이며, 투자자 본인이 몇 % 떨어지면 사볼만 하겠다 설정하고 실제 투자하게 될 때 과거 통계를 기반으로 투자성공율과 보유기간별 수익율을 예상해 보는 사이트입니다.</p>
    </div>
""", unsafe_allow_html=True)

menu_tab1, menu_tab2, menu_tab3 = st.tabs(
