import streamlit as st
import pandas as pd
import requests
from datetime import date

# =========================
# Streamlit Settings
# =========================
st.set_page_config(
    page_title="PH Regional Factor Calculator (NCR Base)",
    layout="wide"
)

# =========================
# Default Data (Official sources)
# =========================
# Minimum wage examples (Non-Agriculture daily wage)
# NCR: Php 695 (WO NCR-26) [1](https://nwpc.dole.gov.ph/ncr/)
# Region XI (Davao): Php 525 (RB XI-24) [2](https://newsinfo.inquirer.net/1672715/tougher-days-ahead-household-income-spending-falling)
DEFAULT_MIN_WAGE = {
    "National Capital Region (NCR)": 695.0,
    "Region XI - Davao Region": 525.0,
}

# FIES: PSA Table 2 (Average Annual Family Expenditure by Region, 2023p, thousand PHP)
# NCR: 385.05, Davao: 204.33, etc. [3](https://www.humanresourcesonline.net/wage-hikes-expected-for-more-than-132-000-minimum-wage-workers-in-the-philippines-in-2024)
DEFAULT_FIES_2023P_KPHP = {
    "National Capital Region (NCR)": 385.05,
    "Cordillera Administrative Region (CAR)": 247.86,
    "Region I - Ilocos Region": 232.44,
    "Region II - Cagayan Valley": 214.00,
    "Region III - Central Luzon": 298.70,
    "Region IV-A - CALABARZON": 310.32,
    "MIMAROPA Region": 189.77,
    "Region V - Bicol Region": 202.62,
    "Region VI - Western Visayas": 229.74,
    "Negros Island Region (NIR)": 203.84,
    "Region VII - Central Visayas": 218.03,
    "Region VIII - Eastern Visayas": 199.91,
    "Region IX - Zamboanga Peninsula": 200.93,
    "Region X - Northern Mindanao": 202.58,
    "Region XI - Davao Region": 204.33,
    "Region XII - SOCCSKSARGEN": 202.34,
    "Caraga": 213.12,
    "Bangsamoro Autonomous Region in Muslim Mindanao (BARMM)": 168.91,
    "Philippines (National)": 258.05,
}

# PSA OpenSTAT (PXWeb) CPI table:
# "Consumer Price Index for All Income Households by Commodity Group (2018=100)" table code 0012M4ACP09 [4](https://edgedavao.net/the-economy/2025/06/davao-region-logs-lowest-inflation-since-oct-2019/)[5](https://openstat.psa.gov.ph/PXWeb/pxweb/en/DB/search/?searchquery=2025.02.11_TB.2-4+%2820250206+-+BBE+-+draft+decision+letter%29.pdf)
OPENSTAT_PXWEB_API = "https://openstat.psa.gov.ph/PXWeb/api/v1/en/DB/DB__2M__PI__CPI__2018/0012M4ACP09.px"


# =========================
# Helpers
# =========================
def normalize_weights(w1, w2, w3):
    s = w1 + w2 + w3
    if s <= 0:
        return (0.0, 0.0, 0.0)
    return (w1 / s, w2 / s, w3 / s)

def df_from_dict(name_col, value_col, d):
    return pd.DataFrame([{name_col: k, value_col: v} for k, v in d.items()])

def lookup_value(df: pd.DataFrame, key_col: str, key, val_col: str):
    if df is None:
        return None
    m = df.loc[df[key_col] == key, val_col]
    if len(m) == 0:
        return None
    return float(m.iloc[0])

@st.cache_data(ttl=6 * 60 * 60)
def pxweb_get_metadata():
    """Fetch PXWeb table metadata. Only called when user explicitly clicks."""
    r = requests.get(OPENSTAT_PXWEB_API, timeout=30)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=6 * 60 * 60)
def pxweb_fetch_cpi(geo_code: str, year: str, period: str, commodity_code: str = "0"):
    """
    Fetch CPI value:
    Geolocation=geo_code, Commodity Description=commodity_code (0=ALL ITEMS),
    Year=year, Period=period (Jan..Dec, Ave)
    """
    payload = {
        "query": [
            {"code": "Geolocation", "selection": {"filter": "item", "values": [geo_code]}},
            {"code": "Commodity Description", "selection": {"filter": "item", "values": [commodity_code]}},
            {"code": "Year", "selection": {"filter": "item", "values": [year]}},
            {"code": "Period", "selection": {"filter": "item", "values": [period]}},
        ],
        "response": {"format": "json-stat2"}
    }
    r = requests.post(OPENSTAT_PXWEB_API, json=payload, timeout=30)
    r.raise_for_status()
    data = r.json()
    values = data.get("value", [])
    if not values:
        return None
    return float(values[0])

