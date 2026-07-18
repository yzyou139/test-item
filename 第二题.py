import requests
import csv
import json
import re
import time
from bs4 import BeautifulSoup

BASE_URL = "https://www.cosrx.com"
TOTAL_PAGES = 6


headers = {
    "accept": "*/*",
    "accept-language": "zh-CN,zh;q=0.9",
    "x-requested-with": "XMLHttpRequest",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/144.0.0.0 Safari/537.36 QuarkPC/6.9.5.892",
}
cookies = {
    "localization": "US",
    "cart_currency": "USD",
    "_shopify_y": "2f5a7a0b-85a6-4c8a-9e77-7edd41742c71",
    "_shopify_s": "f6c94180-fdd9-4995-8819-e897e4c07532",
    "shopify_client_id": "2f5a7a0b-85a6-4c8a-9e77-7edd41742c71",
    "_ga": "GA1.2.663460646.1784255879",
    "_gid": "GA1.2.1888415423.1784255880",
    "_fbp": "fb.1.1784255880123.964594816481630028",
}


def get_page(url, headers, params=None):

    for retry in range(3):
        try:
            resp = requests.get(url, headers=headers, cookies=cookies, params=params, timeout=30)
            resp.encoding = "utf-8"
            if resp.status_code == 200:
                return resp.text
            print(f"    请求失败 {resp.status_code}, 重试 {retry + 1}/3")
        except Exception as e:
            print(f"    异常: {e}, 重试 {retry + 1}/3")
        time.sleep(2)
    return None


def get_product_links_and_ids():
    """爬取列表页，获取所有商品链接和 product_id"""
    all_products = []  # [(handle, product_id), ...]
    seen_handles = set()

    for page in range(1, TOTAL_PAGES + 1):
        print(f"爬取列表页 {page}/{TOTAL_PAGES}...")
        html = get_page(
            f"{BASE_URL}/collections/all",
            headers,
            params={"page": str(page), "section_id": "template--22575445016792__main"},
        )
        if not html:
            continue

        soup = BeautifulSoup(html, "html.parser")
        # 每个 product-block 有 data-product-id，内部有 a.product-link
        for block in soup.select("div.product-block[data-product-id]"):
            product_id = block.get("data-product-id", "")
            a = block.select_one("a.product-link[href*='/products/']")
            if not a:
                continue
            href = a.get("href", "")
            # 提取 handle: /collections/all/products/{handle}
            handle = href.split("/products/")[-1].split("?")[0]
            if handle not in seen_handles:
                seen_handles.add(handle)
                all_products.append((handle, product_id))

        print(f"  累计 {len(all_products)} 个商品")

    print(f"\n共找到 {len(all_products)} 个商品")
    return all_products


def get_product_detail(handle):
    """获取完整商品详情页 HTML"""
    url = f"{BASE_URL}/collections/all/products/{handle}"
    return get_page(url, headers, params=None)


