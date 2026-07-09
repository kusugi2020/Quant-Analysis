"""
이격도(Disparity) 기반 통계적 검증 및 퀀트 분석 플랫폼
================================================================
구조: Multi-tab 웹 애플리케이션 형태 (대시보드, 분석 원리, 사용 설명서)
"""

import streamlit as st
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
import warnings
warnings.filterwarnings("ignore")

# 스트림릿 페이지 기본 설정 (웹사이트 스타일)
st.set_page_config(
    page_title="Disparity Quant Platform",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ----------------------------------------------------------------------
# [백엔드 함수] 1. 데이터 로딩 및 연산 로직 (기존 알고리즘 유지)
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
            rows.append({"보유기간(일)": h, "신호발생 횟수": len(sig_ret), "비고": "표본 부족으로 검증 불가"})
            continue

        win_rate = (sig_ret > 0).mean()
        avg_ret = sig_ret.mean()
        bench_avg = all_ret.mean()
        excess = avg_ret - bench_avg
        ci_lo, ci_hi = bootstrap_ci(sig_ret)
        _, p_val = stats.ttest_ind(sig_ret, all_ret, equal_var=False)

        rows.append({
            "보유기간(일)": h,
            "신호발생 횟수": int(len(sig_ret)),
            "승률 (Win Rate)": f"{win_rate*100:.1f}%",
            "전략 평균수익률": f"{avg_ret*100:.2f}%",
            "시장 평균수익률": f"{bench_avg*100:.2f}%",
            "초과 수익률": f"{excess*100:.2f}%",
            "90% 신뢰구간 (CI)": f"[{ci_lo*100:.1f}%, {ci_hi*100:.1f}%]",
            "p-value (우연성 검정)": f"{p_val:.4f}",
            "통계적 유의성(p<0.05)": "✅ 유의함" if p_val < 0.05 else "❌ 우연일 수 있음"
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
        bench = fold[col]
        if len(sig) < 5:
            results.append({"구간 (Fold)": i + 1, "테스트 기간": f"{fold.index[0].date()} ~ {fold.index[-1].date()}", "신호 횟수": len(sig), "전략 승률": "-", "전략 수익률": "-"})
            continue
        results.append({
            "구간 (Fold)": i + 1,
            "테스트 기간": f"{fold.index[0].date()} ~ {fold.index[-1].date()}",
            "신호 횟수": int(len(sig)),
            "전략 승률": f"{(sig > 0).mean()*100:.1f}%",
            "전략 수익률": f"{sig.mean()*100:.2f}%",
            "시장 수익률": f"{bench.mean()*100:.2f}%"
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
    
    return {
        "coef": dict(zip(["이격도 (Disparity)", "20일 변동성 (Volatility)", "거래량 이상치 (Volume Z-score)"], model.coef_[0].round(4))),
        "train_acc": model.score(X_train, train[target_col]),
        "test_acc": model.score(X_test, test[target_col]),
        "baseline_acc": max(test[target_col].mean(), 1 - test[target_col].mean()),
        "train_p": f"{train.index[0].date()}~{train.index[-1].date()}",
        "test_p": f"{test.index[0].date()}~{test.index[-1].date()}"
    }

# ----------------------------------------------------------------------
# [프론트엔드] 2. 사이트 메뉴 및 레이아웃 구성
# ----------------------------------------------------------------------

# 상단 웹사이트 타이틀 바 
st.markdown("""
    <div style="background-color:#1E293B; padding:20px; border-radius:10px; margin-bottom:25px;">
        <h1 style="color:white; margin:0; font-size:28px;">📊 이격도 기반 통계적 검증 및 퀀트 플랫폼</h1>
        <p style="color:#94A3B8; margin:5px 0 0 0; font-size:14px;">데이터 사이언스 기반으로 가짜 반등 신호와 진정한 알파를 구별합니다.</p>
    </div>
""", unsafe_allow_html=True)

# 메인 네비게이션 탭 (홈페이지 메뉴 구조)
menu_tab1, menu_tab2, menu_tab3 = st.tabs(["🎯 실시간 대시보드", "📚 분석 원리 및 근거", "📖 시스템 사용 설명서"])

# 사이드바 제어판 (전역 설정)
st.sidebar.markdown("### ⚙️ 전략 시뮬레이션 설정")
data_mode = st.sidebar.selectbox("💾 데이터 소스", ["합성 데이터 (검증용)", "국내 주식 (실거래 데이터)"])
input_threshold = st.sidebar.slider("📉 이격도 매수 임계값 (%)", min_value=85.0, max_value=100.0, value=95.0, step=0.5)

if data_mode == "국내 주식 (실거래 데이터)":
    ticker_code = st.sidebar.text_input("📌 종목코드 입력 (6자리)", value="005930")
    start_date = st.sidebar.text_input("📅 분석 시작년도", value="2015-01-01")
    execute_button = st.sidebar.button("🚀 데이터 분석 실행", use_container_width=True)
else:
    ticker_code, start_date = None, "2015-01-01"
    execute_button = True

# 데이터 로드 프로세스
if data_mode == "국내 주식 (실거래 데이터)" and ticker_code:
    try:
        raw_df = load_price_data(ticker_code, start_date, None)
        is_data_loaded = True
    except Exception:
        st.sidebar.error("⚠️ 종목코드를 확인해 주세요. (예: 삼성전자 005930)")
        is_data_loaded = False
else:
    raw_df = generate_synthetic_data()
    is_data_loaded = True

# ----------------------------------------------------------------------
# 메뉴 1: 실시간 대시보드 화면
# ----------------------------------------------------------------------
with menu_tab1:
    if is_data_loaded and execute_button:
        processed_df = compute_indicators(raw_df)
        processed_df = add_forward_returns(processed_df)
        
        # 핵심 요약 지표 (Metrics Row)
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("총 분석 일수", f"{len(processed_df)} 일")
        with m2:
            current_disparity = processed_df['Disparity'].iloc[-1]
            st.metric("최근 이격도 (20MA)", f"{current_disparity:.2f}%")
        with m3:
            total_signals = (processed_df['Disparity'] < input_threshold).sum()
            st.metric("역사적 신호 발생 횟수", f"{total_signals} 번")
            
        st.markdown("---")
        
        # 분석 테이블 세션
        st.markdown(f"#### 1. {input_threshold}% 미만 진입 시 보유기간별 기대 성과")
        bt_res = backtest_threshold_strategy(processed_df, input_threshold)
        st.dataframe(bt_res, use_container_width=True, hide_index=True)
        
        col_left, col_right = st.columns(2)
        
        with col_left:
            st.markdown("#### 2. 과적합 방지 Walk-forward 구간 검증")
            wf_res = walk_forward_validation(processed_df, input_threshold)
            st.dataframe(wf_res, use_container_width=True, hide_index=True)
            
        with col_right:
            st.markdown("#### 3. 머신러닝 기반 반등 유효성 추정")
            model_res = fit_rebound_probability_model(processed_df)
            
            st.markdown(f"**🤖 아웃샘플 예측 검증 결과**")
            st.write(f"- 알고리즘 예측 정확도: `{model_res['test_acc']*100:.1f}%` *(기준선: {model_res['baseline_acc']*100:.1f}%)*")
            st.write(f"- 모델 신뢰 수준 판정: `{'✅ 통계적 우위 확보' if model_res['test_acc'] > model_res['baseline_acc'] else '❌ 우연에 의한 수익 모델'}`")
            
            st.markdown("**📐 각 지표별 가중치(표준화 계수)**")
            for f, c in model_res["coef"].items():
                st.write(f"- **{f}**: `{c}`")
    else:
        st.info("👈 왼쪽 패널에서 실거래 데이터 설정을 완료한 후 [데이터 분석 실행] 버튼을 눌러주세요.")

# ----------------------------------------------------------------------
# 메뉴 2: 분석 원리 및 근거 설명 화면
# ----------------------------------------------------------------------
with menu_tab2:
    st.markdown("### 📊 왜 '감'이 아닌 '통계적 검증'이 필요한가?")
    
    st.markdown("""
    많은 투자자들이 **"많이 떨어졌으니 이제 반등하겠지"**라는 막연한 기대감이나 임의로 만든 지표 점수(예: Rebound Energy 공식 등)를 맹신하여 시장에 뛰어듭니다.
    그러나 이는 극심한 과적합(Overfitting)과 생존 편향을 낳아 자산을 잃게 만드는 주원인이 됩니다.
    
    본 플랫폼은 전략의 신뢰도를 **수학적**으로 판별하기 위해 아래 3가지 검증 원리를 사용합니다.
    """)
    
    # 세부 원리 카드 형태 배치
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("""
        <div style="background-color:#F8FAFC; padding:15px; border-radius:8px; border-left:5px solid #3B82F6; min-height:220px;">
            <h4 style="color:#1E293B; margin-top:0;">① 독립표본 t-test (우연성 검정)</h4>
            <p style="color:#475569; font-size:13px;">이격도가 낮을 때 진입한 전략의 수익률이, 시장 전체의 무작위 평균 수익률과 확실하게 차이가 나는지 검증합니다.</p>
            <p style="color:#2563EB; font-size:12px;"><b>p-value < 0.05</b> 일 때만 운이 아닌 실력(알파)으로 인정합니다.</p>
        </div>
        """, unsafe_allow_html=True)
        
    with c2:
        st.markdown("""
        <div style="background-color:#F8FAFC; padding:15px; border-radius:8px; border-left:5px solid #10B981; min-height:220px;">
            <h4 style="color:#1E293B; margin-top:0;">② 부트스트랩 신뢰구간 (CI)</h4>
            <p style="color:#475569; font-size:13px;">"20일 뒤 5% 오른다" 같은 단일 점 추정은 위험합니다. 과거 데이터를 3,000번 이상 무작위 복원 추출(Bootstrap)하여 수익률의 범위를 추정합니다.</p>
            <p style="color:#059669; font-size:12px;"><b>하단과 상단의 범위</b>를 확인함으로써 리스크 한계를 계산할 수 있습니다.</p>
        </div>
        """, unsafe_allow_html=True)
        
    with c3:
        st.markdown("""
        <div style="background-color:#F8FAFC; padding:15px; border-radius:8px; border-left:5px solid #8B5CF6; min-height:220px;">
            <h4 style="color:#1E293B; margin-top:0;">③ Walk-forward (전진 분석)</h4>
            <p style="color:#475569; font-size:13px;">시계열 데이터를 시간 순서대로 5개 구간으로 쪼갠 뒤, 특정 시기에만 반등 패턴이 먹힌 것은 아닌지 확인합니다.</p>
            <p style="color:#7C3AED; font-size:12px;">모든 구간에서 승률과 수익률이 <b>일관성 있게 유지되는지</b>가 핵심입니다.</p>
        </div>
        """, unsafe_allow_html=True)

    

# ----------------------------------------------------------------------
# 메뉴 3: 시스템 사용 설명서 화면
# ----------------------------------------------------------------------
with menu_tab3:
    st.markdown("### 📖 플랫폼 이용 가이드")
    
    st.markdown("""
    본 플랫폼을 통해 관심 종목의 매수 전략을 검증하는 순서는 다음과 같습니다.
    
    #### 1단계 : 분석 대상 세팅 (좌측 패널)
    * **데이터 소스 선택**: 
        * 시스템이 잘 작동하는지 보려면 `합성 데이터`를 선택하세요.
        * 실제 종목을 분석하려면 `국내 주식`을 선택하세요.
    * **이격도 매수 임계값**: 일반적으로 20일 이동평균선 기준 하단으로 크게 이탈하는 기준점(예: 95% 이하, 92% 이하 등)을 설정합니다.
    * **종목코드 입력**: 국내 주식은 6자리 표준 코드(예: 삼성전자 `005930`, SK하이닉스 `000660`)를 입력하고 **[🚀 데이터 분석 실행]** 버튼을 누릅니다.
    
    #### 2단계 : 검증 지표 판독법 (실시간 대시보드 탭)
    1. **`통계적 유의성` 열 확인**: 가장 중요합니다. `✅ 유의함`이 떠야 우연히 오른 게 아니라는 뜻입니다. 만약 `❌ 우연일 수 있음`이 뜬다면 과거 성적이 좋았더라도 앞으로는 안 맞을 확률이 높으니 투자 대상에서 제외하십시오.
    2. **`90% 신뢰구간` 열 확인**: 하단 수치가 지나치게 마이너스(`-5%` 이하)로 내려간다면 반등하기 전에 지옥을 맛볼 수 있다는 뜻이므로, 투자 비중을 대폭 낮춰야 합니다.
    3. **`알고리즘 예측 정확도` 확인**: 이 값은 하단의 `기준 정확도`보다 높아야만 모델로서 가치가 있습니다. 만약 낮다면 이격도 외에 거래량이나 변동성이 반등을 전혀 예측하지 못하고 있음을 뜻합니다.
    """)
    st.success("💡 **핵심 요약:** 통계적 유의성이 확보되고(p<0.05), 신뢰구간 하단이 감당 가능한 수준이며, 전진 분석(Walk-forward) 결과가 일관된 전략만을 실제 트레이딩에 채택하십시오.")
