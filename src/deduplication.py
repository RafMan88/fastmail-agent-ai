def deduplicate(rows, mode="interviews"):
    if mode == "interviews":
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
    elif mode == "applications":
        unique = {}
        for row in rows:
            if not row.get("is_application_response"):
                continue
            key = (row.get("company"), row.get("poste"))
            if key not in unique:
                unique[key] = row
        return list(unique.values())
