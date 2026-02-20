import streamlit as st
import pandas as pd
from datetime import date
import altair as alt

from jira_client import fetch_worklogs_for_day

st.set_page_config(page_title="Jira Daily Worklog Dashboard", layout="wide")

st.title("Jira Worklog Dashboard")

# --- Secrets / config ---
jira_domain = st.secrets["JIRA_DOMAIN"]
email = st.secrets["JIRA_EMAIL"]
api_token = st.secrets["JIRA_API_TOKEN"]

# --- Sidebar filtri ---
st.sidebar.header("Filtri")
day = st.sidebar.date_input("Giorno", value=date.today())

refresh = st.sidebar.button("Aggiorna dati")

@st.cache_data(ttl=300, show_spinner=False)
def load_data(day):
    rows = fetch_worklogs_for_day(jira_domain, email, api_token, day)
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    df["Ore"] = pd.to_numeric(df["Ore"])
    return df

if refresh:
    st.cache_data.clear()

with st.spinner("Caricamento worklog da Jira..."):
    df = load_data(day)

if df.empty:
    st.info("Nessun worklog trovato per il giorno selezionato.")
    st.stop()

# --- Filtro utente (dopo aver caricato) ---
users = ["(tutti)"] + sorted(df["Utente"].unique().tolist())
user_sel = st.sidebar.selectbox("Utente", users)

if user_sel != "(tutti)":
    df_view = df[df["Utente"] == user_sel].copy()
else:
    df_view = df.copy()

# --- KPI ---
c1, c2, c3 = st.columns(3)
c1.metric("Totale ore", f"{df_view['Ore'].sum():.2f}")
c2.metric("N. worklog", f"{len(df_view)}")
c3.metric("N. task", f"{df_view['TaskKey'].nunique()}")

st.divider()

# --- Tabelle / grafici ---
left, right = st.columns([2, 1])

with left:
    st.subheader("Dettaglio")
    st.dataframe(df_view, use_container_width=True, hide_index=True)

    csv_bytes = df_view.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download CSV",
        data=csv_bytes,
        file_name=f"worklog_{day.isoformat()}.csv",
        mime="text/csv"
    )

with right:
    st.subheader("Ore per utente")
    agg = df.groupby("Utente", as_index=False)["Ore"].sum().sort_values("Ore", ascending=False)

    chart = (
        alt.Chart(agg)
        .mark_bar()
        .encode(
            x=alt.X("Ore:Q", title="Ore"),
            y=alt.Y("Utente:N", sort="-x", title=""),
            tooltip=["Utente", "Ore"]
        )
        .properties(height=400)
    )
    st.altair_chart(chart, use_container_width=True)
