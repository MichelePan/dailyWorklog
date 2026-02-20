import streamlit as st
import pandas as pd
from datetime import date
import altair as alt

from jira_client import fetch_worklogs_for_range

st.set_page_config(page_title="Jira Worklog Dashboard", layout="wide")
st.title("Jira Worklog Dashboard")

# --- Secrets ---
jira_domain = st.secrets["JIRA_DOMAIN"]
email = st.secrets["JIRA_EMAIL"]
api_token = st.secrets["JIRA_API_TOKEN"]

# --- Sidebar ---
st.sidebar.header("Filtri")

default_from = date.today().replace(day=1)
date_from = st.sidebar.date_input("Dal", value=default_from)
date_to = st.sidebar.date_input("Al", value=date.today())

if date_from > date_to:
    st.sidebar.error("Intervallo non valido: 'Dal' deve essere <= 'Al'.")
    st.stop()

# opzionale: restringi per progetto o altro (consigliato per performance)
jql_extra = st.sidebar.text_input("JQL extra (opzionale)", value="")

refresh = st.sidebar.button("Aggiorna dati")

@st.cache_data(ttl=300, show_spinner=False)
def load_data(date_from: date, date_to: date, jql_extra: str):
    rows = fetch_worklogs_for_range(
        jira_domain=jira_domain,
        email=email,
        api_token=api_token,
        date_from=date_from,
        date_to=date_to,
        jql_extra=jql_extra or None,
    )
    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df["Ore"] = pd.to_numeric(df["Ore"])
    df["Data"] = pd.to_datetime(df["Data"]).dt.date  # garantisce tipo date
    return df

if refresh:
    st.cache_data.clear()

with st.spinner("Caricamento worklog da Jira..."):
    df = load_data(date_from, date_to, jql_extra)

if df.empty:
    st.info("Nessun worklog trovato nell’intervallo selezionato.")
    st.stop()

# --- Filtri post-load: Utente + Tipo (single select) ---
users = ["(tutti)"] + sorted([u for u in df["Utente"].dropna().unique().tolist() if str(u).strip() != ""])
types = ["(tutti)"] + sorted([t for t in df["Tipo"].dropna().unique().tolist() if str(t).strip() != ""])

user_sel = st.sidebar.selectbox("Utente", users)
type_sel = st.sidebar.selectbox("Tipo attività", types)

df_view = df.copy()
if user_sel != "(tutti)":
    df_view = df_view[df_view["Utente"] == user_sel]
if type_sel != "(tutti)":
    df_view = df_view[df_view["Tipo"] == type_sel]

# Ordina per data/utente/task
df_view = df_view.sort_values(["Data", "Utente", "TaskKey"])

# --- KPI ---
c1, c2, c3 = st.columns(3)
c1.metric("Totale ore", f"{df_view['Ore'].sum():.2f}")
c2.metric("N. worklog", f"{len(df_view)}")
c3.metric("N. task", f"{df_view['TaskKey'].nunique()}")

st.divider()

left, right = st.columns([2, 1])

with left:
    st.subheader("Dettaglio")

    # Mostro Data come dd/mm/YYYY
    df_show = df_view.copy()
    df_show["Data"] = pd.to_datetime(df_show["Data"]).dt.strftime("%d/%m/%Y")

    st.dataframe(df_show, use_container_width=True, hide_index=True)

    csv_bytes = df_show.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download CSV",
        data=csv_bytes,
        file_name=f"worklog_{date_from.isoformat()}_{date_to.isoformat()}.csv",
        mime="text/csv",
    )

with right:
    st.subheader("Ore per utente")
    agg = df_view.groupby("Utente", as_index=False)["Ore"].sum().sort_values("Ore", ascending=False)

    chart = (
        alt.Chart(agg)
        .mark_bar()
        .encode(
            x=alt.X("Ore:Q", title="Ore"),
            y=alt.Y("Utente:N", sort="-x", title=""),
            tooltip=["Utente", "Ore"],
        )
        .properties(height=420)
    )
    st.altair_chart(chart, use_container_width=True)
