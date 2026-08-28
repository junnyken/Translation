/** Nguồn sự thật DUY NHẤT để dịch trạng thái backend ra chữ hiển thị (E11).
 *
 * Vì sao phải tập trung một chỗ: rải chuỗi trạng thái khắp component là cách mà một màn hình
 * gọi `typeset_done` là "Hoàn tất" trong khi màn khác gọi là "Cần rà soát" — và sớm muộn sẽ có
 * chỗ gọi `pending` là "xong". Toàn bộ triết lý evidence-first của M1–M10 nằm ở chỗ không nói
 * quá về trạng thái, nên chỗ dịch chữ này phải được canh bằng test.
 *
 * Quy ước: mỗi trạng thái phải có `nhan` (chữ) + `icon`. **Màu chỉ là hỗ trợ**, không bao giờ là
 * nguồn thông tin duy nhất.
 */

/** @typedef {'trung'|'tin'|'ok'|'canh'|'loi'} SacThai */

const B = (nhan, sac, icon, mo_ta, viec_tiep) => ({
  nhan, sac, icon, mo_ta, viec_tiep,
})

/** Trạng thái TRANG (`page_status` — 10 giá trị, chốt ở M1). */
export const TRANG = {
  queued: B('Đang chờ xử lý', 'trung', 'dong-ho',
    'Đã tải lên, chưa tới lượt máy xử lý.'),
  detecting: B('Đang nhận diện khung chữ', 'tin', 'quay',
    'Máy đang tìm các bong bóng thoại trên trang.'),
  detected: B('Đã nhận diện khung chữ', 'tin', 'tich',
    'Đã tìm xong bong bóng, chờ đọc chữ.'),
  detection_failed: B('Không nhận diện được khung chữ', 'loi', 'canh',
    'Bước tìm bong bóng thất bại.', 'Thử lại nhận diện'),
  ocr_done: B('Đã đọc chữ gốc', 'tin', 'tich',
    'Đọc xong chữ trong bong bóng — chưa có nghĩa là đọc đúng hết.'),
  inpainted: B('Đã xoá chữ gốc', 'tin', 'tich',
    'Đã có ảnh sạch để chèn chữ dịch.'),
  inpaint_needs_review: B('Xoá chữ chưa sạch', 'canh', 'canh',
    'Kiểm lại thấy vẫn còn chữ gốc trong vùng vừa xoá.', 'Mở để rà soát'),
  translated: B('Đã dịch, chờ căn chữ', 'tin', 'tich',
    'Có bản dịch, chưa chèn vào bong bóng.'),
  typeset_done: B('Đã căn chữ, cần rà soát', 'ok', 'tich',
    'Chữ đã vào bong bóng. Nên xem lại trước khi xuất.', 'Mở để rà soát'),
  ready_for_export: B('Sẵn sàng xuất', 'ok', 'tich',
    'Trang này đã sẵn sàng để đưa vào file xuất.'),
}

/** Trạng thái VIỆC (`job_status`) — dùng cho cả việc xuất chapter. */
export const VIEC = {
  queued: B('Đang chờ', 'trung', 'dong-ho', 'Đã xếp hàng, chưa chạy.'),
  running: B('Đang chạy', 'tin', 'quay', 'Máy đang xử lý.'),
  done: B('Xong', 'ok', 'tich', 'Đã chạy xong.'),
  failed: B('Thất bại', 'loi', 'canh', 'Việc này lỗi.', 'Xem chi tiết lỗi'),
}

/** Trạng thái MẺ (`batch_status` — M9). */
export const ME = {
  queued: B('Đang xếp hàng', 'trung', 'dong-ho', 'Mẻ đã tạo, chưa bắt đầu.'),
  running: B('Đang chạy', 'tin', 'quay', 'Còn trang chưa xong.'),
  completed: B('Xong tất cả', 'ok', 'tich', 'Mọi trang trong mẻ đã hoàn tất.'),
  partial_failed: B('Xong một phần', 'canh', 'canh',
    'Có trang hỏng — mẻ KHÔNG hoàn tất.', 'Chạy lại trang hỏng'),
  blocked_quota: B('Tạm dừng vì hết lượt gọi', 'canh', 'tam-dung',
    'Hết hạn mức dịch. Không phải hỏng — chờ hạn mức hồi rồi chạy lại.', 'Chạy lại'),
  failed: B('Hỏng', 'loi', 'canh', 'Mọi trang đều hỏng.', 'Chạy lại trang hỏng'),
  cancelled: B('Đã dừng', 'trung', 'tam-dung', 'Người dùng dừng mẻ.'),
}

