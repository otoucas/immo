import json
from pathlib import Path

FILTERS_DIR = Path(__file__).parent
FILTERS_FILE = FILTERS_DIR / "saved_filters.json"

def save_filter(name: str, filter_dict: dict):
    saved = load_filters()
    saved[name] = filter_dict
    FILTERS_FILE.parent.mkdir(exist_ok=True)
    with open(FILTERS_FILE, "w", encoding="utf-8") as f:
        json.dump(saved, f, ensure_ascii=False, indent=2)

def load_filters():
    if FILTERS_FILE.exists():
        with open(FILTERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def delete_filter(name: str):
    saved = load_filters()
    if name in saved:
        del saved[name]
        with open(FILTERS_FILE, "w", encoding="utf-8") as f:
            json.dump(saved, f, ensure_ascii=False, indent=2)