def best_effort_find_code(options, label_guess: str):
    """
    options: list of (code, label)
    tries exact match then contains match.
    """
    if not label_guess:
        return None
    g = label_guess.strip().lower()
    # exact
    for code, label in options:
        if label.strip().lower() == g:
            return code
    # contains
    for code, label in options:
        if g in label.strip().lower():
            return code
    return None


# =========================
# UI
# =========================
st.title("🇵🇭 Regional Factor Calculator（NCRベース）")

st.markdown(
    """
このアプリは、NCR（マニラ）を基準に **地域係数（Regional Factor）** を算出します。

- **Layer 1: 最低賃金（NWPC/DOLE）**：制度上の下限差を反映  
  例）NCR Non-Agriculture ₱695/日、Davao Region ₱525/日 [1](https://nwpc.dole.gov.ph/ncr/)[2](https://newsinfo.inquirer.net/1672715/tougher-days-ahead-household-income-spending-falling)  
- **Layer 2: FIES（PSA）**：家計支出（実額）で生活費水準差を反映  
  例）2023p 平均年間家計支出（NCR 385.05千PHP / Davao 204.33千PHP） [3](https://www.humanresourcesonline.net/wage-hikes-expected-for-more-than-132-000-minimum-wage-workers-in-the-philippines-in-2024)  
- **Layer 3: CPI（PSA OpenSTAT）**：年次更新（物価変動）を反映（手入力も可） [4](https://edgedavao.net/the-economy/2025/06/davao-region-logs-lowest-inflation-since-oct-2019/)[5](https://openstat.psa.gov.ph/PXWeb/pxweb/en/DB/search/?searchquery=2025.02.11_TB.2-4+%2820250206+-+BBE+-+draft+decision+letter%29.pdf)  

> **重要**：CPIが未取得でも、暫定で **CPIIndex=1.0（中立）** として計算できます。
"""
)

st.divider()

# =========================
# Regions and weights
# =========================
regions = sorted(set(list(DEFAULT_FIES_2023P_KPHP.keys()) + list(DEFAULT_MIN_WAGE.keys())))

col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("① Base / Target（地域）")
    base_region = st.selectbox(
        "Base（通常は NCR）",
        options=regions,
        index=regions.index("National Capital Region (NCR)") if "National Capital Region (NCR)" in regions else 0
    )
    target_region = st.selectbox(
        "Target",
        options=regions,
        index=regions.index("Region XI - Davao Region") if "Region XI - Davao Region" in regions else 0
    )

with col2:
    st.subheader("② 重み（合計=1に正規化）")
    w1 = st.number_input("Weight: Minimum Wage", 0.0, 1.0, 0.30, 0.05)
    w2 = st.number_input("Weight: FIES (Expenditure)", 0.0, 1.0, 0.50, 0.05)
    w3 = st.number_input("Weight: CPI", 0.0, 1.0, 0.20, 0.05)
    w1n, w2n, w3n = normalize_weights(w1, w2, w3)
    st.caption(f"Normalized → Wage={w1n:.2f}, FIES={w2n:.2f}, CPI={w3n:.2f}")

st.divider()

# =========================
# Data input tabs
# =========================
st.subheader("③ 入力（MW / FIES / CPI）")

tab_mw, tab_fies, tab_cpi = st.tabs(["最低賃金（MW）", "FIES支出", "CPI（OpenSTAT/手入力）"])

