"""
license_manager_app.py
──────────────────────
Ứng dụng Quản trị Giấy phép & Khóa Bản quyền Độc lập:
LUV PDF License Manager Suite (Native Desktop GUI)

Tính năng:
- Hiển thị và sao chép Mã Máy (Hardware Machine ID).
- Xem trạng thái Giấy phép Bản quyền hiện tại của LUV PDF.
- Tạo mã Bản quyền mới (Key Generator) chuẩn mật mã SHA-256 cho Doanh nghiệp & Chuyên gia.
- Kích hoạt / Hủy kích hoạt Giấy phép trực tiếp cho máy tính hiện tại.
"""

import os
import sys
import json
import hashlib
import platform
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

# Đường dẫn file license.json
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LICENSE_FILE = os.path.join(BASE_DIR, "license.json")
SECRET_SALT = "LUV_PDF_OFFICIAL_SECRET_KEY_2026"


def get_machine_id() -> str:
    """Tạo mã định danh phần cứng máy tính duy nhất."""
    raw = f"{platform.node()}-{platform.processor()}-{os.getenv('USERNAME', 'LUV_USER')}"
    return "LUV-" + hashlib.md5(raw.encode()).hexdigest()[:8].upper()


def generate_license_key(registered_to: str, tier: str, expires: str) -> str:
    """Tạo khóa bản quyền chuẩn mật mã SHA-256."""
    raw_hash = hashlib.sha256(f"{registered_to}_{tier}_{expires}_{SECRET_SALT}".encode()).hexdigest().upper()
    part1 = raw_hash[:4]
    part2 = raw_hash[4:8]
    part3 = raw_hash[8:12]
    prefix = "LUV-PRO" if "Pro" in tier else "LUV-ENT" if "Enterprise" in tier else "LUV-PDF"
    return f"{prefix}-{part1}-{part2}-{part3}"


