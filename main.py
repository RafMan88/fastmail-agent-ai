from datetime import datetime
import json
import os
from dotenv import load_dotenv
import argparse
from src.mail import get_session, query_emails, fetch_emails, extract_body
from src.interviews_extraction import extract_with_claude as extract_interview
from src.jobs_responses_extraction import extract_with_claude as extract_application
from src.deduplication import deduplicate
from src.export import export_excel


def main():
    load_dotenv()
    fastmail_token = os.getenv("FASTMAIL_TOKEN")
    claude_key = os.getenv("CLAUDE_API_KEY")
    raw_emails = os.getenv("FILTER_EMAILS", "")
    filter_emails = [e.strip() for e in raw_emails.replace(" ", ",").split(",") if e.strip()]
    # email_2 = os.getenv("EMAIL_2")

    if not fastmail_token or not claude_key:
        raise RuntimeError("Missing FASTMAIL_TOKEN or CLAUDE_API_KEY in .env")

    parser = argparse.ArgumentParser(description="Fastmail email extractor")
    parser.add_argument(
        "--mode",
        choices=["interviews", "applications"],
        required=True,
        help="interviews = extract interview invitations | applications = extract job application responses"
    )
    args = parser.parse_args()

    if args.mode == "interviews":
        extract_fn = extract_interview
        is_valid = lambda info: info.get("is_interview")
        filename = "data/entretiens.xlsx"
    else:
        extract_fn = extract_application
        is_valid = lambda info: info.get("is_application_response")
        filename = "data/candidatures.xlsx"

    print(f"Mode: {args.mode}")
    print("Connexion à FastMail JMAP…")
    session = get_session(fastmail_token)
    api_url = session["apiUrl"]
    account_id = session["primaryAccounts"]["urn:ietf:params:jmap:mail"]

    print(f"get emails from: {filter_emails} ")
    email_ids = query_emails(api_url, account_id, fastmail_token, filter_emails, days=90)
    print(f"NB emails : " + str(len(email_ids)))

    print(f"fetch emails :")
    emails = fetch_emails(api_url, account_id, email_ids, fastmail_token)

    print("extract data:")
    extracted = []
    for i, mail in enumerate(emails):
        subject = mail.get("subject", "")
        sender = mail.get("from", [{}])[0].get("email", "")
        date = mail.get("receivedAt", "")
        body = extract_body(mail)

        full_text = f"Subject: {subject}\nFrom: {sender}\nDate: {date}\n\n{body}"
        print(f"[{i + 1}/{len(emails)}] Analyzing: {subject[:60]} Date: {date}")
        info = extract_fn(full_text, claude_key)
        if is_valid(info):
            if args.mode == "applications":
                info["response_date"] = info.get("response_date") or date
            extracted.append(info)
            print(f"  → {info}")

    deduced = deduplicate(extracted, mode=args.mode)
    export_excel(deduced, filename=filename, mode=args.mode)
    #save extracted data
    save_cache(extracted)


def save_cache(rows):
    data = {
        "saved_at": datetime.now().isoformat(),
        "count": len(rows),
        "rows": rows
    }
    with open("data/applications.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Cache saved: data/applications.json ({len(rows)} rows)")


if __name__ == "__main__":
    main()
