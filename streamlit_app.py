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
    st.subheader("④ 係数計算")

def lookup_value(df: pd.DataFrame, region: str, col: str):
    if df is None:
        return None
    m = df.loc[df["Region"] == region, col]
    if len(m) == 0:
        return None
    return float(m.iloc[0])

# --- MW / FIES の取得 ---
mw_base = lookup_value(mw_df, base_region, "Daily_Min_Wage") if mw_df is not None else None
mw_target = lookup_value(mw_df, target_region, "Daily_Min_Wage") if mw_df is not None else None

f_base = lookup_value(fies_df, base_region, "Annual_Expenditure_kPHP") if fies_df is not None else None
f_target = lookup_value(fies_df, target_region, "Annual_Expenditure_kPHP") if fies_df is not None else None

# --- CPI の取得（CPIが取れてなくても暫定で1.0扱いにする）---
# cpi_base_val / cpi_target_val が None の場合は中立(=1.0)として扱う
if cpi_base_val is None or cpi_target_val is None:
    cpi_base_val = 1.0
    cpi_target_val = 1.0
    st.info("CPIが未取得のため、暫定で CPIIndex=1.0（中立）として計算しています。")

# --- 計算に必要な最小条件（MWとFIESさえあれば計算できる）---
missing = []
if mw_base is None: missing.append(f"最低賃金（Base: {base_region}）")
if mw_target is None: missing.append(f"最低賃金（Target: {target_region}）")
if f_base is None: missing.append(f"FIES支出（Base: {base_region}）")
if f_target is None: missing.append(f"FIES支出（Target: {target_region}）")

if missing:
    st.error("データが不足しています：\n- " + "\n- ".join(missing))
    st.stop()

# --- 指数 ---
wage_index = mw_target / mw_base
fies_index = f_target / f_base
cpi_index = cpi_target_val / cpi_base_val

# --- 係数 ---
factor = w1n * wage_index + w2n * fies_index + w3n * cpi_index

col1, col2, col3, col4 = st.columns(4)
col1.metric("WageIndex", f"{wage_index:.4f}")
col2.metric("FIESIndex", f"{fies_index:.4f}")
col3.metric("CPIIndex", f"{cpi_index:.4f}")
col4.metric("RegionalFactor", f"{factor:.4f}")

st.markdown("### ⑤ 換算（マニラ賃金→地域賃金）")
salary_mode = st.radio("賃金入力単位", ["月給", "年収(13th含む想定)"], horizontal=True)

base_low = st.number_input("Baseレンジ下限", min_value=0.0, value=30000.0, step=1000.0)
base_high = st.number_input("Baseレンジ上限", min_value=0.0, value=40000.0, step=1000.0)

target_low = base_low * factor
target_high = base_high * factor

st.success(f"Targetレンジ（{salary_mode}）: {target_low:,.0f} 〜 {target_high:,.0f}")

out = pd.DataFrame([{
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
    "wage_weight": w1n,
    "fies_weight": w2n,
    "cpi_weight": w3n,
    "regional_factor": factor,
    "base_low": base_low,
    "base_high": base_high,
    "target_low": target_low,
    "target_high": target_high,
}])

st.download_button(
    "結果をCSVでダウンロード",
    data=out.to_csv(index=False).encode("utf-8-sig"),
    file_name="regional_factor_result.csv",
    mime="text/csv"
)