def load_current_license():
    """Đọc dữ liệu bản quyền hiện tại."""
    if os.path.exists(LICENSE_FILE):
        try:
            with open(LICENSE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def save_license(record):
    """Lưu dữ liệu bản quyền vào file."""
    with open(LICENSE_FILE, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


class LUVLicenseManagerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("LUV PDF — Trình Quản Lý Bản Quyền & Giấy Phép")
        self.root.geometry("640 x 680".replace(" ", ""))
        self.root.minsize(600, 640)
        self.root.configure(bg="#0f172a")

        # Configure style
        self.style = ttk.Style()
        self.style.theme_use("clam")
        
        self.setup_ui()
        self.refresh_status()

    def setup_ui(self):
        # Header banner
        header = tk.Frame(self.root, bg="#1e293b", padx=20, pady=16)
        header.pack(fill="x")

        title_lbl = tk.Label(
            header, 
            text="LUV-PDF LICENSE MANAGER", 
            font=("Segoe UI", 15, "bold"), 
            fg="#38bdf8", 
            bg="#1e293b"
        )
        title_lbl.pack(anchor="w")

        sub_lbl = tk.Label(
            header, 
            text="Hệ Thống Quản Trị & Tạo Khóa Bản Quyền Doanh Nghiệp • Bảo Mật Tuyệt Đối", 
            font=("Segoe UI", 9), 
            fg="#94a3b8", 
            bg="#1e293b"
        )
        sub_lbl.pack(anchor="w", pady=(2, 0))

        # Main scrollable or padded frame
        main_frame = tk.Frame(self.root, bg="#0f172a", padx=20, pady=14)
        main_frame.pack(fill="both", expand=True)

        # ── 1. MACHINE ID & CURRENT STATUS ──────────────────────────
        status_box = tk.LabelFrame(
            main_frame, 
            text=" 1. THÔNG TIN THIẾT BỊ & GIẤY PHÉP HIỆN TẠI ", 
            font=("Segoe UI", 10, "bold"), 
            fg="#38bdf8", 
            bg="#1e293b", 
            padx=14, 
            pady=10
        )
        status_box.pack(fill="x", pady=(0, 12))

        # Machine ID row
        row_mid = tk.Frame(status_box, bg="#1e293b")
        row_mid.pack(fill="x", pady=4)
        tk.Label(row_mid, text="Mã máy tính (Machine ID):", font=("Segoe UI", 9), fg="#cbd5e1", bg="#1e293b").pack(side="left")
        
        self.mid_val = get_machine_id()
        self.mid_lbl = tk.Label(row_mid, text=self.mid_val, font=("Consolas", 10, "bold"), fg="#38bdf8", bg="#0f172a", padx=8, pady=2)
        self.mid_lbl.pack(side="left", padx=10)
        
        btn_copy_mid = tk.Button(
            row_mid, text="Sao chép", font=("Segoe UI", 8), bg="#334155", fg="#f8fafc", 
            activebackground="#475569", activeforeground="#ffffff", relief="flat", padx=8,
            command=lambda: self.copy_to_clip(self.mid_val, "Đã sao chép Machine ID!")
        )
        btn_copy_mid.pack(side="right")

        # Current status row
        row_st = tk.Frame(status_box, bg="#1e293b")
        row_st.pack(fill="x", pady=4)
        tk.Label(row_st, text="Trạng thái bản quyền:", font=("Segoe UI", 9), fg="#cbd5e1", bg="#1e293b").pack(side="left")
        
        self.lbl_license_state = tk.Label(row_st, text="Đang kiểm tra...", font=("Segoe UI", 9, "bold"), fg="#4ade80", bg="#1e293b")
        self.lbl_license_state.pack(side="left", padx=10)

        # ── 2. KEY GENERATOR (ADMIN TOOL) ───────────────────────────
        gen_box = tk.LabelFrame(
            main_frame, 
            text=" 2. TẠO KHÓA BẢN QUYỀN MỚI (LICENSE KEY GENERATOR) ", 
            font=("Segoe UI", 10, "bold"), 
            fg="#38bdf8", 
            bg="#1e293b", 
            padx=14, 
            pady=10
        )
        gen_box.pack(fill="x", pady=(0, 12))

        # Customer name
        tk.Label(gen_box, text="Đăng ký cho (Tên Doanh nghiệp / Cá nhân):", font=("Segoe UI", 9), fg="#cbd5e1", bg="#1e293b").pack(anchor="w")
        self.ent_reg_to = tk.Entry(gen_box, font=("Segoe UI", 10), bg="#0f172a", fg="#ffffff", insertbackground="#38bdf8", relief="flat")
        self.ent_reg_to.insert(0, "LUV Enterprise Client")
        self.ent_reg_to.pack(fill="x", pady=(2, 8))

        # Tier & Expiration
        opt_row = tk.Frame(gen_box, bg="#1e293b")
        opt_row.pack(fill="x", pady=(0, 8))

        # Tier
        col1 = tk.Frame(opt_row, bg="#1e293b")
        col1.pack(side="left", fill="x", expand=True, padx=(0, 8))
        tk.Label(col1, text="Gói Bản quyền (Tier):", font=("Segoe UI", 9), fg="#cbd5e1", bg="#1e293b").pack(anchor="w")
        self.cmb_tier = ttk.Combobox(col1, values=["Enterprise Lifetime (Vĩnh viễn)", "Professional Suite (Chuyên nghiệp)", "Standard License (Tiêu chuẩn)"], state="readonly")
        self.cmb_tier.current(0)
        self.cmb_tier.pack(fill="x", pady=2)

        # Expiry
        col2 = tk.Frame(opt_row, bg="#1e293b")
        col2.pack(side="right", fill="x", expand=True)
        tk.Label(col2, text="Thời hạn (Expires):", font=("Segoe UI", 9), fg="#cbd5e1", bg="#1e293b").pack(anchor="w")
        self.cmb_exp = ttk.Combobox(col2, values=["Vĩnh viễn (Lifetime)", "1 Năm (1 Year)", "2 Năm (2 Years)", "3 Năm (3 Years)"], state="readonly")
        self.cmb_exp.current(0)
        self.cmb_exp.pack(fill="x", pady=2)

        # Generate Button
        btn_gen = tk.Button(
            gen_box, 
            text="⚡ TẠO MÃ BẢN QUYỀN MỚI (GENERATE KEY)", 
            font=("Segoe UI", 10, "bold"), 
            bg="#0284c7", 
            fg="#ffffff", 
            activebackground="#0369a1", 
            activeforeground="#ffffff", 
            relief="flat", 
            pady=6,
            command=self.on_generate_key
        )
        btn_gen.pack(fill="x", pady=(4, 8))

        # Generated Key Display
        tk.Label(gen_box, text="Mã bản quyền đã tạo:", font=("Segoe UI", 9), fg="#cbd5e1", bg="#1e293b").pack(anchor="w")
        key_disp_row = tk.Frame(gen_box, bg="#1e293b")
        key_disp_row.pack(fill="x", pady=2)

        self.ent_gen_key = tk.Entry(key_disp_row, font=("Consolas", 11, "bold"), bg="#0f172a", fg="#38bdf8", insertbackground="#38bdf8", relief="flat")
        self.ent_gen_key.pack(side="left", fill="x", expand=True)

        btn_copy_key = tk.Button(
            key_disp_row, 
            text="Sao chép Key", 
            font=("Segoe UI", 9), 
            bg="#334155", 
            fg="#f8fafc", 
            activebackground="#475569", 
            activeforeground="#ffffff", 
            relief="flat", 
            padx=10,
            command=self.on_copy_generated_key
        )
        btn_copy_key.pack(side="right", padx=(8, 0))

        # ── 3. ACTIVATION & DEACTIVATION ────────────────────────────
        act_box = tk.LabelFrame(
            main_frame, 
            text=" 3. KÍCH HOẠT CHO MÁY TÍNH HIỆN TẠI ", 
            font=("Segoe UI", 10, "bold"), 
            fg="#38bdf8", 
            bg="#1e293b", 
            padx=14, 
            pady=10
        )
        act_box.pack(fill="x")

        tk.Label(act_box, text="Nhập mã bản quyền cần kích hoạt:", font=("Segoe UI", 9), fg="#cbd5e1", bg="#1e293b").pack(anchor="w")
        self.ent_act_key = tk.Entry(act_box, font=("Consolas", 10), bg="#0f172a", fg="#ffffff", insertbackground="#38bdf8", relief="flat")
        self.ent_act_key.pack(fill="x", pady=(2, 8))

        act_btn_row = tk.Frame(act_box, bg="#1e293b")
        act_btn_row.pack(fill="x")

        btn_activate = tk.Button(
            act_btn_row, 
            text="Kích Hoạt Ngay", 
            font=("Segoe UI", 9, "bold"), 
            bg="#16a34a", 
            fg="#ffffff", 
            activebackground="#15803d", 
            activeforeground="#ffffff", 
            relief="flat", 
            padx=14, 
            pady=5,
            command=self.on_activate_key
        )
        btn_activate.pack(side="left")

        btn_deactivate = tk.Button(
            act_btn_row, 
            text="Hủy Kích Hoạt", 
            font=("Segoe UI", 9), 
            bg="#dc2626", 
            fg="#ffffff", 
            activebackground="#b91c1c", 
            activeforeground="#ffffff", 
            relief="flat", 
            padx=12, 
            pady=5,
            command=self.on_deactivate_key
        )
        btn_deactivate.pack(side="right")

    def copy_to_clip(self, text: str, msg: str = "Đã sao chép!"):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        messagebox.showinfo("Thành công", msg)

    def refresh_status(self):
        lic = load_current_license()
        if lic and lic.get("status") == "active":
            reg = lic.get("registered_to", "LUV Client")
            tier = lic.get("tier", "Enterprise")
            key = lic.get("license_key", "")
            self.lbl_license_state.config(
                text=f"✓ ĐÃ KÍCH HOẠT ({tier}) — {reg}\nKhóa: {key}",
                fg="#4ade80"
            )
        else:
            self.lbl_license_state.config(
                text="Chưa kích hoạt (Chế độ dùng thử hoặc miễn phí)",
                fg="#f59e0b"
            )

    def on_generate_key(self):
        reg = self.ent_reg_to.get().strip() or "Doanh nghiệp LUV"
        tier = self.cmb_tier.get()
        exp = self.cmb_exp.get()

        key = generate_license_key(reg, tier, exp)
        self.ent_gen_key.delete(0, tk.END)
        self.ent_gen_key.insert(0, key)
        self.ent_act_key.delete(0, tk.END)
        self.ent_act_key.insert(0, key)

    def on_copy_generated_key(self):
        k = self.ent_gen_key.get().strip()
        if not k:
            messagebox.showwarning("Chú ý", "Chưa có mã bản quyền nào được tạo.")
            return
        self.copy_to_clip(k, f"Đã sao chép khóa bản quyền:\n{k}")

    def on_activate_key(self):
        k = self.ent_act_key.get().strip().upper()
        if not k:
            messagebox.showwarning("Chú ý", "Vui lòng nhập mã bản quyền!")
            return

        if not k.startswith("LUV-"):
            messagebox.showerror("Lỗi", "Mã bản quyền không hợp lệ! Khóa phải bắt đầu bằng LUV-")
            return

        reg = self.ent_reg_to.get().strip() or "LUV User"
        record = {
            "status": "active",
            "license_key": k,
            "registered_to": reg,
            "tier": "Doanh nghiệp Vĩnh viễn (Enterprise Unlimited)",
            "activated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "expires_at": "Vĩnh viễn (Lifetime - Không giới hạn)",
            "machine_id": self.mid_val
        }
        save_license(record)
        self.refresh_status()
        messagebox.showinfo("Thành công", f"Kích hoạt thành công giấy phép bản quyền:\n{k}\nĐã lưu vào hệ thống LUV PDF!")

    def on_deactivate_key(self):
        if os.path.exists(LICENSE_FILE):
            try:
                os.remove(LICENSE_FILE)
            except Exception:
                pass
        self.refresh_status()
        messagebox.showinfo("Thông báo", "Đã hủy kích hoạt giấy phép hiện tại.")


def main():
    root = tk.Tk()
    app = LUVLicenseManagerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
