import requests
import csv
import json

URL = "https://www.questnutrition.com/collections/protein-bars-all/products.json"

headers = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36",
}

resp = requests.get(URL, headers=headers, timeout=30)
resp.encoding = "utf-8"
data = resp.json()

products = data.get("products", [])

result = []
for p in products:
    handle = p.get("handle", "")
    title = p.get("title", "")
    ids = [str(v.get("id", "")) for v in p.get("variants", [])]
    result.append({
        "handle": handle,
        "title": title,
        "id": ",".join(ids),
    })

csv_file = "第三题数据.csv"
with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["handle", "title", "id"])
    writer.writeheader()
    writer.writerows(result)

print(f"共提取 {len(result)} 个产品")
print(f"结果已保存到 {csv_file}")
print()
for r in result[:5]:
    print(f"handle={r['handle']}, title={r['title']}, id={r['id'][:60]}")
