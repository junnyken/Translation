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
  // E13 — dùng getter vì các bảng này khai báo ở cuối tệp.
  get thuat_ngu() { return TT_THUAT_NGU },
  get ho_so_giong() { return TT_HO_SO_GIONG },
  get loai_viec_nhat_quan() { return LOAI_VIEC_NHAT_QUAN },
  get viec_nhat_quan() { return TT_VIEC_NHAT_QUAN },
  get vung_an_toan() { return TT_VUNG_AN_TOAN },
  get nguon_vung_an_toan() { return NGUON_VUNG_AN_TOAN },
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

// ---------- E13: thuật ngữ & rà soát nhất quán ----------

/** Loại thuật ngữ. Cố ý hẹp — nhóm quá rộng thì phân loại xong cũng không dùng được vào đâu. */
export const LOAI_THUAT_NGU = {
  character_name: 'Tên nhân vật',
  place: 'Địa danh',
  organization: 'Tổ chức',
  item: 'Vật phẩm',
  skill: 'Chiêu thức / phép',
  title_rank: 'Chức danh / cấp bậc',
  honorific: 'Cách xưng hô',
  catchphrase: 'Câu cửa miệng',
  general_term: 'Từ ngữ chung',
}

/** Vòng đời thuật ngữ. CHỈ "đã duyệt" mới được đem đi quét. */
export const TT_THUAT_NGU = {
  draft: B('Nháp', 'trung', 'dong-ho',
    'Chưa duyệt nên chưa tham gia rà soát.', 'Duyệt để bắt đầu dùng'),
  approved: B('Đã duyệt', 'ok', 'tich', 'Đang được dùng khi rà soát cả chapter.'),
  rejected: B('Đã bỏ', 'trung', 'tam-dung', 'Không dùng tới.'),
  archived: B('Đã cất đi', 'trung', 'tam-dung',
    'Không tham gia rà soát nữa. Các việc đã tạo từ nó vẫn còn để đối chiếu.'),
}

/** Hồ sơ giọng nhân vật — là hướng dẫn của BẠN, không phải suy luận của máy. */
export const TT_HO_SO_GIONG = {
  draft: B('Nháp', 'trung', 'dong-ho', 'Chưa bật.'),
  active: B('Đang dùng', 'ok', 'tich', 'Hiện lên khi bạn rà soát các vùng thoại.'),
  archived: B('Đã cất đi', 'trung', 'tam-dung', 'Không hiện nữa.'),
}

export const GIONG_NOI = {
  neutral: 'Trung tính',
  formal: 'Trang trọng',
  casual: 'Thân mật',
  childlike: 'Trẻ con',
  rough: 'Cộc cằn',
  archaic: 'Cổ phong',
  comic: 'Hài hước',
}

/** Vì sao có việc này. Mỗi loại nói rõ máy dựa vào đâu — không có loại nào là "máy thấy sai". */
export const LOAI_VIEC_NHAT_QUAN = {
  glossary_missing: B('Chưa dùng thuật ngữ đã chốt', 'canh', 'canh',
    'Chữ gốc có thuật ngữ này, nhưng bản dịch chưa dùng cách dịch bạn đã chốt.'),
  glossary_variant: B('Dùng cách dịch khác', 'canh', 'canh',
    'Bản dịch dùng một biến thể khác với cách đã chốt.'),
  prohibited_variant: B('Dùng cách dịch bạn đã cấm', 'loi', 'canh',
    'Bản dịch đang dùng đúng cách dịch mà bạn ghi là không dùng.'),
  voice_consistency_suspect: B('Có thể lệch giọng nhân vật', 'canh', 'canh',
    'Cần bạn xem lại — máy không tự kết luận về giọng.'),
  llm_suggestion: B('Gợi ý của AI', 'tin', 'canh',
    'Do AI đề xuất. Bạn phải duyệt trước khi áp — AI không tự sửa.'),
}

