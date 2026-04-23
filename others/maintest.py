import requests
import json
from datetime import datetime, timedelta
from anthropic import Anthropic
import pandas as pd
import os
from dotenv import load_dotenv
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

client = Anthropic(api_key=claude_key)


# -------------------------
# JMAP: Get session
# -------------------------
def get_session():
    response = requests.get(JMAP_URL, headers=HEADERS)
    response.raise_for_status()
    return response.json()


# -------------------------
# JMAP: Query email IDs
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
                    "filter": {"after": date_limit, "to": "rbpro@fastmail.com", "hasAttachment": True},
                    "sort": [{"property": "receivedAt", "isAscending": False}],
                    "limit": 200
                },
                "a"
            ]
        ]
    }

    response = requests.post(api_url, headers=HEADERS, data=json.dumps(body))
    response.raise_for_status()
    data = response.json()

    return data["methodResponses"][0][1]["ids"]


# -------------------------
# JMAP: Fetch email details
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
                    ],
                    "fetchAllBodyValues": True
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
# EXTRACTION DU CORPS TEXTE
# -------------------------
def extract_body(mail):
    body = ""
    text_body = mail.get("textBody", [])
    body_values = mail.get("bodyValues", {})

    for part in text_body:
        part_id = part.get("partId")
        if not part_id:
            continue
        value = body_values.get(part_id, {}).get("value", "")
        if isinstance(value, str):
            body += value

    return body


# -------------------------
# CLAUDE: Extract interview info
# -------------------------
def extract_with_claude(text):
    prompt = f"""
Tu es un extracteur d'informations spécialisé dans les mails d'entretien.

TA MISSION :
1. Déterminer si ce mail correspond à un entretien (interview, meeting RH, screening, échange technique, visio, Teams, Google Meet, Zoom, etc.)
2. Si OUI, extraire les informations suivantes :
   - esn : nom de l'ESN si identifiable (ex: Alten, SII, Extia, etc.)
   - client : nom du client final si identifiable (ex: Amadeus, Symphony, Airbus)
   - date : date et heure du rendez-vous (si présent dans le mail)
   - poste : intitulé du poste (ex: QA Lead, QA Automation Engineer)
   - source : "subject", "sender", "signature", "body", "calendar" (liste des sources utilisées)

3. Si NON, renvoyer uniquement :
   {{"is_interview": false}}

COMMENT DÉTECTER UN ENTRETIEN :
- Le sujet contient : entretien, interview, meeting, échange, discussion, call, visio, rdv, rendez-vous
- Le mail contient une invitation calendrier : "When", "Where", "Microsoft Teams", "Google Meet"
- Le mail contient un créneau horaire : "3:00 PM – 4:00 PM", "14h-15h"
- Le mail contient des phrases typiques : "je vous propose un entretien", "call de recrutement", "échange technique"

COMMENT IDENTIFIER L'ESN :
- Le domaine email du sender (ex: xx@sii.fr → ESN = SII)
- Le nom dans la signature
- Le nom dans le sujet (ex: "Entretien - Rafik / Symphony" → client = Symphony)

COMMENT IDENTIFIER LE CLIENT :
- Souvent dans le sujet : "Entretien - Rafik / Symphony"
- Parfois dans le corps du mail
- Parfois dans la signature

FORMAT DE SORTIE :
Tu dois renvoyer STRICTEMENT du JSON valide, sans texte autour.

Si entretien détecté :
{{
  "is_interview": true,
  "esn": "...",
  "client": "...",
  "date": "...",
  "poste": "...",
  "source": ["subject", "sender", "signature"]
}}

Si pas un entretien :
{{
  "is_interview": false
}}

Voici le mail à analyser :
{text}
"""

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=200,
        messages=[{"role": "user", "content": prompt}]
    )
    # print("RAW CLAUDE RESPONSE:", response)
    # print("RAW CLAUDE TEXT:", response.content[0].text)

    raw = response.content[0].text

    # Nettoyage JSON
    cleaned = raw.strip().replace("```json", "").replace("```", "").strip()
    # print(cleaned)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
        else:
            return {"is_interview": False}

    except Exception as e:
        print("JSON parsing failed:", e)
        print("RAW:", raw)
        return {"is_interview": False}


# -------------------------
# DEDOUBLONNAGE PAR ENTREPRISE
# -------------------------
def deduplicate(rows):
    unique = {}
    for row in rows:
        if not row.get("is_interview"):
            continue

        key = row.get("client") or row.get("esn")
        if not key:
            continue

        if key not in unique:
            unique[key] = row

    return list(unique.values())


