import streamlit as st
import pandas as pd
import os
from datetime import datetime

# File to store plays
DATA_FILE = "plays.csv"

# Load or initialize dataframe
if os.path.exists(DATA_FILE):
    df = pd.read_csv(DATA_FILE)
else:
    df = pd.DataFrame(columns=[
        "Timestamp", "TeamSide", "Quarter", "Down", "Distance", "YardLine",
        "Formation", "PlayType", "ResultYards", "Success", "Notes"
    ])

st.title("🏈 Football Game Tracker")

# ---- Data Entry Form ----
st.header("Enter Play Data")

with st.form("play_form"):
    team_side = st.selectbox("Team Side", ["Offense", "Defense"])
    quarter = st.selectbox("Quarter", [1, 2, 3, 4])
    down = st.selectbox("Down", [1, 2, 3, 4])
    distance = st.number_input("Distance to First (yards)", min_value=1, max_value=30)
    yardline = st.number_input("Yard Line", min_value=1, max_value=99)
    formation = st.text_input("Formation/Personnel")
    play_type = st.selectbox("Play Type", ["Run", "Pass", "Screen", "RPO", "Special Teams", "Other"])
    result_yards = st.number_input("Result (yards gained/lost)", min_value=-20, max_value=100)
    notes = st.text_area("Notes/Comments")
    
    # Success metric
    success = False
    if down == 1 and result_yards >= 4:
        success = True
    elif down == 2 and result_yards >= distance / 2:
        success = True
    elif down in [3,4] and result_yards >= distance:
        success = True

    submitted = st.form_submit_button("Add Play")

    if submitted:
        new_play = {
            "Timestamp": datetime.now(),
            "TeamSide": team_side,
            "Quarter": quarter,
            "Down": down,
            "Distance": distance,
            "YardLine": yardline,
            "Formation": formation,
            "PlayType": play_type,
            "ResultYards": result_yards,
            "Success": success,
            "Notes": notes
        }
        df = pd.concat([df, pd.DataFrame([new_play])], ignore_index=True)
        df.to_csv(DATA_FILE, index=False)
        st.success("Play added!")

# ---- Display Table ----
st.header("📋 Play Log")
st.dataframe(df)

# ---- Charts ----
st.header("📊 Analytics")

if not df.empty:
    # Run vs Pass Breakdown
    play_counts = df["PlayType"].value_counts()
    st.subheader("Run vs Pass Distribution")
    st.bar_chart(play_counts)

    # Success by Down
    success_by_down = df.groupby("Down")["Success"].mean()
    st.subheader("Success Rate by Down")
    st.bar_chart(success_by_down)

    # Average Yards by Play Type
    avg_yards = df.groupby("PlayType")["ResultYards"].mean()
    st.subheader("Average Yards by Play Type")
    st.bar_chart(avg_yards)