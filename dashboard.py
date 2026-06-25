import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path

st.set_page_config(page_title="광고 대시보드", layout="wide")

st.markdown("""
<style>
[data-testid="stMetricValue"] { font-size: 1.1rem !important; }
[data-testid="stMetricLabel"] { font-size: 0.75rem !important; }
</style>
""", unsafe_allow_html=True)

DATA_DIR = Path(r"C:\Users\MADUP\Desktop\0626클로드코드")

CHANNEL_COLORS = {"구글": "#4285F4", "메타": "#0866FF", "네이버": "#03C75A"}

# ── 데이터 로드 ───────────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def load_data():
    ch_files = sorted((DATA_DIR / "data" / "channel").glob("*.parquet"))
    af_files = sorted((DATA_DIR / "data" / "appsflyer").glob("*.parquet"))

    def read(files):
        if not files:
            return pd.DataFrame()
        return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)

    ch = read(ch_files)
    af = read(af_files)

    if ch.empty:
        return pd.DataFrame()

    ch["일"] = pd.to_datetime(ch["일"])

    if not af.empty:
        af["일"] = pd.to_datetime(af["일"])
        df = pd.merge(ch, af, on=["일", "캠페인", "그룹", "소재"], how="left",
                      suffixes=("_ch", "_af"))
        df = df.rename(columns={"클릭_ch": "클릭", "회원가입_ch": "회원가입",
                                  "구매_ch": "구매", "구매매출_ch": "구매매출"})
    else:
        df = ch.copy()

    df["소재타입"] = df["소재"].str.extract(r"^(VID|IMG|CRS|TXT)_")
    df["AB"] = df["소재"].str.extract(r"_(A|B)_v\d+$").fillna("단독")
    return df


df = load_data()

