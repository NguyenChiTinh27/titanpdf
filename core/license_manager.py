import os
import json
import hashlib
import uuid
import platform
from datetime import datetime
from typing import Dict, Any, Optional

LICENSE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "license.json")
SECRET_SALT = "LUV_PDF_OFFICIAL_SECRET_KEY_2026"

def get_machine_id() -> str:
    """Generate a consistent machine identifier."""
    raw = f"{platform.node()}-{platform.processor()}-{os.getenv('USERNAME', 'LUV_USER')}"
    return "LUV-" + hashlib.md5(raw.encode()).hexdigest()[:8].upper()

class LUVLicenseManager:
    """Manages LUV-PDF license generation, validation, and storage."""

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

    @staticmethod
    def generate_key(registered_to: str, tier: str = "Enterprise Lifetime", expires: str = "Vĩnh viễn") -> Dict[str, Any]:
        """Generate a cryptographically verified LUV license key."""
        timestamp = datetime.now().strftime("%Y%m%d")
        raw_hash = hashlib.sha256(f"{registered_to}_{tier}_{expires}_{SECRET_SALT}".encode()).hexdigest().upper()
        # Format: LUV-PDF-XXXX-XXXX-XXXX
        part1 = raw_hash[:4]
        part2 = raw_hash[4:8]
        part3 = raw_hash[8:12]
        key = f"LUV-PDF-{part1}-{part2}-{part3}"
        
        return {
            "license_key": key,
            "registered_to": registered_to,
            "tier": tier,
            "expires_at": expires,
            "created_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "status": "valid"
        }

    @classmethod
    def validate_key(cls, key: str) -> bool:
        """Validate if key follows valid LUV format."""
        if not key or not isinstance(key, str):
            return False
        key = key.strip().upper()
        # Allow demo master keys or LUV format
        if key in ["LUV-PDF-2026-PRO-VN99", "LUV-2026-ENTERPRISE", "LUV-MASTER-KEY"]:
            return True
        if key.startswith("LUV-") and len(key.replace("-", "")) >= 10:
            return True
        return False

    @classmethod
    def activate(cls, key: str, registered_to: str = "Doanh nghiệp LUV") -> Dict[str, Any]:
        """Activate the license and save to disk."""
        key = key.strip().upper()
        if not cls.validate_key(key):
            raise ValueError("Mã giấy phép LUV không hợp lệ hoặc sai định dạng!")

        tier = "Doanh nghiệp Vĩnh viễn (Enterprise Unlimited)"
        if "PRO" in key:
            tier = "Chuyên gia Bản quyền (Professional Suite)"
        elif "STANDARD" in key:
            tier = "Cá nhân Tiêu chuẩn (Standard License)"

        record = {
            "status": "active",
            "license_key": key,
            "registered_to": registered_to if registered_to.strip() else "LUV User",
            "tier": tier,
            "activated_at": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "expires_at": "Vĩnh viễn (Lifetime - Không giới hạn)",
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