/** Trạng thái việc rà soát. `stale` KHÔNG phải lỗi — chỉ là đề xuất đã lỗi thời. */
export const TT_VIEC_NHAT_QUAN = {
  open: B('Cần xem', 'canh', 'canh', 'Chưa xử lý.', 'Mở để rà soát'),
  accepted: B('Đã áp dụng', 'ok', 'tich', 'Bạn đã đồng ý và bản dịch đã được sửa.'),
  rejected: B('Không áp dụng', 'trung', 'tam-dung', 'Bạn đã xem và quyết định không dùng.'),
  resolved_no_change: B('Giữ bản hiện tại', 'trung', 'tich', 'Bạn đã xem và giữ nguyên bản dịch.'),
  stale: B('Đề xuất đã cũ', 'trung', 'dong-ho',
    'Bản dịch đã đổi từ lần quét nên đề xuất này không còn dùng được.', 'Quét lại'),
}


/** E14 — nguồn gốc vùng an toàn. Cố ý KHÔNG dùng chữ "đã xác định chính xác": đây là suy ra
 *  từ vùng sáng trong ảnh, không phải bộ nhận diện bong bóng. */
export const NGUON_VUNG_AN_TOAN = {
  shape_derived: B('Đã nhận diện vùng an toàn', 'ok', 'tich',
    'Suy ra từ vùng sáng của bong bóng trong ảnh đã xoá chữ.'),
  fallback_rectangle: B('Đang dùng khung chữ nhật dự phòng', 'canh', 'canh',
    'Không đủ bằng chứng về hình bong bóng nên căn theo khung chữ nhật như trước.'),
  manual_override: B('Do người đặt', 'tin', 'but', 'Hình do người chỉnh tay.'),
}

export const TT_VUNG_AN_TOAN = {
  ready: B('Đã nhận diện', 'ok', 'tich', 'Có hình bong bóng dùng được.'),
  fallback_rectangle: B('Khung dự phòng', 'canh', 'canh',
    'Vẫn căn chữ được, nhưng nên nhìn lại vị trí chữ.'),
  needs_review: B('Cần kiểm tra', 'canh', 'canh',
    'Vùng an toàn quá nhỏ hoặc không tin được — nên chỉnh khung tay.'),
  failed: B('Không tính được', 'loi', 'canh', 'Đầu vào hỏng hoặc không đọc được ảnh.'),
}

/** Vì sao ra kết quả đó — dịch mã lý do sang tiếng người. */
export const LY_DO_VUNG_AN_TOAN = {
  shape_candidate_found: 'Tìm được hình bong bóng quanh chữ',
  shape_candidate_too_small: 'Vùng sáng tìm được nhỏ hơn cả khung chữ',
  shape_candidate_not_centered: 'Không có vùng sáng nào bao quanh chữ',
  shape_candidate_touches_roi_boundary: 'Bong bóng bị cắt ở mép vùng tìm kiếm',
  shape_candidate_multiple_ambiguous: 'Có nhiều vùng sáng lồng nhau, không rõ cái nào',
  shape_candidate_fills_roi: 'Vùng sáng chiếm gần hết chỗ tìm — nhiều khả năng là nền trang',
  shape_low_contrast: 'Chỗ này không có vùng sáng nào',
  shape_invalid_geometry: 'Khung chữ hoặc ảnh không hợp lệ',
  shape_erosion_eliminated_area: 'Chừa lề vào thì không còn chỗ đặt chữ',
  fallback_no_reliable_shape: 'Không đủ chắc về hình bong bóng nên dùng khung dự phòng',
  safe_area_smaller_than_minimum: 'Vùng còn lại nhỏ hơn mức tối thiểu',
  manual_bbox_changed: 'Khung chữ vừa được chỉnh tay',
  render_footprint_outside_safe_area: 'Chữ vẽ ra vượt khỏi vùng an toàn',
}