/** Trạng thái MỤC trong mẻ (`batch_item_status` — M9). */
export const MUC_ME = {
  pending: B('Chờ tới lượt', 'trung', 'dong-ho', 'Chưa tới lượt trang này.'),
  running: B('Đang chạy', 'tin', 'quay', 'Đang xử lý trang này.'),
  completed: B('Xong', 'ok', 'tich', 'Trang này đã đi hết các bước.'),
  failed: B('Hỏng', 'loi', 'canh', 'Trang này lỗi.', 'Chạy lại'),
  blocked_quota: B('Hết lượt gọi', 'canh', 'tam-dung',
    'Bị chặn vì hạn mức dịch, chưa chạy được.', 'Chạy lại'),
  skipped: B('Bỏ qua', 'trung', 'tam-dung', 'Không chạy trang này.'),
}

/** Kết quả canh chữ của một vùng (`fit_status` — M6). */
export const CANH_CHU = {
  pending: B('Chưa căn chữ', 'trung', 'dong-ho', 'Vùng này chưa được chèn chữ dịch.'),
  fit_ok: B('Vừa khung', 'ok', 'tich', 'Chữ dịch nằm gọn trong bong bóng.'),
  overflow_warning: B('Chữ chưa vừa khung', 'loi', 'canh',
    'Chữ dịch tràn ra ngoài bong bóng — xuất vẫn được nhưng sẽ lộ.', 'Mở để rà soát'),
}

/** Kết quả đọc chữ của một vùng (`ocr_status` — M3). */
export const DOC_CHU = {
  pending: B('Chưa đọc', 'trung', 'dong-ho', 'Vùng này chưa được đọc chữ.'),
  ok: B('Đã đọc được', 'ok', 'tich', 'Đọc ra chữ gốc.'),
  needs_manual: B('Cần kiểm tra thủ công', 'canh', 'canh',
    'Không đọc ra chữ gốc — bong bóng này sẽ TRỐNG trong file xuất.', 'Mở để rà soát'),
}

/** Kết quả dịch của một vùng (`translation_status` — M5). */
export const DICH = {
  pending: B('Chưa có bản dịch', 'trung', 'dong-ho', 'Vùng này chưa dịch.'),
  ok: B('Đã dịch', 'ok', 'tich', 'Có bản dịch.'),
  fallback_used: B('Đã dịch (đường dự phòng)', 'canh', 'canh',
    'Bản dịch theo ngữ cảnh lỗi nên đã lùi về dịch nhanh — chất lượng thấp hơn.'),
}

/** Độ tin cậy của một vùng nhận diện (`region_status` — M2). */
export const VUNG = {
  pending: B('Chưa xử lý', 'trung', 'dong-ho', 'Vùng vừa nhận diện.'),
  low_confidence: B('Nhận diện chưa chắc', 'canh', 'canh',
    'Máy không chắc đây là bong bóng thoại.', 'Mở để rà soát'),
  confirmed: B('Đã xác nhận', 'ok', 'tich', 'Vùng này đã được xác nhận.'),
}

const BANG = {
  trang: TRANG, viec: VIEC, me: ME, muc_me: MUC_ME,
  canh_chu: CANH_CHU, doc_chu: DOC_CHU, dich: DICH, vung: VUNG,
  get phan_loai_vung() { return PHAN_LOAI_VUNG },
  get quyet_dinh_vung() { return QUYET_DINH_VUNG },
  get muc_chat_luong() { return MUC_CHAT_LUONG },
}

/** Mọi bảng gộp lại — dùng cho test canh đủ enum. */
export const TAT_CA_BANG = BANG

/**
 * Dịch một trạng thái backend sang cách hiển thị.
 *
 * Trạng thái LẠ (backend thêm mới mà giao diện chưa biết) **không được** đoán là thành công —
 * hiện rõ "Trạng thái chưa được hỗ trợ" kèm mã thô để còn lần ra.
 *
 * `boi_canh.soTran` / `boi_canh.soCanDocLai`: trang căn chữ xong nhưng còn vùng lỗi thì
 * KHÔNG được gọi là hoàn hảo — hạ xuống mức cảnh báo và nói rõ còn bao nhiêu vùng.
 */
