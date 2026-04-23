import json
import time
import httpx
from anthropic import Anthropic

client = Anthropic(
    timeout=httpx.Timeout(
        connect=5.0,
        read=60.0,
        write=10.0,
        pool=5.0
    )
)


def extract_with_claude(full_text, api_key, retries=2):
    client = Anthropic(api_key=api_key)
    retries = int(retries)  # ensure it's an int
    full_text = full_text[:4000]

    prompt = f"""
    Tu es un extracteur d'informations spécialisé dans les emails de recrutement.
    You are an information extractor specialized in recruitment emails.

    ---

    ÉTAPE 1 — EST-CE UN ENTRETIEN ?
    STEP 1 — IS THIS AN INTERVIEW?

    Réponds OUI si le mail contient UN des éléments suivants :
    Answer YES if the email contains ANY of the following:

    - Un créneau horaire proposé ou confirmé / A time slot proposed or confirmed
      ex: "14h-15h", "3:00 PM – 4:00 PM", "le 16 avril à 14h", "April 16 at 2 PM"

    - Une invitation calendrier / A calendar invitation
      ex: "When:", "Quand:", "Microsoft Teams Meeting", "Google Meet", "Zoom"

    - Un verbe d'action lié à un échange / An action verb linked to a meeting
      ex: "je vous propose", "I'd like to schedule", "pouvez-vous confirmer", "can we connect"
      ex: "call de recrutement", "entretien téléphonique", "phone screen", "visio", "Teams call"

    - Un mot-clé de recrutement avec contexte de rendez-vous / A recruitment keyword with meeting context
      (FR) : entretien, échange, discussion, rendez-vous, rdv, recrutement, candidature
      (EN) : interview, meeting, call, screening, chat, hire, candidate, recruiter, opportunity

    Réponds NON si c'est uniquement :
    Answer NO if it is only:
    - Une offre d'emploi sans rendez-vous / A job offer with no meeting
    - Un email de refus / A rejection email
    - Une newsletter ou digest LinkedIn/Indeed
    - Un email de remerciement sans créneau / A thank-you with no slot

    ---

    ÉTAPE 2 — EXTRAIRE LES INFORMATIONS
    STEP 2 — EXTRACT THE INFORMATION

    ESN (société de conseil/staffing) :
    - Domaine de l'expéditeur / Sender domain : xx@sii.fr → SII, xx@alten.com → Alten
    - Nom dans la signature ou le corps / Name in signature or body
    - ESN françaises connues : Alten, SII, Extia, Capgemini, Sopra, CGI, Devoteam, Aubay, Akka, Altran, Atos, Hardis
    - Si l'expéditeur est une entreprise directe (pas ESN), mettre le même nom pour ESN et client

    CLIENT (entreprise finale) :
    - Souvent dans le sujet / Often in subject : "Entretien Rafik / Symphony" → Symphony
    - Phrases clés (FR) : "pour notre client", "chez [société]", "mission chez"
    - Phrases clés (EN) : "for our client", "with [company]", "at [company]", "end client"

    DATE :
    - Cherche un créneau explicite / Look for an explicit slot
      ex: "16 avril 2026 à 14h00" → "2026-04-16T14:00:00+02:00"
      ex: "April 16 at 2:00 PM CET" → "2026-04-16T14:00:00+02:00"
    - Format de sortie obligatoire : ISO 8601 avec timezone
    - Si plusieurs dates, prendre la première mentionnée

    POSTE :
    - Intitulé explicite / Explicit title : "QA Lead", "Data Engineer", "Product Owner"
    - Phrases clés (FR) : "pour le poste de", "mission de", "profil recherché"
    - Phrases clés (EN) : "for the role of", "position of", "we are looking for a"

    TÉLÉPHONE RH (phone) :
    - Cherche dans le corps du mail ou la signature un numéro de téléphone RH ou recrutement
      Look in the email body or signature for an HR or recruitment phone number
    - Priorité / Priority :
      1. Numéro direct RH / recrutement mentionné dans le mail
      2. Numéro dans la signature de l'expéditeur
    - Format international obligatoire / International format required : +33 1 23 45 67 89
    - Ne retourne pas un numéro de fax / Do not return a fax number
    - Si aucun numéro trouvé dans le mail, retourne null / If no number found in the email, return null

    ---

    FORMAT DE SORTIE — OUTPUT FORMAT:
    Retourne UNIQUEMENT du JSON valide, sans texte autour, sans markdown.
    Return ONLY valid JSON, no surrounding text, no markdown.

    Si entretien détecté / If interview detected:
    {{
      "is_interview": true,
      "esn": "nom ou null",
      "client": "nom ou null",
      "date": "ISO 8601 ou null",
      "poste": "intitulé ou null",
      "phone": "+33 1 23 45 67 89 ou null",
    }}

    Si pas un entretien / If not an interview:
    {{
      "is_interview": false
    }}

    ---

    EMAIL À ANALYSER / EMAIL TO ANALYZE:
    {full_text}
    """

    for attempt in range(retries + 1):
        try:
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            content = response.content[0].text.strip()
            # Nettoyage JSON
            cleaned = content.strip().replace("```json", "").replace("```", "").strip()
            # print(cleaned)
            parsed = json.loads(cleaned)
            if isinstance(parsed, dict):
                return parsed

        except httpx.ReadTimeout:
            print(f"[Attempt {attempt + 1}] Claude took too long to respond")
        except httpx.TimeoutException:
            print(f"[Attempt {attempt + 1}] Request timed out")
        except json.JSONDecodeError as e:
            print(f"[Attempt {attempt + 1}] Invalid JSON from Claude: {e}")
            return {"is_interview": False}  # no point retrying bad JSON
        except Exception as e:
            print(f"[Attempt {attempt + 1}] Unexpected error: {e}")
            return {"is_interview": False}

        if attempt < retries:
            wait = 2 ** attempt  # 1s, then 2s
            print(f"Retrying in {wait}s...")
            time.sleep(wait)

    print("All attempts failed, skipping email")
    return {"is_interview": False}