# ---- MW ----
with tab_mw:
    st.write("最低賃金（Non-Agriculture 日額）を入力します。NCR/Davaoのデフォルトは公式値例として搭載しています。[1](https://nwpc.dole.gov.ph/ncr/)[2](https://newsinfo.inquirer.net/1672715/tougher-days-ahead-household-income-spending-falling)")
    mw_mode = st.radio("入力方法", ["デフォルト", "手入力（Base/Target）", "CSVアップロード"], horizontal=True)

    mw_df = None
    if mw_mode == "デフォルト":
        mw_df = df_from_dict("Region", "Daily_Min_Wage", DEFAULT_MIN_WAGE)
        st.dataframe(mw_df, use_container_width=True)

        # If selected regions not in defaults, guide user
        missing = []
        if base_region not in DEFAULT_MIN_WAGE:
            missing.append(base_region)
        if target_region not in DEFAULT_MIN_WAGE:
            missing.append(target_region)
        if missing:
            st.warning(f"デフォルトMWに未登録の地域があります：{', '.join(missing)}。『手入力』か『CSV』で補完してください。")

    elif mw_mode == "手入力（Base/Target）":
        mw_base = st.number_input(f"{base_region}（日額）", value=float(DEFAULT_MIN_WAGE.get(base_region, 695.0)))
        mw_target = st.number_input(f"{target_region}（日額）", value=float(DEFAULT_MIN_WAGE.get(target_region, 525.0)))
        mw_df = pd.DataFrame([
            {"Region": base_region, "Daily_Min_Wage": mw_base},
            {"Region": target_region, "Daily_Min_Wage": mw_target},
        ])
        st.dataframe(mw_df, use_container_width=True)

    else:
        up = st.file_uploader("MW CSV（列: Region, Daily_Min_Wage）", type=["csv"])
        if up:
            mw_df = pd.read_csv(up)
            st.dataframe(mw_df, use_container_width=True)
        else:
            st.info("CSVアップロード待ちです。")

# ---- FIES ----
with tab_fies:
    st.write("FIES（PSA）の平均年間家計支出（千PHP）を使用します。2023pの地域別平均年間支出をデフォルト搭載しています。[3](https://www.humanresourcesonline.net/wage-hikes-expected-for-more-than-132-000-minimum-wage-workers-in-the-philippines-in-2024)")
    fies_mode = st.radio("入力方法", ["デフォルト（2023p）", "手入力（Base/Target）", "CSVアップロード"], horizontal=True)

    fies_df = None
    if fies_mode == "デフォルト（2023p）":
        fies_df = df_from_dict("Region", "Annual_Expenditure_kPHP", DEFAULT_FIES_2023P_KPHP)
        st.dataframe(fies_df, use_container_width=True)

    elif fies_mode == "手入力（Base/Target）":
        f_base = st.number_input(f"{base_region}（年間支出：千PHP）", value=float(DEFAULT_FIES_2023P_KPHP.get(base_region, 385.05)))
        f_target = st.number_input(f"{target_region}（年間支出：千PHP）", value=float(DEFAULT_FIES_2023P_KPHP.get(target_region, 204.33)))
        fies_df = pd.DataFrame([
            {"Region": base_region, "Annual_Expenditure_kPHP": f_base},
            {"Region": target_region, "Annual_Expenditure_kPHP": f_target},
        ])
        st.dataframe(fies_df, use_container_width=True)

    else:
        up = st.file_uploader("FIES CSV（列: Region, Annual_Expenditure_kPHP）", type=["csv"])
        if up:
            fies_df = pd.read_csv(up)
            st.dataframe(fies_df, use_container_width=True)
        else:
            st.info("CSVアップロード待ちです。")