export function dienGiaiTrangThai(loai, trang_thai, boi_canh = {}) {
  const bang = BANG[loai]
  if (!bang) throw new Error(`Loại trạng thái không có bảng: ${loai}`)

  const co_ban = bang[trang_thai]
  if (!co_ban) {
    return {
      nhan: 'Trạng thái chưa được hỗ trợ',
      sac: 'canh',
      icon: 'canh',
      mo_ta: `Giao diện chưa biết trạng thái "${trang_thai}". Đừng coi đây là đã xong.`,
      viec_tiep: undefined,
      thoi: trang_thai,
    }
  }

  const { soTran = 0, soCanDocLai = 0 } = boi_canh
  const co_canh_bao = soTran > 0 || soCanDocLai > 0
  const la_xong = (loai === 'trang' && (trang_thai === 'typeset_done' || trang_thai === 'ready_for_export'))
    || (loai === 'me' && trang_thai === 'completed')

  if (la_xong && co_canh_bao) {
    const phan = []
    if (soTran > 0) phan.push(`${soTran} vùng chữ tràn khung`)
    if (soCanDocLai > 0) phan.push(`${soCanDocLai} vùng chưa đọc được chữ`)
    return {
      ...co_ban,
      nhan: 'Đã căn chữ, còn vùng cần sửa',
      sac: 'canh',
      icon: 'canh',
      mo_ta: `Còn ${phan.join(' và ')}. Xuất vẫn được, nhưng chưa phải là bản sạch.`,
      viec_tiep: 'Mở để rà soát',
      thoi: trang_thai,
    }
  }
  return { ...co_ban, thoi: trang_thai }
}

/** Nhãn tiếng Việt cho các enum không phải trạng thái (chỉ diễn giải, không đổi nghĩa). */
export const MUC_DICH = { personal: 'Đọc cá nhân', study: 'Học tập / nghiên cứu', other: 'Khác' }
export const NGON_NGU = { en: 'Tiếng Anh', ja: 'Tiếng Nhật (manga)', zh: 'Tiếng Trung' }
export const CACH_DICH = {
  google_fast: 'Dịch nhanh (miễn phí)',
  llm_context: 'Dịch theo ngữ cảnh (AI)',
}

// ---------- E12: cổng chất lượng từng vùng ----------

/** Vùng này có khả năng là gì. Cố ý dùng chữ "có thể" — máy không kết luận thay người. */
export const PHAN_LOAI_VUNG = {
  likely_translatable: B('Có khả năng là chữ cần dịch', 'ok', 'tich',
    'Bằng chứng sạch: đọc được chữ, có bản dịch, chữ vừa khung.'),
  possible_sfx: B('Có thể là hiệu ứng âm thanh', 'canh', 'canh',
    'Chữ rất ngắn hoặc cách điệu. Vẫn có thể cần dịch — bạn quyết định.'),
  possible_number_or_decoration: B('Có thể là số hoặc trang trí', 'canh', 'canh',
    'Chỉ có số/ký hiệu. Có thể là số trang, mà cũng có thể là chữ trong tranh.'),
  uncertain: B('Chưa chắc', 'canh', 'canh',
    'Có dấu hiệu cần nhìn lại trước khi xuất.'),
}

/** Ai đã quyết định vùng này. `reviewed_skip` CHỈ do người bấm. */
export const QUYET_DINH_VUNG = {
  not_required: B('Không cần rà soát', 'ok', 'tich', 'Không có dấu hiệu bất thường.'),
  needs_review: B('Cần rà soát', 'canh', 'canh', 'Nên xem lại trước khi xuất.', 'Mở để rà soát'),
  reviewed_keep: B('Đã giữ để dịch', 'ok', 'tich', 'Bạn đã xem và quyết định giữ vùng này.'),
  reviewed_skip: B('Đã bỏ qua thủ công', 'trung', 'tam-dung',
    'Bạn đã chủ động bỏ qua. Dữ liệu vẫn còn nguyên, không bị xoá.'),
}

/** Mức chung. `blocked` = KHÔNG đánh giá được, không phải "dịch sai". */
export const MUC_CHAT_LUONG = {
  clear: B('Rõ ràng', 'ok', 'tich', 'Không có dấu hiệu cần xem lại.'),
  attention: B('Cần chú ý', 'canh', 'canh', 'Có dấu hiệu nên nhìn lại.'),
  blocked: B('Chưa đánh giá được', 'trung', 'dong-ho',
    'Thiếu dữ liệu để đánh giá — không có nghĩa là bản dịch sai.'),
}

/** Điểm tin cậy: "không có điểm" KHÁC "điểm thấp". Không bao giờ hiện 0%. */
export const TINH_TRANG_DIEM = {
  available: 'Có điểm tin cậy',
  low: 'Điểm tin cậy thấp',
  unavailable: 'Engine OCR không cung cấp điểm tin cậy',
}
