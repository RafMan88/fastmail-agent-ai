import json
import time
import httpx
from anthropic import Anthropic

client = Anthropic(
    timeout=httpx.Timeout(connect=5.0, read=60.0, write=10.0, pool=5.0)
)


def extract_with_claude(full_text, api_key, retries=2):
    client = Anthropic(api_key=api_key)
    retries = int(retries)  # ensure it's an int
    full_text = full_text[:4000]
    prompt = f"""
    Tu es un extracteur d'informations spécialisé dans les réponses à des candidatures d'emploi.
    You are an information extractor specialized in job application response emails.

    ---

    ÉTAPE 1 — EST-CE UNE RÉPONSE À UNE CANDIDATURE ?
    STEP 1 — IS THIS A JOB APPLICATION RESPONSE?

    COMMENT DÉTECTER UNE RÉPONSE À CANDIDATURE :
    HOW TO DETECT A JOB APPLICATION RESPONSE:

    - Le sujet contient / Subject contains :
      (FR) : candidature, poste, offre, recrutement, profil, CV, sélection, suite à votre
      (EN) : application, position, role, recruitment, resume, profile, selection, following your

    - Le corps contient une décision ou un accusé de réception / Body contains a decision or acknowledgement :
      (FR) : "nous accusons réception", "nous avons bien reçu votre candidature",
              "après étude de votre dossier", "nous avons le plaisir de",
              "nous ne sommes pas en mesure", "nous avons retenu", "nous n'avons pas retenu",
              "votre profil correspond", "votre profil ne correspond pas",
              "nous vous proposons un entretien", "nous revenons vers vous",
              "malgré l'intérêt", "d'autres candidatures", "nous vous souhaitons"
      (EN) : "we have received your application", "thank you for applying",
              "after reviewing your profile", "we are pleased to inform",
              "we regret to inform", "we will not be moving forward",
              "your profile matches", "we would like to invite you",
              "we have decided to move forward with other candidates",
              "we wish you the best"

    - L'expéditeur est un service RH ou recrutement / Sender is HR or recruitment:
      (FR) : "service recrutement", "équipe RH", "ressources humaines", "talent acquisition"
      (EN) : "recruitment team", "HR team", "human resources", "talent acquisition", "hiring team"

    RÉPONDS NON SI / ANSWER NO IF:
    - C'est une offre d'emploi sans réponse à une candidature / Job offer with no response to an application
    - C'est une newsletter ou digest LinkedIn/Indeed
    - C'est un entretien déjà planifié sans mention de candidature
    - Il n'y a aucune mention d'une candidature envoyée par Rafik

    ---

    ÉTAPE 2 — EXTRAIRE LES INFORMATIONS
    STEP 2 — EXTRACT THE INFORMATION

    RÉPONSE (response) — obligatoire / required:
      "positive" → candidature retenue, entretien proposé, intérêt exprimé, profil sélectionné
                   application accepted, interview proposed, interest expressed, profile shortlisted
      "negative" → candidature refusée, profil ne correspond pas, "nous ne sommes pas en mesure"
                   application rejected, profile does not match, "we will not be moving forward"
      "pending"  → accusé de réception sans décision / acknowledgement with no decision yet
                   "nous revenons vers vous", "we will get back to you", "under review"

    ENTREPRISE (company) :
    - Nom de l'entreprise qui répond / Name of the company responding
    - Cherche dans / Look in : signature, domaine email, corps du mail
    - ex: "Le Service Recrutement - Airbus" → Airbus
    - ex: sender = "rh@berger-levrault.com" → Berger-Levrault

    POSTE (position) :
    - Intitulé du poste mentionné / Job title mentioned
    - ex: "votre candidature au poste de QA Lead" → QA Lead
    - ex: subject = "Ingénieur QA F/H at Berger-Levrault" → Ingénieur QA
    - Phrases clés (FR) : "poste de", "offre", "mission de", "profil", "au poste"
    - Phrases clés (EN) : "role of", "position of", "job of", "opportunity for", "for the position"

    DATE DE RÉPONSE (response_date) :
    - Utilise la date du champ Date du mail / Use the email Date field
    - Format ISO 8601 : "2026-04-16T14:00:00+02:00"
    
    TÉLÉPHONE RH (phone) :
    - Cherche dans le corps du mail ou la signature un numéro de téléphone RH ou recrutement
      Look in the email body or signature for an HR or recruitment phone number
    - Priorité / Priority :
      1. Numéro direct RH / recrutement mentionné dans le mail
      2. Numéro dans la signature de l'expéditeur
    - Format international obligatoire / International format required : +33 1 23 45 67 89
    - Ne retourne pas un numéro de fax / Do not return a fax number
    - Si aucun numéro trouvé dans le mail, retourne null / If no number found in the email, return null

    COMMENTAIRE (comment) :
    - Résumé court (1 phrase) du ton et contenu / Short summary (1 sentence) of tone and content
    - ex: "Refus poli après étude du dossier, encouragements pour la suite"
    - ex: "Positive response, interview proposed for next week"
    - ex: "Accusé de réception, décision à venir"

    ---

    FORMAT DE SORTIE — OUTPUT FORMAT:
    Retourne UNIQUEMENT du JSON valide, sans texte autour, sans markdown, sans backticks.
    Return ONLY valid JSON, no surrounding text, no markdown, no backticks.

    Si réponse à candidature / If job application response:
    {{
      "is_application_response": true,
      "response": "positive | negative | pending",
      "company": "nom ou null",
      "poste": "intitulé ou null",
      "response_date": "ISO 8601 ou null",
      "phone": "+33 1 23 45 67 89 ou null",
      "comment": "résumé court ou null"
    }}

    Si pas une réponse à candidature / If not a job application response:
    {{
      "is_application_response": false
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
            raw = response.content[0].text.strip()
            print(f"DEBUG Claude raw output: '{raw[:500]}'")
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
            return {"is_application_response": False}
        except Exception as e:
            print(f"[Attempt {attempt + 1}] Unexpected error: {e}")
            return {"is_application_response": False}

        if attempt < retries:
            wait = 2 ** attempt
            print(f"Retrying in {wait}s...")
            time.sleep(wait)

    print("All attempts failed, skipping email")
    return {"is_application_response": False}