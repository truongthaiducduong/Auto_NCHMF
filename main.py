"!pip install pdfplumber -q

import requests
from bs4 import BeautifulSoup
import pdfplumber
import pandas as pd
import re
import unicodedata
from IPython.display import display

# --- CẤU HÌNH ---
WEB_APP_URL = ""https://script.google.com/macros/s/AKfycbz59xIGaV_ymrEAdutZ9axDj-gkVXauJZ6eMrIKXukgSUCgV9VQC3zCNStFc0QyAANw/exec""
TARGET_STATIONS = [""Hòa Bình"", ""Yên Bái"", ""Phú Thọ"", ""Tuyên Quang"", ""Vụ Quang"", ""Hà Nội""]
HEADERS = {'User-Agent': 'Mozilla/5.0'}

def clean_and_split(val):
    if val is None: return [""""]
    parts = re.split(r'\n{2,}|\s{2,}', str(val).strip())
    return [p.strip() for p in parts if p.strip()]

def get_num(v):
    if not v: return """"
    return re.sub(r'[^\d.-]', '', str(v))

def process_one_pdf(pdf_url):
    try:
        res = requests.get(pdf_url, timeout=20)
        with open(""temp.pdf"", ""wb"") as f: f.write(res.content)
        extracted_rows = []
        with pdfplumber.open(""temp.pdf"") as pdf:
            year_match = re.search(r'năm (\d{4})', pdf.pages[0].extract_text() or """")
            year = year_match.group(1) if year_match else ""2026""
            
            # Hàm này vẫn giữ nguyên vì nó lọc rác cực kỳ chuẩn
            target_page = next(p for p in pdf.pages if ""Hòa Bình"" in (p.extract_text() or """") and ""Yên Bái"" in (p.extract_text() or """"))
            df_raw = pd.DataFrame(target_page.extract_table())
            
            raw_headers = df_raw.iloc[1, 2:].values
            all_times = []
            for h in raw_headers: all_times.extend(clean_and_split(h))
            actual_times = all_times[:4] 

            station_data = {}
            for st in TARGET_STATIONS:
                row = df_raw[df_raw[1].str.contains(st, na=False, case=False)]
                if not row.empty:
                    raw_vals = row.iloc[0, 2:].values
                    vals_split = []
                    for v in raw_vals: vals_split.extend(clean_and_split(v))
                    station_data[st] = vals_split

            for i, time_str in enumerate(actual_times):
                match = re.search(r'(\d+)h-?(\d+)/(\d+)', time_str.replace('\n', '').replace(' ', ''))
                if match:
                    h, d, m = match.groups()
                    unique_id = f""{year}-{int(m)}-{int(d)}-{int(h)}""
                    
                    entry = {
                        ""Ngày"": f""{int(d)}/{int(m)}/{year}"",
                        ""Giờ"": int(h),
                        ""ID_Match"": unique_id 
                    }
                    for st in TARGET_STATIONS:
                        try: val = get_num(station_data[st][i])
                        except: val = """"
                        entry[st] = val
                    extracted_rows.append(entry)
        return extracted_rows
    except: return []

print(""--- 🚀 KHỞI ĐỘNG CHẾ ĐỘ QUÉT VÀ BẮN TỰ ĐỘNG ---"")
all_data = []

for page in range(1, 3):
    print(f""🔎 Đang rà soát trang {page}..."")
    list_url = f""https://nchmf.gov.vn/kttv/vi-VN/1/du-bao-han-ngan-13-18.html?pageindex={page}""
    soup = BeautifulSoup(requests.get(list_url, headers=HEADERS).text, 'html.parser')
    
    links = []
    for a in soup.select('a'):
        t = a.text.upper()
        # --- CHỈ SỬA ĐÚNG DÒNG NÀY ---
        # Thêm ""NGUỒN NƯỚC"" vào danh sách tìm kiếm
        if ""DỰ BÁO"" in t and (""THỦY VĂN"" in t or ""THUỶ VĂN"" in t or ""NGUỒN NƯỚC"" in t):
            h = a.get('href')
            links.append(h if h.startswith('http') else ""https://nchmf.gov.vn"" + h)
    
    for link in list(dict.fromkeys(links)):
        try:
            p_soup = BeautifulSoup(requests.get(link, headers=HEADERS).text, 'html.parser')
            pdf = next((a['href'] for a in p_soup.find_all('a', href=True) if "".pdf"" in a['href'].lower()), """")
            if pdf:
                pdf_url = pdf if pdf.startswith('http') else ""https://nchmf.gov.vn"" + pdf
                data = process_one_pdf(pdf_url)
                if data:
                    all_data.extend(data)
                    print(f""   -> Đã bóc xong: {pdf_url.split('/')[-1]}"")
        except: continue

if all_data:
    df_final = pd.DataFrame(all_data)
    print(f""\n--- 📊 TỔNG KẾT: THU ĐƯỢC {len(df_final)} DÒNG THỰC ĐO ---"")
    display(df_final) 
    
    print(""🚀 Đang tự động bắn dữ liệu lên Google Sheets..."")
    payload = [[r['ID_Match'], r['Giờ']] + [r[st] for st in TARGET_STATIONS] for r in all_data]
    try:
        response = requests.post(WEB_APP_URL, json=payload)
        print(f""🏁 Kết quả từ Apps Script: {response.text}"")
    except Exception as e:
        print(f""❗ Lỗi đường truyền: {e}"")
else:
    print(""\n❌ Không lấy được dữ liệu. Kiểm tra lại kết nối nhé!"")"
