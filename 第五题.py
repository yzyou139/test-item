import requests
import time




headers = {
    "accept": "application/json, text/javascript, */*; q=0.01",
    "accept-language": "zh-CN,zh;q=0.9",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "priority": "u=1, i",
    "referer": "https://match.yuanrenxue.cn/match/19",
    "sec-ch-ua": "\"Not(A:Brand\";v=\"8\", \"Chromium\";v=\"144\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 QuarkPC/6.9.5.892",
    "x-requested-with": "XMLHttpRequest"
}
cookies = {
    "Hm_lvt_f80b2b389f44bbfb3bfe1704817d44e0": "1784333759",
    "HMACCOUNT": "0C9DF7980EAA1C36",
    "sessionid": "liizsrao1brbi6hnj8tlv63q93mo6bia",
    "Hm_lpvt_f80b2b389f44bbfb3bfe1704817d44e0": "1784333809"
}
url = "https://match.yuanrenxue.cn/api/question/19"

all_data = []

max_page = 5

# for循环遍历页码
for page in range(1, max_page + 1):
    params = {
        "page": str(page),
        "pageSize": "10",
        "kw": ""
    }
    if page ==5:
        headers["user-agent"] = "yuanrenxue"


    res = requests.get(url, headers=headers, cookies=cookies, params=params)

    json_res = res.json()
    page_data = json_res.get("data", [])

    print(f"第{page}页，获取{len(page_data)}条数据")


    all_data.extend(page_data)


print(f"\n全部爬取完毕，总计{len(all_data)}条数据")
print(all_data)

total = sum(all_data)
print("所有数字相加总和：", total)
