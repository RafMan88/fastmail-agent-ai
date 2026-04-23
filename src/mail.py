import json
import requests
from datetime import datetime, timedelta

JMAP_URL = "https://api.fastmail.com/jmap/session"


def get_session(token):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    resp = requests.get(JMAP_URL, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def query_emails(api_url, account_id, token, filter_emails=None, days=90):
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    date_limit = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")
    # Build OR conditions for emails
    email_conditions = []
    if filter_emails:
        for email in filter_emails:
            email_conditions.append({"to": email})  # or "from": email

    # Build final filter
    if len(filter_emails) > 1:
        filter_block = {
            "operator": "AND",
            "conditions": [
                {"after": date_limit},
                {
                    "operator": "OR",
                    "conditions": email_conditions
                }
            ]
        }
    elif len(filter_emails) == 1:
        filter_block = {"after": date_limit, "to":filter_emails[0]}
    else:
        # No email filter → only date filter
        filter_block = {"after": date_limit}

    body = {
        "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
        "methodCalls": [
            [
                "Email/query",
                {
                    "accountId": account_id,
                    "filter": filter_block,
                    "sort": [{"property": "receivedAt", "isAscending": False}]
                    # ,"limit": 300
                },
                "a"
            ]
        ]
    }

    resp = requests.post(api_url, headers=headers, data=json.dumps(body), timeout=30)
    resp.raise_for_status()
    data = resp.json()
    return data["methodResponses"][0][1]["ids"]


def fetch_emails(api_url, account_id, email_ids, token):
    if not email_ids:
        return []
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = {
        "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
        "methodCalls": [
            ["Email/get",
             {"accountId": account_id,
              "ids": email_ids,
              "properties": ["id", "subject", "from", "to", "receivedAt", "bodyValues", "textBody"],
              "fetchTextBodyValues": True},
             "b"]
        ]
    }
    resp = requests.post(api_url, headers=headers, data=json.dumps(body))
    resp.raise_for_status()
    data = resp.json()
    return data["methodResponses"][0][1]["list"]


def extract_body(mail):
    body = ""
    text_body = mail.get("textBody", [])
    body_values = mail.get("bodyValues", {})
    for part in text_body:
        part_id = part.get("partId")
        if part_id and part_id in body_values:
            value = body_values[part_id].get("value", "")
            if isinstance(value, str):
                body += value
    return body
