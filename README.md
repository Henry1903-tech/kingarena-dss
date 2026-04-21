# King Arena DSS Studio (Streamlit)

Hệ hỗ trợ ra quyết định cho quản lý sân bóng King Arena: dashboard KPI + insight tự động + Decision Lab + (tùy chọn) trợ lý AI Gemini.

## Chạy local

```bash
cd project_new
pip install -r requirements.txt
streamlit run app.py
```

## Dùng trên web (Streamlit Cloud) — không cần Python

### Bước 1: Tạo GitHub repo
- Tạo repo mới (ví dụ: `kingarena-dss`)
- Upload toàn bộ nội dung thư mục `project_new/` lên repo (các file `.env` / `secrets.toml` **không** upload)

Gợi ý: bạn có thể upload bằng giao diện GitHub (Add file → Upload files).

### Bước 2: Deploy trên Streamlit Cloud
- Vào Streamlit Community Cloud và đăng nhập bằng GitHub
- Chọn **New app**
- Chọn:
  - Repository: repo vừa tạo
  - Branch: `main`
  - Main file path: `app.py`
- Bấm **Deploy**

### Bước 3: (Tuỳ chọn) cấu hình Gemini bằng Secrets
Trong app trên Streamlit Cloud → **Settings** → **Secrets**, thêm:

```toml
GEMINI_API_KEY="YOUR_KEY"
# GEMINI_MODEL="gemini-2.0-flash"
```

Không có key thì tab “Trợ lý phân tích” sẽ tự báo chưa kích hoạt, app vẫn chạy bình thường.

## Bật trợ lý Gemini (tùy chọn)

- Tạo file `.env` đặt cạnh `app.py`:

```env
GEMINI_API_KEY=your_key_here
# GEMINI_MODEL=gemini-2.0-flash
```

Nếu không có `GEMINI_API_KEY`, tab “Trợ lý phân tích” sẽ tự hiện thông báo và **không làm crash app**.

## Dữ liệu Excel

### Cách dùng khuyến nghị (cả local và cloud)
- Mở app → sidebar “Nguồn dữ liệu” → **tải file Excel (.xlsx)** lên trực tiếp.

### Cách auto-load (local)
Ứng dụng cũng có thể tự tìm file theo danh sách `EXCEL_CANDIDATES` trong `config.py` (đặt file ngay trong thư mục `project_new/`).

Nếu bạn đang có Excel mẫu khác cột, chỉ cần chỉnh mapping trong `data_loader.py` (hàm `_standardize_columns`).