// ---------------------------------------------------------------------------
// E15 — hướng chữ
// ---------------------------------------------------------------------------

/** Nhãn theo `orientation` ĐƠN THUẦN. Nhãn thật còn phụ thuộc `status` — dùng `nhanHuongChu()`. */
export const HUONG_CHU = {
  horizontal_ltr: B('Chữ ngang', 'ok', 'tich', 'Chữ xếp theo hàng ngang như bình thường.'),
  vertical_ttb: B('Chữ dọc', 'tin', 'tich', 'Chữ xếp theo cột từ trên xuống.'),
  rotated_horizontal: B('Chữ nghiêng/cách điệu', 'canh', 'canh',
    'Chữ nằm nghiêng hoặc là hiệu ứng âm thanh được vẽ cách điệu.'),
  unknown: B('Chưa xác định hướng chữ', 'canh', 'canh',
    'Không đủ bằng chứng để nói hướng chữ. Đây là câu trả lời trung thực, không phải lỗi.'),
}

export const TT_HUONG_CHU = {
  ready: B('Đã căn theo hướng đó', 'ok', 'tich', 'Chữ đã được dựng đúng hướng nhận ra.'),
  needs_review: B('Cần kiểm tra thủ công', 'canh', 'canh', 'Nên tự nhìn lại vùng này.'),
  unavailable: B('Chưa dựng được', 'canh', 'canh',
    'Nhận ra hướng rồi nhưng hệ thống chưa dựng được chữ theo hướng đó.'),
  failed: B('Không tính được', 'loi', 'canh', 'Bước nhận biết hướng chữ lỗi.'),
}

/** Nguồn bằng chứng. */
export const NGUON_HUONG_CHU = {
  ctd_geometry: 'Hình học từ bộ nhận diện khung',
  ocr_layout: 'Đường bao dòng chữ của bước đọc chữ',
  image_heuristic: 'Suy từ hình ảnh',
  manual_reserved: 'Do người đặt',
  fallback_unknown: 'Không có nguồn bằng chứng nào',
}

/** 15 mã lý do — khớp 1:1 với `LyDo.TAT_CA` ở backend
 *  (`backend/app/services/orientation/decision.py`). Có test canh không thiếu, không thừa. */
export const LY_DO_HUONG_CHU = {
  ocr_line_geometry_vertical: 'Các dòng chữ đọc được xếp theo chiều dọc',
  ocr_line_geometry_horizontal: 'Các dòng chữ đọc được xếp theo chiều ngang',
  ocr_layout_unavailable: 'Bước đọc chữ không trả về hình dạng dòng nào',
  ctd_geometry_unavailable: 'Bộ nhận diện khung chỉ cho khung chữ nhật, không cho hình dạng dòng',
  roi_rotated_text_evidence: 'Ảnh cho thấy các dòng chữ nằm nghiêng',
  bbox_aspect_vertical_signal: 'Khung chữ cao hơn rộng — chỉ là tín hiệu, không đủ để kết luận',
  bbox_aspect_horizontal_signal: 'Khung chữ rộng hơn cao — chỉ là tín hiệu, không đủ để kết luận',
  possible_sfx_from_quality_gate: 'Cổng chất lượng đánh dấu đây có thể là hiệu ứng âm thanh',
  safe_area_fallback_rectangle: 'Đang dùng khung chữ nhật dự phòng nên hình dạng kém tin cậy',
  vertical_renderer_unavailable:
    'Hệ thống chưa có bộ dựng chữ dọc — nhận ra hướng nhưng chưa dựng được',
  vertical_font_glyph_unavailable: 'Font đang dùng không có đủ ký tự để dựng chữ dọc',
  vertical_layout_overflow: 'Xếp theo cột thì chữ tràn ra ngoài khung',
  rotated_text_manual_review_only:
    'Bản này KHÔNG tự xoay chữ — cần đặt thủ công bằng công cụ sẵn có ở màn sửa tay',
  orientation_evidence_conflict: 'Các dòng chữ cho dấu hiệu mâu thuẫn nhau',
  orientation_unknown: 'Không đủ bằng chứng để kết luận hướng chữ',
}

