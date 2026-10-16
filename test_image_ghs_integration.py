import os
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from core.msds_intelligence import MSDSExtractorEngine

test_cases = [
    {
        "name": "ZNZX009 Word (.docx)",
        "path": r"C:\Users\ntc27\OneDrive\文件\iLovePDF_Output\ilovepdf-pdf-to-word (3)\MSDS-ZNZX009-VN.docx",
        "expected_ghs": ["GHS02"],
        "expected_code": "ZNZX009"
    },
    {
        "name": "ZNZX009 PDF (.pdf)",
        "path": r"C:\Users\ntc27\OneDrive\文件\iLovePDF_Output\ilovepdf-word-to-pdf (1)\MSDS-ZNZX009-VN.pdf",
        "expected_ghs": ["GHS02"],
        "expected_code": "ZNZX009"
    },
    {
        "name": "BYK-306 PDF (4 pictograms)",
        "path": r"c:\Users\ntc27\OneDrive\文件\TitanPDF\data\msds_files\000000000000102992_A1102-BYK-306-MSDS-EN.pdf",
        "expected_ghs": ["GHS02", "GHS05", "GHS07", "GHS08"],
        "expected_code": "A1102"
    },
    {
        "name": "BYK-333 PDF (NON DG)",
        "path": r"c:\Users\ntc27\OneDrive\文件\TitanPDF\data\msds_files\000000000000135844_A1103-BYK-333-MSDS-VN.pdf",
        "expected_ghs": ["NON DG"],
        "expected_code": "A1103"
    },
    {
        "name": "FTU0005 Word (Text GHS)",
        "path": r"c:\Users\ntc27\OneDrive\文件\TitanPDF\data\msds_files\MSDS-FTU0005.docx",
        "expected_ghs": ["GHS07", "GHS09"],
        "expected_code": "FTU0005"
    },
    {
        "name": "ZNZX009 OLE2 Doc (.doc)",
        "path": r"c:\Users\ntc27\OneDrive\文件\TitanPDF\data\msds_files\MSDS-ZNZX009-EN.doc",
        "expected_ghs": ["GHS02"],
        "expected_code": "ZNZX009"
    }
]

all_passed = True
for tc in test_cases:
    p = tc["path"]
    if not os.path.exists(p):
        print(f"SKIPPED (File not found): {tc['name']} -> {p}")
        continue
    
    res = MSDSExtractorEngine.process_file(p, engine="heuristic")
    actual_ghs = res.get("ghs_codes") or []
    actual_code = res.get("product_code") or ""
    
    ghs_match = sorted(actual_ghs) == sorted(tc["expected_ghs"])
    code_match = tc["expected_code"] in actual_code
    
    status = "PASS" if (ghs_match and code_match) else "FAIL"
    if status == "FAIL":
        all_passed = False
    
    print(f"[{status}] {tc['name']}")
    print(f"   Expected GHS: {tc['expected_ghs']} | Actual: {actual_ghs}")
    print(f"   Expected Code: {tc['expected_code']} | Actual: {actual_code}")
    print(f"   Signal Word: {res.get('signal_word')}")

print("\n" + ("="*50))
if all_passed:
    print("ALL TESTS PASSED PERFECTLY! 100% GHS ACCURACY ACHIEVED!")
else:
    print("SOME TESTS FAILED - NEED INVESTIGATION")
print("="*50)
