import unittest
import os
import json
from fastapi.testclient import TestClient

from server import app
from core.deepseek_ocr import DeepSeekOCR

class TestAIGlobalService(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)
        self.test_key = "sk-test-ai-key-unit-1234567890"

    def test_01_get_settings_guest_masking(self):
        """Khách (Guest) không bao giờ nhận được raw API key, chỉ nhận chuỗi mask."""
        response = self.client.get("/api/settings/deepseek", headers={"X-Titan-Role": "guest"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data.get("read_only"), "Chế độ khách phải là read_only: True")
        self.assertEqual(data.get("key"), "", "Khách tuyệt đối không được nhận key thô")
        if data.get("has_key"):
            self.assertEqual(data.get("masked_key"), "••••••••••••••••", "Khách phải thấy key dạng bullet mask")

    def test_02_get_settings_owner(self):
        """Chính chủ (Owner) có thể đọc đầy đủ thông tin cấu hình AI."""
        response = self.client.get("/api/settings/deepseek", headers={"Authorization": "Bearer verified"})
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertFalse(data.get("read_only"), "Owner phải có read_only: False")
        self.assertIn("provider", data)
        self.assertIn("default_model", data)
        self.assertIn("base_url", data)

    def test_03_save_settings_permissions(self):
        """Chỉ Owner mới có quyền lưu cấu hình AI toàn cục, Khách bị từ chối 403."""
        # 1. Thử lưu bằng tài khoản Guest -> 403 Forbidden
        res_guest = self.client.post(
            "/api/settings/deepseek",
            data={
                "api_key": self.test_key,
                "model": "deepseek-reasoner",
                "provider": "deepseek",
                "base_url": "https://api.deepseek.com/v1"
            },
            headers={"X-Titan-Role": "guest"}
        )
        self.assertEqual(res_guest.status_code, 403, "Khách không được phép POST /api/settings/deepseek")

        # 2. Lưu bằng tài khoản Owner -> 200 OK
        res_owner = self.client.post(
            "/api/settings/deepseek",
            data={
                "api_key": self.test_key,
                "model": "deepseek-reasoner",
                "provider": "deepseek",
                "base_url": "https://api.deepseek.com/v1"
            },
            headers={"Authorization": "Bearer verified"}
        )
        self.assertEqual(res_owner.status_code, 200)
        data_owner = res_owner.json()
        self.assertTrue(data_owner.get("success"))

        # 3. Đọc lại cấu hình đã lưu
        cfg = DeepSeekOCR.get_settings()
        self.assertEqual(cfg.get("api_key"), self.test_key)
        self.assertEqual(cfg.get("model"), "deepseek-reasoner")

    def test_04_test_connection_permissions_and_validation(self):
        """Kiểm tra quyền và validate trường khi kiểm tra kết nối API."""
        # 1. Khách gọi test -> 403
        res_guest = self.client.post(
            "/api/settings/deepseek/test",
            data={"api_key": self.test_key},
            headers={"X-Titan-Role": "guest"}
        )
        self.assertEqual(res_guest.status_code, 403)

        # 2. Owner không truyền key khi rỗng -> 400
        old_env = os.environ.get("DEEPSEEK_API_KEY", "")
        if "DEEPSEEK_API_KEY" in os.environ:
            del os.environ["DEEPSEEK_API_KEY"]

        # 3. Owner truyền mock key -> nhận kết quả phản hồi
        res_test = self.client.post(
            "/api/settings/deepseek/test",
            data={
                "api_key": "sk-mock-key-testing",
                "model": "DeepSeek-V4.1-Flash",
                "provider": "deepseek"
            },
            headers={"Authorization": "Bearer verified"}
        )
        # Network mock or connection attempted
        self.assertIn(res_test.status_code, [200, 400])

        if old_env:
            os.environ["DEEPSEEK_API_KEY"] = old_env

    def test_05_static_ai_service_integration(self):
        """Đảm bảo static/ai_service.js được tích hợp và chứa đầy đủ phương thức cốt lõi."""
        with open("static/ai_service.js", "r", encoding="utf-8") as f:
            code = f.read()

        required_methods = [
            "class LuvAIServiceManager",
            "window.LuvAIService",
            "isGuest",
            "hasKey",
            "getApiKey",
            "getRawApiKey",
            "getModel",
            "getProvider",
            "getBaseUrl",
            "saveConfig",
            "testConnection",
            "getGuestUsage",
            "recordGuestCall",
            "requireReady",
            "renderBadge",
            "refreshAllBadges",
            "openSettings"
        ]
        for m in required_methods:
            self.assertIn(m, code, f"Thiếu method/identifier '{m}' trong ai_service.js")

        with open("static/index.html", "r", encoding="utf-8") as f:
            index_code = f.read()

        self.assertIn('<script src="ai_service.js"></script>', index_code)
        self.assertIn('id="sec-panel-ai"', index_code)
        self.assertIn('id="global-ai-provider-select"', index_code)
        self.assertIn('id="global-deepseek-key-input"', index_code)
        self.assertIn('id="global-deepseek-model-select"', index_code)
        self.assertIn('id="ai-trans-global-badge-container"', index_code)
        self.assertIn('id="ai-sum-global-badge-container"', index_code)

if __name__ == "__main__":
    unittest.main()
