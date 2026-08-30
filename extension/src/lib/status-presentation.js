/** Dịch trạng thái backend ra chữ hiển thị — bản rút gọn cho tiện ích.
 *
 * Chữ ở đây **chép đúng** từ `frontend/src/lib/status-presentation.js` của web app. Lý do: một
 * trạng thái mà panel gọi "Xong" còn web app gọi "Cần rà soát" là cách nhanh nhất để người dùng
 * mất lòng tin vào cả hai. Có test canh chuyện lệch chữ này.
 *
 * Luật cứng: trạng thái KHÔNG nằm trong bảng thì hiện "Không rõ trạng thái" — **không bao giờ**
 * rơi vào nhánh thành công.
 */

const B = (nhan, sac, mo_ta) => ({ nhan, sac, mo_ta })

/** `page_status` — 10 giá trị, chốt ở M1. */
export const TRANG = {
  queued: B('Đang chờ xử lý', 'trung', 'Đã tải lên, chưa tới lượt máy xử lý.'),
  detecting: B('Đang nhận diện khung chữ', 'tin', 'Máy đang tìm các bong bóng thoại trên trang.'),
  detected: B('Đã nhận diện khung chữ', 'tin', 'Đã tìm xong bong bóng, chờ đọc chữ.'),
  detection_failed: B('Không nhận diện được khung chữ', 'loi', 'Bước tìm bong bóng thất bại.'),
  ocr_done: B('Đã đọc chữ gốc', 'tin', 'Đọc xong chữ trong bong bóng — chưa có nghĩa là đọc đúng hết.'),
  inpainted: B('Đã xoá chữ gốc', 'tin', 'Đã có ảnh sạch để chèn chữ dịch.'),
  inpaint_needs_review: B('Xoá chữ chưa sạch', 'canh',
    'Kiểm lại thấy vẫn còn chữ gốc trong vùng vừa xoá.'),
  translated: B('Đã dịch, chờ căn chữ', 'tin', 'Có bản dịch, chưa chèn vào bong bóng.'),
  typeset_done: B('Đã căn chữ, cần rà soát', 'ok',
    'Chữ đã vào bong bóng. Nên xem lại trước khi xuất.'),
  ready_for_export: B('Sẵn sàng xuất', 'ok', 'Trang này đã sẵn sàng để đưa vào file xuất.'),
}

/** `project_status` — 2 giá trị (`backend/app/models/enums.py`). */
export const CHAPTER = {
  active: B('Đang làm', 'tin', 'Chapter còn đang xử lý.'),
  archived: B('Đã lưu trữ', 'trung', 'Chapter đã được cất đi.'),
}

export const KHONG_RO = B('Không rõ trạng thái', 'canh',
  'Máy chủ trả về một trạng thái tiện ích chưa biết. Mở web app để xem cho chắc.')

function tra(bang, ma) {
  if (typeof ma !== 'string' || !Object.prototype.hasOwnProperty.call(bang, ma)) return KHONG_RO
  return bang[ma]
}

export const nhanTrang = (ma) => tra(TRANG, ma)
export const nhanChapter = (ma) => tra(CHAPTER, ma)

/** Trang được phép đưa vào file xuất — LẤY TỪ backend, không đoán:
 *  `routes.py::export_preview` lọc đúng hai trạng thái này. */
export const TRANG_XUAT_DUOC = new Set(['typeset_done', 'ready_for_export'])

/** Trang mở được màn rà soát tay (M7): đã có chữ để nhìn, hoặc đang cần người xem lại. */
export const TRANG_RA_SOAT_DUOC = new Set([
  'inpaint_needs_review', 'typeset_done', 'ready_for_export',
])

/**
 * Tóm tắt một chapter thành đúng những gì panel được phép hiện.
 * Không suy ra "đã xong" từ bất cứ đâu — chỉ đếm.
 */
export function tomTatChapter(chapter) {
  const trang = Array.isArray(chapter?.trang) ? chapter.trang : []
  const xuat_duoc = trang.filter((p) => TRANG_XUAT_DUOC.has(p.trangThai))
  const ra_soat_duoc = trang.filter((p) => TRANG_RA_SOAT_DUOC.has(p.trangThai))
  return {
    soTrang: trang.length,
    soTrangXuatDuoc: xuat_duoc.length,
    // Trang đầu tiên đáng mở để rà soát; không có thì nút bị tắt chứ không mở bừa trang 1.
    trangRaSoat: ra_soat_duoc[0]?.id ?? null,
    coTheXuat: xuat_duoc.length > 0,
    coTheRaSoat: ra_soat_duoc.length > 0,
  }
}

/** "cập nhật lần cuối" — bản chụp phải luôn đi kèm nhãn thời gian, nếu không nó là số nói dối. */
export function nhanThoiGian(iso, bay_gio = Date.now()) {
  if (typeof iso !== 'string') return ''
  const t = Date.parse(iso)
  if (!Number.isFinite(t)) return ''
  const giay = Math.max(0, Math.round((bay_gio - t) / 1000))
  if (giay < 60) return 'vừa xong'
  const phut = Math.round(giay / 60)
  if (phut < 60) return `${phut} phút trước`
  const gio = Math.round(phut / 60)
  if (gio < 24) return `${gio} giờ trước`
  return `${Math.round(gio / 24)} ngày trước`
}
