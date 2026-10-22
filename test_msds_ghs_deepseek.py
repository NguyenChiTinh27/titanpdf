import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import tempfile
import docx
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from core.ai_text_engine import AITextEngine
from core.deepseek_ocr import DeepSeekOCR
from core.interlinear_translator import InterlinearTranslator
from core.msds_intelligence import MSDSExtractorEngine

def test_ai_model_standardization():
    print("=== [TEST 1] Kiểm tra chuẩn hóa model AI chuẩn quốc tế deepseek-chat ===")
    assert AITextEngine.PRIMARY_MODEL == "deepseek-chat", f"Expected deepseek-chat, got {AITextEngine.PRIMARY_MODEL}"
    assert DeepSeekOCR.DEFAULT_MODEL == "deepseek-chat", f"Expected deepseek-chat, got {DeepSeekOCR.DEFAULT_MODEL}"
    assert InterlinearTranslator.DEFAULT_MODEL == "deepseek-chat", f"Expected deepseek-chat, got {InterlinearTranslator.DEFAULT_MODEL}"
    print("  ✓ Toàn bộ các module AI đều chuẩn hóa về model: deepseek-chat!")

def test_word_msds_flammable_ghs02_not_non_dg():
    print("=== [TEST 2] Kiểm tra bóc tách file Word MSDS có tính dễ cháy không bị gán NON DG ===")
    # Tạo một file Word (.docx) mô phỏng tài liệu MSDS thực tế có tính chất dễ cháy
    doc = docx.Document()
    doc.add_heading("PHIẾU AN TOÀN HÓA CHẤT (MSDS)", level=1)
    doc.add_paragraph("Tên thương mại: Dung Môi Pha Sơn UV-101")
    doc.add_paragraph("Mã sản phẩm: FTU0005")
    doc.add_paragraph("Nhà sản xuất: VISION NEW MATERIALS VIETNAM CO., LTD")
    
    # Bảng Section 2 (Mục 2)
    p2 = doc.add_paragraph("PHẦN 2: NHẬN DẠNG ĐẶC TÍNH NGUY HIỂM")
    p2_desc = doc.add_paragraph("Phân loại GHS: Chất lỏng dễ cháy (Flammable liquid) - Cấp 2")
    doc.add_paragraph("Từ cảnh báo: Nguy hiểm (Danger)")
    doc.add_paragraph("Cảnh báo nguy cơ: H225: Chất lỏng và hơi rất dễ cháy. H319: Gây kích ứng mắt nghiêm trọng.")
    doc.add_paragraph("Cảnh báo phòng ngừa: P210: Tránh xa nguồn nhiệt, tia lửa, ngọn lửa trần.")
    
    # Bảng thành phần Mục 3
    doc.add_paragraph("PHẦN 3: THÔNG TIN VỀ THÀNH PHẦN HÓA HỌC")
    tbl = doc.add_table(rows=2, cols=3)
    tbl.cell(0, 0).text = "Tên thành phần"
    tbl.cell(0, 1).text = "Số CAS"
    tbl.cell(0, 2).text = "Hàm lượng (%)"
    tbl.cell(1, 0).text = "Ethanol"
    tbl.cell(1, 1).text = "64-17-5"
    tbl.cell(1, 2).text = "80 - 95%"
    
    # Lưu file tạm
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tf:
        temp_docx = tf.name
    
    try:
        doc.save(temp_docx)
        
        # Chạy bóc tách file Word
        result = MSDSExtractorEngine.process_file(
            temp_docx,
            original_filename="MSDS_FTU0005_Flammable.docx",
            engine="heuristic" # Test heuristic rule fallback & guardrails
        )
        
        ghs_codes = result.get("ghs_codes", [])
        signal_word = result.get("signal_word", "")
        print(f"  → Kết quả trích xuất mã GHS: {ghs_codes}")
        print(f"  → Từ cảnh báo: {signal_word}")
        
        # Khẳng định chất lượng: BẮT BUỘC có GHS02, TUYỆT ĐỐI KHÔNG ĐƯỢC LÀ NON DG
        assert "GHS02" in ghs_codes, f"LỖI: Kỳ vọng GHS02 (Dễ cháy), nhưng nhận được: {ghs_codes}"
        assert "NON DG" not in ghs_codes, f"LỖI: Tệp dễ cháy bị gán nhầm thành NON DG!"
        assert "Danger" in signal_word or "Nguy hiểm" in signal_word, f"LỖI: Từ cảnh báo phải là Nguy hiểm, nhận được: {signal_word}"
        print("  ✓ Tệp Word MSDS dễ cháy được bóc tách chính xác GHS02, không còn bị gán nhầm NON DG!")
    finally:
        if os.path.exists(temp_docx):
            os.remove(temp_docx)

