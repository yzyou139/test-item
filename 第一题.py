
import re
import sys
import json


if sys.stdout.encoding and sys.stdout.encoding.upper() in ("GBK", "GB2312", "GB18030"):
    sys.stdout.reconfigure(encoding="utf-8")

import requests




HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "zh-CN,zh;q=0.9",
    "cache-control": "no-cache",
    "pragma": "no-cache",
    "priority": "u=0, i",
    "sec-ch-ua": '"Not(A:Brand";v="8", "Chromium";v="144"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "same-origin",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 QuarkPC/6.9.5.892",
}
COOKIES = {
    "localization": "US",
    "cart_currency": "USD",
    "_shopify_y": "9a18b6b9-c54b-4feb-986d-1fd124970f73",
    "_shopify_s": "6a54c762-72e7-44e5-8123-e101dc4d58c7",
}

PRODUCT_URL = "https://roark.com/products/mens-bless-up-breathable-stretch-shirt-fossil-print"
VARIANT_PARAMS = {"variant": "41988608098375"}


def fetch_page(url: str, params: dict | None = None) -> str:
    """爬取产品页面，返回 HTML"""
    resp = requests.get(url, headers=HEADERS, cookies=COOKIES, params=params)
    resp.raise_for_status()
    return resp.text




def _extract_balanced(raw: str, start_pos: int, open_ch: str, close_ch: str) -> str:
    """从起始位置提取配对的括号/花括号内容，正确处理字符串转义"""
    depth = 0
    in_str = False
    str_char = None
    i = start_pos
    while i < len(raw):
        ch = raw[i]
        if in_str:
            if ch == '\\':
                i += 2  # skip escaped char
                continue
            if ch == str_char:
                in_str = False
            i += 1
            continue
        if ch in '"\'':
            in_str = True
            str_char = ch
            i += 1
            continue
        if ch == open_ch:
            depth += 1
        elif ch == close_ch:
            depth -= 1
            if depth == 0:
                return raw[start_pos : i + 1]
        i += 1
    return ""


def extract_js_object(raw: str, start_pos: int) -> str:
    return _extract_balanced(raw, start_pos, '{', '}')


def extract_json_array(raw: str, start_pos: int) -> str:
    return _extract_balanced(raw, start_pos, '[', ']')


def _find_script_content(html: str) -> str:
    """找到第一个含有 product-data 的 script 标签内容"""
    # 方法1: 精确匹配 product-data=""
    for pattern in [
        r'<script\s+product-data=""[^>]*>(.*?)</script>',
        r'<script\s+product-data[^>]*>(.*?)</script>',
    ]:
        matches = re.findall(pattern, html, re.DOTALL)
        if matches:
            m = re.search(r"window\.products\['([^']+)'\]\s*=\s*", matches[0])
            if m:
                return matches[0]
    raise ValueError("未找到 product-data script 标签")