/**
 * Nhãn hiển thị cho một vùng — phụ thuộc CẢ hướng lẫn trạng thái.
 *
 * Vì sao không dùng thẳng `dienGiaiTrangThai`: "chữ dọc" mà `ready` là hệ thống đã dựng chữ theo
 * cột thật; "chữ dọc" mà `unavailable` là mới nhận ra chứ chưa dựng được. Gộp hai thứ đó vào một
 * nhãn là đúng kiểu nói quá mà E15 sinh ra để chống.
 *
 * Hướng/trạng thái LẠ không bao giờ rơi vào nhánh thành công — hiện rõ mã thô để còn lần ra.
 */
export function nhanHuongChu(huong, trang_thai, ma_ly_do = []) {
  const ly_do = Array.isArray(ma_ly_do) ? ma_ly_do : []

  if (ly_do.includes('orientation_evidence_conflict')) {
    return B('Dấu hiệu hướng chữ mâu thuẫn', 'canh', 'canh',
      'Các dòng chữ trong vùng này cho dấu hiệu ngược nhau — không bỏ phiếu đa số cho xong.')
  }

  const goc = HUONG_CHU[huong]
  if (!goc) {
    return {
      nhan: 'Hướng chữ chưa được hỗ trợ',
      sac: 'canh',
      icon: 'canh',
      mo_ta: `Giao diện chưa biết hướng "${huong}". Đừng coi đây là đã xong.`,
      tho: huong,
    }
  }
  if (!TT_HUONG_CHU[trang_thai]) {
    return {
      nhan: `${goc.nhan} — trạng thái chưa được hỗ trợ`,
      sac: 'canh',
      icon: 'canh',
      mo_ta: `Giao diện chưa biết trạng thái "${trang_thai}". Đừng coi đây là đã xong.`,
      tho: trang_thai,
    }
  }

  if (huong === 'horizontal_ltr') return goc

  if (huong === 'vertical_ttb') {
    return trang_thai === 'ready'
      ? B('Chữ dọc — đã căn theo cột', 'ok', 'tich',
        'Chữ đã được dựng theo cột từ trên xuống.')
      : B('Chữ dọc — cần kiểm tra thủ công', 'canh', 'canh',
        'Nhận ra là chữ dọc nhưng hệ thống chưa dựng được theo cột. Cần tự xem lại.')
  }

  if (huong === 'rotated_horizontal') {
    return B('Chữ nghiêng/cách điệu — cần đặt thủ công', 'canh', 'canh',
      'Bản này không tự xoay chữ. Dùng công cụ sẵn có ở màn sửa tay để đặt lại.')
  }

  return goc
}

/** Bộ lọc vùng theo hướng chữ (E15 §D1). Mỗi mục là một vị từ trên bản ghi hướng chữ. */
export const LOC_HUONG_CHU = [
  { ma: 'tat_ca', nhan: 'Tất cả', hop: () => true },
  { ma: 'doc', nhan: 'Chữ dọc', hop: (o) => o?.orientation === 'vertical_ttb' },
  {
    ma: 'nghieng',
    nhan: 'Chữ nghiêng/cách điệu',
    hop: (o) => o?.orientation === 'rotated_horizontal',
  },
  { ma: 'chua_biet', nhan: 'Chưa xác định', hop: (o) => o?.orientation === 'unknown' },
  {
    ma: 'can_kiem',
    nhan: 'Cần kiểm tra hướng chữ',
    // Vùng CHƯA phân tích cũng vào đây: "chưa kiểm" khác hẳn "kiểm rồi và không sao".
    hop: (o) => !o || (o.status !== 'ready'),
  },
]
