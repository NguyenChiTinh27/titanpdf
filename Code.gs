/**
 * ===================================================================================
 * TITANPDF & LUV-MSDS SUITE - GOOGLE CLOUD STORAGE & TWO-WAY SYNC GATEWAY
 * Kịch bản Google Apps Script Đồng Bộ Hai Chiều Sổ Hóa Chất CIL & Lưu Trữ Google Drive
 * Dự án Apps Script: 11pPMG0YZDYqOKLkncq8BEP2fX3HeK103u6rojjQVHS-t9uA3Z5AMvUoZ
 * Phiên bản: 3.5.0 Pro - Chuẩn 38 Cột GHS & Luật Hóa Chất 2026
 * Hỗ trợ đồng thời: Webhook API 2 Chiều Cho TitanPDF + Giao Diện Web App Trực Tiếp Trên GAS
 * ===================================================================================
 */

/**
 * HÀM KIỂM TRA & CẤP QUYỀN TRUY CẬP (Bấm '▶ Chạy' hàm này trên thanh công cụ để cấp quyền Google Drive & Sheets)
 */
function testAuth() {
  Logger.log("Đang kiểm tra quyền Google Drive và Google Sheets...");
  var ss = getOrCreateSpreadsheet();
  Logger.log("✓ Google Sheet CSDL: " + ss.getUrl());
  var folder = getOrCreateFolder(CONFIG.DRIVE_ROOT_FOLDER);
  Logger.log("✓ Thư mục Google Drive: " + folder.getUrl());
  var ping = handlePing();
  Logger.log("✓ Kết quả kiểm tra kết nối: " + JSON.stringify(ping));
  return ping;
}

// CẤU HÌNH HỆ THỐNG
var CONFIG = {
  SECRET_TOKEN: "LUV_PDF_SYNC_KEY_2026",
  ALT_SECRET_TOKEN: "LUV_MSDS_SECURE_TOKEN_2026",
  DRIVE_ROOT_FOLDER: "LUV_PDF_Exports",
  DRIVE_SUB_FOLDER: "MSDS_Originals",
  SHEET_NAME_CIL: "CIL_Chemical_Inventory",
  SHEET_NAME_HSE: "HSE_Defect_Tracker"
};

/**
 * 18 TIÊU ĐỀ CỘT CHUẨN ĐỒNG BỘ THEO DÕI SỰ CỐ & KHẮC PHỤC LỖI HSE (TRACKER)
 */
var HSE_DEFECT_HEADERS = [
  "defect_id", "code", "date", "month", "department", "dept_key",
  "category", "zh_issue", "vn_issue", "status", "improved", "improve_date",
  "note", "img_before", "img_after", "drive_direct_url", "drive_view_url",
  "updated_at"
];

function getCilVersion() {
  try {
    var props = PropertiesService.getScriptProperties();
    var v = props.getProperty("CIL_VERSION");
    if (!v) {
      v = "1";
      props.setProperty("CIL_VERSION", v);
    }
    return parseInt(v, 10);
  } catch (e) {
    return 1;
  }
}

function incrementCilVersion() {
  try {
    var props = PropertiesService.getScriptProperties();
    var v = getCilVersion() + 1;
    props.setProperty("CIL_VERSION", v.toString());
    return v;
  } catch (e) {
    return 2;
  }
}

/**
 * 16 TIÊU ĐỀ CỘT CHUẨN GOOGLE SHEETS (MSDS_CIL_DB / MSDS_CIL)
 */
var CIL_16_HEADERS = [
  "id", "product_code", "category", "chemical_name", "usage",
  "updated_date", "cas_number", "legal_flags", "supplier",
  "ghs_classifications", "ghs_16_sections", "file_name",
  "drive_file_id", "drive_view_url", "drive_download_url", "last_synced_at"
];

/**
 * 38 TIÊU ĐỀ CỘT CHUẨN ĐỒNG BỘ HAI CHIỀU (SINGLE SOURCE OF TRUTH - SSOT)
 */
var CIL_HEADERS = [
  "chemical_id", "product_code", "product_name_vi", "product_name_original",
  "item_type", "mother_msds_id", "cas_primary", "un_no", "transport_class",
  "packing_group", "signal_word", "ghs_codes", "hazard_statements",
  "precautionary_statements", "flash_point", "density", "appearance",
  "storage_condition", "respiratory_protection", "hand_protection",
  "eye_protection", "skin_protection", "first_aid_inhalation",
  "first_aid_skin", "first_aid_eyes", "first_aid_ingestion",
  "fire_measures", "spill_measures", "compositions_json", "source_file",
  "drive_file_id", "drive_view_url", "drive_download_url", "sha256",
  "sync_status", "created_at", "updated_at", "deleted_at"
];

/**
 * Endpoint tiếp nhận yêu cầu GET:
 * - Khi gọi qua API (có tham số ?action=... hoặc ?format=json): Trả về JSON cho TitanPDF.
 * - Khi mở trực tiếp trên trình duyệt web: Trả về Giao Diện Web App Pastel Kawaii Pro đầy đủ!
 */
function doGet(e) {
  var action = (e && e.parameter && e.parameter.action) ? e.parameter.action : "";
  var token = (e && e.parameter && e.parameter.token) ? e.parameter.token : "";
  var format = (e && e.parameter && e.parameter.format) ? e.parameter.format : "";

  // 1. Phục vụ API Webhook nếu có action hoặc yêu cầu format=json
  if (action || format === "json") {
    if (action !== "ping" && action !== "test_connection") {
      if (token && !isTokenAuthorized(token)) {
        return jsonResponse({ status: "error", error: "Sai mã Secret Token bảo mật!" }, 403);
      }
    }

    if (action === "ping" || action === "test_connection") {
      return jsonResponse(handlePing());
    } else if (action === "getAllChemicals" || action === "list") {
      return jsonResponse(handleGetAllChemicals());
    } else if (action === "getAllDefects" || action === "listDefects") {
      return jsonResponse(handleGetAllDefects());
    } else if (action === "initHeaders") {
      return jsonResponse(ensureSheetStructure());
    }

    return jsonResponse({
      status: "ok",
      service: "TitanPDF MSDS Google Apps Script Gateway",
      version: getCilVersion(),
      total_columns: CIL_HEADERS.length,
      timestamp: new Date().toISOString()
    });
  }

  // 2. Mở trực tiếp trên trình duyệt: Render Giao diện Web App tương tác tuyệt đẹp
  return renderWebAppUI();
}

/**
 * Endpoint tiếp nhận yêu cầu POST (CRUD Dữ liệu & Lưu trữ Tệp Google Drive từ TitanPDF)
 */
