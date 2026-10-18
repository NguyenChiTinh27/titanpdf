import os
import json
import hashlib
import uuid
import platform
import threading
import urllib.request
import urllib.error
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LICENSE_FILE = os.path.join(BASE_DIR, "license.json")
LICENSES_DB_FILE = os.path.join(BASE_DIR, "licenses_db.json")
SECRET_SALT = "LUV_PDF_OFFICIAL_SECRET_KEY_2026"

CLOUDFLARE_ADMIN_URL = "https://luv-license-api.luv-sds.workers.dev"
CLOUDFLARE_ADMIN_TOKEN = "rHHfK9eC_8lTH02SP0CQPnyXAqMMDUXxwV2MiPothM7Avc4TxNZgnkKp5CFsIBP_"

_db_lock = threading.Lock()

def get_machine_id() -> str:
    """Generate a consistent machine identifier."""
    raw = f"{platform.node()}-{platform.processor()}-{os.getenv('USERNAME', 'LUV_USER')}"
    return "LUV-" + hashlib.md5(raw.encode()).hexdigest()[:8].upper()


class LUVLicenseManager:
    """Manages LUV-PDF license generation, validation, storage, and online registry."""

    @staticmethod
    def _read_db() -> List[Dict[str, Any]]:
        with _db_lock:
            if not os.path.exists(LICENSES_DB_FILE):
                return []
            try:
                with open(LICENSES_DB_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
            except Exception:
                return []

    @staticmethod
    def _write_db(records: List[Dict[str, Any]]) -> None:
        with _db_lock:
            temp_path = LICENSES_DB_FILE + ".tmp"
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(records, f, ensure_ascii=False, indent=2)
            if os.path.exists(LICENSES_DB_FILE):
                os.replace(temp_path, LICENSES_DB_FILE)
            else:
                os.rename(temp_path, LICENSES_DB_FILE)

    @staticmethod
    def get_info() -> Dict[str, Any]:
        """Read current stored license info."""
        if not os.path.exists(LICENSE_FILE):
            return {
                "is_active": False,
                "license_key": None,
                "registered_to": None,
                "tier": "Chưa kích hoạt",
                "expires_at": None,
                "machine_id": get_machine_id()
            }
        try:
            with open(LICENSE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["is_active"] = data.get("status") == "active"
                data["machine_id"] = get_machine_id()
                return data
        except Exception:
            return {
                "is_active": False,
                "license_key": None,
                "registered_to": None,
                "tier": "Chưa kích hoạt",
                "expires_at": None,
                "machine_id": get_machine_id()
            }

    @classmethod
    def generate_key(
        cls, 
        registered_to: str, 
        tier: str = "Enterprise Lifetime", 
        expires: str = "Vĩnh viễn",
        notes: str = "",
        save_to_db: bool = True
    ) -> Dict[str, Any]:
        """
        Generate a cryptographically verified LUV license key.
        Connects directly to Cloudflare Worker D1 to issue an official Ed25519-backed key.
        """
        reg_clean = (registered_to or "LUV Client").strip()
        tier_clean = (tier or "Enterprise Lifetime").strip()
        exp_clean = (expires or "Vĩnh viễn").strip()

        # Parse expiry date to YYYY-MM-DD
        exp_date_str = "2036-12-31"
        if "1 tháng" in exp_clean.lower() or "30 ngày" in exp_clean.lower():
            exp_date_str = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
        elif "3 tháng" in exp_clean.lower():
            exp_date_str = (datetime.now() + timedelta(days=90)).strftime("%Y-%m-%d")
        elif "6 tháng" in exp_clean.lower():
            exp_date_str = (datetime.now() + timedelta(days=180)).strftime("%Y-%m-%d")
        elif "1 năm" in exp_clean.lower() or "12 tháng" in exp_clean.lower():
            exp_date_str = (datetime.now() + timedelta(days=365)).strftime("%Y-%m-%d")

        key = None
        record_id = None
        try:
            cf_payload = {
                "customer_name": reg_clean,
                "customer_email": "",
                "expires_at": exp_date_str,
                "products": {
                    "DOC": {"enabled": True, "max_devices": 10},
                    "SDS": {"enabled": True, "max_devices": 10}
                },
                "offline_days": 14,
                "plan": "enterprise" if "Enterprise" in tier_clean else "pro",
                "features": ["core", "import", "export", "edit", "doc_tran"],
                "notes": notes.strip()
            }
            req = urllib.request.Request(
                f"{CLOUDFLARE_ADMIN_URL}/v1/admin/licenses",
                data=json.dumps(cf_payload).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {CLOUDFLARE_ADMIN_TOKEN}",
                    "Content-Type": "application/json",
                    "User-Agent": "LUV-License-Admin/1.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=12) as resp:
                cf_res = json.loads(resp.read().decode("utf-8"))
                key = cf_res.get("license_key")
                record_id = cf_res.get("id")
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")
                err_json = json.loads(err_body)
                err_msg = err_json.get("message") or err_json.get("error") or str(e)
            except Exception:
                err_msg = str(e)
            raise RuntimeError(f"Lỗi máy chủ Cloudflare Worker ({e.code}): {err_msg}")
        except Exception as e:
            raise RuntimeError(f"Lỗi kết nối máy chủ Cloudflare Worker: {str(e)}")

        if not key:
            raise RuntimeError("Máy chủ Cloudflare Worker không trả về mã bản quyền hợp lệ.")

        record = {
            "id": record_id or str(uuid.uuid4()),
            "license_key": key,
            "registered_to": reg_clean,
            "tier": tier_clean,
            "expires_at": exp_clean,
            "created_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "status": "active",
            "notes": notes.strip(),
            "handover_message": cls.format_handover_message(key, reg_clean, tier_clean, exp_clean)
        }

        if save_to_db:
            db = cls._read_db()
            existing_idx = next((i for i, r in enumerate(db) if r.get("license_key") == key), None)
            if existing_idx is not None:
                db[existing_idx] = record
            else:
                db.insert(0, record)
            cls._write_db(db)

        return record

    @staticmethod
    def format_handover_message(key: str, registered_to: str, tier: str, expires: str) -> str:
        """Format a polite, professional handover message for clients."""
        return (
            f"🎉 CHÚC MỪNG QUÝ KHÁCH ĐÃ ĐĂNG KÝ BẢN QUYỀN LUV-DOC-TRAN THÀNH CÔNG!\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 Khách hàng / Doanh nghiệp : {registered_to}\n"
            f"📦 Gói bản quyền             : {tier}\n"
            f"⏳ Thời hạn sử dụng          : {expires}\n"
            f"🔑 MÃ BẢN QUYỀN (LICENSE KEY): {key}\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"📖 HƯỚNG DẪN KÍCH HOẠT NHANH (CHỈ 10 GIÂY):\n"
            f"1. Mở ứng dụng LUV-DOC-TRAN trên trình duyệt.\n"
            f"2. Bấm vào nút '🔑 Kích Hoạt Bản Quyền' ở góc trên bên phải màn hình.\n"
            f"3. Dán chính xác Mã Bản Quyền ở trên và bấm 'Kích Hoạt Ngay'.\n"
            f"4. Hệ thống sẽ mở khóa vĩnh viễn toàn bộ tính năng dịch song ngữ Word, PDF, Excel!\n\n"
            f"✨ Xin trân trọng cảm ơn Quý khách đã tin tưởng và đồng hành cùng hệ sinh thái LUV!"
        )

    @classmethod
    def list_licenses(cls, search: str = "", status: str = "") -> List[Dict[str, Any]]:
        """List license keys querying Cloudflare Worker D1 directly, with local cache fallback."""
        search = (search or "").strip().lower()
        status = (status or "").strip().lower()

        remote_items = []
        try:
            req = urllib.request.Request(
                f"{CLOUDFLARE_ADMIN_URL}/v1/admin/licenses",
                headers={
                    "Authorization": f"Bearer {CLOUDFLARE_ADMIN_TOKEN}",
                    "User-Agent": "LUV-License-Admin/1.0"
                }
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                for lic in data.get("licenses", []):
                    prefix = lic.get("license_key_prefix") or lic.get("key_prefix") or "LUV"
                    active_dev = lic.get("active_devices", 0)
                    max_dev = lic.get("max_devices", 1)
                    device_str = f"{active_dev}/{max_dev} máy"
                    masked_key = f"{prefix}-••••••••••••••••"
                    
                    remote_items.append({
                        "id": lic.get("id"),
                        "license_key": masked_key,
                        "license_key_prefix": prefix,
                        "registered_to": lic.get("customer_name") or "Khách hàng LUV",
                        "tier": f"Cloudflare D1 ({str(lic.get('plan', 'standard')).upper()})",
                        "expires_at": lic.get("expires_at") or "Vĩnh viễn",
                        "created_at": lic.get("created_at") or "",
                        "status": lic.get("status") or "active",
                        "notes": f"Thiết bị: {device_str}",
                        "devices": device_str,
                        "active_devices": active_dev,
                        "max_devices": max_dev
                    })
        except Exception:
            pass

        local_db = cls._read_db()
        combined = []
        seen_ids = set()
        local_by_id = {item.get("id"): item for item in local_db if item.get("id")}
        
        for r_item in remote_items:
            rid = r_item.get("id")
            if rid:
                seen_ids.add(rid)
                loc = local_by_id.get(rid)
                if loc and loc.get("license_key") and not loc.get("license_key").endswith("••••"):
                    r_item["full_key"] = loc.get("license_key")
                    r_item["handover_message"] = loc.get("handover_message")
            combined.append(r_item)

        for loc in local_db:
            lid = loc.get("id")
            if lid and lid not in seen_ids:
                combined.append(loc)

        results = []
        for item in combined:
            if status and item.get("status", "").lower() != status:
                continue
            if search:
                match_key = search in str(item.get("license_key", "")).lower()
                match_reg = search in str(item.get("registered_to", "")).lower()
                match_tier = search in str(item.get("tier", "")).lower()
                match_notes = search in str(item.get("notes", "")).lower()
                if not (match_key or match_reg or match_tier or match_notes):
                    continue
            results.append(item)
        return results

    # Alias list_keys to list_licenses
    list_keys = list_licenses

    @classmethod
    def reset_devices(cls, license_id: str) -> Dict[str, Any]:
        """
        Reset active device bindings for a license in Cloudflare D1.
        Calls POST /v1/admin/licenses/{license_id}/reset-devices
        """
        if not license_id or not isinstance(license_id, str):
            return {"success": False, "ok": False, "message": "Mã ID giấy phép không hợp lệ."}
        
        target_id = license_id.strip()
        # If passed a license_key, try to find ID from local DB
        if not ("-" in target_id and len(target_id) == 36):
            db = cls._read_db()
            for item in db:
                if item.get("license_key") == target_id:
                    target_id = item.get("id")
                    break

        try:
            req = urllib.request.Request(
                f"{CLOUDFLARE_ADMIN_URL}/v1/admin/licenses/{target_id}/reset-devices",
                data=json.dumps({}).encode("utf-8"),
                headers={
                    "Authorization": f"Bearer {CLOUDFLARE_ADMIN_TOKEN}",
                    "Content-Type": "application/json",
                    "User-Agent": "LUV-License-Admin/1.0"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "success": True,
                    "ok": True,
                    "id": target_id,
                    "action": data.get("action", "reset-devices"),
                    "message": "Đã đặt lại liên kết thiết bị thành công."
                }
        except urllib.error.HTTPError as e:
            err_body = ""
            try:
                err_body = e.read().decode("utf-8")
                err_json = json.loads(err_body)
                err_msg = err_json.get("message") or err_json.get("error") or str(e)
            except Exception:
                err_msg = str(e)
            return {"success": False, "ok": False, "message": f"Lỗi Cloudflare API ({e.code}): {err_msg}"}
        except Exception as e:
            return {"success": False, "ok": False, "message": f"Lỗi kết nối máy chủ Cloudflare: {str(e)}"}

    @classmethod
    def revoke_key(cls, key_or_id: str) -> bool:
        """Revoke an active key in Cloudflare D1 and local DB."""
        if not key_or_id or not isinstance(key_or_id, str):
            return False
        identifier = key_or_id.strip()
        
        target_id = None
        try:
            target_id = str(uuid.UUID(identifier))
        except ValueError:
            pass

        # 1. Update local DB if present
        db = cls._read_db()
        updated_local = False
        for item in db:
            if (target_id and item.get("id") == target_id) or item.get("license_key") == identifier or (item.get("id") == identifier):
                item["status"] = "revoked"
                item["revoked_at"] = datetime.now().strftime("%d/%m/%Y %H:%M")
                if not target_id:
                    target_id = item.get("id")
                updated_local = True
                break
        if updated_local:
            cls._write_db(db)

        # 2. Call Cloudflare Worker if ID known
        cf_success = False
        if target_id:
            try:
                req = urllib.request.Request(
                    f"{CLOUDFLARE_ADMIN_URL}/v1/admin/licenses/{target_id}/revoke",
                    data=json.dumps({}).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {CLOUDFLARE_ADMIN_TOKEN}",
                        "Content-Type": "application/json",
                        "User-Agent": "LUV-License-Admin/1.0"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status in (200, 201):
                        cf_success = True
            except Exception:
                pass
        return updated_local or cf_success

    @classmethod
    def delete_key(cls, key_or_id: str) -> bool:
        """Permanently delete a key from registry and Cloudflare D1."""
        if not key_or_id or not isinstance(key_or_id, str):
            return False
        identifier = key_or_id.strip()
        target_id = None
        try:
            target_id = str(uuid.UUID(identifier))
        except ValueError:
            pass

        db = cls._read_db()
        new_db = []
        deleted_local = False
        for item in db:
            if (target_id and item.get("id") == target_id) or item.get("license_key") == identifier or (item.get("id") == identifier):
                if not target_id:
                    target_id = item.get("id")
                deleted_local = True
            else:
                new_db.append(item)
        if deleted_local:
            cls._write_db(new_db)

        cf_deleted = False
        if target_id:
            try:
                req = urllib.request.Request(
                    f"{CLOUDFLARE_ADMIN_URL}/v1/admin/licenses/{target_id}/delete",
                    data=json.dumps({"confirm": True}).encode("utf-8"),
                    headers={
                        "Authorization": f"Bearer {CLOUDFLARE_ADMIN_TOKEN}",
                        "Content-Type": "application/json",
                        "User-Agent": "LUV-License-Admin/1.0"
                    },
                    method="POST"
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    if resp.status in (200, 201):
                        cf_deleted = True
            except Exception:
                pass
        return deleted_local or cf_deleted

    @classmethod
    def verify_key_online(cls, key: str) -> Dict[str, Any]:
        """
        Verify license key online against the registry.
        If in DB: returns DB status and details.
        """
        if not key or not isinstance(key, str):
            return {"valid": False, "reason": "Mã khóa trống"}
        
        clean_key = key.strip().upper()
        
        # 1. Check registry DB
        db = cls._read_db()
        for item in db:
            if item.get("license_key") == clean_key:
                is_active = item.get("status") == "active"
                return {
                    "valid": is_active,
                    "status": item.get("status"),
                    "license_key": clean_key,
                    "registered_to": item.get("registered_to"),
                    "tier": item.get("tier"),
                    "expires_at": item.get("expires_at"),
                    "created_at": item.get("created_at"),
                    "source": "registry"
                }

        # 2. Master Demo keys / Owner key
        if clean_key in ["LUV-PDF-2026-PRO-VN99", "LUV-2026-ENTERPRISE", "LUV-MASTER-KEY", "LUV-EGKRH-HZCWD-7PBLS-ZG5G8"]:
            return {
                "valid": True,
                "status": "active",
                "license_key": clean_key,
                "registered_to": "Quản Trị Viên VIP",
                "tier": "Doanh nghiệp Vĩnh viễn (Master Key)",
                "expires_at": "Vĩnh viễn",
                "source": "master"
            }

        return {"valid": False, "reason": "Mã khóa không tồn tại trên hệ thống hoặc đã bị thu hồi."}

    @classmethod
    def validate_key(cls, key: str) -> bool:
        """Validate if key is a valid active key."""
        if not key or not isinstance(key, str):
            return False
        verif = cls.verify_key_online(key)
        return bool(verif.get("valid"))

    @classmethod
    def activate(cls, key: str, registered_to: str = "Doanh nghiệp LUV") -> Dict[str, Any]:
        """Activate the license and save to disk."""
        key = key.strip().upper()
        verif = cls.verify_key_online(key)
        if not verif.get("valid"):
            raise ValueError(verif.get("reason", "Mã giấy phép LUV không hợp lệ hoặc đã bị thu hồi!"))

        tier = verif.get("tier", "Doanh nghiệp Vĩnh viễn (Enterprise Unlimited)")
        reg_name = registered_to if (registered_to and registered_to.strip() != "LUV User") else verif.get("registered_to", "Doanh nghiệp LUV")

        record = {
            "status": "active",
            "license_key": key,
            "registered_to": reg_name,
            "tier": tier,
            "activated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "expires_at": verif.get("expires_at", "Vĩnh viễn (Lifetime - Không giới hạn)"),
            "machine_id": get_machine_id()
        }

        with open(LICENSE_FILE, "w", encoding="utf-8") as f:
            json.dump(record, f, ensure_ascii=False, indent=2)

        record["is_active"] = True
        return record

    @classmethod
    def deactivate(cls) -> bool:
        """Remove existing license."""
        if os.path.exists(LICENSE_FILE):
            try:
                os.remove(LICENSE_FILE)
            except Exception:
                pass
        return True
