import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, date

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json",
}


def _jira_date(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def search_issues(base_url: str, auth: HTTPBasicAuth, jql: str, fields=None, max_results=100):
    """
    Ritorna tutte le issue che matchano la JQL (paginando).
    Usa POST /rest/api/3/search.
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
            "fields": fields,
        }
        r = requests.post(url, headers=HEADERS, json=payload, auth=auth, timeout=60)
        r.raise_for_status()
        data = r.json()

        batch = data.get("issues", [])
        issues.extend(batch)

        start_at += len(batch)
        total = data.get("total", 0)
        if not batch or start_at >= total:
            break

    return issues


def get_issue_worklogs(base_url: str, auth: HTTPBasicAuth, issue_key: str):
    """
    Prende tutti i worklog di una issue (paginando).
    GET /issue/{issueKey}/worklog
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
        total = data.get("total", 0)
        if not wls or start_at >= total:
            break

    return out


def fetch_worklogs_for_range(
    jira_domain: str,
    email: str,
    api_token: str,
    date_from: date,
    date_to: date,
    jql_extra: str | None = None,
):
    """
    Estrae worklog nel range [date_from, date_to] inclusi.
    Include IssueType (Bug/Task/Story/…).
    """
    base_url = f"https://{jira_domain}/rest/api/3"
    auth = HTTPBasicAuth(email, api_token)

    # Selettore robusto: prendo issue che hanno worklog nel range.
    jql = f'worklogDate >= "{_jira_date(date_from)}" AND worklogDate
