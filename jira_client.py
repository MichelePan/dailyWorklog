import requests
from requests.auth import HTTPBasicAuth
from datetime import datetime, date, time

HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}

def get_all_worklog_ids_since(base_url: str, auth: HTTPBasicAuth, since_ms: int):
    worklog_ids = []
    url = f"{base_url}/worklog/updated"
    params = {"since": since_ms}

    while True:
        r = requests.get(url, headers=HEADERS, params=params, auth=auth, timeout=60)
        r.raise_for_status()
        data = r.json()

        values = data.get("values", [])
        worklog_ids.extend([v["worklogId"] for v in values])

        # Jira: lastPage True/False (può variare), gestiamo robusto
        if data.get("lastPage") is True:
            break

        until = data.get("until")
        if not until:
            break
        params["since"] = until

    return worklog_ids

def get_worklogs_details(base_url: str, auth: HTTPBasicAuth, worklog_ids, chunk_size=1000):
    all_worklogs = []
    for i in range(0, len(worklog_ids), chunk_size):
        chunk = worklog_ids[i:i + chunk_size]
        url = f"{base_url}/worklog/list"
        payload = {"ids": chunk}
        r = requests.post(url, headers=HEADERS, json=payload, auth=auth, timeout=60)
        r.raise_for_status()
        all_worklogs.extend(r.json())
    return all_worklogs

def get_issue_key_and_summary(base_url: str, auth: HTTPBasicAuth, issue_id: str):
    url = f"{base_url}/issue/{issue_id}"
    r = requests.get(url, headers=HEADERS, auth=auth, timeout=60)
    r.raise_for_status()
    data = r.json()
    return data["key"], data["fields"]["summary"]

def fetch_worklogs_for_day(jira_domain: str, email: str, api_token: str, day: date):
    base_url = f"https://{jira_domain}/rest/api/3"
    auth = HTTPBasicAuth(email, api_token)

    since_datetime = datetime.combine(day, time.min)
    since_ms = int(since_datetime.timestamp() * 1000)

    worklog_ids = get_all_worklog_ids_since(base_url, auth, since_ms)
    if not worklog_ids:
        return []

    worklogs = get_worklogs_details(base_url, auth, worklog_ids)

    issue_map = {}
    rows = []

    for wl in worklogs:
        started = datetime.strptime(wl["started"][:10], "%Y-%m-%d").date()
        if started != day:
            continue

        author = wl["author"]["displayName"]
        issue_id = wl["issueId"]
        hours = round(wl["timeSpentSeconds"] / 3600, 2)

        if issue_id not in issue_map:
            try:
                key, summary = get_issue_key_and_summary(base_url, auth, issue_id)
                issue_map[issue_id] = (key, summary)
            except Exception:
                issue_map[issue_id] = (f"UNKNOWN-{issue_id}", "")

        key, summary = issue_map[issue_id]
        rows.append({
            "Utente": author,
            "TaskKey": key,
            "Summary": summary,
            "Ore": hours
        })

    return rows