# ---- CPI ----
with tab_cpi:
    st.write("CPIは PSA OpenSTAT（PXWeb API）から取得できます（All Items, 2018=100）。手入力運用も可能です。[4](https://edgedavao.net/the-economy/2025/06/davao-region-logs-lowest-inflation-since-oct-2019/)[5](https://openstat.psa.gov.ph/PXWeb/pxweb/en/DB/search/?searchquery=2025.02.11_TB.2-4+%2820250206+-+BBE+-+draft+decision+letter%29.pdf)")

    cpi_mode = st.radio("CPI取得方法", ["暫定（CPIIndex=1.0）", "手入力", "OpenSTATから取得"], horizontal=True)

    # default: neutral
    cpi_base_val = 1.0
    cpi_target_val = 1.0
    cpi_index_note = "CPIは暫定（中立）"

    if cpi_mode == "手入力":
        cpi_base_val = st.number_input("CPI Base（2018=100）", value=1.0)
        cpi_target_val = st.number_input("CPI Target（2018=100）", value=1.0)
        cpi_index_note = "CPIは手入力"

    elif cpi_mode == "OpenSTATから取得":
        st.info("※起動時に外部APIを叩くと不安定になりやすいので、必ずボタン押下で取得します。")

        if "px_meta" not in st.session_state:
            st.session_state.px_meta = None
            st.session_state.geo_options = None
            st.session_state.year_values = None
            st.session_state.period_values = None
            st.session_state.comm_options = None

        colL, colR = st.columns([1, 1])

        with colL:
            if st.button("① OpenSTAT メタデータ（コード表）を読み込む", type="primary"):
                try:
                    meta = pxweb_get_metadata()
                    st.session_state.px_meta = meta

                    vars_ = {v["code"]: v for v in meta.get("variables", [])}
                    geo = vars_.get("Geolocation", {})
                    year = vars_.get("Year", {})
                    period = vars_.get("Period", {})
                    comm = vars_.get("Commodity Description", {})

                    geo_codes = geo.get("values", [])
                    geo_labels = geo.get("valueTexts", geo_codes)
                    st.session_state.geo_options = list(zip(geo_codes, geo_labels))

                    st.session_state.year_values = year.get("values", [])
                    st.session_state.period_values = period.get("values", [])

                    comm_codes = comm.get("values", ["0"])
                    comm_labels = comm.get("valueTexts", comm_codes)
                    st.session_state.comm_options = list(zip(comm_codes, comm_labels))

                    st.success("メタデータ読込完了（Geolocation/Year/Period/Commodity）")
                except Exception as e:
                    st.error(f"メタデータ読込に失敗しました: {e}")

        with colR:
            st.caption("メタデータ読込後、地域コードを自動解決して取得できます（必要なら手動でコード指定も可）")

        if st.session_state.geo_options:
            # UI for year/period/commodity
            years = st.session_state.year_values or []
            periods = st.session_state.period_values or []
            comms = st.session_state.comm_options or [("0", "0 - ALL ITEMS")]

            year_sel = st.selectbox("Year", options=years, index=len(years)-1 if years else 0)
            period_sel = st.selectbox("Period（推奨: Ave=年平均）", options=periods, index=periods.index("Ave") if "Ave" in periods else 0)

            comm_map = {label: code for code, label in comms}
            comm_label_sel = st.selectbox(
                "Commodity（推奨: 0 - ALL ITEMS）",
                options=list(comm_map.keys()),
                index=list(comm_map.keys()).index("0 - ALL ITEMS") if "0 - ALL ITEMS" in comm_map else 0
            )
            comm_code_sel = comm_map[comm_label_sel]

            geo_options = st.session_state.geo_options

            # Try resolve codes by region labels
            base_code_guess = best_effort_find_code(geo_options, base_region)
            target_code_guess = best_effort_find_code(geo_options, target_region)

            st.write("### Geolocation code（自動推定）")
            c1, c2 = st.columns(2)
            with c1:
                base_geo_code = st.text_input(
                    f"Base Geolocation code（自動推定: {base_code_guess}）",
                    value=base_code_guess if base_code_guess else ""
                )
            with c2:
                target_geo_code = st.text_input(
                    f"Target Geolocation code（自動推定: {target_code_guess}）",
                    value=target_code_guess if target_code_guess else ""
                )

            if st.button("② CPIを取得（OpenSTAT）"):
                try:
                    if not base_geo_code or not target_geo_code:
                        st.error("Geolocation code が空です。メタデータ読込＆コード指定を確認してください。")
                    else:
                        cpi_base_val = pxweb_fetch_cpi(base_geo_code, year_sel, period_sel, comm_code_sel)
                        cpi_target_val = pxweb_fetch_cpi(target_geo_code, year_sel, period_sel, comm_code_sel)

                        if cpi_base_val is None or cpi_target_val is None:
                            st.warning("CPI値が取得できませんでした（データなしの可能性）。暫定=1.0で計算します。")
                            cpi_base_val, cpi_target_val = 1.0, 1.0
                            cpi_index_note = "CPI取得失敗→暫定"
                        else:
                            st.success(f"CPI取得完了：{year_sel} / {period_sel} / {comm_label_sel}")
                            cpi_index_note = f"CPI(OpenSTAT): {year_sel}-{period_sel}"
                except Exception as e:
                    st.error(f"CPI取得エラー: {e}")
                    st.warning("暫定=1.0で計算します。")
                    cpi_base_val, cpi_target_val = 1.0, 1.0
                    cpi_index_note = "CPI取得エラー→暫定"
        else:
            st.warning("まだメタデータが読み込まれていません。まず「① OpenSTAT メタデータ」を押してください。")

    else:
        st.caption("CPIは暫定（中立）として扱います。必要になったら手入力 or OpenSTAT取得に切替。")