def extract_with_claude_old(full_text, api_key):
    client = Anthropic(api_key=api_key)
    prompt = f"""
    You are an expert information extractor specialized in recruitment emails and interview invitations.

    YOUR MISSION:
    1. Determine if this email relates to a job interview or recruitment step.
    2. If YES, extract the structured information below.
    3. If NO, return only: {{"is_interview": false}}

    ---

    WHAT COUNTS AS AN INTERVIEW (be broad):
    - Any job interview: technical, HR, screening, managerial, panel, cultural fit
    - Any recruitment call or video meeting: Teams, Zoom, Google Meet, Skype, phone call
    - Any recruitment step with a scheduled time: "let's connect", "I'd love to chat", "book a slot"
    - Calendar invitations related to recruitment (even without the word "interview")
    - Follow-up or confirmation emails for a scheduled interview
    - Keywords (French): entretien, échange, discussion, visio, rendez-vous, rdv, recrutement, candidature, poste, mission
    - Keywords (English): interview, meeting, call, screening, chat, opportunity, role, position, candidate, recruiter, hiring

    DO NOT flag as interview:
    - Job offer newsletters or job board digests (LinkedIn, Indeed, etc.)
    - Rejection emails with no scheduled meeting
    - General networking emails with no recruitment context

    ---

    HOW TO IDENTIFY THE ESN (staffing/consulting company):
    - Sender email domain (e.g. xx@sii.fr → ESN = SII, xx@alten.com → ESN = Alten)
    - Sender name or signature
    - Email body or subject mentioning a consulting firm
    - Common French ESNs: Alten, SII, Extia, Capgemini, Sopra, CGI, Devoteam, Aubay, Akka, Altran, Atos, Hardis

    HOW TO IDENTIFY THE CLIENT (end client company):
    - Often in subject: "Entretien - Rafik / Symphony" → client = Symphony
    - Phrases like "for our client", "pour notre client", "chez [company]", "with [company]"
    - Company name mentioned in the context of the role or mission
    - If sender is a direct company (not ESN), they may be both ESN and client

    HOW TO EXTRACT THE DATE:
    - Explicit datetime: "16 avril 2026 à 14h00", "April 16 at 2:00 PM"
    - Calendar fields: "When:", "Date:", "Quand:"
    - Time ranges: "3:00 PM – 4:00 PM", "14h-15h"
    - Relative references to avoid unless no other date: "tomorrow", "next Monday"
    - Format output as ISO 8601: "2026-04-16T14:00:00+02:00"

    HOW TO IDENTIFY THE ROLE (poste):
    - Job title in subject or body: "QA Lead", "Data Engineer", "Product Manager"
    - Phrases like "for the role of", "pour le poste de", "mission de", "position of"

    ---

    OUTPUT FORMAT:
    Return STRICTLY valid JSON, no text before or after, no markdown, no explanation.

    If interview detected:
    {{
      "is_interview": true,
      "esn": "name or null",
      "client": "name or null",
      "date": "ISO 8601 or null",
      "poste": "job title or null",
      "source": ["subject", "sender", "body", "calendar", "signature"]
    }}

    If not an interview:
    {{
      "is_interview": false
    }}

    ---

    EMAIL TO ANALYZE:
    {full_text}
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