def parse_detail_page(html):
    """解析详情页HTML，提取所需字段"""
    result = {
        "name": "",
        "price": "",
        "images": "",
        "Key Ingredients": "",
        "Size": "",
    }

    soup = BeautifulSoup(html, "html.parser")

    # ---- 1. 产品名称 ----
    title_el = soup.select_one("h1.title")
    if title_el:
        result["name"] = title_el.get_text(strip=True)

    # ---- 2. 价格 ----
    price_el = soup.select_one("span.current-price.theme-money")
    if price_el:
        result["price"] = price_el.get_text(strip=True)

    # ---- 3. 图片 ---- 
    images = []

    # 从 JSON-LD 取主图
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string)
            if isinstance(data, dict) and data.get("@type") == "Product":
                imgs = data.get("image", [])
                if isinstance(imgs, str):
                    imgs = [imgs]
                for img in imgs:
                    if img not in images:
                        images.append(img)
        except:
            pass

    # 从图库 img 标签取更多图片
    for img in soup.select("img.rimage__image.lazyload.fade-in"):
        src = (img.get("data-src") or img.get("src") or "")
        if not src or "placeholder" in src.lower() or "thumbnail" in src.lower():
            continue
        url = src.replace("{width}x", "1024x1024")
        if url.startswith("//"):
            url = "https:" + url
        # 去重
        basename = url.split("/")[-1].split("?")[0].split("_1024x1024")[0]
        if basename and "icon" not in basename.lower() and "logo" not in basename.lower():
            if not any(basename in img_url for img_url in images):
                images.append(url)

    result["images"] = ",".join(images)

    # ---- 4. Key Ingredients ----
    # 来源1: Product Fact Pack 表格中的 Key Ingredients 行
    for table in soup.find_all("table", class_="cb-table"):
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True)
                if label == "Key Ingredients":
                    val = cells[1].get_text(strip=True)
                    if val:
                        result["Key Ingredients"] = val
                        break
        if result["Key Ingredients"]:
            break

    # 来源2: .acc_content_area 中的 KEY INGREDIENTS
    if not result["Key Ingredients"]:
        for area in soup.find_all("div", class_="acc_content_area"):
            area_text = area.get_text(" ", strip=True)
            if "KEY INGREDIENTS" not in area_text:
                continue
            # 优先取 Full Ingredients modal 中的完整成分列表
            full_ing = area.select_one(".full-ingredients-container .ingre-modal-content .modal-body")
            if full_ing:
                val = full_ing.get_text(strip=True)
                if val:
                    result["Key Ingredients"] = val
                    break
            # 否则从 bullet 点列表中提取成分名
            ingredients = []
            for p in area.select("p"):
                p_text = p.get_text(strip=True)
                m = re.match(r'[•\*]\s*(.+?)\s*:', p_text)
                if m:
                    ingredients.append(m.group(1).strip().rstrip("\u00a0"))
            if ingredients:
                result["Key Ingredients"] = ", ".join(ingredients)
                break

    # 来源3: JSON-LD description (不含表格的产品)
    if not result["Key Ingredients"]:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get("@type") == "Product":
                    desc = str(data.get("description", ""))
                    ki_m = re.search(r'Key Ingredients\s*:\s*([^\n\r<.]+)', desc)
                    if ki_m:
                        val = ki_m.group(1).strip()
                        if val:
                            result["Key Ingredients"] = val
                            break
            except:
                pass

    # ---- 5. Size（尺码选项）----
    # 来源1: Product Fact Pack 表格中的 Volume 行
    for table in soup.find_all("table", class_="cb-table"):
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 2:
                label = cells[0].get_text(strip=True)
                if label == "Volume":
                    val = cells[1].get_text(strip=True)
                    if val:
                        result["Size"] = val
                        break
        if result["Size"]:
            break

    # 来源2: variant titles (非 "Default Title" 的)
    if not result["Size"]:
        for script in soup.find_all("script"):
            t = script.string or ""
            for m in re.finditer(r'"variants"\s*:\s*\[(.*?)\]', t, re.DOTALL):
                sizes = set()
                for vm in re.finditer(r'"title"\s*:\s*"([^"]+)"', m.group(1)):
                    title = vm.group(1)
                    if title and title != "Default Title":
                        sizes.add(title.replace("\\/", "/"))
                if sizes:
                    result["Size"] = ", ".join(sorted(sizes))
                    break
            if result["Size"]:
                break

    # 来源3: 描述中的 Size / Volume
    if not result["Size"]:
        desc = soup.select_one(".product-description")
        if desc:
            desc_text = desc.get_text(" ", strip=True)
            m = re.search(r'(?:Size|Volume)\s*[:\u00a0\s]\s*([^\n<]+)', desc_text)
            if m:
                val = m.group(1).strip()
                if val:
                    result["Size"] = val

    # 来源4: JSON-LD description 中的 Size / Volume
    if not result["Size"]:
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string)
                if isinstance(data, dict) and data.get("@type") == "Product":
                    desc = str(data.get("description", ""))
                    m = re.search(r'(?:Size|Volume)\s*[:\u00a0\s]\s*([^\n<]+)', desc)
                    if m:
                        val = m.group(1).strip()
                        if val:
                            result["Size"] = val
                            break
            except:
                pass

    return result


def main():
    # Step 1: 获取所有商品 handle + product_id
    all_products = get_product_links_and_ids()

    # Step 2: 爬取每个商品详情
    parsed = []
    failed = 0

    for i, (handle, product_id) in enumerate(all_products, 1):
        print(f"[{i}/{len(all_products)}] {handle}")

        html = get_product_detail(handle)
        if not html:
            failed += 1
            continue

        data = parse_detail_page(html)
        parsed.append(data)

        ing = data["Key Ingredients"][:60] if data["Key Ingredients"] else "(无)"
        sz = data["Size"][:40] if data["Size"] else "(无)"
        print(f"  name={data['name'][:40]} price={data['price']} ingredients={ing} size={sz}")

        time.sleep(1)

    print(f"\n完成! 成功: {len(parsed)}, 失败: {failed}")

    # Step 3: 保存到 CSV
    csv_file = "cosrx_detail_products_v2.csv"
    with open(csv_file, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["name", "price", "images", "Key Ingredients", "Size"])
        writer.writeheader()
        for p in parsed:
            writer.writerow(p)

    print(f"结果已保存到 {csv_file}")

    # 统计
    ki_count = sum(1 for p in parsed if p["Key Ingredients"])
    sz_count = sum(1 for p in parsed if p["Size"])
    print(f"\n有 Key Ingredients: {ki_count}/{len(parsed)}")
    print(f"有 Size: {sz_count}/{len(parsed)}")

    # 预览
    print("\n--- 预览前 5 个 ---")
    for p in parsed[:5]:
        print(f"名称: {p['name']}")
        print(f"价格: {p['price']}")
        print(f"Key Ingredients: {p['Key Ingredients']}")
        print(f"Size: {p['Size']}")
        img_count = len(p['images'].split(",")) if p['images'] else 0
        print(f"图片: {img_count} 张")
        print()


if __name__ == "__main__":
    main()