st.divider()

# =========================
# Calculation (always visible)
# =========================
st.subheader("④ 計算結果（WageIndex / FIESIndex / CPIIndex / RegionalFactor）")

# MW
mw_base = lookup_value(mw_df, "Region", base_region, "Daily_Min_Wage") if mw_df is not None else None
mw_target = lookup_value(mw_df, "Region", target_region, "Daily_Min_Wage") if mw_df is not None else None

# FIES
f_base = lookup_value(fies_df, "Region", base_region, "Annual_Expenditure_kPHP") if fies_df is not None else None
f_target = lookup_value(fies_df, "Region", target_region, "Annual_Expenditure_kPHP") if fies_df is not None else None

missing = []
if mw_base is None: missing.append(f"最低賃金（Base: {base_region}）")
if mw_target is None: missing.append(f"最低賃金（Target: {target_region}）")
if f_base is None: missing.append(f"FIES（Base: {base_region}）")
if f_target is None: missing.append(f"FIES（Target: {target_region}）")

if missing:
    st.error("以下のデータが不足しています：\n- " + "\n- ".join(missing))
    st.info("→ MW/FIESタブで『手入力』または『CSVアップロード』に切り替えて補完してください。")
    st.stop()

# Indexes
wage_index = mw_target / mw_base
fies_index = f_target / f_base
cpi_index = (cpi_target_val / cpi_base_val) if (cpi_base_val and cpi_base_val != 0) else 1.0

# Factor
regional_factor = w1n * wage_index + w2n * fies_index + w3n * cpi_index

colA, colB, colC, colD = st.columns(4)
colA.metric("WageIndex", f"{wage_index:.4f}")
colB.metric("FIESIndex", f"{fies_index:.4f}")
colC.metric("CPIIndex", f"{cpi_index:.4f}")
colD.metric("RegionalFactor", f"{regional_factor:.4f}")
st.caption(f"Note: {cpi_index_note}")

st.divider()

# =========================
# Salary conversion
# =========================
st.subheader("⑤ 換算（Base賃金レンジ → Target賃金レンジ）")

salary_unit = st.radio("単位", ["月給", "年収（総額想定）"], horizontal=True)
c1, c2 = st.columns(2)
with c1:
    base_low = st.number_input("Baseレンジ下限", min_value=0.0, value=30000.0, step=1000.0)
with c2:
    base_high = st.number_input("Baseレンジ上限", min_value=0.0, value=40000.0, step=1000.0)

target_low = base_low * regional_factor
target_high = base_high * regional_factor

st.success(f"Targetレンジ（{salary_unit}）: {target_low:,.0f} 〜 {target_high:,.0f}")

st.divider()

# =========================
# Export
# =========================
st.subheader("⑥ 結果ダウンロード（CSV）")

result = pd.DataFrame([{
    "base_region": base_region,
    "target_region": target_region,
    "mw_base": mw_base,
    "mw_target": mw_target,
    "wage_index": wage_index,
    "fies_base_kphp": f_base,
    "fies_target_kphp": f_target,
    "fies_index": fies_index,
    "cpi_base": cpi_base_val,
    "cpi_target": cpi_target_val,
    "cpi_index": cpi_index,
    "weight_wage": w1n,
    "weight_fies": w2n,
    "weight_cpi": w3n,
    "regional_factor": regional_factor,
    "salary_unit": salary_unit,
    "base_low": base_low,
    "base_high": base_high,
    "target_low": target_low,
    "target_high": target_high,
    "as_of": str(date.today()),
}])

st.dataframe(result, use_container_width=True)

st.download_button(
    "CSVをダウンロード",
    data=result.to_csv(index=False).encode("utf-8-sig"),
    file_name="regional_factor_result.csv",
    mime="text/csv"
)