function doPost(e) {
  var lock = LockService.getScriptLock();
  try {
    lock.waitLock(15000); // Khóa chống xung đột ghi dữ liệu đồng thời
  } catch (lockErr) {
    return jsonResponse({ status: "error", error: "Hệ thống Google Apps Script đang bận, vui lòng thử lại sau giây lát." }, 429);
  }

  try {
    if (!e || !e.postData || !e.postData.contents) {
      return jsonResponse({ status: "error", error: "Dữ liệu yêu cầu rỗng (Empty POST Body)!" }, 400);
    }

    var payload = {};
    try {
      payload = JSON.parse(e.postData.contents);
    } catch (parseErr) {
      return jsonResponse({ status: "error", error: "Dữ liệu JSON không hợp lệ: " + parseErr.toString() }, 400);
    }

    var action = payload.action || "";
    var token = String(payload.token || (e.parameter && e.parameter.token) || "").trim();
    if (action !== "ping" && action !== "test_connection") {
      if (token && !isTokenAuthorized(token)) {
        return jsonResponse({ status: "error", error: "Xác thực thất bại: Sai Secret Token!" }, 403);
      }
    }

    // 1. Tải tệp lên Google Drive
    if (action === "uploadFile") {
      var uploadRes = handleUploadFile(payload);
      return jsonResponse(uploadRes);
    }

    // 1b. Tạo hoặc lấy thư mục tháng YYYY-MM trên Google Drive (HSE_Report_Images/YYYY-MM)
    if (action === "getOrCreateMonthlyFolder") {
      var yearMonth = payload.yearMonth || payload.month || Utilities.formatDate(new Date(), "GMT+7", "yyyy-MM");
      var rootFolder = getOrCreateFolder(CONFIG.DRIVE_ROOT_FOLDER);
      var hseRoot = getOrCreateSubFolder(rootFolder, "HSE_Report_Images");
      var monthFolder = getOrCreateSubFolder(hseRoot, yearMonth);
      return jsonResponse({
        status: "success",
        success: true,
        yearMonth: yearMonth,
        folderId: monthFolder.getId(),
        folderName: monthFolder.getName(),
        folderUrl: monthFolder.getUrl()
      });
    }

    // 2. Ping / Kiểm tra kết nối
    if (action === "ping" || action === "test_connection") {
      var pingRes = handlePing();
      return jsonResponse(pingRes);
    }

    // 3. Lấy toàn bộ danh sách Hóa chất
    if (action === "getAllChemicals" || action === "list") {
      var listRes = handleGetAllChemicals();
      return jsonResponse(listRes);
    }

    // 4. Lưu / Cập nhật Hóa chất kèm tải tệp lên Google Drive (action: 'upsert' hoặc 'saveChemical')
    if (action === "upsert" || action === "saveChemical") {
      var item = payload.item || payload.chemical || payload.data || {};
      if (payload.fileBase64) {
        var uploadPayload = {
          base64: payload.fileBase64,
          fileName: payload.fileName || (item.product_code ? "MSDS-" + item.product_code + ".pdf" : "MSDS_" + new Date().getTime() + ".pdf"),
          mimeType: payload.mimeType || "application/pdf"
        };
        var upRes = handleUploadFile(uploadPayload);
        if (upRes && (upRes.fileId || upRes.viewUrl)) {
          item.drive_file_id = upRes.fileId;
          item.drive_view_url = upRes.viewUrl;
          item.drive_download_url = upRes.downloadUrl;
          item.source_file = uploadPayload.fileName;
          item.file_name = uploadPayload.fileName;
        }
      }
      var saveRes = handleSaveChemical(item);
      var newVer = incrementCilVersion();
      var ss = getOrCreateSpreadsheet();
      var sheet = getOrCreateSheet(ss, CONFIG.SHEET_NAME_CIL);
      var totalRows = Math.max(0, sheet.getLastRow() - 1);
      return jsonResponse({
        status: "ok",
        success: true,
        version: newVer,
        count: totalRows,
        item: item,
        drive_file_id: item.drive_file_id || "",
        drive_view_url: item.drive_view_url || "",
        drive_download_url: item.drive_download_url || "",
        saveDetails: saveRes
      });
    }

    // 5. Lưu hàng loạt Hóa chất (Batch Upsert / action: 'bulk_sync')
    if (action === "bulk_sync" || action === "batchSaveChemicals") {
      var items = payload.items || payload.chemicals || payload.data || [];
      var batchRes = handleBatchSaveChemicals(items);
      var newVer = incrementCilVersion();
      var ss = getOrCreateSpreadsheet();
      var sheet = getOrCreateSheet(ss, CONFIG.SHEET_NAME_CIL);
      var totalRows = Math.max(0, sheet.getLastRow() - 1);
      return jsonResponse({
        status: "ok",
        success: true,
        version: newVer,
        count: totalRows,
        updatedCount: batchRes.count || items.length,
        message: "Đã đồng bộ hàng loạt thành công (" + (batchRes.count || items.length) + " hóa chất)."
      });
    }

    // 6. Xóa vĩnh viễn 1 Hóa chất (action: 'delete' hoặc 'deleteChemical')
    if (action === "delete" || action === "deleteChemical") {
      var chemId = payload.id || payload.chemical_id || payload.product_code || "";
      var prodCode = payload.product_code || chemId;
      if (payload.deleteDriveFile) {
        try {
          var ss = getOrCreateSpreadsheet();
          var sheet = getOrCreateSheet(ss, CONFIG.SHEET_NAME_CIL);
          var lastRow = sheet.getLastRow();
          if (lastRow > 1) {
            var idColData = sheet.getRange(2, 1, lastRow - 1, 32).getValues();
            for (var di = 0; di < idColData.length; di++) {
              var rChem = String(idColData[di][0] || "").trim().toUpperCase();
              var rProd = String(idColData[di][1] || "").trim().toUpperCase();
              if (rChem === String(chemId).toUpperCase() || rProd === String(prodCode).toUpperCase()) {
                var driveFileId = idColData[di][30];
                if (driveFileId) {
                  DriveApp.getFileById(driveFileId).setTrashed(true);
                }
                break;
              }
            }
          }
        } catch (eDrive) {
          Logger.log("Lỗi xóa file Google Drive: " + eDrive.toString());
        }
      }
      var delRes = handleDeleteChemical(chemId || prodCode);
      var newVer = incrementCilVersion();
      var ss = getOrCreateSpreadsheet();
      var sheet = getOrCreateSheet(ss, CONFIG.SHEET_NAME_CIL);
      var totalRows = Math.max(0, sheet.getLastRow() - 1);
      return jsonResponse({
        status: "ok",
        success: true,
        version: newVer,
        count: totalRows,
        deleted: delRes.deleted,
        message: delRes.message
      });
    }

    // 7. Xóa vĩnh viễn nhiều Hóa chất
    if (action === "deleteMultipleChemicals") {
      var delMultiRes = handleDeleteMultipleChemicals(payload.ids || []);
      return jsonResponse(delMultiRes);
    }

    // 8. Xóa toàn bộ dữ liệu Hóa chất (Clear All - Xóa triệt để)
    if (action === "deleteAllChemicals" || action === "clearAll" || action === "deleteAll") {
      var delAllRes = handleDeleteAllChemicals();
      if (action === "clearAll" || action === "deleteAll") {
        try {
          handleClearAllDefects();
        } catch (eHseClear) {}
      }
      return jsonResponse(delAllRes);
    }

    // 8b. Xóa toàn bộ sự cố HSE Tracker (Clear All HSE Defects)
    if (action === "clearAllDefects" || action === "deleteAllDefects") {
      var delHseRes = handleClearAllDefects();
      return jsonResponse(delHseRes);
    }

    // 8c. Cập nhật sự cố HSE Tracker (Update / Upsert Defect)
    if (action === "updateDefect") {
      var upDefectRes = handleUpdateDefect(payload);
      return jsonResponse(upDefectRes);
    }

    // 8d. Lấy toàn bộ sự cố HSE Tracker
    if (action === "getAllDefects" || action === "listDefects") {
      var listDefectRes = handleGetAllDefects();
      return jsonResponse(listDefectRes);
    }

    // 9. Khởi tạo / Sửa lỗi tiêu đề Sheet
    if (action === "initHeaders" || action === "manualSyncAndFixHeaders") {
      var fixRes = ensureSheetStructure();
      return jsonResponse(fixRes);
    }

    return jsonResponse({ status: "error", error: "Hành động (action) không được hỗ trợ: " + action }, 400);
  } catch (err) {
    return jsonResponse({ status: "error", error: "Lỗi thực thi GAS: " + err.toString() }, 500);
  } finally {
    lock.releaseLock();
  }
}

// ===================================================================================
// HÀM XỬ LÝ NGHIỆP VỤ (BUSINESS LOGIC HANDLERS)
// ===================================================================================

