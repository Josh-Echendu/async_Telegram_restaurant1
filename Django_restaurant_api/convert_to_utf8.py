# convert_to_utf8.py
import chardet

with open("data_backup.json", "rb") as f:
    raw = f.read()

# detect original encoding
result = chardet.detect(raw)
encoding = result['encoding']
print(f"Detected encoding: {encoding}")

# decode and re-save as UTF-8
text = raw.decode(encoding)
with open("data_backup_utf8.json", "w", encoding="utf-8") as f:
    f.write(text)

print("Saved UTF-8 file: data_backup_utf8.json")
# whats thie use of this useless command i want a  very short answer: createdb new_db_name
# psql -U your_db_user -d new_db_name -f backup_postgres.sql