# ── 사이드바 ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("### 광고 대시보드")
    st.divider()

    if df.empty:
        st.error("data/ 폴더에 parquet 파일이 없습니다.")
        st.stop()

    date_min, date_max = df["일"].min().date(), df["일"].max().date()
    date_range = st.date_input("날짜 범위", [date_min, date_max],
                                min_value=date_min, max_value=date_max)

    channels = st.multiselect("채널", ["구글", "메타", "네이버"],
                               default=["구글", "메타", "네이버"])

    st.divider()
    if st.button("데이터 새로고침", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# ── 필터 적용 ─────────────────────────────────────────────────────────────────

d0 = pd.to_datetime(date_range[0])
d1 = pd.to_datetime(date_range[-1])
fdf = df[(df["일"] >= d0) & (df["일"] <= d1)]
if channels:
    fdf = fdf[fdf["채널"].isin(channels)]

# ── 탭 ───────────────────────────────────────────────────────────────────────

tab1, tab2 = st.tabs(["오늘의 요약", "최적화 레이더"])

# ════════════════════════════════════════════════════════
# TAB 1: 오늘의 요약
# ════════════════════════════════════════════════════════

with tab1:
    latest_date = fdf["일"].max()
    yesterday = fdf[fdf["일"] == latest_date]

    st.caption(f"전날 성과 — {latest_date.strftime('%Y년 %m월 %d일')}")

    # ── 채널별 카드 ───────────────────────────────────────────────────────────

    ch_cols = st.columns(len(channels)) if channels else st.columns(1)

    for i, ch in enumerate(channels):
        ch_data = yesterday[yesterday["채널"] == ch]
        cost    = ch_data["비용"].sum()
        revenue = ch_data["구매매출"].sum()
        purchase = ch_data["구매"].sum()
        roas    = (revenue / cost * 100) if cost else 0
        cpa     = (cost / purchase) if purchase else 0

        roas_color = "#1D9E75" if roas >= 600 else ("#EF9F27" if roas >= 300 else "#D85A30")
        dot_color  = CHANNEL_COLORS.get(ch, "#888")

        with ch_cols[i]:
            st.markdown(f"""
            <div style="border:0.5px solid rgba(0,0,0,0.1);border-radius:12px;padding:14px 16px;
                        background:var(--background-color, #fff)">
              <div style="font-size:13px;font-weight:500;margin-bottom:10px;display:flex;align-items:center;gap:6px;">
                <span style="width:8px;height:8px;border-radius:50%;background:{dot_color};display:inline-block;"></span>
                {ch}
              </div>
              <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:0.5px solid rgba(0,0,0,0.07);">
                <span style="font-size:11px;color:gray;">비용</span>
                <span style="font-size:13px;font-weight:500;">₩{cost:,.0f}</span>
              </div>
              <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:0.5px solid rgba(0,0,0,0.07);">
                <span style="font-size:11px;color:gray;">ROAS</span>
                <span style="font-size:13px;font-weight:500;color:{roas_color};">{roas:,.0f}%</span>
              </div>
              <div style="display:flex;justify-content:space-between;padding:5px 0;border-bottom:0.5px solid rgba(0,0,0,0.07);">
                <span style="font-size:11px;color:gray;">구매</span>
                <span style="font-size:13px;font-weight:500;">{purchase:,.0f}건</span>
              </div>
              <div style="display:flex;justify-content:space-between;padding:5px 0;">
                <span style="font-size:11px;color:gray;">CPA</span>
                <span style="font-size:13px;font-weight:500;">₩{cpa:,.0f}</span>
              </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 추이 차트 ─────────────────────────────────────────────────────────────

    daily_ch = (fdf.groupby(["일", "채널"])
                .agg(비용=("비용", "sum"), 구매매출=("구매매출", "sum"), 구매=("구매", "sum"))
                .reset_index())
    daily_ch["ROAS"] = (daily_ch["구매매출"] / daily_ch["비용"] * 100).round(1)
    daily_ch = daily_ch[daily_ch["채널"].isin(channels)]

    col1, col2 = st.columns(2)

    with col1:
        fig_roas = px.line(daily_ch, x="일", y="ROAS", color="채널",
                           color_discrete_map=CHANNEL_COLORS,
                           markers=True, title="최근 ROAS 추이")
        fig_roas.update_layout(height=260, margin=dict(t=36, b=20, l=0, r=0),
                               legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                               xaxis_title="", yaxis_title="ROAS (%)")
        fig_roas.update_traces(line=dict(width=2), marker=dict(size=5))
        st.plotly_chart(fig_roas, use_container_width=True)

    with col2:
        fig_cost = px.line(daily_ch, x="일", y="비용", color="채널",
                           color_discrete_map=CHANNEL_COLORS,
                           markers=True, title="최근 비용 추이")
        fig_cost.update_layout(height=260, margin=dict(t=36, b=20, l=0, r=0),
                               legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
                               xaxis_title="", yaxis_title="비용 (₩)")
        fig_cost.update_traces(line=dict(width=2), marker=dict(size=5))
        st.plotly_chart(fig_cost, use_container_width=True)


# ════════════════════════════════════════════════════════
# TAB 2: 최적화 레이더
# ════════════════════════════════════════════════════════

with tab2:

    def flag_roas(r):
        if r < 200:   return "🔴 ROAS<200%"
        if r < 400:   return "🟡 낮음"
        if r < 600:   return "🟢 양호"
        return              "✅ 최상"

    def color_roas(r):
        if r < 200:   return "color:#D85A30;font-weight:500"
        if r < 400:   return "color:#EF9F27;font-weight:500"
        return              "color:#1D9E75;font-weight:500"

    # ── 캠페인 테이블 ─────────────────────────────────────────────────────────

    st.markdown("##### 캠페인별 성과")

    cmp_agg = (fdf.groupby(["채널", "캠페인", "캠페인목적"])
               .agg(비용=("비용", "sum"), 구매매출=("구매매출", "sum"),
                    구매=("구매", "sum"), 클릭=("클릭", "sum"), 노출=("노출", "sum"))
               .reset_index())
    cmp_agg["ROAS"] = (cmp_agg["구매매출"] / cmp_agg["비용"] * 100).round(1)
    cmp_agg["CPA"]  = (cmp_agg["비용"] / cmp_agg["구매"]).round(0)
    cmp_agg["CTR"]  = (cmp_agg["클릭"] / cmp_agg["노출"] * 100).round(2)
    cmp_agg = cmp_agg.sort_values("ROAS")

    cmp_display = cmp_agg[["채널", "캠페인", "캠페인목적", "비용", "ROAS", "CPA", "구매"]].copy()
    cmp_display["상태"] = cmp_agg["ROAS"].apply(flag_roas)
    cmp_display["비용"] = cmp_display["비용"].apply(lambda x: f"₩{x:,.0f}")
    cmp_display["ROAS"] = cmp_display["ROAS"].apply(lambda x: f"{x:,.0f}%")
    cmp_display["CPA"]  = cmp_display["CPA"].apply(lambda x: f"₩{x:,.0f}")
    cmp_display["구매"] = cmp_display["구매"].apply(lambda x: f"{x:,.0f}건")
    cmp_display = cmp_display.rename(columns={"캠페인목적": "목적"})

    st.dataframe(cmp_display.reset_index(drop=True), use_container_width=True, hide_index=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 소재 테이블 ───────────────────────────────────────────────────────────

    st.markdown("##### 소재별 성과 — ROAS 낮은 순")

    cr_agg = (fdf.groupby(["채널", "소재타입", "소재", "AB"])
              .agg(비용=("비용", "sum"), 구매매출=("구매매출", "sum"),
                   구매=("구매", "sum"), 노출=("노출", "sum"), 클릭=("클릭", "sum"))
              .reset_index())
    cr_agg["ROAS"] = (cr_agg["구매매출"] / cr_agg["비용"] * 100).round(1)
    cr_agg["CPA"]  = (cr_agg["비용"] / cr_agg["구매"]).round(0)
    cr_agg["CTR"]  = (cr_agg["클릭"] / cr_agg["노출"] * 100).round(2)
    cr_agg = cr_agg[cr_agg["노출"] >= 1000]  # 노출 1천 미만 제외
    cr_agg = cr_agg.sort_values("ROAS")

    cr_display = cr_agg[["채널", "소재타입", "소재", "AB", "노출", "비용", "ROAS", "CPA", "구매"]].copy()
    cr_display["상태"] = cr_agg["ROAS"].apply(flag_roas)
    cr_display["노출"] = cr_display["노출"].apply(lambda x: f"{x:,.0f}")
    cr_display["비용"] = cr_display["비용"].apply(lambda x: f"₩{x:,.0f}")
    cr_display["ROAS"] = cr_display["ROAS"].apply(lambda x: f"{x:,.0f}%")
    cr_display["CPA"]  = cr_display["CPA"].apply(lambda x: f"₩{x:,.0f}")
    cr_display["구매"] = cr_display["구매"].apply(lambda x: f"{x:,.0f}건")

    st.dataframe(cr_display.reset_index(drop=True), use_container_width=True, hide_index=True)

    st.caption("※ 노출 1,000 미만 소재는 통계 유의성 부족으로 제외")
