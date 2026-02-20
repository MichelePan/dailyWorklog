import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, date, time, timedelta

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}

def _jira_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")

def search_issues(base_url: str, auth: HTTPBasicAuth, jql: str, fields=None, max_results=100):
    """
    Ritorna tutte le issue che matchano la JQL (paginando).
    """
    if fields is None:
        fields = ["summary", "issuetype"]

    url = f"{base_url}/search"
    start_at = 0
    issues = []

    while True:
        payload = {
            "jql": jql,
            "startAt": start_at,
            "maxResults": max_results,
            "fields": fields
        }
        r = requests.post(url, headers=HEADERS, json=payload, auth=auth, timeout=60)
        r.raise_for_status()
        data = r.json()

        batch = data.get("issues", [])
        issues.extend(batch)

        start_at += len(batch)
        if start_at >= data.get("total", 0) or not batch:
            break

    return issues

def get_issue_worklogs(base_url: str, auth: HTTPBasicAuth, issue_key: str):
    """
    Prende TUTTI i worklog di una issue (paginando startAt/maxResults).
    """
    url = f"{base_url}/issue/{issue_key}/worklog"
    start_at = 0
    max_results = 100
    out = []

    while True:
        params = {"startAt": start_at, "maxResults": max_results}
        r = requests.get(url, headers=HEADERS, params=params, auth=auth, timeout=60)
        r.raise_for_status()
        data = r.json()

        wls = data.get("worklogs", [])
        out.extend(wls)

        start_at += len(wls)
        if start_at >= data.get("total", 0) or not wls:
            break

    return out

def fetch_worklogs_for_range(
    jira_domain: str,
    email: str,
    api_token: str,
    date_from: date,
    date_to: date,
    jql_extra: str = None
):
    """
    Estrae worklog nel range [date_from, date_to] (inclusi),
    includendo IssueType (Task/Bug/…).
    """
    base_url = f"https://{jira_domain}/rest/api/3"
    auth = HTTPBasicAuth(email, api_token)

    # JQL: prendiamo le issue che hanno worklog nel range
    jql = f'worklogDate >= "{_jira_date(date_from)}" AND worklogDate <= "{_jira_date(date_to)}"'
    if jql_extra:
        jql = f"({jql}) AND ({jql_extra})"

    issues = search_issues(base_url, auth, jql, fields=["summary", "issuetype"])
    rows = []

    for issue in issues:
        key = issue["key"]
        fields = issue.get("fields", {})
        summary = fields.get("summary", "")
        issuetype = (fields.get("issuetype") or {}).get("name", "")

        worklogs = get_issue_worklogs(base_url, auth, key)

        for wl in worklogs:
            # "started" include timezone, ma per il filtro ti basta la data YYYY-MM-DD
            started_day = datetime.strptime(wl["started"][:10], "%Y-%m-%d").date()
            if started_day < date_from or started_day > date_to:
                continue

            author = wl["author"]["displayName"]
            hours = round(wl["timeSpentSeconds"] / 3600, 2)

            rows.append({
                "Data": started_day.strftime("%d/%m/%Y"),
                "Utente": author,
                "Tipo": issuetype,          # <-- Task/Bug/…
                "TaskKey": key,
                "Summary": summary,
                "Ore": hours
            })

    return rows
