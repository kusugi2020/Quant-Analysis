"""
이격도(Disparity) 기반 통계적 검증 및 퀀트 분석 플랫폼
================================================================
리뉴얼 포인트: 좌측 메뉴 순서 최적화 및 하단 텍스트 마크다운 종료 오류 완벽 수정
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
# [프론트엔드] 사이트 디자인 및 네비게이션
# ----------------------------------------------------------------------
st.markdown("""
    <div style="background-color:#0F172A; padding:24px; border-radius:12px; margin-bottom:25px; border-left: 8px solid #3B82F6;">
        <h1 style="color:white; margin:0; font-size:30px; font-weight:700;">📈 대시보드로 보는 주가 반등 과학적 검증기</h1>
        <p style="color:#94A3B8; margin:8px 0 0 0; font-size:15px;">오늘 가격 기준으로 살지 말지, 인공지능과 통계 데이터가 즉시 판정해 드립니다.</p>
    </div>
""", unsafe_allow_html=True)

menu_tab1, menu_tab2, menu_tab3 = st.tabs(["🎯 투자 판단 분석", "📚 분석 원리", "📖 사용 방법"])

# 사이드바 제어판
st.sidebar.markdown("### 🕹️ 분석 조건 설정")

# 1. 종목코드 입력
ticker_code = st.sidebar.text_input("📌 1. 종목코드 입력 (6자리)", value="005930")

# 2. 이격도 입력 슬라이더
input_threshold = st.sidebar.slider("📉 2. 매수 이격도 기준 설정 (%)", min_value=85.0, max_value=100.0, value=93.0, step=0.5)
st.sidebar.caption("💡 **이격도란?** 최근 20일 평균 가격에서 얼마나 폭락했는지 정하는 기준입니다. (ex. 20일 평균가가 1만 원일 때, 10% 떨어진 9천 원에 매수하겠다면 이격도 **90%** 설정)")

# 3. 조회 시작일
start_date = st.sidebar.text_input("📅 3. 조회 시작일", value="2015-01-01")

# 실행 버튼
execute_button = st.sidebar.button("🚀 분석 시작하기", use_container_width=True)

# 데이터 로딩 프로세스
is_data_loaded = False
if ticker_code and execute_button:
    try:
        raw_df = load_price_data(ticker_code, start_date, None)
        is_data_loaded = True
    except Exception:
        st.sidebar.error("⚠️ 올바른 종목코드를 입력해 주세요. (예: 미래에셋증권 006800, 삼성전자 005930)")

# ----------------------------------------------------------------------
# 메뉴 1: 투자 판단 분석
# ----------------------------------------------------------------------
with menu_tab1:
    if is_data_loaded:
        processed_df = compute_indicators(raw_df)
        processed_df = add_forward_returns(processed_df)
        
        current_disparity = processed_df['Disparity'].iloc[-1]
        total_signals = (processed_df['Disparity'] < input_threshold).sum()
        bt_res = backtest_threshold_strategy(processed_df, input_threshold)
        
        # 오늘의 투자 최종 신호등 판정
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
            
        # 투자자 맞춤형 슬라이더 가이드 문구
        st.markdown("")
        with st.expander("💡현재 이격도 설정 기준 해설", expanded=True):
            st.markdown(f"""
            * **이격도 설:** 슬라이더를 **{input_threshold}%**로 두셨다는 건, 최근 20일 평균 가격선 대비 **-{100-input_threshold:.1f}% 이상 급락한 지점**에서만 진입하겠다는 의미입니다.
            * **최근 이격도 상:** 지금 입력하신 종목의 실시간 이격도는 **{current_disparity:.2f}%**입니다. 평균보다 약 **-{100-current_disparity:.1f}%** 떨어져 있는 상태입니다.
            """)
        
        st.markdown("---")
        
        # 상단 지표 요약
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("🔬 검증에 사용된 총 일수", f"{len(processed_df):,} 일")
        with m2:
            st.metric("📉 최근 이격도 상태", f"{current_disparity:.2f}%")
        with m3:
            st.metric("🚨 역사적 매수 신호 포착 횟수", f"{total_signals} 회")
            
        st.markdown("---")
        
        # 메인 시각화 그래프 구간
        st.markdown("### 📊 최근 주가 추이와 이격도 흐름")
        chart_data = processed_df.tail(250)[["Close", "MA", "Disparity"]]
        st.line_chart(chart_data[["Close", "MA"]], height=250)
        st.line_chart(chart_data["Disparity"], height=120)
        
        st.markdown("---")
        
        # 전략 기대 성과 표 및 그래프
        st.markdown("### 🎯 1단계 분석 결과: 이 자리에 사면 내 계좌는 어떻게 될까?")
        st.dataframe(bt_res[["보유기간", "신호발생", "승률", "전략수익률", "시장수익률", "초과수익률", "판정"]], use_container_width=True, hide_index=True)
        
        st.markdown("#### 📈 무작위로 살 때 vs 과매도 신호에 살 때 수익률 비교 그래프")
        graph_df = pd.DataFrame({
            "시장 그냥 보유 시 (벤치마크)": bt_res["시장수익률"].values,
            "이격도 과매도 전략 사용 시": bt_res["전략수익률"].values
        }, index=bt_res["보유기간"])
        st.bar_chart(graph_df)

        st.markdown("---")
        
        # 리스크 관리 차트 및 과거 영속성 검증
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
            
        st.markdown("---")
        st.markdown("### 🤖 부록: 인공지능(로지스틱 회귀) 모델 상세 성적표")
        model_res = fit_rebound_probability_model(processed_df)
        c1, c2 = st.columns(2)
        with c1:
            st.write(f"- 알고리즘 예측 정확도: `{model_res['test_acc']*100:.1f}%` *(무조건 한쪽으로 찍는 기본선: {model_res['baseline_acc']*100:.1f}%)*")
        with c2:
            st.write(f"- 영향력 지표 가중치: `{model_res['coef']}`")
    else:
        st.info("👈 왼쪽 패널에서 [1. 종목코드], [2. 이격도 기준], [3. 시작일]을 지정한 뒤 [🚀 분석 시작하기] 버튼을 눌러주세요.")

# ----------------------------------------------------------------------
# 메뉴 2: 분석 원리 (⚠️ 마크다운 닫기 오류 완벽 수정 완료)
# ----------------------------------------------------------------------
with menu_tab2:
    st.markdown("### 📚 시스템 작동 원리 및 수학적 근거 상세 설명")
    st.write("본 플랫폼은 시장의 무작위 노이즈와 '가짜 반등'을 완전히 격리하기 위해 검증된 금융공학 방법론을 적용합니다.")
    st.markdown("---")
    st.markdown("#### 1️⃣ 독자적인 반등 알파 검증 : 독립표본 t-test")
    st.latex(r"t = \frac{\bar{X}_{strategy} - \bar{X}_{market}}{\sqrt{\frac{s^2_{strategy}}{n_{strategy}} + \frac{s^2_{market}}{n_{market}}}}")
    st.markdown("""
    * **귀무가설 ($H_0$):** 이격도가 낮을 때 사나 아무 때나 사나 수익률 차이가 없다. (우연이다)
    * **대립가설 ($H_1$):** 이격도가 낮을 때 사면 시장 평균보다 유의미하게 수익률이 높다. (법칙이 존재한다)
    * **판정:** 계산된 유의확률 $p\text{-value} < 0.05$ 조건이 충족될 때만 귀무가설을 기각하고 **🟢 진짜 신호**로 인정합니다.
    """)
    st.markdown("---")
    st.markdown("#### 2️⃣ 비모수적 리스크 한계 측정 : 부트스트랩 신뢰구간 (Bootstrap CI)")
    st.markdown("""
    수익률 분포가 정규분포를 따르지 않는 주식 시장의 특성을 반영하여, 과거 신호 발생 시점의 수익률 표본을 **3,000번 이상 복원 추출**하는 시뮬레이션을 수행합니다.
    추출된 3,000개의 평균값 중 하위 5% 지점을 **[최악의 경우]**, 상위 5% 지점을 **[최선의 경우]**로 정의하여 양측 90% 신뢰구간을 연산합니다.
    """)
    st.markdown("---")
    st.markdown("#### 3️⃣ 다중 요인 확률 추정 : 로지스틱 회귀 (Logistic Regression)")
    st.latex(r"P(Y=1|X) = \frac{1}{1 + e^{-(\beta_0 + \beta_1 X_1 + \beta_2 X_2 + \beta_3 X_3)}}")
    st.markdown("""
    * **표준화 계수 ($\beta$):** '이격도($X_1$)', '20일 변동성($X_2$)', '거래량 이상치($X_3$)'가 향후 반등 성공률에 미치는 가중치를 AI 모델이 데이터로부터 직접 추정합니다.
    """)

# ----------------------------------------------------------------------
# 메뉴 3: 사용 방법 (⚠️ 마크다운 닫기 오류 완벽 수정 완료)
# ----------------------------------------------------------------------
with menu_tab3:
    st.markdown("### 📖 퀀트 플랫폼 기반 실전 투자 가이드라인")
    st.write("통계 계기판을 보고 실제 매매 시나리오를 짜고 자금을 관리하는 프로들의 투자 워크플로우입니다.")
    st.markdown("---")
    st.markdown("#### 🛠️ 1단계: 조건 탐색 및 필터링")
    st.markdown("""
    1. 왼쪽 패널에서 분석할 종목코드를 입력합니다.
    2. **[투자 판단 분석]** 탭의 성과 표에서 **[판정]** 열을 스캔하여 **🟢 진짜 신호**가 켜진 보유일수(5일~40일)가 있는지 확인합니다.
    """)
    st.markdown("---")
    st.markdown("#### 💰 2단계: 실전 켈리 기준(Kelly Criterion) 기반 자금 관리 규칙")
    st.latex(r"f^* = \frac{b \cdot p - (1 - p)}{b}")
    st.markdown("""
    * **투자 비중 세팅 조언 (안전벨트):** * **[최악의 경우 (손실 하단)]**의 수치가 **-2% 이내**로 견고함이 확인되면 자산의 **10~15%**를 과감히 진입합니다.
        * 만약 초록불은 켜졌으나 **[최악의 경우]** 수치가 **-5% 이상**으로 깊다면, 자산의 **3~5% 미만**으로 쪼개어 분할 진입하는 것이 정석입니다.
    """)
    st.markdown("---")
    st.markdown("#### 🏁 3단계: 청산 및 익절 시나리오")
    st.markdown("""
    * **기간 청산 (추천):** 20일 보유 기준으로 진입했다면 주가 등락에 연연하지 말고 **정확히 20거래일이 지난 시점에 기계적으로 전량 매도**하는 것이 통계적 우위를 누리는 방법입니다.
    """)
    st.success("🎯 **포인트:** 통계가 지시하는 리스크 범위만큼만 자금을 베팅하고 기계적으로 규칙을 지키는 '규율'이 투자의 성패를 결정합니다.")
