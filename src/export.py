import os

import pandas as pd
from datetime import datetime


def normalize_for_dataframe(rows):
    clean = []

    for row in rows:
        fixed = {}

        for k, v in row.items():

            # ❌ On supprime complètement "source"
            if k == "source" or k == "is_interview":
                continue

            # 🕒 Formatage propre de la date
            if k == "date" and isinstance(v, str):
                try:
                    # Support ISO avec ou sans timezone
                    dt = datetime.fromisoformat(v.replace("Z", ""))
                    v = dt.strftime("%d/%m/%Y %H:%M")
                except:
                    pass  # si Claude renvoie un format bizarre, on laisse tel quel

            # 🔄 Conversion des listes → string (ta logique d'origine)
            if isinstance(v, list):
                fixed[k] = ", ".join(str(x) for x in v)
            else:
                fixed[k] = v

        clean.append(fixed)

    return clean


def export_excel(rows, filename="data/entretiens.xlsx", mode="interviews"):
    if mode == "interviews":
        rows = normalize_for_dataframe(rows)
        df = pd.DataFrame(rows)
        df.to_excel(filename, index=False)
        print(f"Excel généré : {filename}")
    elif mode == "applications":
        clean = []
        for row in rows:
            fixed = {}
            for k, v in row.items():
                if k == "is_application_response":
                    continue
                elif k == "response_date" and v:
                    fixed[k] = v[:10]
                elif isinstance(v, list):
                    fixed[k] = ", ".join(str(x) for x in v)
                elif v is None:
                    fixed[k] = ""
                else:
                    fixed[k] = v
            clean.append(fixed)

        df_new = pd.DataFrame(clean)

        # if os.path.exists(filename):
        #     df_existing = pd.read_excel(filename, engine="openpyxl")
        #     df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        #     df_combined = df_combined.drop_duplicates(subset=["company", "poste", "response_date"], keep="last")
        # else:
        #     df_combined = df_new

        df_new.to_excel(filename, index=False, engine="openpyxl")
        print(f"Excel generated: {filename}")