def normalize_for_dataframe(rows):
    clean = []
    for row in rows:
        fixed = {}
        for k, v in row.items():
            if isinstance(v, (list, tuple)):
                fixed[k] = ", ".join(str(x) for x in v)
            elif hasattr(v, 'tolist'):  # catches numpy arrays
                fixed[k] = ", ".join(str(x) for x in v.tolist())
            else:
                fixed[k] = v
        clean.append(fixed)
    return clean


def export_excel(rows, filename="entretiens.xlsx"):
    clean = []
    for row in rows:
        fixed = {}
        for k, v in row.items():
            if k == "source":
                continue
            elif k == "date" and v:
                fixed[k] = v[:10]
            elif isinstance(v, list):
                fixed[k] = ", ".join(str(x) for x in v)
            elif v is None:
                fixed[k] = ""
            else:
                fixed[k] = v
        clean.append(fixed)

    df_new = pd.DataFrame(clean)

    # # Append to existing file if it exists
    # if os.path.exists(filename):
    #     df_existing = pd.read_excel(filename)
    #     df_combined = pd.concat([df_existing, df_new], ignore_index=True)
    #     df_combined = df_combined.drop_duplicates(subset=["client", "date"], keep="last")
    # else:
    #     df_combined = df_new

    df_new.to_excel(filename, index=False)
    print(f"Excel généré : {filename}")


# -------------------------
# MAIN PIPELINE
# -------------------------
def main():
    session = get_session()
    api_url = session["apiUrl"]
    account_id = session["primaryAccounts"]["urn:ietf:params:jmap:mail"]

    email_ids = query_emails(api_url, account_id)
    emails = fetch_emails(api_url, account_id, email_ids)

    extracted = []

    for mail in emails:
        subject = mail.get("subject", "")
        sender = mail.get("from", [{}])[0].get("email", "")
        date = mail.get("receivedAt", "")
        body = extract_body(mail)

        full_text = f"Subject: {subject}\nFrom: {sender}\nDate: {date}\n\n{body}"

        info = extract_with_claude(full_text)
        if info.get("is_interview"):
            extracted.append(info)

    deduped = deduplicate(extracted)
    export_excel(deduped)


def old_main():
    print("Connecting to FastMail JMAP…")

    # 1. Session
    session = get_session()
    api_url = session["apiUrl"]
    account_id = session["primaryAccounts"]["urn:ietf:params:jmap:mail"]

    # 2. Query email IDs
    email_ids = query_emails(api_url, account_id, days=90)
    print(f"Found {len(email_ids)} emails in last 90 days")

    if not email_ids:
        print("No emails found.")
        return

    # 3. Fetch email details
    emails = fetch_emails(api_url, account_id, email_ids)

    extracted_rows = []

    # 4. Process each email with Claude
    for mail in emails:
        subject = mail.get("subject", "")
        sender = mail.get("from", [{}])[0].get("email", "")
        date = mail.get("receivedAt", "")

        # Fixed body extraction
        body = ""
        text_body = mail.get("textBody", [])
        body_values = mail.get("bodyValues", {})

        for part in text_body:
            part_id = part.get("partId")
            if part_id and part_id in body_values:
                value = body_values[part_id].get("value", "")
                if isinstance(value, str):
                    body += value

        full_text = (
            f"Subject: {subject}\n"
            f"From: {sender}\n"
            f"Date: {date}\n\n"
            f"{body}"
        )

        # print(full_text)
        try:
            extracted = extract_with_claude(full_text)
            # print("claude:  "+extracted)
        except Exception as e:
            print("Claude extraction error:", e)
            continue

        extracted_rows.append(extracted)

    # 5. Export to Excel
    # -------------------------
    # REMOVE DUPLICATES
    # -------------------------
    cleaned_rows = []
    for row in extracted_rows:
        if isinstance(row, dict):
            cleaned_rows.append(row)
        else:
            print("⚠️ Skipping non-dict row:", row)

    unique = {}

    for row in cleaned_rows:
        # skip non-interview mails
        if not row.get("is_interview"):
            continue

        # priority: client > esn
        key = row.get("client") or row.get("esn")

        # if no identifier, skip
        if not key:
            continue

        # keep only the first occurrence
        if key not in unique:
            unique[key] = row

    deduped_rows = list(unique.values())

    # -------------------------
    # EXPORT TO EXCEL
    # -------------------------
    # final_rows = [sanitize(r) for r in deduped_rows if isinstance(r, dict)]
    df = pd.DataFrame(deduped_rows)
    df.to_excel("entretiens.xlsx", index=False)

    print(f"{len(deduped_rows)} unique interviews exported.")


# -------------------------
# ENTRY POINT
# -------------------------
if __name__ == "__main__":
    print("Connexion à FastMail JMAP…")
    main()
