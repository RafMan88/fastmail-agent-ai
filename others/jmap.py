import os
from dotenv import load_dotenv
import requests
import json
from datetime import datetime, timedelta

# -------------------------
# CONFIG
# -------------------------
JMAP_URL = "https://api.fastmail.com/jmap/session"

load_dotenv()
fastmail_token = os.getenv("FASTMAIL_TOKEN")
claude_key = os.getenv("CLAUDE_API_KEY")

if not fastmail_token or not claude_key:
    raise RuntimeError("Missing FASTMAIL_TOKEN or CLAUDE_API_KEY in .env")

HEADERS = {
    "Authorization": f"Bearer {fastmail_token}",
    "Content-Type": "application/json"
}
# -------------------------
# STEP 1 — Get session info
# -------------------------
def get_session():
    response = requests.get(JMAP_URL, headers=HEADERS)
    response.raise_for_status()
    return response.json()

# -------------------------
# STEP 2 — Query email IDs
# -------------------------
def query_emails(api_url, account_id, days=90):
    date_limit = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%dT00:00:00Z")

    body = {
        "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
        "methodCalls": [
            [
                "Email/query",
                {
                    "accountId": account_id,
                    "filter": {"after": date_limit, "to": "rbpro@fastmail.com"},
                    "sort": [{"property": "receivedAt", "isAscending": False}],
                    "limit": 100
                },
                "a"
            ]
        ]
    }

    response = requests.post(api_url, headers=HEADERS, data=json.dumps(body))
    response.raise_for_status()
    data = response.json()
    print (data)

    return data["methodResponses"][0][1]["ids"]

# -------------------------
# STEP 3 — Fetch email data
# -------------------------
def fetch_emails(api_url, account_id, email_ids):
    body = {
        "using": ["urn:ietf:params:jmap:core", "urn:ietf:params:jmap:mail"],
        "methodCalls": [
            [
                "Email/get",
                {
                    "accountId": account_id,
                    "ids": email_ids,
                    "properties": [
                        "id", "subject", "from", "receivedAt", "to",
                        "bodyValues", "textBody"
                    ]
                },
                "b"
            ]
        ]
    }

    response = requests.post(api_url, headers=HEADERS, data=json.dumps(body))
    response.raise_for_status()
    data = response.json()

    return data["methodResponses"][0][1]["list"]

# -------------------------
# MAIN FUNCTION
# -------------------------
def main():
    print("Connecting to FastMail JMAP…")

    # 1. Session
    session = get_session()
    api_url = session["apiUrl"]
    account_id = session["primaryAccounts"]["urn:ietf:params:jmap:mail"]
    print(session)

    # 2. Query email IDs
    email_ids = query_emails(api_url, account_id, days=90)
    print(f"Found {len(email_ids)} emails in last 90 days")

    if not email_ids:
        print("No emails found.")
        return

    # 3. Fetch email details
    emails = fetch_emails(api_url, account_id, email_ids)

    # 4. Print summary
    for mail in emails:
        #print(mail)
        subject = mail.get("subject", "")
        sender = mail.get("from", [{}])[0].get("email", "")
        receiver = mail.get("to", [{}])[0].get("email", "")
        date = mail.get("receivedAt", "")
        print(f"- {date} | {sender} | {subject} | {receiver} ")

    print("Done.")

# -------------------------
# ENTRY POINT
# -------------------------
if __name__ == "__main__":
    main()