def test_prune_phantom_ghs_codes():
    print("=== [TEST 3] Kiểm tra khử triệt để 'hình đồ từa lưa' (Phantom GHS) ===")
    # Giả lập tình huống AI bị ảo giác sinh thêm GHS05 (ăn mòn), GHS06 (độc cấp) nhưng văn bản chỉ có GHS02 (dễ cháy)
    mock_ai_output = {
        "product_code": "ZN009",
        "product_name_vi": "Chất pha loãng dễ cháy",
        "ghs_codes": ["GHS02", "GHS05", "GHS06"], # GHS05, GHS06 là ảo giác không có trong bài
        "signal_word": "Nguy hiểm (Danger)"
    }
    
    doc = docx.Document()
    doc.add_paragraph("Mã sản phẩm: ZN009")
    doc.add_paragraph("PHẦN 2: NHẬN DẠNG MỐI NGUY")
    doc.add_paragraph("Chất lỏng dễ cháy (Flammable liquid) Cấp 2. H225: Chất lỏng và hơi rất dễ cháy.")
    
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tf:
        temp_docx = tf.name
    
    try:
        doc.save(temp_docx)
        # Monkey patch parse_with_deepseek để trả về mock_ai_output
        orig_fn = MSDSExtractorEngine.parse_with_deepseek
        MSDSExtractorEngine.parse_with_deepseek = lambda *args, **kwargs: mock_ai_output
        
        res = MSDSExtractorEngine.process_file(temp_docx, original_filename="ZN009.docx", engine="deepseek")
        ghs_codes = res.get("ghs_codes", [])
        print(f"  → Mã GHS sau khi lọc đối soát: {ghs_codes}")
        
        # GHS02 phải được giữ lại vì có từ khóa dễ cháy, còn GHS05, GHS06 phải bị loại bỏ vì không có căn cứ
        assert "GHS02" in ghs_codes, "GHS02 phải tồn tại"
        assert "GHS05" not in ghs_codes, "LỖI: GHS05 ảo giác không bị loại bỏ!"
        assert "GHS06" not in ghs_codes, "LỖI: GHS06 ảo giác không bị loại bỏ!"
        print("  ✓ Đã khử hoàn toàn các hình đồ GHS ảo giác không có căn cứ!")
    finally:
        MSDSExtractorEngine.parse_with_deepseek = orig_fn
        if os.path.exists(temp_docx):
            os.remove(temp_docx)

def test_genuine_non_dg_file():
    print("=== [TEST 4] Kiểm tra tệp thực sự NON DG (Nước, keo nước không nguy hại) ===")
    doc = docx.Document()
    doc.add_paragraph("PHIẾU AN TOÀN HÓA CHẤT")
    doc.add_paragraph("Tên: Keo nước PVA dán giấy")
    doc.add_paragraph("PHẦN 2: NHẬN DẠNG NGUY CƠ")
    doc.add_paragraph("Sản phẩm không thuộc danh mục nguy hại. Not classified as hazardous according to GHS.")
    doc.add_paragraph("Từ cảnh báo: Không có")
    
    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tf:
        temp_docx = tf.name
    
    try:
        doc.save(temp_docx)
        res = MSDSExtractorEngine.process_file(temp_docx, original_filename="PVA_Water.docx", engine="heuristic")
        ghs_codes = res.get("ghs_codes", [])
        print(f"  → Mã GHS tệp không nguy hại: {ghs_codes}")
        assert ghs_codes == ["NON DG"], f"LỖI: Tệp không nguy hại phải trả về ['NON DG'], nhận được: {ghs_codes}"
        print("  ✓ Tệp thực sự an toàn được phân loại chính xác NON DG!")
    finally:
        if os.path.exists(temp_docx):
            os.remove(temp_docx)

if __name__ == "__main__":
    print("==================================================================")
    print("🚀 BẮT ĐẦU KIỂM THỬ HỆ THỐNG AI DEEPSEEK-V4.1-FLASH & GHS MSDS")
    print("==================================================================")
    test_ai_model_standardization()
    test_word_msds_flammable_ghs02_not_non_dg()
    test_prune_phantom_ghs_codes()
    test_genuine_non_dg_file()
    print("==================================================================")
    print("🎉 TOÀN BỘ CÁC BÀI KIỂM THỬ AI & GHS BÓC TÁCH MSDS ĐÃ ĐẠT 100% PASS!")
    print("==================================================================")
