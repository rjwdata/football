# ---- PERSONNEL EXPLORER ------------------------------------------------------
import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

st.header("🧩 Personnel Explorer")

if "df" not in locals():
    # if you're using a saved CSV, replace this with your load
    try:
        df = pd.read_csv("plays.csv")
    except FileNotFoundError:
        df = pd.DataFrame(columns=["TeamSide","Personnel","PlayType","Down","Distance","ResultYards","Success"])

# --- UI: choose side & personnel
colA, colB = st.columns(2)
side = colA.selectbox("Team Side", ["Offense","Defense"])
# show only personnel seen for selected side
personnel_options = sorted(df.loc[df["TeamSide"]==side, "Personnel"].dropna().astype(str).unique().tolist())
default_personnel = personnel_options[0] if personnel_options else "11"
personnel = colB.selectbox("Personnel Grouping", options=personnel_options or ["11"], index=0)

# --- helper: parse personnel string like "11", "12", "21", "10"
def parse_personnel(tag: str):
    s = str(tag).strip()
    if len(s) == 1:  # allow "1" -> "10" style mistakes
        s = s + "0"
    rb = int(s[0])
    te = int(s[1])
    wr = 5 - (rb + te)  # QB + 5 OL are fixed; 5 skill = RB+TE+WR
    wr = max(0, wr)
    return rb, te, wr

# --- helper: draw a simple diagram
def draw_personnel_diagram(tag: str):
    rb, te, wr = parse_personnel(tag)

    # field canvas
    fig, ax = plt.subplots(figsize=(6, 3.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 53.3)
    ax.axis("off")

    # hash marks (light)
    for y in [18.2, 35.1]:
        ax.plot([10, 90], [y, y], linewidth=1, alpha=0.2)

    # OL (five white dots across middle)
    ol_x = np.linspace(44, 56, 5)
    for x in ol_x:
        ax.scatter(x, 26.65, s=220, edgecolors="black", facecolors="white")
    ax.text(50, 26.65+6, "OL", ha="center", va="bottom")

    # QB
    ax.scatter(50, 21, s=220, edgecolors="black", facecolors="white")
    ax.text(50, 21-3, "QB", ha="center", va="top")

    # Place TEs (Y/H) tight to each side first
    te_spots = []
    if te >= 1:
        te_spots.append((58, 26.65))  # right TE (Y)
    if te >= 2:
        te_spots.append((42, 26.65))  # left TE (H)
    for i, (x, y) in enumerate(te_spots):
        ax.scatter(x, y+4.5, s=220, edgecolors="black", facecolors="white")
        ax.text(x, y+4.5+2.5, "TE" if i == 0 else "TE/H", ha="center")

    # WRs: spread them wide (X/Z/slot)
    wr_locs = [(30, 26.65+6.5), (70, 26.65+6.5), (60, 26.65+14)]
    for i in range(min(wr, 3)):
        x, y = wr_locs[i]
        ax.scatter(x, y, s=220, edgecolors="black", facecolors="white")
        ax.text(x, y+2.5, "WR", ha="center")
    # if >3 WR, drop extra into trips bunch area
    extra = wr - 3
    for i in range(max(0, extra)):
        x, y = 64 + i*3, 26.65+12 - i*2
        ax.scatter(x, y, s=220, edgecolors="black", facecolors="white")
        ax.text(x, y+2.5, "WR", ha="center")

    # RBs: depth behind QB (HB/FB)
    rb_locs = [(50, 16), (46, 18)]
    for i in range(min(rb, 2)):
        x, y = rb_locs[i]
        ax.scatter(x, y, s=220, edgecolors="black", facecolors="white")
        ax.text(x, y-2.5, "RB" if i == 0 else "FB", ha="center", va="top")

    # title
    ax.text(50, 52, f"{tag} PERSONNEL  (WR {wr} / TE {te} / RB {rb})", ha="center", fontsize=12, fontweight="bold")
    return fig

# --- TENDENCY TABLES/CHARTS
mask = (df["TeamSide"] == side) & (df["Personnel"].astype(str) == str(personnel))
sub = df.loc[mask].copy()

st.subheader("Diagram")
fig = draw_personnel_diagram(personnel)
st.pyplot(fig, use_container_width=True)

st.subheader("Tendencies")
if sub.empty:
    st.info("No plays logged for this personnel yet.")
else:
    # normalize text columns
    sub["PlayType"] = sub["PlayType"].astype(str).str.strip().str.title()

    total = len(sub)
    run_like = sub["PlayType"].str.contains("Run|Rpo")  # treat RPO as run-like for ratio
    pass_like = ~run_like

    metrics = {
        "Plays": total,
        "Run %": round(100*run_like.mean(), 1),
        "Pass %": round(100*pass_like.mean(), 1),
        "Success Rate %": round(100*sub["Success"].mean(), 1) if "Success" in sub else np.nan,
        "Avg Yards": round(sub["ResultYards"].mean(), 2) if "ResultYards" in sub else np.nan,
        "Explosive Rate %": round(100*np.mean(
            ((sub["ResultYards"] >= 10) & run_like) | ((sub["ResultYards"] >= 15) & pass_like)
        ), 1) if "ResultYards" in sub else np.nan
    }
    st.metric("Total Plays", metrics["Plays"])
    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Run %", f'{metrics["Run %"]}%')
    c2.metric("Pass %", f'{metrics["Pass %"]}%')
    c3.metric("Success Rate", f'{metrics["Success Rate %"]}%')
    c4.metric("Avg Yds", metrics["Avg Yards"])

    # PlayType breakdown
    st.write("**Play Type Breakdown**")
    type_counts = sub["PlayType"].value_counts().rename_axis("PlayType").reset_index(name="Plays")
    st.dataframe(type_counts)

    # Charts
    st.write("**Charts**")
    st.bar_chart(type_counts.set_index("PlayType"))

    by_down = sub.groupby("Down").agg(
        Plays=("Down","count"),
        SuccessRate=("Success","mean"),
        AvgYds=("ResultYards","mean")
    ).reset_index()
    by_down["SuccessRate"] = (by_down["SuccessRate"]*100).round(1)
    st.write("**By Down**")
    st.dataframe(by_down)

# ---- Add 'Personnel' to your entry form (elsewhere in your app) ---------------
# In your play entry form, include:
# personnel = st.text_input("Personnel (e.g., 11, 12, 21, 10, 22)")
# and store it in the row under the "Personnel" column.