import streamlit as st
import pandas as pd
import requests
from datetime import date

st.set_page_config(page_title="PH Regional Factor Calculator", layout="wide")

# -----------------------------
# Defaults / Reference datasets
# -----------------------------

# (A) Default FIES 2023p: Average Annual Family Expenditure by Region (thousand PHP)
# Source: PSA press release (Table 2) 2018/2021/2023p. [3](https://www.humanresourcesonline.net/wage-hikes-expected-for-more-than-132-000-minimum-wage-workers-in-the-philippines-in-2024)
DEFAULT_FIES_2023P = {
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

# (B) Default Minimum Wage (daily, Non-Agriculture)
# NCR: 695 (effective 18 Jul 2025) [1](https://nwpc.dole.gov.ph/ncr/)
# Region XI Davao: 525 (effective 13 Mar 2026) [2](https://newsinfo.inquirer.net/1672715/tougher-days-ahead-household-income-spending-falling)
DEFAULT_MIN_WAGE = {
    "National Capital Region (NCR)": 695.0,
    "Region XI - Davao Region": 525.0,
}

# (C) PSA OpenSTAT CPI table endpoint (PXWeb)
# CPI for All Income Households by Commodity Group (2018=100) (e.g., 0012M4ACP09.px) [4](https://edgedavao.net/the-economy/2025/06/davao-region-logs-lowest-inflation-since-oct-2019/)[6](https://openstat.psa.gov.ph/PXWeb/pxweb/en/DB/search/?searchquery=2025.02.11_TB.2-4+%2820250206+-+BBE+-+draft+decision+letter%29.pdf)
OPENSTAT_PXWEB_API = "https://openstat.psa.gov.ph/PXWeb/api/v1/en/DB/DB__2M__PI__CPI__2018/0012M4ACP09.px"  # [4](https://edgedavao.net/the-economy/2025/06/davao-region-logs-lowest-inflation-since-oct-2019/)


# -----------------------------
# Helpers
# -----------------------------
@st.cache_data(ttl=24 * 60 * 60)
def fetch_pxweb_metadata():
    """Fetch table metadata (variables + codes) from OpenSTAT PXWeb."""
    r = requests.get(OPENSTAT_PXWEB_API, timeout=30)
    r.raise_for_status()
    return r.json()

@st.cache_data(ttl=6 * 60 * 60)
def fetch_cpi_value(geo_code: str, year: str, period: str, commodity_code: str = "0"):
    """
    Fetch CPI value for:
      Geolocation=geo_code, Commodity Description=commodity_code (0=ALL ITEMS),
      Year=year, Period=period (Jan..Dec or Ave)
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

    # json-stat2 parsing
    # value can be scalar list; we return first numeric
    values = data.get("value", [])
    if not values:
        return None
    return float(values[0])

def normalize_weights(w1, w2, w3):
    s = w1 + w2 + w3
    if s == 0:
        return (0, 0, 0)
    return (w1 / s, w2 / s, w3 / s)


# -----------------------------
# UI
# -----------------------------
st.title("🇵🇭 Regional Factor Calculator (NCR base)")

st.markdown(
    """
このツールは、**地域係数 = 最低賃金指数 + FIES(家計支出)指数 + CPI指数** を重み付けして算出します。  
- 最低賃金（NWPC）[1](https://nwpc.dole.gov.ph/ncr/)[2](https://newsinfo.inquirer.net/1672715/tougher-days-ahead-household-income-spending-falling)  
- FIES（PSA：Average Annual Family Expenditure）[3](https://www.humanresourcesonline.net/wage-hikes-expected-for-more-than-132-000-minimum-wage-workers-in-the-philippines-in-2024)  
- CPI（PSA OpenSTAT/PXWeb）[4](https://edgedavao.net/the-economy/2025/06/davao-region-logs-lowest-inflation-since-oct-2019/)[5](https://pxweb2.stat.fi/PxWeb/pxweb/en/StatFin/StatFin__khi/)  
"""
)

colA, colB = st.columns([1, 1])

with colA:
    st.subheader("① ベース地域 & 対象地域")
    base_region = st.selectbox(
        "Base (通常は NCR)",
        options=list(DEFAULT_FIES_2023P.keys()),
        index=list(DEFAULT_FIES_2023P.keys()).index("National Capital Region (NCR)")
    )
    target_region = st.selectbox(
        "Target",
        options=list(DEFAULT_FIES_2023P.keys()),
        index=list(DEFAULT_FIES_2023P.keys()).index("Region XI - Davao Region")
    )

with colB:
    st.subheader("② 重み（合計=1に正規化されます）")
    w1 = st.number_input("Weight: Minimum Wage", min_value=0.0, max_value=1.0, value=0.30, step=0.05)
    w2 = st.number_input("Weight: FIES (Expenditure)", min_value=0.0, max_value=1.0, value=0.50, step=0.05)
    w3 = st.number_input("Weight: CPI", min_value=0.0, max_value=1.0, value=0.20, step=0.05)
    w1n, w2n, w3n = normalize_weights(w1, w2, w3)
    st.caption(f"Normalized weights → Wage={w1n:.2f}, FIES={w2n:.2f}, CPI={w3n:.2f}")

st.divider()

st.subheader("③ 入力データ（最低賃金 / FIES / CPI）")

tab1, tab2, tab3 = st.tabs(["最低賃金 (MW)", "FIES支出", "CPI (OpenSTAT)"])

with tab1:
    st.write("NWPCの最低賃金（Non-Agriculture日額）を入力/CSVで管理します。[1](https://nwpc.dole.gov.ph/ncr/)[2](https://newsinfo.inquirer.net/1672715/tougher-days-ahead-household-income-spending-falling)")
    mode_mw = st.radio("入力方法", ["デフォルト（簡易）", "手入力", "CSVアップロード"], horizontal=True)

    mw_df = None
    if mode_mw == "デフォルト（簡易）":
        mw_df = pd.DataFrame([{"Region": k, "Daily_Min_Wage": v} for k, v in DEFAULT_MIN_WAGE.items()])
        st.dataframe(mw_df, use_container_width=True)

    elif mode_mw == "手入力":
        mw_base = st.number_input(f"{base_region} 日額", value=float(DEFAULT_MIN_WAGE.get(base_region, 695.0)))
        mw_target = st.number_input(f"{target_region} 日額", value=float(DEFAULT_MIN_WAGE.get(target_region, 525.0)))
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
            st.info("CSVをアップロードしてください。")

with tab2:
    st.write("PSA FIESの平均年間支出（2023p）をデフォルト搭載。必要ならCSVで差し替え可能。[3](https://www.humanresourcesonline.net/wage-hikes-expected-for-more-than-132-000-minimum-wage-workers-in-the-philippines-in-2024)")
   
