import json
from datetime import datetime

def save_jsonl(file_path, data):
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False) + "\n")

def now_iso():
    return datetime.utcnow().isoformat()