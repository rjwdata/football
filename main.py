# app.py
import os
from datetime import datetime
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

# =========================
# CONFIG
# =========================
APP_TITLE = "🏈 Football Game Tracker"
DATA_FILE = "plays.csv"                      # used if USE_GOOGLE_SHEETS = False
GOOGLE_SHEET_NAME = "Football Plays"         # used if USE_GOOGLE_SHEETS = True
USE_GOOGLE_SHEETS = False                    # <-- set True to use Google Sheets backend

# =========================
# DATA ACCESS LAYER
# =========================
class Storage:
    def __init__(self):
        self.columns = [
            "Timestamp","Game","Opponent","TeamSide","Quarter","Down","Distance",
            "YardLine","Hash","Formation","PlayType",
            "ResultYards","Success","Notes"
        ]
        if USE_GOOGLE_SHEETS:
            self._init_gsheets()
        else:
            self._init_csv()

    # ---- CSV backend
    def _init_csv(self):
        if not os.path.exists(DATA_FILE):
            pd.DataFrame(columns=self.columns).to_csv(DATA_FILE, index=False)

    def load(self) -> pd.DataFrame:
        if USE_GOOGLE_SHEETS:
            import gspread
            from oauth2client.service_account import ServiceAccountCredentials
            scope = ["https://spreadsheets.google.com/feeds",
                     "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
            client = gspread.authorize(creds)
            sh = client.open(GOOGLE_SHEET_NAME).sheet1
            data = sh.get_all_records()
            df = pd.DataFrame(data)
            if df.empty:
                return pd.DataFrame(columns=self.columns)
            # ensure column order/superset
            for c in self.columns:
                if c not in df.columns:
                    df[c] = np.nan
            return df[self.columns]
        else:
            try:
                df = pd.read_csv(DATA_FILE)
            except FileNotFoundError:
                df = pd.DataFrame(columns=self.columns)
            # coerce types
            return df

    def append_row(self, row: dict):
        if USE_GOOGLE_SHEETS:
            import gspread
            from oauth2client.service_account import ServiceAccountCredentials
            scope = ["https://spreadsheets.google.com/feeds",
                     "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
            client = gspread.authorize(creds)
            sh = client.open(GOOGLE_SHEET_NAME).sheet1
            # Ensure header exists
            if sh.row_count == 0 or sh.row_values(1) == []:
                sh.append_row(self.columns)
            values = [row.get(c, "") for c in self.columns]
            sh.append_row(values)
        else:
            df = self.load()
            new_df = pd.DataFrame([row])
            df = pd.concat([df, new_df], ignore_index=True)
            df.to_csv(DATA_FILE, index=False)

    def overwrite(self, df: pd.DataFrame):
        df = df.copy()
        for c in self.columns:
            if c not in df.columns:
                df[c] = np.nan
        df = df[self.columns]
        if USE_GOOGLE_SHEETS:
            import gspread
            from oauth2client.service_account import ServiceAccountCredentials
            scope = ["https://spreadsheets.google.com/feeds",
                     "https://www.googleapis.com/auth/drive"]
            creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
            client = gspread.authorize(creds)
            sh = client.open(GOOGLE_SHEET_NAME).sheet1
            sh.clear()
            sh.append_row(self.columns)
            if not df.empty:
                sh.append_rows(df.values.tolist())
        else:
            df.to_csv(DATA_FILE, index=False)

storage = Storage()

# =========================
# HELPERS
# =========================
def compute_success(down: int, distance: float, gained: float) -> bool:
    if down == 1:
        return gained >= 4
    if down == 2:
        return gained >= (distance / 2.0)
    return gained >= distance  # 3rd / 4th


def explosive_mask(df):
    pt = df["PlayType"].astype(str).str.lower()
    is_runlike = pt.str.contains("run|rpo")
    return (is_runlike & (df["ResultYards"] >= 10)) | ((~is_runlike) & (df["ResultYards"] >= 15))

# =========================
# UI: SIDEBAR NAV
# =========================
st.set_page_config(page_title="Football Tracker", layout="wide")
st.title(APP_TITLE)

page = st.sidebar.radio(
    "Navigation",
    ["Data Entry", "Play Log", "Analytics", "Formation Explorer", "Admin"],
    index=0
)

df = storage.load()
# Basic cleaning
if not df.empty:
    for col in ["Quarter","Down","Distance","YardLine","ResultYards"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    if "Success" in df.columns:
        df["Success"] = df["Success"].astype(str).str.lower().isin(["true","1","yes","y","t"])

# =========================
# PAGE: DATA ENTRY
# =========================
if page == "Data Entry":
    st.subheader("Enter Play")

    with st.form("play_form", clear_on_submit=True):
        colA, colB, colC = st.columns(3)
        game = colA.text_input("Game ID / Date", value=datetime.now().strftime("%Y-%m-%d"))
        opponent = colB.text_input("Opponent", value="")
        team_side = colC.selectbox("Team Side", ["Offense", "Defense"])

        col1, col2, col3, col4 = st.columns(4)
        quarter = col1.selectbox("Quarter", [1,2,3,4])
        down = col2.selectbox("Down", [1,2,3,4])
        distance = col3.number_input("Distance to First (yds)", min_value=1, max_value=30, value=10)
        yardline = col4.number_input("Ball On (yd line, 1-99)", min_value=1, max_value=99, value=50)

        colh1, colh2, colh3 = st.columns(3)
        hash_mark = colh1.selectbox("Hash", ["Left","Middle","Right"])
        formation = colh3.number_input("Formation/Set (e.g., Trips Rt, Ace)", value = 0, min_value=0, max_value=10)

        play_type = st.selectbox("Play Type", ["Run","Pass","Screen","RPO","Play Action","Special Teams","Other"])
        result_yards = st.number_input("Result (yards gained/lost)", min_value=-50, max_value=99, value=0)
        notes = st.text_input("Notes")

        # auto success
        success_calc = compute_success(int(down), float(distance), float(result_yards))
        st.caption(f"Calculated Success: **{success_calc}**  "
                   "(1st≥4, 2nd≥½ to-go, 3rd/4th gain≥to-go)")

        submitted = st.form_submit_button("Add Play")
        if submitted:
            row = {
                "Timestamp": datetime.now().isoformat(timespec="seconds"),
                "Game": game, "Opponent": opponent, "TeamSide": team_side,
                "Quarter": int(quarter), "Down": int(down), "Distance": float(distance),
                "YardLine": int(yardline), "Hash": hash_mark,
                "Formation": int(formation), "PlayType": play_type,
                "ResultYards": float(result_yards), "Success": bool(success_calc),
                "Notes": notes.strip()
            }
            storage.append_row(row)
            st.success("✅ Play added.")

# =========================
# PAGE: PLAY LOG
# =========================
elif page == "Play Log":
    st.subheader("📋 Play Log")
    if df.empty:
        st.info("No plays yet.")
    else:
        # Filters
        fc1, fc2, fc3 = st.columns(3)
        games = ["(all)"] + sorted([x for x in df["Game"].dropna().astype(str).unique()])
        opps  = ["(all)"] + sorted([x for x in df["Opponent"].dropna().astype(str).unique()])
        sides = ["(all)","Offense","Defense"]
        gsel = fc1.selectbox("Game", games)
        osel = fc2.selectbox("Opponent", opps)
        ssel = fc3.selectbox("Side", sides)

        sub = df.copy()
        if gsel != "(all)":
            sub = sub[sub["Game"].astype(str)==gsel]
        if osel != "(all)":
            sub = sub[sub["Opponent"].astype(str)==osel]
        if ssel != "(all)":
            sub = sub[sub["TeamSide"]==ssel]

        st.dataframe(sub, use_container_width=True)

# =========================
# PAGE: ANALYTICS
# =========================
elif page == "Analytics":
    st.subheader("📊 Analytics")
    if df.empty:
        st.info("No data to analyze yet.")
    else:
        # filter by game/opponent
        c1,c2 = st.columns(2)
        game = c1.selectbox("Game", ["(all)"] + sorted(df["Game"].dropna().astype(str).unique().tolist()))
        opp  = c2.selectbox("Opponent", ["(all)"] + sorted(df["Opponent"].dropna().astype(str).unique().tolist()))
        sub = df.copy()
        if game != "(all)":
            sub = sub[sub["Game"].astype(str)==game]
        if opp != "(all)":
            sub = sub[sub["Opponent"].astype(str)==opp]

        # totals
        st.metric("Total Plays", len(sub))
        m1, m2, m3, m4 = st.columns(4)
        if len(sub):
            runlike = sub["PlayType"].astype(str).str.lower().str.contains("run|rpo")
            passlike = ~runlike
            m1.metric("Run %", f"{(runlike.mean()*100):.1f}%")
            m2.metric("Pass %", f"{(passlike.mean()*100):.1f}%")
            m3.metric("Success Rate", f"{(sub['Success'].mean()*100):.1f}%")
            m4.metric("Avg Gain", f"{sub['ResultYards'].mean():.2f}")

        # bar: play type counts
        st.write("**Play Types**")
        counts = sub["PlayType"].fillna("Unknown").value_counts()
        st.bar_chart(counts)

        # by down
        st.write("**By Down**")
        by_down = sub.groupby("Down").agg(
            Plays=("Down","count"),
            SuccessRate=("Success","mean"),
            AvgYds=("ResultYards","mean")
        ).reset_index()
        if not by_down.empty:
            by_down["SuccessRate"] = (by_down["SuccessRate"]*100).round(1)
        st.dataframe(by_down)

        # explosive rate
        if "ResultYards" in sub.columns:
            st.write("**Explosive Rate**")
            sub["Explosive"] = explosive_mask(sub)
            expl = sub["Explosive"].mean() if len(sub) else 0
            st.metric("Explosive Play Rate", f"{expl*100:.1f}%")

# =========================
# PAGE: Formation EXPLORER
# =========================
elif page == "Formation Explorer":
    st.subheader("🧩 Formation Explorer")
    if df.empty:
        st.info("No plays yet.")
    else:
        side = st.selectbox("Team Side", ["Offense","Defense"])
        options = sorted(df.loc[df["TeamSide"]==side, "Formation"].dropna().astype(str).unique().tolist())
        if not options:
            st.info(f"No Formation logged for {side}.")
        else:
            formation = st.selectbox("Formation", options, index=0)
            formation_str = str(formation).replace(" ", "_").lower()
            img_path = os.path.join("hudl_drawings", f"formation_{formation_str}.png")
            if os.path.exists(img_path):
                st.image(img_path, caption=f"Formation: {formation}", use_container_width=True)
            else:
                st.warning(f"No image found for formation '{formation}'. Expected at: {img_path}")

            # tendencies
            sub = df[(df["TeamSide"]==side) & (df["Formation"].astype(str)==str(formation))].copy()
            if sub.empty:
                st.info("No plays for this grouping yet.")
            else:
                sub["PlayType"] = sub["PlayType"].astype(str).str.strip().str.title()
                runlike = sub["PlayType"].str.contains("Run|Rpo")
                passlike = ~runlike
                total = len(sub)
                metrics = {
                    "Plays": total,
                    "Run %": round(100*runlike.mean(), 1),
                    "Pass %": round(100*passlike.mean(), 1),
                    "Success Rate %": round(100*sub["Success"].mean(), 1),
                    "Avg Yards": round(sub["ResultYards"].mean(), 2),
                    "Explosive Rate %": round(100*explosive_mask(sub).mean(), 1)
                }
                st.metric("Total Plays", metrics["Plays"])
                c1,c2,c3,c4 = st.columns(4)
                c1.metric("Run %", f'{metrics["Run %"]}%')
                c2.metric("Pass %", f'{metrics["Pass %"]}%')
                c3.metric("Success Rate", f'{metrics["Success Rate %"]}%')
                c4.metric("Avg Yds", f'{metrics["Avg Yards"]}')

                st.write("**Play Type Breakdown**")
                pt = sub["PlayType"].value_counts().rename_axis("PlayType").reset_index(name="Plays")
                st.dataframe(pt, use_container_width=True)
                st.bar_chart(pt.set_index("PlayType"))

                by_down = sub.groupby("Down").agg(
                    Plays=("Down","count"),
                    SuccessRate=("Success","mean"),
                    AvgYds=("ResultYards","mean")
                ).reset_index()
                if not by_down.empty:
                    by_down["SuccessRate"] = (by_down["SuccessRate"]*100).round(1)
                st.write("**By Down**")
                st.dataframe(by_down, use_container_width=True)



# =========================
# PAGE: ADMIN
# =========================
elif page == "Admin":
    st.subheader("🛠 Admin")
    st.write(f"Backend: **{'Google Sheets' if USE_GOOGLE_SHEETS else 'CSV file'}**")
    if not df.empty:
        st.download_button("Download CSV", df.to_csv(index=False).encode("utf-8"),
                           file_name="plays_export.csv", mime="text/csv")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Reset (clear all plays)"):
            storage.overwrite(pd.DataFrame(columns=storage.columns))
            st.success("Cleared all data.")
    with col2:
        st.caption("Make sure `.gitignore` excludes `credentials.json` if you use Google Sheets.")