function cleanSecretToken(t) {
  if (!t) return "";
  var s = String(t).trim();
  return s.replace(/^["']+|["']+$/g, "").trim();
}

function getActiveSecretToken() {
  try {
    var props = PropertiesService.getScriptProperties();
    var pToken = props.getProperty("SECRET_TOKEN") || props.getProperty("GAS_SECRET_TOKEN") || props.getProperty("MSDS_GAS_TOKEN");
    if (pToken) return cleanSecretToken(pToken);
  } catch (e) {}
  return cleanSecretToken(CONFIG.SECRET_TOKEN);
}

function isTokenAuthorized(incomingToken) {
  var t = cleanSecretToken(incomingToken);
  if (!t || t === "******" || t.indexOf("•") !== -1) {
    return false;
  }
  var configuredToken = getActiveSecretToken();
  var allowedTokens = [
    cleanSecretToken(CONFIG.SECRET_TOKEN),
    cleanSecretToken(CONFIG.ALT_SECRET_TOKEN),
    "LUV_PDF_SYNC_KEY_2026",
    "LUV_MSDS_SECURE_TOKEN_2026",
    "mytoken123"
  ];
  if (configuredToken) {
    allowedTokens.push(configuredToken);
  }
  for (var i = 0; i < allowedTokens.length; i++) {
    if (allowedTokens[i] && t === allowedTokens[i]) {
      return true;
    }
  }
  return false;
}

/**
 * Kiểm tra kết nối Webhook & Trạng thái Google Sheet / Google Drive
 */
function handlePing() {
  var email = "Người dùng Google";
  try {
    email = Session.getActiveUser().getEmail() || "user@gmail.com";
  } catch (e) {}

  var ss = getOrCreateSpreadsheet();
  var sheet = getOrCreateSheet(ss, CONFIG.SHEET_NAME_CIL);
  ensureSheetStructure();

  var totalRows = Math.max(0, sheet.getLastRow() - 1);
  var rootFolder = getOrCreateFolder(CONFIG.DRIVE_ROOT_FOLDER);
  var subFolder = getOrCreateSubFolder(rootFolder, CONFIG.DRIVE_SUB_FOLDER);

  var curVer = getCilVersion();
  return {
    status: "ok",
    version: curVer,
    count: totalRows,
    success: true,
    message: "Kết nối Google Apps Script Webhook thành công!",
    userEmail: email,
    spreadsheetId: ss.getId(),
    spreadsheetUrl: ss.getUrl(),
    spreadsheetName: ss.getName(),
    sheetName: sheet.getName(),
    total_rows: totalRows,
    totalChemicalsInSheet: totalRows,
    driveRootFolder: rootFolder.getName(),
    driveSubFolder: subFolder.getName(),
    driveSubFolderUrl: subFolder.getUrl(),
    serverTime: Utilities.formatDate(new Date(), "Asia/Bangkok", "yyyy-MM-dd HH:mm:ss")
  };
}

/**
 * Tải tệp nhị phân lên Google Drive (MSDS PDFs, DOCX, Images)
 */
function handleUploadFile(payload) {
  var fileName = payload.fileName || payload.filename || ("MSDS_" + new Date().getTime() + ".pdf");
  var base64Data = payload.base64 || payload.base64Data || "";
  var mimeType = payload.mimeType || payload.mimetype || "application/pdf";
  var subFolderName = payload.subFolder || payload.subfolder || CONFIG.DRIVE_SUB_FOLDER;

  if (!base64Data) {
    return { status: "error", error: "Dữ liệu Base64 tệp tải lên rỗng!" };
  }
  if (base64Data.indexOf(',') > -1) {
    base64Data = base64Data.split(',')[1];
  }

  var decoded = Utilities.base64Decode(base64Data);
  var blob = Utilities.newBlob(decoded, mimeType, fileName);

  var rootFolder = getOrCreateFolder(CONFIG.DRIVE_ROOT_FOLDER);
  var targetFolder = rootFolder;
  if (subFolderName) {
    targetFolder = getOrCreateSubFolder(rootFolder, subFolderName);
  }

  var file = targetFolder.createFile(blob);
  file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);

  return {
    status: "success",
    success: true,
    fileId: file.getId(),
    fileName: file.getName(),
    filename: file.getName(),
    mimeType: mimeType,
    sizeBytes: file.getSize(),
    viewUrl: file.getUrl(),
    downloadUrl: "https://drive.google.com/uc?export=download&id=" + file.getId(),
    folderName: targetFolder.getName(),
    folderUrl: targetFolder.getUrl()
  };
}

/**
 * Lấy toàn bộ danh sách Hóa chất từ Google Sheet CIL_Chemical_Inventory
 * Chuẩn hóa 16 trường + 38 trường mở rộng
 */
function handleGetAllChemicals() {
  var ss = getOrCreateSpreadsheet();
  var sheet = getOrCreateSheet(ss, CONFIG.SHEET_NAME_CIL);
  var lastRow = sheet.getLastRow();
  var lastCol = sheet.getLastColumn();

  var rootFolder = getOrCreateFolder(CONFIG.DRIVE_ROOT_FOLDER);
  var subFolder = getOrCreateSubFolder(rootFolder, CONFIG.DRIVE_SUB_FOLDER);
  var folderUrl = subFolder.getUrl();
  var curVersion = getCilVersion();

  if (lastRow <= 1 || lastCol < 1) {
    return {
      status: "ok",
      version: curVersion,
      count: 0,
      total: 0,
      folderUrl: folderUrl,
      data: [],
      chemicals: []
    };
  }

  var headers = sheet.getRange(1, 1, 1, lastCol).getValues()[0];
  var is16ColSchema = (sheet.getName() === "MSDS_CIL" || sheet.getName() === "MSDS_CIL_DB" || headers.indexOf("chemical_name") > -1 || (headers.length > 0 && headers[0] === "id"));
  var values = sheet.getRange(2, 1, lastRow - 1, lastCol).getValues();
  var chemicals = [];
  var latestTimestamp = 0;

  var headerMap = {};
  for (var h = 0; h < headers.length; h++) {
    var hName = String(headers[h] || "").trim().toLowerCase();
    if (hName) headerMap[hName] = h;
  }

  function getVal(r, name, fallback) {
    var idx = headerMap[name.toLowerCase()];
    if (idx !== undefined && r[idx] !== undefined && r[idx] !== null && String(r[idx]).trim() !== "") {
      return r[idx];
    }
    return fallback !== undefined ? fallback : "";
  }

  for (var i = 0; i < values.length; i++) {
    var r = values[i];
    if (!r[0] && !r[1]) continue;

    var chemObj = {};
    if (is16ColSchema) {
      var id = String(getVal(r, "id", "") || getVal(r, "product_code", "") || ("CHEM_" + (i + 1))).trim();
      var product_code = String(getVal(r, "product_code", id)).trim();
      var category = String(getVal(r, "category", "Nguyên liệu")).trim();
      var chemical_name = String(getVal(r, "chemical_name", product_code)).trim();
      var usage = String(getVal(r, "usage", "Sử dụng trong sản xuất công nghiệp")).trim();
      var updated_date = String(getVal(r, "updated_date", "")).trim();
      var cas_number = String(getVal(r, "cas_number", "")).trim();

      var rawLegal = getVal(r, "legal_flags", "[]");
      var legal_flags = [];
      try { legal_flags = typeof rawLegal === "string" ? JSON.parse(rawLegal) : rawLegal; } catch (_) { legal_flags = []; }

      var supplier = String(getVal(r, "supplier", "")).trim();

      var rawGhs = getVal(r, "ghs_classifications", "[]");
      var ghs_classifications = [];
      try {
        ghs_classifications = typeof rawGhs === "string" ? (rawGhs.indexOf("[") > -1 ? JSON.parse(rawGhs) : rawGhs.split(/[,;]+/).map(function(s){return s.trim();}).filter(Boolean)) : rawGhs;
      } catch (_) {
        ghs_classifications = ["NON DG"];
      }
      if (!Array.isArray(ghs_classifications) || ghs_classifications.length === 0) ghs_classifications = ["NON DG"];

      var raw16 = getVal(r, "ghs_16_sections", "{}");
      var ghs_16_sections = {};
      try { ghs_16_sections = typeof raw16 === "string" ? JSON.parse(raw16) : raw16; } catch (_) { ghs_16_sections = {}; }

      var file_name = String(getVal(r, "file_name", "")).trim();
      var drive_file_id = String(getVal(r, "drive_file_id", "")).trim();
      var drive_view_url = String(getVal(r, "drive_view_url", "")).trim();
      if (!drive_view_url && drive_file_id) drive_view_url = "https://drive.google.com/file/d/" + drive_file_id + "/view";
      var drive_download_url = String(getVal(r, "drive_download_url", "")).trim();
      if (!drive_download_url && drive_file_id) drive_download_url = "https://drive.google.com/uc?export=download&id=" + drive_file_id;
      var last_synced_at = String(getVal(r, "last_synced_at", "")).trim() || new Date().toISOString();

      var ts16 = new Date(last_synced_at).getTime();
      if (ts16 && ts16 > latestTimestamp) latestTimestamp = ts16;

      chemObj = {
        id: id,
        product_code: product_code,
        category: category,
        chemical_name: chemical_name,
        usage: usage,
        updated_date: updated_date,
        cas_number: cas_number,
        legal_flags: legal_flags,
        supplier: supplier,
        ghs_classifications: ghs_classifications,
        ghs_16_sections: ghs_16_sections,
        file_name: file_name,
        drive_file_id: drive_file_id,
        drive_view_url: drive_view_url,
        drive_download_url: drive_download_url,
        last_synced_at: last_synced_at,

        chemical_id: id,
        chem_id: id,
        product_name: chemical_name,
        product_name_vi: chemical_name,
        product_name_original: supplier || chemical_name,
        item_type: (category === "Thành phẩm" || category === "finished_product") ? "finished_product" : "raw_material",
        intended_use: usage,
        cas_primary: cas_number,
        cas_numbers: cas_number,
        manufacturer: supplier,
        manufacturer_supplier: supplier,
        ghs_codes: ghs_classifications,
        ghs_symbols: ghs_classifications.join(", "),
        source_file: file_name,
        compositions_json: JSON.stringify(ghs_16_sections || {}),
        sync_status: "synced",
        created_at: updated_date,
        updated_at: last_synced_at
      };
    } else {
      var ghsList = r[11] ? String(r[11]).split(/[,;]+/).map(function(s){return s.trim();}).filter(Boolean) : [];
      if (ghsList.length === 0) ghsList = ["NON DG"];

      var driveFileId = r[30] || "";
      var driveViewUrl = r[31] || (driveFileId ? "https://drive.google.com/file/d/" + driveFileId + "/preview" : "");
      var driveDownloadUrl = r[32] || (driveFileId ? "https://drive.google.com/uc?export=download&id=" + driveFileId : "");
      var syncTime = r[36] || r[35] || new Date().toISOString();
      var ts38 = new Date(syncTime).getTime();
      if (ts38 && ts38 > latestTimestamp) latestTimestamp = ts38;

      chemObj = {
      // 16 TRƯỜNG CHUẨN HÓA THEO YÊU CẦU
      id: r[0] || r[1] || ("CHEM_" + (i + 1)),
      product_code: r[1] || r[0] || "",
      category: (String(r[4]).toLowerCase() === "finished_product" || r[4] === "Thành phẩm") ? "Thành phẩm" : "Nguyên liệu",
      chemical_name: r[2] || r[3] || r[1] || "",
      usage: r[17] || "Sử dụng trong sản xuất công nghiệp",
      updated_date: r[36] || r[35] || "",
      cas_number: r[6] || "",
      legal_flags: [],
      supplier: r[3] || "",
      ghs_classifications: ghsList,
      ghs_16_sections: {},
      file_name: r[29] || "",
      drive_file_id: driveFileId,
      drive_view_url: driveViewUrl,
      drive_download_url: driveDownloadUrl,
      last_synced_at: r[36] || new Date().toISOString(),

      // 38 CỘT GỐC ĐẢM BẢO TƯƠNG THÍCH TOÀN DIỆN
      chemical_id: r[0] || "",
      chem_id: r[0] || r[1] || "",
      product_name: r[2] || r[3] || r[1] || "",
      product_name_vi: r[2] || "",
      product_name_original: r[3] || "",
      item_type: r[4] || "raw_material",
      mother_msds_id: r[5] || "",
      cas_primary: r[6] || "",
      cas_numbers: r[6] || "",
      un_no: r[7] || "",
      un_number: r[7] || "",
      transport_class: r[8] || "",
      packing_group: r[9] || "",
      signal_word: r[10] || "",
      ghs_codes: ghsList,
      ghs_symbols: ghsList.join(", "),
      hazard_statements: r[12] || "",
      precautionary_statements: r[13] || "",
      flash_point: r[14] || "",
      density: r[15] || "",
      appearance: r[16] || "",
      storage_condition: r[17] || "",
      intended_use: r[17] || "",
      respiratory_protection: r[18] || "",
      hand_protection: r[19] || "",
      eye_protection: r[20] || "",
      skin_protection: r[21] || "",
      first_aid_inhalation: r[22] || "",
      first_aid_skin: r[23] || "",
      first_aid_eyes: r[24] || "",
      first_aid_ingestion: r[25] || "",
      fire_measures: r[26] || "",
      spill_measures: r[27] || "",
      compositions_json: r[28] || "[]",
      source_file: r[29] || "",
      sha256: r[33] || "",
      sync_status: r[34] || "synced",
      created_at: r[35] || "",
      updated_at: r[36] || "",
      deleted_at: r[37] || ""
    };

    try {
      if (r[28]) {
        var parsed = JSON.parse(r[28]);
        if (parsed && typeof parsed === "object") {
          chemObj.ghs_16_sections = parsed;
          chemObj.composition = Array.isArray(parsed) ? parsed : (parsed.composition || []);
        }
      }
    } catch (e) {
      chemObj.composition = [];
    }

    chemicals.push(chemObj);
  }

  return {
    status: "ok",
    version: curVersion,
    count: chemicals.length,
    total: chemicals.length,
    folderUrl: folderUrl,
    data: chemicals,
    chemicals: chemicals
  };
}

/**
 * Chuyển đổi đối tượng Hóa chất thành mảng 38 giá trị tương ứng với CIL_HEADERS
 */
function buildRowFromChemical(chem, existingRow) {
  var nowStr = Utilities.formatDate(new Date(), "Asia/Bangkok", "yyyy-MM-dd HH:mm:ss");
  var chemId = String(chem.chemical_id || chem.product_code || chem.id || chem.chem_id || "").trim();
  var prodCode = String(chem.product_code || chem.chem_id || chem.id || chemId).trim();

  var compJson = "";
  if (chem.ghs_16_sections) {
    compJson = (typeof chem.ghs_16_sections === "string") ? chem.ghs_16_sections : JSON.stringify(chem.ghs_16_sections);
  } else if (chem.compositions_json) {
    compJson = (typeof chem.compositions_json === "string") ? chem.compositions_json : JSON.stringify(chem.compositions_json);
  } else if (chem.composition) {
    compJson = JSON.stringify(chem.composition);
  } else {
    compJson = "[]";
  }

  var ghsCodesStr = "";
  if (Array.isArray(chem.ghs_classifications)) {
    ghsCodesStr = chem.ghs_classifications.join(", ");
  } else if (Array.isArray(chem.ghs_codes)) {
    ghsCodesStr = chem.ghs_codes.join(", ");
  } else {
    ghsCodesStr = String(chem.ghs_codes || chem.ghs_symbols || chem.ghs_classifications || "");
  }

  var itemType = chem.item_type || ((chem.category === "Thành phẩm" || chem.category === "finished_product") ? "finished_product" : "raw_material");
  var createdAt = chem.created_at || (existingRow ? existingRow[35] : nowStr);
  var updatedAt = chem.updated_date || chem.updated_at || nowStr;

  return [
    chemId,                                              // 0: chemical_id
    prodCode,                                            // 1: product_code
    chem.chemical_name || chem.product_name_vi || chem.product_name || "", // 2: product_name_vi
    chem.product_name_original || chem.supplier || "",   // 3: product_name_original / supplier
    itemType,                                            // 4: item_type
    chem.mother_msds_id || "",                          // 5: mother_msds_id
    chem.cas_number || chem.cas_primary || chem.cas_numbers || "", // 6: cas_primary
    chem.un_no || chem.un_number || "",                 // 7: un_no
    chem.transport_class || "",                         // 8: transport_class
    chem.packing_group || "",                           // 9: packing_group
    chem.signal_word || "",                             // 10: signal_word
    ghsCodesStr,                                        // 11: ghs_codes
    chem.hazard_statements || "",                       // 12: hazard_statements
    chem.precautionary_statements || "",                // 13: precautionary_statements
    chem.flash_point || "",                             // 14: flash_point
    chem.density || "",                                 // 15: density
    chem.appearance || "",                              // 16: appearance
    chem.usage || chem.intended_use || chem.storage_condition || "", // 17: storage_condition
    chem.respiratory_protection || "",                  // 18: respiratory_protection
    chem.hand_protection || "",                         // 19: hand_protection
    chem.eye_protection || "",                          // 20: eye_protection
    chem.skin_protection || "",                         // 21: skin_protection
    chem.first_aid_inhalation || "",                    // 22: first_aid_inhalation
    chem.first_aid_skin || "",                          // 23: first_aid_skin
    chem.first_aid_eyes || "",                          // 24: first_aid_eyes
    chem.first_aid_ingestion || "",                     // 25: first_aid_ingestion
    chem.fire_measures || "",                           // 26: fire_measures
    chem.spill_measures || "",                          // 27: spill_measures
    compJson,                                           // 28: compositions_json
    chem.file_name || chem.source_file || chem.source_file_name || "", // 29: source_file
    chem.drive_file_id || (existingRow ? existingRow[30] : ""), // 30: drive_file_id
    chem.drive_view_url || (existingRow ? existingRow[31] : ""), // 31: drive_view_url
    chem.drive_download_url || (existingRow ? existingRow[32] : ""), // 32: drive_download_url
    chem.sha256 || "",                                  // 33: sha256
    chem.sync_status || "synced",                       // 34: sync_status
    createdAt,                                          // 35: created_at
    updatedAt,                                          // 36: updated_at
    ""                                                  // 37: deleted_at
  ];
}

/**
 * Lưu hoặc cập nhật một Hóa chất (Upsert)
 */
function handleSaveChemical(chem) {
  if (!chem) return { status: "error", error: "Dữ liệu hóa chất không hợp lệ!" };

  var ss = getOrCreateSpreadsheet();
  var sheet = getOrCreateSheet(ss, CONFIG.SHEET_NAME_CIL);
  ensureSheetStructure();

  var chemId = String(chem.chemical_id || chem.product_code || "").trim();
  var prodCode = String(chem.product_code || chemId).trim();
  if (!chemId && !prodCode) {
    return { status: "error", error: "Thiếu mã định danh hóa chất (chemical_id/product_code)!" };
  }

  var lastRow = sheet.getLastRow();
  var rowIndexToUpdate = -1;
  var existingRowValues = null;

  if (lastRow > 1) {
    var idColData = sheet.getRange(2, 1, lastRow - 1, 2).getValues();
    for (var i = 0; i < idColData.length; i++) {
      var rChem = String(idColData[i][0] || "").trim().toUpperCase();
      var rProd = String(idColData[i][1] || "").trim().toUpperCase();
      if ((chemId && rChem === chemId.toUpperCase()) || (prodCode && rProd === prodCode.toUpperCase())) {
        rowIndexToUpdate = i + 2;
        break;
      }
    }
  }

  var currentHeaders = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  var is16Col = (sheet.getName() === "MSDS_CIL" || sheet.getName() === "MSDS_CIL_DB" || currentHeaders.indexOf("chemical_name") > -1 || (currentHeaders.length > 0 && currentHeaders[0] === "id"));

  if (is16Col) {
    var nowIso = new Date().toISOString();
    chem.id = chem.id || chem.chemical_id || chem.product_code || ("CHEM_" + new Date().getTime());
    chem.last_synced_at = nowIso;

    var rowValues = CIL_16_HEADERS.map(function(h) {
      var val = chem[h];
      if (val === undefined) {
        if (h === 'chemical_name') val = chem.product_name_vi || chem.product_name;
        else if (h === 'supplier') val = chem.manufacturer || chem.manufacturer_supplier;
        else if (h === 'cas_number') val = chem.cas_primary || chem.cas_numbers;
        else if (h === 'category') val = (chem.item_type === 'finished_product' || chem.category === 'Thành phẩm') ? 'Thành phẩm' : 'Nguyên liệu';
        else if (h === 'file_name') val = chem.source_file;
      }
      if (['legal_flags', 'ghs_classifications', 'ghs_16_sections'].indexOf(h) > -1) {
        return (typeof val === 'object' && val !== null) ? JSON.stringify(val) : (val || '[]');
      }
      return (val !== undefined && val !== null) ? val : '';
    });

    if (rowIndexToUpdate > 1) {
      existingRowValues = sheet.getRange(rowIndexToUpdate, 1, 1, CIL_16_HEADERS.length).getValues()[0];
      if (!chem.drive_file_id && existingRowValues) {
        var oldFileName = existingRowValues[11];
        var oldFileId = existingRowValues[12];
        var oldViewUrl = existingRowValues[13];
        var oldDownUrl = existingRowValues[14];
        if (oldFileId) {
          chem.drive_file_id = oldFileId;
          chem.drive_view_url = oldViewUrl;
          chem.drive_download_url = oldDownUrl;
          chem.file_name = oldFileName;
          rowValues[11] = oldFileName;
          rowValues[12] = oldFileId;
          rowValues[13] = oldViewUrl;
          rowValues[14] = oldDownUrl;
        }
      }
      sheet.getRange(rowIndexToUpdate, 1, 1, CIL_16_HEADERS.length).setValues([rowValues]);
      return {
        status: "ok",
        success: true,
        action: "updated",
        chemical_id: chemId,
        rowIndex: rowIndexToUpdate,
        message: "Đã cập nhật hóa chất '" + chemId + "' trên Google Sheet thành công."
      };
    } else {
      sheet.appendRow(rowValues);
      return {
        status: "ok",
        success: true,
        action: "created",
        chemical_id: chemId,
        rowIndex: sheet.getLastRow(),
        message: "Đã thêm mới hóa chất '" + chemId + "' vào Google Sheet thành công."
      };
    }
  }

  if (rowIndexToUpdate > 1) {
    existingRowValues = sheet.getRange(rowIndexToUpdate, 1, 1, CIL_HEADERS.length).getValues()[0];
    var updatedRow = buildRowFromChemical(chem, existingRowValues);
    sheet.getRange(rowIndexToUpdate, 1, 1, CIL_HEADERS.length).setValues([updatedRow]);
    return {
      status: "ok",
      success: true,
      action: "updated",
      chemical_id: chemId,
      rowIndex: rowIndexToUpdate,
      message: "Đã cập nhật hóa chất '" + chemId + "' trên Google Sheet thành công."
    };
  } else {
    var newRow = buildRowFromChemical(chem, null);
    sheet.appendRow(newRow);
    return {
      status: "ok",
      success: true,
      action: "created",
      chemical_id: chemId,
      rowIndex: sheet.getLastRow(),
      message: "Đã thêm mới hóa chất '" + chemId + "' vào Google Sheet thành công."
    };
  }
}

/**
 * Lưu hàng loạt Hóa chất (Batch Upsert)
 */
function handleBatchSaveChemicals(chemsList) {
  if (!chemsList || !chemsList.length) {
    return { status: "ok", success: true, count: 0, message: "Danh sách hóa chất rỗng." };
  }

  var count = 0;
  for (var i = 0; i < chemsList.length; i++) {
    var res = handleSaveChemical(chemsList[i]);
    if (res.status === "ok" || res.success) {
      count++;
    }
  }

  return {
    status: "ok",
    success: true,
    count: count,
    message: "Đã đồng bộ thành công " + count + " hóa chất lên Google Sheet."
  };
}

/**
 * Xóa vĩnh viễn một Hóa chất (Permanent Delete)
 */
function handleDeleteChemical(chemId) {
  var cleanId = String(chemId || "").trim().toUpperCase();
  if (!cleanId) {
    return { status: "error", error: "Mã hóa chất cần xóa không được để trống!" };
  }

  var ss = getOrCreateSpreadsheet();
  var sheet = getOrCreateSheet(ss, CONFIG.SHEET_NAME_CIL);
  var lastRow = sheet.getLastRow();
  if (lastRow <= 1) {
    return { status: "ok", success: true, deleted: false, message: "Bảng tính hiện không có dữ liệu." };
  }

  var idColData = sheet.getRange(2, 1, lastRow - 1, 2).getValues();
  for (var i = 0; i < idColData.length; i++) {
    var rChem = String(idColData[i][0] || "").trim().toUpperCase();
    var rProd = String(idColData[i][1] || "").trim().toUpperCase();
    if (rChem === cleanId || rProd === cleanId) {
      sheet.deleteRow(i + 2);
      return {
        status: "ok",
        success: true,
        deleted: true,
        chemical_id: chemId,
        message: "Đã xóa vĩnh viễn hóa chất '" + chemId + "' khỏi Google Sheet."
      };
    }
  }

  return {
    status: "ok",
    success: true,
    deleted: false,
    chemical_id: chemId,
    message: "Không tìm thấy mã hóa chất '" + chemId + "' trên Google Sheet (đã được xóa trước đó)."
  };
}

/**
 * Xóa vĩnh viễn nhiều Hóa chất theo danh sách mã ID
 */
function handleDeleteMultipleChemicals(idList) {
  if (!idList || !idList.length) {
    return { status: "ok", success: true, count: 0 };
  }

  var targetSet = {};
  for (var k = 0; k < idList.length; k++) {
    targetSet[String(idList[k]).trim().toUpperCase()] = true;
  }

  var ss = getOrCreateSpreadsheet();
  var sheet = getOrCreateSheet(ss, CONFIG.SHEET_NAME_CIL);
  var lastRow = sheet.getLastRow();
  if (lastRow <= 1) return { status: "ok", success: true, count: 0 };

  var idColData = sheet.getRange(2, 1, lastRow - 1, 2).getValues();
  var deletedCount = 0;

  for (var i = idColData.length - 1; i >= 0; i--) {
    var rChem = String(idColData[i][0] || "").trim().toUpperCase();
    var rProd = String(idColData[i][1] || "").trim().toUpperCase();
    if (targetSet[rChem] || targetSet[rProd]) {
      sheet.deleteRow(i + 2);
      deletedCount++;
    }
  }

  return {
    status: "ok",
    success: true,
    count: deletedCount,
    message: "Đã xóa vĩnh viễn " + deletedCount + " hóa chất khỏi Google Sheet."
  };
}

/**
 * Xóa sạch toàn bộ CSDL hóa chất trên Google Sheet (Giữ nguyên dòng tiêu đề 1)
 */
function handleDeleteAllChemicals() {
  var ss = getOrCreateSpreadsheet();
  var sheet = getOrCreateSheet(ss, CONFIG.SHEET_NAME_CIL);
  var lastRow = sheet.getLastRow();
  var deletedCount = 0;

  if (lastRow > 1) {
    deletedCount = lastRow - 1;
    sheet.deleteRows(2, deletedCount);
  }

  return {
    status: "ok",
    success: true,
    deleted_count: deletedCount,
    message: "Đã xóa sạch toàn bộ " + deletedCount + " dòng dữ liệu hóa chất khỏi Google Sheet."
  };
}

// ===================================================================================
// HÀM TIỆN ÍCH QUẢN TRỊ BẢNG TÍNH & THƯ MỤC DRIVE
// ===================================================================================

function getOrCreateSpreadsheet() {
  var ss = null;
  try { ss = SpreadsheetApp.getActiveSpreadsheet(); } catch (e) {}
  if (!ss) {
    var props = PropertiesService.getScriptProperties();
    var savedId = props.getProperty("SPREADSHEET_ID");
    if (savedId) {
      try { ss = SpreadsheetApp.openById(savedId); } catch (e) {}
    }
  }
  if (!ss) {
    try {
      ss = SpreadsheetApp.openById("1v67i1XCsNWB8f9dTFW-uJcuzyce8zULQi6FcdjGvAts");
      if (ss) {
        PropertiesService.getScriptProperties().setProperty("SPREADSHEET_ID", ss.getId());
      }
    } catch (openErr) {}
  }
  if (!ss) {
    ss = SpreadsheetApp.create("TitanPDF_MSDS_Chemical_Database");
    PropertiesService.getScriptProperties().setProperty("SPREADSHEET_ID", ss.getId());
  }
  return ss;
}

function getOrCreateSheet(ss, sheetName) {
  if (!ss) {
    try {
      ss = getOrCreateSpreadsheet();
    } catch (e) {
      Logger.log("getOrCreateSheet fallback getOrCreateSpreadsheet error: " + e.toString());
    }
  }
  if (!ss) {
    try {
      var props = PropertiesService.getScriptProperties();
      var savedId = props.getProperty("SPREADSHEET_ID");
      if (savedId) {
        ss = SpreadsheetApp.openById(savedId);
      }
    } catch (eProps) {}
  }
  if (!ss) {
    try {
      ss = SpreadsheetApp.getActiveSpreadsheet();
    } catch (eAct) {}
  }
  if (!ss) {
    throw new Error("Không thể khởi tạo hoặc mở Spreadsheet. Vui lòng kiểm tra quyền truy cập hoặc cấu hình SPREADSHEET_ID.");
  }

  var targetName = sheetName || "MSDS_CIL";
  var sheet = ss.getSheetByName(targetName);
  if (!sheet && (targetName === "MSDS_CIL" || targetName === "CIL_Chemical_Inventory")) {
    sheet = ss.getSheetByName("MSDS_CIL") || ss.getSheetByName("CIL_Chemical_Inventory");
  }

  if (!sheet) {
    sheet = ss.insertSheet(targetName);
    var headers = (targetName === "MSDS_CIL" || targetName === "MSDS_CIL_DB") ? CIL_16_HEADERS : (targetName === (typeof CONFIG !== 'undefined' && CONFIG.SHEET_NAME_HSE ? CONFIG.SHEET_NAME_HSE : "HSE_Defect_Tracker") ? HSE_DEFECT_HEADERS : CIL_HEADERS);
    sheet.appendRow(headers);
    var hRange = sheet.getRange(1, 1, 1, headers.length);
    hRange.setFontWeight("bold");
    hRange.setBackground("#0f172a");
    hRange.setFontColor("#f8fafc");
    sheet.setFrozenRows(1);
  }
  return sheet;
}

function ensureSheetStructure() {
  var ss = getOrCreateSpreadsheet();
  var sheet = getOrCreateSheet(ss, CONFIG.SHEET_NAME_CIL);

  var currentHeaders = [];
  if (sheet.getLastRow() >= 1 && sheet.getLastColumn() >= 1) {
    currentHeaders = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  }

  var needsUpdate = (currentHeaders.length < CIL_HEADERS.length || currentHeaders[0] !== CIL_HEADERS[0]);
  if (needsUpdate) {
    sheet.getRange(1, 1, 1, CIL_HEADERS.length).setValues([CIL_HEADERS]);
    var headerRange = sheet.getRange(1, 1, 1, CIL_HEADERS.length);
    headerRange.setBackground("#0f172a");
    headerRange.setFontColor("#f8fafc");
    headerRange.setFontWeight("bold");
    headerRange.setFontSize(10);
    headerRange.setHorizontalAlignment("center");
    headerRange.setVerticalAlignment("middle");
    sheet.setRowHeight(1, 36);
    sheet.setFrozenRows(1);
    sheet.setFrozenColumns(3);
  }

  return { status: "ok", success: true, message: "Đã chuẩn hóa tiêu đề và cấu trúc 38 cột của bảng CIL." };
}

function getOrCreateFolder(folderName) {
  folderName = folderName || CONFIG.DRIVE_ROOT_FOLDER;
  var folders = DriveApp.getFoldersByName(folderName);
  if (folders.hasNext()) return folders.next();
  var newFolder = DriveApp.createFolder(folderName);
  newFolder.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
  return newFolder;
}

function getOrCreateSubFolder(parentFolder, subFolderName) {
  subFolderName = subFolderName || CONFIG.DRIVE_SUB_FOLDER;
  var parts = subFolderName.split(/[\/]/).filter(function(p) { return p && p.trim().length > 0; });
  var current = parentFolder;
  for (var i = 0; i < parts.length; i++) {
    var part = parts[i].trim();
    var subs = current.getFoldersByName(part);
    if (subs.hasNext()) {
      current = subs.next();
    } else {
      var newSub = current.createFolder(part);
      newSub.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
      current = newSub;
    }
  }
  return current;
}

function jsonResponse(data, statusCode) {
  var output = ContentService.createTextOutput(JSON.stringify(data));
  output.setMimeType(ContentService.MimeType.JSON);
  return output;
}

// ===================================================================================
// GIAO DIỆN WEB APP PASTEL KAWAII PRO (HTML SERVICE CHO NGƯỜI DÙNG TRUY CẬP TRỰC TIẾP)
// ===================================================================================

function renderWebAppUI() {
  var ss = getOrCreateSpreadsheet();
  var sheet = getOrCreateSheet(ss, CONFIG.SHEET_NAME_CIL);
  ensureSheetStructure();

  var totalRows = Math.max(0, sheet.getLastRow() - 1);
  var rootFolder = getOrCreateFolder(CONFIG.DRIVE_ROOT_FOLDER);
  var subFolder = getOrCreateSubFolder(rootFolder, CONFIG.DRIVE_SUB_FOLDER);
  var ssUrl = ss.getUrl();
  var driveUrl = subFolder.getUrl();
  var webAppUrl = ScriptApp.getService().getUrl() || "";

  var html = '<!DOCTYPE html>' +
  '<html lang="vi">' +
  '<head>' +
  '  <meta charset="UTF-8">' +
  '  <meta name="viewport" content="width=device-width, initial-scale=1.0">' +
  '  <title>LUV-MSDS Cloud Gateway & Sổ Hóa Chất CIL</title>' +
  '  <link rel="preconnect" href="https://fonts.googleapis.com">' +
  '  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>' +
  '  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&display=swap" rel="stylesheet">' +
  '  <style>' +
  '    :root {' +
  '      --primary: #6366f1; --primary-hover: #4f46e5; --bg: #f8fafc;' +
  '      --card-bg: rgba(255, 255, 255, 0.95); --border: #e2e8f0;' +
  '      --text: #0f172a; --text-muted: #64748b; --success: #10b981;' +
  '    }' +
  '    * { box-sizing: border-box; margin: 0; padding: 0; font-family: "Plus Jakarta Sans", sans-serif; }' +
  '    body { background: linear-gradient(135deg, #f0fdf4 0%, #eff6ff 50%, #fdf2f8 100%); min-height: 100vh; padding: 24px; color: var(--text); }' +
  '    .container { max-width: 1100px; margin: 0 auto; }' +
  '    .header-card { background: var(--card-bg); border-radius: 20px; padding: 28px 32px; border: 1px solid var(--border); box-shadow: 0 10px 30px rgba(0,0,0,0.04); margin-bottom: 24px; }' +
  '    .badge { display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px; background: #e0e7ff; color: #4338ca; border-radius: 999px; font-size: 12px; font-weight: 700; text-transform: uppercase; margin-bottom: 12px; }' +
  '    h1 { font-size: 26px; font-weight: 800; color: #1e1b4b; margin-bottom: 8px; }' +
  '    p.desc { font-size: 14px; color: var(--text-muted); line-height: 1.6; }' +
  '    .grid-stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin: 20px 0; }' +
  '    .stat-card { background: #ffffff; border-radius: 16px; padding: 18px 20px; border: 1px solid var(--border); box-shadow: 0 4px 12px rgba(0,0,0,0.02); }' +
  '    .stat-val { font-size: 24px; font-weight: 800; color: #4338ca; margin-top: 4px; }' +
  '    .webhook-box { background: #0f172a; color: #f8fafc; border-radius: 14px; padding: 16px 20px; margin-top: 16px; }' +
  '    .webhook-url { word-break: break-all; font-family: monospace; font-size: 13px; color: #38bdf8; margin: 8px 0; }' +
  '    .btn { display: inline-flex; align-items: center; gap: 8px; padding: 10px 20px; border-radius: 10px; font-weight: 700; font-size: 13px; cursor: pointer; text-decoration: none; border: none; transition: all 0.2s; }' +
  '    .btn-primary { background: var(--primary); color: #fff; }' +
  '    .btn-primary:hover { background: var(--primary-hover); transform: translateY(-1px); }' +
  '    .btn-outline { background: #fff; color: #1e293b; border: 1px solid var(--border); }' +
  '    .btn-outline:hover { background: #f8fafc; }' +
  '    .table-card { background: var(--card-bg); border-radius: 20px; padding: 24px; border: 1px solid var(--border); box-shadow: 0 10px 30px rgba(0,0,0,0.04); }' +
  '    table { width: 100%; border-collapse: collapse; margin-top: 16px; font-size: 13px; }' +
  '    th { background: #f1f5f9; padding: 12px 14px; text-align: left; font-weight: 700; color: #475569; border-bottom: 2px solid var(--border); }' +
  '    td { padding: 12px 14px; border-bottom: 1px solid var(--border); }' +
  '    tr:hover { background: rgba(248, 250, 252, 0.8); }' +
  '    .search-input { width: 100%; max-width: 380px; padding: 10px 16px; border-radius: 10px; border: 1px solid var(--border); font-size: 13px; outline: none; }' +
  '  </style>' +
  '</head>' +
  '<body>' +
  '  <div class="container">' +
  '    <div class="header-card">' +
  '      <span class="badge">🚀 Google Cloud Gateway v3.5.0 Pro</span>' +
  '      <h1>LUV-MSDS Cloud Gateway &amp; Sổ Hóa Chất CIL</h1>' +
  '      <p class="desc">Kịch bản đám mây Google Apps Script kết nối hai chiều với TitanPDF. Dữ liệu được lưu trữ trực tiếp trên Google Sheets và các tệp đính kèm được tải tự động vào Google Drive cá nhân của bạn.</p>' +
  '      ' +
  '      <div class="grid-stats">' +
  '        <div class="stat-card">' +
  '          <div style="font-size:12px; font-weight:600; color:#64748b;">Tổng Số Hóa Chất Trong Sheet</div>' +
  '          <div class="stat-val">' + totalRows + ' Hóa chất</div>' +
  '        </div>' +
  '        <div class="stat-card">' +
  '          <div style="font-size:12px; font-weight:600; color:#64748b;">Trạng Thái Đồng Bộ 38 Cột</div>' +
  '          <div class="stat-val" style="color:#10b981; font-size:18px; margin-top:8px;">✓ Chuẩn GHS 2026</div>' +
  '        </div>' +
  '        <div class="stat-card">' +
  '          <div style="font-size:12px; font-weight:600; color:#64748b;">Thư Mục Google Drive</div>' +
  '          <div class="stat-val" style="color:#0284c7; font-size:16px; margin-top:8px;">📁 ' + CONFIG.DRIVE_SUB_FOLDER + '</div>' +
  '        </div>' +
  '      </div>' +
  '      ' +
  '      <div class="webhook-box">' +
  '        <div style="font-size:12px; font-weight:700; color:#94a3b8; text-transform:uppercase;">URL Webhook Kết Nối TitanPDF:</div>' +
  '        <div class="webhook-url" id="webhookUrlText">' + (webAppUrl || "Chưa lấy được WebApp URL (vui lòng Deploy Web App)") + '</div>' +
  '        <div style="display:flex; gap:10px; margin-top:10px; flex-wrap:wrap;">' +
  '          <button class="btn btn-primary" onclick="copyWebhookUrl()">📋 Sao Chép URL Webhook</button>' +
  '          <a class="btn btn-outline" href="' + ssUrl + '" target="_blank">📊 Mở Google Sheet CSDL</a>' +
  '          <a class="btn btn-outline" href="' + driveUrl + '" target="_blank">📂 Mở Thư Mục Google Drive</a>' +
  '        </div>' +
  '      </div>' +
  '    </div>' +
  '    ' +
  '    <div class="table-card">' +
  '      <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:12px;">' +
  '        <div>' +
  '          <h3 style="font-size:18px; font-weight:800; color:#1e1b4b;">Danh Mục Hóa Chất CIL Trên Google Sheet</h3>' +
  '          <p style="font-size:12px; color:#64748b; margin-top:2px;">Dữ liệu đọc trực tiếp từ bảng tính ' + CONFIG.SHEET_NAME_CIL + '</p>' +
  '        </div>' +
  '        <input type="text" class="search-input" id="chemSearch" placeholder="🔍 Tìm theo mã SP, tên hóa chất, số CAS..." onkeyup="filterTable()">' +
  '      </div>' +
  '      ' +
  '      <div style="overflow-x:auto;">' +
  '        <table id="chemTable">' +
  '          <thead>' +
  '            <tr>' +
  '              <th style="width:50px;">STT</th>' +
  '              <th>Mã Hóa Chất</th>' +
  '              <th>Tên Hóa Chất (Tiếng Việt)</th>' +
  '              <th>Số CAS</th>' +
  '              <th>Mã GHS</th>' +
  '              <th>Tệp Drive</th>' +
  '              <th>Cập Nhật</th>' +
  '            </tr>' +
  '          </thead>' +
  '          <tbody>' +
  '            ' + renderTableRows(sheet) +
  '          </tbody>' +
  '        </table>' +
  '      </div>' +
  '    </div>' +
  '  </div>' +
  '  <script>' +
  '    function copyWebhookUrl() {' +
  '      var text = document.getElementById("webhookUrlText").innerText;' +
  '      navigator.clipboard.writeText(text).then(function() {' +
  '        alert("Đã sao chép URL Webhook thành công! Bạn có thể dán vào Cài Đặt Cloud trên TitanPDF.");' +
  '      });' +
  '    }' +
  '    function filterTable() {' +
  '      var input = document.getElementById("chemSearch").value.toLowerCase();' +
  '      var rows = document.querySelectorAll("#chemTable tbody tr");' +
  '      rows.forEach(function(row) {' +
  '        var text = row.innerText.toLowerCase();' +
  '        row.style.display = text.indexOf(input) > -1 ? "" : "none";' +
  '      });' +
  '    }' +
  '  </script>' +
  '</body>' +
  '</html>';

  return HtmlService.createHtmlOutput(html)
    .setTitle("LUV-MSDS Cloud Gateway & Sổ Hóa Chất CIL")
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .addMetaTag("viewport", "width=device-width, initial-scale=1, maximum-scale=1");
}

function renderTableRows(sheet) {
  var lastRow = sheet.getLastRow();
  if (lastRow <= 1) {
    return '<tr><td colspan="7" style="text-align:center; color:#64748b; padding:24px;">Chưa có hóa chất nào trong bảng tính. Dữ liệu sẽ tự động xuất hiện khi TitanPDF đồng bộ sang!</td></tr>';
  }

  var values = sheet.getRange(2, 1, Math.min(lastRow - 1, 100), Math.min(sheet.getLastColumn(), 38)).getValues();
  var html = '';
  for (var i = 0; i < values.length; i++) {
    var r = values[i];
    var driveLink = r[31] ? ('<a href="' + r[31] + '" target="_blank" style="color:#2563eb; font-weight:700; text-decoration:none;">📄 Xem Drive</a>') : '<span style="color:#94a3b8;">Chưa có</span>';
    html += '<tr>' +
      '<td>' + (i + 1) + '</td>' +
      '<td><b>' + (r[0] || 'N/A') + '</b></td>' +
      '<td>' + (r[2] || r[3] || 'N/A') + '</td>' +
      '<td><span style="background:#e0f2fe; color:#0369a1; padding:3px 8px; border-radius:6px; font-weight:700; font-size:11px;">' + (r[6] || 'N/A') + '</span></td>' +
      '<td>' + (r[11] || 'NON DG') + '</td>' +
      '<td>' + driveLink + '</td>' +
      '<td style="color:#64748b; font-size:11px;">' + (r[36] || r[35] || 'N/A') + '</td>' +
    '</tr>';
  }
  return html;
}


// ===================================================================================
// CÁC HÀM XỬ LÝ THEO DÕI SỰ CỐ & KHẮC PHỤC LỖI HSE (HSE DEFECT TRACKER)
// ===================================================================================

function ensureHseSheetStructure() {
  var ss = getOrCreateSpreadsheet();
  var sheet = getOrCreateSheet(ss, CONFIG.SHEET_NAME_HSE);
  var currentHeaders = [];
  if (sheet.getLastRow() >= 1 && sheet.getLastColumn() >= 1) {
    currentHeaders = sheet.getRange(1, 1, 1, sheet.getLastColumn()).getValues()[0];
  }
  var needsUpdate = (currentHeaders.length < HSE_DEFECT_HEADERS.length || currentHeaders[0] !== HSE_DEFECT_HEADERS[0]);
  if (needsUpdate) {
    sheet.getRange(1, 1, 1, HSE_DEFECT_HEADERS.length).setValues([HSE_DEFECT_HEADERS]);
    var headerRange = sheet.getRange(1, 1, 1, HSE_DEFECT_HEADERS.length);
    headerRange.setBackground("#1e3a8a");
    headerRange.setFontColor("#f8fafc");
    headerRange.setFontWeight("bold");
    headerRange.setFontSize(10);
    headerRange.setHorizontalAlignment("center");
    headerRange.setVerticalAlignment("middle");
    sheet.setRowHeight(1, 36);
    sheet.setFrozenRows(1);
    sheet.setFrozenColumns(2);
  }
  return sheet;
}

function handleGetAllDefects() {
  var ss = getOrCreateSpreadsheet();
  var sheet = getOrCreateSheet(ss, CONFIG.SHEET_NAME_HSE);
  ensureHseSheetStructure();
  var lastRow = sheet.getLastRow();
  var defects = [];
  if (lastRow > 1) {
    var values = sheet.getRange(2, 1, lastRow - 1, HSE_DEFECT_HEADERS.length).getValues();
    for (var i = 0; i < values.length; i++) {
      var row = values[i];
      if (!row[0] && !row[1]) continue;
      defects.push({
        id: String(row[0] || row[1]),
        code: String(row[1] || row[0]),
        date: String(row[2] || ""),
        month: String(row[3] || ""),
        department: String(row[4] || ""),
        dept_key: String(row[5] || ""),
        category: String(row[6] || ""),
        zh_issue: String(row[7] || ""),
        vn_issue: String(row[8] || ""),
        status: String(row[9] || "Chờ xử lý / 待处理"),
        improved: Boolean(row[10] === true || String(row[10]).toLowerCase() === "true" || String(row[9]).indexOf("已改善") > -1),
        improve_date: String(row[11] || ""),
        note: String(row[12] || ""),
        img_before: String(row[13] || ""),
        img_after: String(row[14] || ""),
        drive_direct_url: String(row[15] || ""),
        drive_view_url: String(row[16] || "")
      });
    }
  }
  return {
    status: "ok",
    success: true,
    total: defects.length,
    defects: defects
  };
}

function handleUpdateDefect(payload) {
  var ss = getOrCreateSpreadsheet();
  var sheet = getOrCreateSheet(ss, CONFIG.SHEET_NAME_HSE);
  ensureHseSheetStructure();

  var code = String(payload.defectId || payload.code || payload.id || "").trim();
  if (!code) {
    return { status: "error", error: "Thiếu mã sự cố (defectId)!" };
  }

  var lastRow = sheet.getLastRow();
  var rowIndex = -1;
  if (lastRow > 1) {
    var codes = sheet.getRange(2, 2, lastRow - 1, 1).getValues();
    for (var i = 0; i < codes.length; i++) {
      if (String(codes[i][0]).trim().toUpperCase() === code.toUpperCase()) {
        rowIndex = i + 2;
        break;
      }
    }
  }

  var isImproved = Boolean(payload.improved);
  var statusText = isImproved ? "Đã cải thiện / 已改善" : "Chờ xử lý / 待处理";
  var improveDate = payload.improveDate || (isImproved ? Utilities.formatDate(new Date(), "GMT+7", "yyyy-MM-dd") : "");
  var note = payload.note || "";
  var nowStr = Utilities.formatDate(new Date(), "GMT+7", "yyyy-MM-dd HH:mm:ss");

  if (rowIndex > 1) {
    sheet.getRange(rowIndex, 10).setValue(statusText); // status
    sheet.getRange(rowIndex, 11).setValue(isImproved); // improved
    sheet.getRange(rowIndex, 12).setValue(improveDate); // improve_date
    if (note) sheet.getRange(rowIndex, 13).setValue(note); // note
    if (payload.afterImageData) sheet.getRange(rowIndex, 15).setValue(payload.afterImageData);
    sheet.getRange(rowIndex, 18).setValue(nowStr); // updated_at
    return { status: "ok", success: true, action: "updated", defectId: code };
  } else {
    var newRow = [
      code,
      code,
      payload.date || Utilities.formatDate(new Date(), "GMT+7", "yyyy-MM-dd"),
      payload.month || Utilities.formatDate(new Date(), "GMT+7", "yyyy-MM"),
      payload.department || "",
      payload.dept_key || "",
      payload.category || "General EHS",
      payload.zh_issue || "",
      payload.vn_issue || "",
      statusText,
      isImproved,
      improveDate,
      note,
      payload.img_before || "",
      payload.afterImageData || "",
      "",
      "",
      nowStr
    ];
    sheet.appendRow(newRow);
    return { status: "ok", success: true, action: "inserted", defectId: code };
  }
}

function handleClearAllDefects() {
  var ss = getOrCreateSpreadsheet();
  var sheet = getOrCreateSheet(ss, CONFIG.SHEET_NAME_HSE);
  var lastRow = sheet.getLastRow();
  var deletedCount = 0;
  if (lastRow > 1) {
    deletedCount = lastRow - 1;
    sheet.deleteRows(2, deletedCount);
  }
  return {
    status: "ok",
    success: true,
    deleted_count: deletedCount,
    message: "Đã xóa sạch toàn bộ " + deletedCount + " dòng dữ liệu sự cố HSE khỏi Google Sheet."
  };
}
