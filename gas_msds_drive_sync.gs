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
  SECRET_TOKEN: "LUV_MSDS_SECURE_TOKEN_2026",
  DRIVE_ROOT_FOLDER: "LUV_PDF_Exports",
  DRIVE_SUB_FOLDER: "MSDS_Originals",
  SHEET_NAME_CIL: "CIL_Chemical_Inventory"
};

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
    var configuredToken = getActiveSecretToken();
    if (configuredToken && token && token !== configuredToken && action !== "ping" && action !== "test_connection") {
      return jsonResponse({ status: "error", error: "Sai mã Secret Token bảo mật!" }, 403);
    }

    if (action === "ping" || action === "test_connection") {
      return jsonResponse(handlePing());
    } else if (action === "getAllChemicals" || action === "list") {
      return jsonResponse(handleGetAllChemicals());
    } else if (action === "initHeaders") {
      return jsonResponse(ensureSheetStructure());
    }

    return jsonResponse({
      status: "ok",
      service: "TitanPDF MSDS Google Apps Script Gateway",
      version: "3.5.0",
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
    var configuredToken = getActiveSecretToken();
    if (action !== "ping" && action !== "test_connection") {
      if (configuredToken && token && token !== "******" && token !== configuredToken && token !== CONFIG.SECRET_TOKEN) {
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

    // 4. Lưu / Cập nhật Hóa chất (Upsert)
    if (action === "saveChemical") {
      var saveRes = handleSaveChemical(payload.chemical || payload.data);
      return jsonResponse(saveRes);
    }

    // 5. Lưu hàng loạt Hóa chất (Batch Upsert)
    if (action === "batchSaveChemicals") {
      var batchRes = handleBatchSaveChemicals(payload.chemicals || payload.data || []);
      return jsonResponse(batchRes);
    }

    // 6. Xóa vĩnh viễn 1 Hóa chất
    if (action === "deleteChemical") {
      var delRes = handleDeleteChemical(payload.chemical_id || payload.product_code);
      return jsonResponse(delRes);
    }

    // 7. Xóa vĩnh viễn nhiều Hóa chất
    if (action === "deleteMultipleChemicals") {
      var delMultiRes = handleDeleteMultipleChemicals(payload.ids || []);
      return jsonResponse(delMultiRes);
    }

    // 8. Xóa toàn bộ dữ liệu Hóa chất (Clear All - Xóa triệt để)
    if (action === "deleteAllChemicals") {
      var delAllRes = handleDeleteAllChemicals();
      return jsonResponse(delAllRes);
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

function getActiveSecretToken() {
  try {
    var props = PropertiesService.getScriptProperties();
    var pToken = props.getProperty("SECRET_TOKEN");
    if (pToken) return pToken.trim();
  } catch (e) {}
  return CONFIG.SECRET_TOKEN;
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

  return {
    status: "ok",
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
 */
function handleGetAllChemicals() {
  var ss = getOrCreateSpreadsheet();
  var sheet = getOrCreateSheet(ss, CONFIG.SHEET_NAME_CIL);
  var lastRow = sheet.getLastRow();
  var lastCol = sheet.getLastColumn();

  if (lastRow <= 1 || lastCol < 1) {
    return { status: "ok", success: true, total: 0, chemicals: [] };
  }

  var values = sheet.getRange(2, 1, lastRow - 1, Math.min(lastCol, CIL_HEADERS.length)).getValues();
  var chemicals = [];

  for (var i = 0; i < values.length; i++) {
    var r = values[i];
    var chemObj = {
      chemical_id: r[0] || "",
      product_code: r[1] || r[0] || "",
      product_name_vi: r[2] || "",
      product_name_original: r[3] || "",
      item_type: r[4] || "raw_material",
      mother_msds_id: r[5] || "",
      cas_primary: r[6] || "",
      un_no: r[7] || "",
      transport_class: r[8] || "",
      packing_group: r[9] || "",
      signal_word: r[10] || "",
      ghs_codes: r[11] ? String(r[11]).split(/[,;]+/).map(function(s){return s.trim();}) : [],
      hazard_statements: r[12] || "",
      precautionary_statements: r[13] || "",
      flash_point: r[14] || "",
      density: r[15] || "",
      appearance: r[16] || "",
      storage_condition: r[17] || "",
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
      drive_file_id: r[30] || "",
      drive_view_url: r[31] || "",
      drive_download_url: r[32] || "",
      sha256: r[33] || "",
      sync_status: r[34] || "synced",
      created_at: r[35] || "",
      updated_at: r[36] || "",
      deleted_at: r[37] || ""
    };

    chemObj.chem_id = chemObj.chemical_id;
    chemObj.product_name = chemObj.product_name_vi || chemObj.product_name_original || chemObj.chemical_id;
    chemObj.cas_numbers = chemObj.cas_primary;
    chemObj.un_number = chemObj.un_no;
    chemObj.ghs_symbols = Array.isArray(chemObj.ghs_codes) ? chemObj.ghs_codes.join(", ") : String(chemObj.ghs_codes || "");

    try {
      chemObj.composition = r[28] ? JSON.parse(r[28]) : [];
    } catch (e) {
      chemObj.composition = [];
    }

    chemicals.push(chemObj);
  }

  return {
    status: "ok",
    success: true,
    total: chemicals.length,
    chemicals: chemicals
  };
}

/**
 * Chuyển đổi đối tượng Hóa chất thành mảng 38 giá trị tương ứng với CIL_HEADERS
 */
function buildRowFromChemical(chem, existingRow) {
  var nowStr = Utilities.formatDate(new Date(), "Asia/Bangkok", "yyyy-MM-dd HH:mm:ss");
  var chemId = String(chem.chemical_id || chem.product_code || "").trim();
  var prodCode = String(chem.product_code || chemId).trim();

  var compJson = "";
  if (chem.compositions_json) {
    compJson = (typeof chem.compositions_json === "string") ? chem.compositions_json : JSON.stringify(chem.compositions_json);
  } else if (chem.composition) {
    compJson = JSON.stringify(chem.composition);
  } else {
    compJson = "[]";
  }

  var ghsCodesStr = "";
  if (Array.isArray(chem.ghs_codes)) {
    ghsCodesStr = chem.ghs_codes.join(", ");
  } else {
    ghsCodesStr = String(chem.ghs_codes || chem.ghs_symbols || "");
  }

  var createdAt = chem.created_at || (existingRow ? existingRow[35] : nowStr);

  return [
    chemId,                                              // 0: chemical_id
    prodCode,                                            // 1: product_code
    chem.product_name_vi || chem.product_name || "",     // 2: product_name_vi
    chem.product_name_original || "",                   // 3: product_name_original
    chem.item_type || "raw_material",                   // 4: item_type
    chem.mother_msds_id || "",                          // 5: mother_msds_id
    chem.cas_primary || chem.cas_numbers || "",         // 6: cas_primary
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
    chem.storage_condition || "",                       // 17: storage_condition
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
    chem.source_file || chem.source_file_name || "",    // 29: source_file
    chem.drive_file_id || "",                           // 30: drive_file_id
    chem.drive_view_url || "",                          // 31: drive_view_url
    chem.drive_download_url || "",                      // 32: drive_download_url
    chem.sha256 || "",                                  // 33: sha256
    chem.sync_status || "synced",                       // 34: sync_status
    createdAt,                                          // 35: created_at
    nowStr,                                             // 36: updated_at
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
    ss = SpreadsheetApp.create("TitanPDF_MSDS_Chemical_Database");
    PropertiesService.getScriptProperties().setProperty("SPREADSHEET_ID", ss.getId());
  }
  return ss;
}

function getOrCreateSheet(ss, sheetName) {
  var sheet = ss.getSheetByName(sheetName);
  if (!sheet) {
    sheet = ss.insertSheet(sheetName);
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
