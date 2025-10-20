import os, json

FILTERS_FILE = "saved_filters.json"

def load_filters():
    if not os.path.exists(FILTERS_FILE):
        return {}
    try:
        with open(FILTERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_filter(name, data):
    filters = load_filters()
    filters[name] = data
    with open(FILTERS_FILE, "w", encoding="utf-8") as f:
        json.dump(filters, f, indent=2, ensure_ascii=False)

def delete_saved_filter(name):
    filters = load_filters()
    if name in filters:
        del filters[name]
        with open(FILTERS_FILE, "w", encoding="utf-8") as f:
            json.dump(filters, f, indent=2, ensure_ascii=False)
