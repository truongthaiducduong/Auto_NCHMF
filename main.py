import requests
from bs4 import BeautifulSoup
import fitz  # PyMuPDF
import re

# --- CẤU HÌNH CỦA CHỦ NHÂN ---
WEB_APP_URL = "https://script.google.com/macros/s/AKfycbz59xIGaV_ymrEAdutZ9axDj-gkVXauJZ6eMrIKXukgSUCgV9VQC3zCNStFc0QyAANw/exec"
TARGET_STATIONS = ["Hòa Bình", "Yên Bái", "Phú Thọ", "Tuyên Quang", "Vụ Quang", "Hà Nội"]
HEADERS = {'User-Agent': 'Mozilla/5.0'}

def process_one_pdf_regex(pdf_url):
    try:
        # Kéo PDF về tổ
        res = requests.get(pdf_url, timeout=20, headers=HEADERS)
        pdf_path = "temp.pdf"
        with open(pdf_path, "wb") as f: 
            f.write(res.content)
            
        doc = fitz.open(pdf_path)
        
        # 1. Bắt Năm từ trang đầu tiên
        year = "2026"
        year_match = re.search(r'năm (\d{4})', doc[0].get_text())
        if year_match:
            year = year_match.group(1)
        else:
            # Backup: Lấy năm từ URL
            year_url = re.search(r'/(\d{4})/', pdf_url)
            if year_url:
                year = year_url.group(1)

        # 2. Rà soát lấy đúng văn bản chứa Bảng II
        target_text = ""
        for page in doc:
            text = page.get_text()
            if "Hòa Bình" in text and "Yên Bái" in text:
                target_text = text
                break
                
        if not target_text:
            return []

        # 3. Móc 4 mốc thời gian thực đo bằng Regex
        # Bắt các chuỗi dạng: "13h-\n27/07" hoặc "13h-28/07"
        time_pattern = r'(\d{1,2})h-?\s*(\d{1,2})/(\d{1,2})'
        all_times = re.findall(time_pattern, target_text)
        actual_times = all_times[:4]  # Chém lấy đúng 4 mốc đầu tiên
        
        if not actual_times:
            return []

        # 4. Móc số liệu của từng trạm
        station_data = {}
        lines = target_text.split('\n')
        
        for st in TARGET_STATIONS:
            st_vals = ["", "", "", ""]
            for idx, line in enumerate(lines):
                # Tìm đúng dòng chứa tên trạm
                if st.lower() in line.lower():
                    val_idx = 0
                    # Rà soát các dòng ngay bên dưới nó
                    for next_line in lines[idx+1:]:
                        next_line = next_line.strip()
                        if not next_line:
                            continue
                        
                        # Nếu dòng đó chứa số (có thể có dấu âm, dấu thập phân)
                        if re.match(r'^-?[\d.]+$', next_line):
                            st_vals[val_idx] = next_line
                            val_idx += 1
                            if val_idx == 4: # Lấy đủ 4 mốc thì dừng
                                break
                        elif re.search(r'[a-zA-Z]', next_line):
                            # Nếu đụng phải chữ cái (tên trạm khác) -> Dừng ngay
                            break
                    break
            station_data[st] = st_vals

        # 5. Ép khuôn JSON giống hệt đầu ra của Chủ nhân
        extracted_rows = []
        for i, time_tuple in enumerate(actual_times):
            h, d, m = time_tuple
            unique_id = f"{year}-{int(m)}-{int(d)}-{int(h)}"
            
            entry = {
                "ID_Match": unique_id,
                "Giờ": int(h)
            }
            for st in TARGET_STATIONS:
                entry[st] = station_data[st][i]
                
            extracted_rows.append(entry)
            
        return extracted_rows
        
    except Exception as e:
        print(f"      [!] Lỗi khi chém PDF {pdf_url.split('/')[-1]}: {e}")
        return []

print("--- 🚀 KHỞI ĐỘNG CỖ MÁY SÁT THỦ BẰNG REGEX (SIÊU TỐC ĐỘ) ---")
all_data = []

# Chủ nhân có thể để range(1, 3) nếu muốn vét lại 20 ngày, hoặc range(1, 2) cho Daily
for page in range(1, 3):
    print(f"🔎 Đang rà soát trang {page}...")
    list_url = f"https://nchmf.gov.vn/kttv/vi-VN/1/du-bao-han-ngan-13-18.html?pageindex={page}"
    try:
        soup = BeautifulSoup(requests.get(list_url, headers=HEADERS, timeout=10).text, 'html.parser')
        links = []
        for a in soup.select('a'):
            t = a.text.upper()
            if "DỰ BÁO" in t and ("THỦY VĂN" in t or "THUỶ VĂN" in t or "NGUỒN NƯỚC" in t):
                h = a.get('href')
                links.append(h if h.startswith('http') else "https://nchmf.gov.vn" + h)
        
        for link in list(dict.fromkeys(links)):
            try:
                p_soup = BeautifulSoup(requests.get(link, headers=HEADERS, timeout=10).text, 'html.parser')
                pdf = next((a['href'] for a in p_soup.find_all('a', href=True) if ".pdf" in a['href'].lower()), "")
                if pdf:
                    pdf_url = pdf if pdf.startswith('http') else "https://nchmf.gov.vn" + pdf
                    print(f"Đang băm nhỏ dữ liệu: {pdf_url.split('/')[-1]}")
                    
                    data = process_one_pdf_regex(pdf_url)
                    if data:
                        all_data.extend(data)
                        print(f"   -> Đã lấy thành công!")
            except: continue
    except: continue

# Bắn thẳng dữ liệu lên Apps Script
if all_data:
    print(f"\n--- 📊 TỔNG KẾT: THU ĐƯỢC {len(all_data)} DÒNG THỰC ĐO TỪ BẢNG II ---")
    payload = [[r.get('ID_Match', ''), r.get('Giờ', '')] + [r.get(st, '') for st in TARGET_STATIONS] for r in all_data]
    
    try:
        response = requests.post(WEB_APP_URL, json=payload)
        print(f"🏁 Kết quả từ Apps Script: {response.text}")
    except Exception as e:
        print(f"❗ Lỗi đường truyền: {e}")
else:
    print("\n❌ Không lấy được dữ liệu.")
