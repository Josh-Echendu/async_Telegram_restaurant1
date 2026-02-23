# detect_encoding.py
import chardet

with open("data_backup.json", "rb") as f:
    raw = f.read()

result = chardet.detect(raw)
print(result)