def parse_product_data(html: str) -> dict:
    """从 HTML 中解析产品数据"""
    script_content = _find_script_content(html)

    m = re.search(r"window\.products\['([^']+)'\]\s*=\s*", script_content)
    if not m:
        raise ValueError("未找到 window.products 赋值语句")

    brace_start = script_content.find('{', m.end())
    raw_js = extract_js_object(script_content, brace_start)

    if not raw_js:
        raise ValueError("未能提取完整的产品 JS 对象")

    result = {}

    # ---------- 1. 产品名称 ----------
    title_m = re.search(r'"title"\s*:\s*"([^"]+)"', raw_js)
    result["name"] = title_m.group(1) if title_m else "N/A"

    # ---------- 2. 价格 ----------
    price_m = re.search(r'"price"\s*:\s*(\d+)', raw_js)
    compare_m = re.search(r'"compare_at_price"\s*:\s*(\d+)', raw_js)
    result["price"] = int(price_m.group(1)) / 100 if price_m else 0
    result["compare_at_price"] = int(compare_m.group(1)) / 100 if compare_m else None

    # ---------- 3. 图片 ----------
    images = re.findall(r'"media_type"\s*:\s*"image"[^}]*"src"\s*:\s*"([^"]+)"', raw_js)
    BS = chr(92)
    result["images"] = [f"https:{img.replace(BS + '/', '/')}" for img in images]

    # ---------- 4. 当前颜色 ----------
    color_m = re.search(r'"color"\s*:\s*"([^"]+)"', raw_js)
    result["color"] = color_m.group(1) if color_m else "N/A"

    # ---------- 5. 选项 (Color / Size) ----------
    opt_m = re.search(r'"options_with_values"\s*:\s*(\[)', raw_js)
    if opt_m:
        opt_section = extract_json_array(raw_js, opt_m.start(1))
        opt_names = re.findall(r'"name"\s*:\s*"([^"]+)"', opt_section)
        opt_vals_list = re.findall(r'"values"\s*:\s*\[(.*?)\]', opt_section)
        options = {}
        for i, name in enumerate(opt_names):
            values = re.findall(r'"([^"]+)"', opt_vals_list[i]) if i < len(opt_vals_list) else []
            options[name] = values
        result["options"] = options

    # ---------- 6. 所有变体 ----------

    variants = []
    var_positions = [m.start() for m in re.finditer(r'"variants"\s*:\s*\[', raw_js)]
    if var_positions:
        var_start = var_positions[-1] + raw_js[var_positions[-1]:].find('[')
        var_section = extract_json_array(raw_js, var_start)
        if var_section:
            # 提取每单个 variant
            i = 0
            while i < len(var_section):

                start = var_section.find('{"id"', i)
                if start < 0:
                    break

                depth = 0
                in_str = False
                str_char = None
                end = start
                while end < len(var_section):
                    ch = var_section[end]
                    if in_str:
                        if ch == '\\':
                            end += 2
                            continue
                        if ch == str_char:
                            in_str = False
                        end += 1
                        continue
                    if ch in '"\'':
                        in_str = True
                        str_char = ch
                        end += 1
                        continue
                    if ch == '{':
                        depth += 1
                    elif ch == '}':
                        depth -= 1
                        if depth == 0:
                            chunk = var_section[start:end + 1]
                            # 解析字段
                            def _val(field):
                                m = re.search(rf'"{field}"\s*:\s*"([^"]*)"', chunk)
                                return m.group(1) if m else ""
                            def _bool(field):
                                m = re.search(rf'"{field}"\s*:\s*(true|false)', chunk)
                                return m.group(1) == "true" if m else False
                            def _null_or(field):
                                m = re.search(rf'"{field}"\s*:\s*"([^"]*)"', chunk)
                                if m:
                                    return m.group(1)
                                return None if re.search(rf'"{field}"\s*:\s*null', chunk) else ""
                            def _int(field):
                                m = re.search(rf'"{field}"\s*:\s*(\d+)', chunk)
                                return int(m.group(1)) if m else 0
                            vid = _int("id")
                            vprice = _int("price")
                            if vid and vprice:
                                # 库存可能有重复键, 取大的
                                qty = 0
                                for m_qty in re.finditer(r'"inventory_quantity"\s*:\s*(\d+)', chunk):
                                    q = int(m_qty.group(1))
                                    qty = max(qty, q)
                                variants.append({
                                    "id": vid,
                                    "title": _val("title"),
                                    "option1": _val("option1"),
                                    "option2": _val("option2"),
                                    "option3": _null_or("option3"),
                                    "sku": _val("sku"),
                                    "price": vprice / 100,
                                    "available": _bool("available"),
                                    "inventory_quantity": qty,
                                })
                            i = end + 1
                            break
                    end += 1
                else:
                    break
        result["variants"] = variants

    return result






def print_product(data: dict):
    """打印产品数据"""
    print("=" * 68)
    print("  产品数据爬取 + 解析结果")
    print("=" * 68)

    print(f"\n{'产品名称 (name):':<35} {data['name']}")

    price_str = f"${data['price']:.2f} USD"
    if data.get("compare_at_price"):
        price_str += f"  (原价 ${data['compare_at_price']:.2f})"
    else:
        price_str += "  (无折扣)"
    print(f"{'原价 (price):':<35} {price_str}")

    print(f"\n{'当前颜色 (Color):':<35} {data.get('color', 'N/A')}")

    if data.get("options"):
        for opt_name, opt_vals in data["options"].items():
            label = f" {opt_name} 选项:"
            print(f"{label:<35} {opt_vals}")

    print(f"\n{'产品图片 (images):':<35} 共 {len(data.get('images', []))} 张")
    for idx, url in enumerate(data.get("images", [])):
        print(f"  [{idx + 1}] {url}")

    variants = data.get("variants", [])
    print(f"\n{'所有变体 (variants):':<35} 共 {len(variants)} 个")
    if variants:
        print(f"  {'ID':<18} {'颜色/尺码':<28} {'SKU':<20} {'价格':<10} {'库存':<6}")
        print(f"  " + "-" * 82)
        for v in variants:
            opts = " / ".join(filter(None, [v.get("option1", ""), v.get("option2", ""), v.get("option3", "")]))
            status = "" if v.get("available") else ""
            qty = v.get("inventory_quantity", "?")
            print(f"  {v['id']:<18} {opts:<28} {v.get('sku', ''):<20} ${v['price']:<6.2f} {status} (库存={qty})")

    print("\n" + "=" * 68)




def main():
    print(" 正在爬取产品页面...")
    try:
        html = fetch_page(PRODUCT_URL, VARIANT_PARAMS)
        print(f"   ✓ 页面获取成功 ({(len(html) / 1024):.1f} KB)")
    except requests.RequestException as e:
        print(f"   ✗ 爬取失败: {e}")
        sys.exit(1)

    print("正在解析产品数据...")
    try:
        data = parse_product_data(html)
        print(f"   ✓ 解析完成")
    except ValueError as e:
        print(f"   ✗ 解析失败: {e}")
        sys.exit(1)

    print_product(data)







if __name__ == "__main__":
    main()
