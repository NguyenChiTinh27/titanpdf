---
title: TitanPDF & HSE Report Studio
emoji: 🛡️
colorFrom: blue
colorTo: indigo
sdk: docker
app_port: 7860
pinned: false
---

# TitanPDF - Private Suite (Bản sao hoàn hảo của iLovePDF)

[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/NguyenChiTinh27/titanpdf)

> **Bộ công cụ xử lý PDF toàn diện chuẩn doanh nghiệp — 100% Offline, Bảo mật tuyệt đối, Tốc độ mili-giây.**

---

## 🌟 Giới thiệu
**TitanPDF** được thiết kế để nhân bản toàn bộ cơ chế hoạt động cốt lõi của **iLovePDF**, nhưng khắc phục hoàn toàn các nhược điểm của phiên bản trực tuyến:
- **100% Cục bộ & Bảo mật:** Toàn bộ quá trình xử lý diễn ra trực tiếp trên máy của bạn (RAM & CPU), không có bất kỳ byte dữ liệu nào gửi lên mạng Internet.
- **Không giới hạn dung lượng:** Xử lý các tài liệu từ vài KB đến nhiều GB mà không bị bóp băng thông hay bắt nâng cấp tài khoản trả phí.
- **Tốc độ cực nhanh:** Tận dụng thư viện C gốc `PyMuPDF (fitz)` và Microsoft Word COM engine tích hợp sẵn trên Windows.

---

## 🛠️ Danh sách 15 công cụ cốt lõi

| Nhóm | Tên công cụ | Mô tả chức năng |
| :--- | :--- | :--- |
| **Tổ chức** | **Ghép PDF (Merge)** | Gộp nhiều file PDF thành một tệp duy nhất |
| | **Tách PDF (Split)** | Tách theo dải trang (ví dụ: `1-3, 5, 8-10`) hoặc tách từng trang lẻ |
| | **Xóa trang (Delete Pages)** | Nhập các trang cần loại bỏ khỏi tệp |
| | **Xoay PDF (Rotate)** | Xoay toàn bộ trang 90°, 180°, 270° |
| | **Đánh số trang (Page Numbers)** | Tự động chèn số trang ở chân tài liệu |
| **Chuyển đổi** | **PDF sang Word** | Chuyển sang `.docx` giữ nguyên bảng biểu và định dạng |
| | **Word sang PDF** | Xuất Word sang PDF bằng Microsoft Word Engine chuẩn 100% |
| | **PDF sang Excel** | Tự động trích xuất bảng biểu ra các Sheet `.xlsx` |
| | **PDF sang Ảnh** | Trích xuất từng trang ra ảnh PNG / JPG độ nét cao |
| | **Ảnh sang PDF** | Ghép nhiều ảnh (PNG, JPG, BMP) thành 1 tệp PDF |
| **Tối ưu** | **Nén PDF (Compress)** | 3 cấp độ: Cực đại (Extreme), Khuyên dùng (Recommended), Nhẹ (Low) |
| | **OCR Nhận diện văn bản** | Quét file scan và trích xuất text (Tesseract OCR) |
| **Bảo mật** | **Khóa bảo vệ (Protect)** | Mã hóa mật khẩu bảo vệ bằng chuẩn quân sự AES-256 |
| | **Mở khóa (Unlock)** | Gỡ bỏ mật khẩu và các hạn chế quyền in/sao chép |
| | **Đóng dấu (Watermark)** | Đóng dấu chìm đường chéo 45° tùy biến chữ & độ mờ |

---

## 🚀 Cách khởi động ứng dụng

### Cách 1: Click đúp 1 chạm (Khuyên dùng)
- Mở thư mục `TitanPDF` và click đúp chuột vào tệp: **`run_app.bat`**.
- Hệ thống sẽ tự động khởi chạy máy chủ cục bộ và tự động mở trình duyệt web tại địa chỉ:
  👉 **`http://127.0.0.1:8888`**

### Cách 2: Khởi động qua dòng lệnh (Terminal / PowerShell)
```powershell
cd "c:\Users\ntc27\OneDrive\文件\TitanPDF"
python server.py
```

---

## 🔒 Bảo mật và Dọn dẹp
- Các tệp tạm tải lên được lưu tại thư mục `TitanPDF/temp/`.
- Các tệp kết quả xuất ra được lưu tại `TitanPDF/output/`.
- Bạn có thể xóa hai thư mục này bất kỳ lúc nào mà không ảnh hưởng đến hệ thống.
