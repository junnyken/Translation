// Địa chỉ API, theo thứ tự ưu tiên:
//   1. `window.__API_BASE__` — sinh lúc CHẠY (config.js), cách dùng khi deploy
//   2. `VITE_API_BASE` — nhúng lúc build
//   3. rỗng — gọi đường dẫn tương đối, đúng khi chạy máy nhà (vite proxy sang API)
export const API_BASE =
  (typeof window !== 'undefined' && window.__API_BASE__) || import.meta.env.VITE_API_BASE || ''
const BASE = `${API_BASE}/api/v1`

// ---------- Khoá truy cập (auth slice A) ----------
//
// Máy chủ có thể bật một khoá chung; khi bật, MỌI lời gọi `/api/v1` thiếu khoá sẽ bị 401.
//
// Đặt khoá vào bằng cách bọc `fetch` NGAY TẠI ĐÂY, rồi mọi lời gọi trong tệp này tự động mang
// theo — thay vì sửa ~40 chỗ gọi và chắc chắn quên một chỗ. Hàm cục bộ tên `fetch` che hàm toàn
// cục trong phạm vi module, nên các dòng bên dưới không phải đổi một chữ nào.
//
// Khoá nằm ở localStorage: đây là công cụ cá nhân, không có phiên đăng nhập. Nó KHÔNG phải hệ
// thống tài khoản — ai cầm khoá là làm được mọi thứ.
const KHOA_LUU = 'translation:khoa-truy-cap'

export function docKhoa() {
  try { return localStorage.getItem(KHOA_LUU) || '' } catch { return '' }
}
export function luuKhoa(khoa) {
  try { localStorage.setItem(KHOA_LUU, khoa.trim()) } catch { /* trình duyệt chặn thì thôi */ }
}
export function xoaKhoa() {
  try { localStorage.removeItem(KHOA_LUU) } catch { /* bỏ qua */ }
}

/** `fetch` có gắn khoá. Che hàm toàn cục CÓ CHỦ Ý — xem ghi chú ở trên. */
function fetch(url, opts = {}) {
  const khoa = docKhoa()
  const headers = khoa ? { ...(opts.headers || {}), 'X-API-Key': khoa } : opts.headers
  return globalThis.fetch(url, { ...opts, headers })
}

/** Thử một lời gọi THẬT để biết khoá có dùng được không.
 *
 * Dùng `batch-config`: là GET, không tham số, không đổi gì, và nằm sau cổng khoá — đúng ba tính
 * chất cần có để kiểm khoá mà không gây tác dụng phụ nào.
 */
export const kiemKhoa = () => layCauHinhMe()   // một hiện thực duy nhất, xem bên dưới

/** Máy chủ có đang đòi khoá không — dùng để giao diện biết lúc nào cần hỏi người dùng.
 *
 * Nhận CẢ `Error` LẪN chuỗi. Bản đầu chỉ đọc `e.message`, mà App lưu lỗi bằng `setLoi(e.message)`
 * — tức truyền vào một CHUỖI. Hàm luôn trả `false`, ô nhập khoá không bao giờ hiện, và test thì
 * vẫn xanh vì nó truyền `new Error(...)` chứ không truyền đúng thứ mã thật truyền.
 */
export function laLoiThieuKhoa(e) {
  const s = typeof e === 'string' ? e : e?.message
  return typeof s === 'string' && s.startsWith('401')
}

async function doc(res) {
  if (!res.ok) {
    let chiTiet = res.statusText
    try {
      const body = await res.json()
      chiTiet = body.detail ?? JSON.stringify(body)
    } catch {
      /* body không phải JSON — giữ statusText */
    }
    throw new Error(`${res.status}: ${chiTiet}`)
  }
  return res.json()
}

export const taoProject = (thongTin) =>
  fetch(`${BASE}/projects`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(thongTin),
  }).then(doc)

/** Tải 1 trang lên. Trả {page_id, job_id, status}. */
export const taiTrangLen = (projectId, file) => {
  const form = new FormData()
  form.append('file', file)
  return fetch(`${BASE}/projects/${projectId}/pages`, { method: 'POST', body: form }).then(doc)
}

export const layProject = (id) => fetch(`${BASE}/projects/${id}`).then(doc)
export const layChiTietTrang = (id) => fetch(`${BASE}/pages/${id}/detail`).then(doc)
export const layJob = (id) => fetch(`${BASE}/jobs/${id}`).then(doc)

export const suaVung = (regionId, thayDoi) =>
  fetch(`${BASE}/regions/${regionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(thayDoi),
  }).then(doc)

export const dichLaiVung = (regionId) =>
  fetch(`${BASE}/regions/${regionId}/re-translate`, { method: 'POST' }).then(doc)

export const docLaiVung = (regionId) =>
  fetch(`${BASE}/regions/${regionId}/re-ocr`, { method: 'POST' }).then(doc)

export const canhLaiVung = (regionId) =>
  fetch(`${BASE}/regions/${regionId}/re-fit`, { method: 'POST' }).then(doc)

export const xemTruocXuat = (projectId) =>
  fetch(`${BASE}/projects/${projectId}/export-preview`).then(doc)

export const xuatChapter = (projectId, format) =>
  fetch(`${BASE}/projects/${projectId}/export`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ format }),
  }).then(doc)

export const layJobXuat = (id) => fetch(`${BASE}/export-jobs/${id}`).then(doc)
export const duongDanTaiVe = (id) => `${BASE}/export-jobs/${id}/download`

/** Chờ việc xuất chapter xong. Trả job cuối; ném lỗi nếu `failed`. */
export async function choXuatXong(jobId, { soLanToiDa = 240, nhipMs = 1000, onTien } = {}) {
  for (let i = 0; i < soLanToiDa; i++) {
    const job = await layJobXuat(jobId)
    onTien?.(job)
    if (job.status === 'done') return job
    if (job.status === 'failed') throw new Error(job.error_log || 'Xuất chapter bị lỗi')
    await new Promise((r) => setTimeout(r, nhipMs))
  }
  throw new Error('Xuất chapter quá lâu, chưa xong')
}

/** Chờ job chạy xong. Trả job cuối; ném lỗi nếu job `failed`.
 *
 * Kiên nhẫn tới 10 phút chứ không phải 42 giây như trước: worker chạy MỘT việc một lúc, nên khi
 * đang có mẻ hoặc chapter khác chạy thì việc của bạn phải xếp hàng. Đo thật ở E11: căn lại chữ
 * mất **108 giây** vì đứng sau một chapter 3 trang — giao diện cũ bỏ cuộc ở giây 42 rồi báo
 * "quá lâu, chưa xong", trong khi việc vẫn chạy và xong bình thường ngay sau đó.
 *
 * `onTien` để giao diện nói được đang chờ tới lượt hay đang chạy, thay vì đứng im.
 */
export async function choJobXong(jobId, { soLanToiDa = 600, nhipMs = 1000, onTien } = {}) {
  for (let i = 0; i < soLanToiDa; i++) {
    const job = await layJob(jobId)
    onTien?.(job)
    if (job.status === 'done') return job
    if (job.status === 'failed') throw new Error(job.error_log || 'Việc chạy nền bị lỗi')
    await new Promise((r) => setTimeout(r, nhipMs))
  }
  // Hết kiên nhẫn KHÔNG có nghĩa là hỏng — nói đúng như vậy.
  const e = new Error(
    'Việc vẫn đang chạy sau 10 phút. Máy chủ xử lý từng việc một nên có thể đang bận; '
    + 'bạn tải lại trang sau ít phút để xem kết quả.',
  )
  e.vanDangChay = true
  throw e
}

// ---------- M9: chạy cả chapter theo mẻ ----------

/** Cấu hình mẻ (chỉ true/false + các con số, không có khoá bí mật). */
export const layCauHinhMe = () => fetch(`${BASE}/batch-config`).then(doc)

export const layDanhSachMe = (projectId) =>
  fetch(`${BASE}/projects/${projectId}/batch-runs`).then(doc)

export const taoMe = (projectId, { engine, pipeline = 'full_pipeline' }) =>
  fetch(`${BASE}/projects/${projectId}/batch-runs`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ requested_pipeline: pipeline, translation_engine: engine }),
  }).then(doc)

export const layMe = (id) => fetch(`${BASE}/batch-runs/${id}`).then(doc)

export const layMucCuaMe = (id) => fetch(`${BASE}/batch-runs/${id}/items?limit=500`).then(doc)

/** Chạy lại các trang hỏng/bị chặn. `itemIds` bỏ trống = chạy lại tất cả. */
export const chayLaiMe = (id, itemIds = null) =>
  fetch(`${BASE}/batch-runs/${id}/resume`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(itemIds ? { item_ids: itemIds } : {}),
  }).then(doc)

export const huyMe = (id) => fetch(`${BASE}/batch-runs/${id}/cancel`, { method: 'POST' }).then(doc)

// ---------- M10: khai báo mục đích & cảnh báo trước khi xuất ----------

/** Số vùng còn lỗi + chapter này đã xác nhận bản quyền lần nào chưa. */
export const layCanhBaoXuat = (projectId) =>
  fetch(`${BASE}/projects/${projectId}/export-warnings`).then(doc)

/** Ghi lại việc người dùng đã đọc cảnh báo. Máy chủ tự đếm lại số liệu, không nhận từ đây. */
export const xacNhanXuat = (jobId, daTick) =>
  fetch(`${BASE}/export-jobs/${jobId}/acknowledge`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_acknowledged: daTick }),
  }).then(doc)

// ---------- E12: cổng chất lượng từng vùng ----------

/** Đánh giá chất lượng từng vùng của một trang (kèm câu lý do tiếng Việt). */
export const layChatLuongTrang = (pageId) => fetch(`${BASE}/pages/${pageId}/quality`).then(doc)

export const layTomTatChatLuong = (projectId) =>
  fetch(`${BASE}/projects/${projectId}/quality-summary`).then(doc)

/** Ghi quyết định của NGƯỜI cho một vùng: `keep` giữ để dịch, `skip` bỏ qua.
 *  `skip` KHÔNG xoá dữ liệu — chỉ ghi lại quyết định. */
export const ghiQuyetDinhVung = (regionId, decision) =>
  fetch(`${BASE}/regions/${regionId}/quality-review`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ decision }),
  }).then(doc)

// ---------- E13: thuật ngữ & rà soát nhất quán ----------

export const layThuatNgu = (projectId, loc = '') =>
  fetch(`${BASE}/projects/${projectId}/glossary${loc}`).then(doc)

export const themThuatNgu = (projectId, du_lieu) =>
  fetch(`${BASE}/projects/${projectId}/glossary`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(du_lieu),
  }).then(doc)

export const suaThuatNgu = (entryId, du_lieu) =>
  fetch(`${BASE}/glossary/${entryId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(du_lieu),
  }).then(doc)

export const duyetThuatNgu = (entryId) =>
  fetch(`${BASE}/glossary/${entryId}/approve`, { method: 'POST' }).then(doc)

export const catThuatNgu = (entryId) =>
  fetch(`${BASE}/glossary/${entryId}/archive`, { method: 'POST' }).then(doc)

export const layHoSoGiong = (projectId) =>
  fetch(`${BASE}/projects/${projectId}/voice-profiles`).then(doc)

export const themHoSoGiong = (projectId, du_lieu) =>
  fetch(`${BASE}/projects/${projectId}/voice-profiles`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(du_lieu),
  }).then(doc)

export const batHoSoGiong = (profileId) =>
  fetch(`${BASE}/voice-profiles/${profileId}/activate`, { method: 'POST' }).then(doc)

export const catHoSoGiong = (profileId) =>
  fetch(`${BASE}/voice-profiles/${profileId}/archive`, { method: 'POST' }).then(doc)

// ---------- E17: gợi ý thuật ngữ & xưng hô rút từ chính chapter ----------

/** Danh xưng lặp lại trong chapter, kèm bằng chứng. Chỉ đọc — không tạo thuật ngữ nào. */
export const layUngVienThuatNgu = (projectId) =>
  fetch(`${BASE}/projects/${projectId}/term-candidates`).then(doc)

/** Tín hiệu xưng hô CÓ THẬT trong bản gốc (hậu tố kính ngữ, đại từ nhân xưng). */
export const layTinHieuXungHo = (projectId) =>
  fetch(`${BASE}/projects/${projectId}/voice-signals`).then(doc)

/** Tầng 3 — hỏi mô hình cách dịch cho danh xưng đã tìm được. Trả 202 + lượt hỏi để theo dõi. */
/** E17 tầng 3b — đối chiếu danh xưng CỦA CHAPTER với CSDL nhân vật AniList.
 *
 * Khác tầng 3a ở chỗ căn bản: 3a hỏi MÔ HÌNH (luôn trả lời kể cả khi không biết), 3b tra một
 * CSDL có thật. Nhưng cả hai chịu chung một cổng: thứ trả về không khớp danh xưng của chapter
 * thì bị loại.
 */
export const doiChieuTenChinhThuc = (projectId, ten_bo_truyen) =>
  fetch(`${BASE}/projects/${projectId}/term-official-names`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ ten_bo_truyen }),
  }).then(doc)

export const xinGoiYTheoTenTruyen = (projectId, series_name) =>
  fetch(`${BASE}/projects/${projectId}/term-suggestions`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ series_name }),
  }).then(doc)

/** `suggestions === null` là CHƯA XONG; `[]` là xong mà không mục nào qua cổng đối chiếu. */
export const layKetQuaGoiY = (runId) =>
  fetch(`${BASE}/term-suggestion-runs/${runId}`).then(doc)

export const quetNhatQuan = (projectId) =>
  fetch(`${BASE}/projects/${projectId}/consistency-scans`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode: 'rules' }),
  }).then(doc)

export const tomTatNhatQuan = (projectId) =>
  fetch(`${BASE}/projects/${projectId}/consistency-summary`).then(doc)

export const layViecNhatQuan = (projectId, loc = '') =>
  fetch(`${BASE}/projects/${projectId}/consistency-tasks${loc}`).then(doc)

export const apViecNhatQuan = (taskId, edited_text) =>
  fetch(`${BASE}/consistency-tasks/${taskId}/accept`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ edited_text: edited_text ?? null }),
  }).then(doc)

export const boQuaViecNhatQuan = (taskId, resolution) =>
  fetch(`${BASE}/consistency-tasks/${taskId}/reject`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ resolution }),
  }).then(doc)


// ---------- E14: vùng an toàn của bong bóng ----------

/** Vùng an toàn của từng vùng chữ trên một trang, gom thành `{region_id: bản ghi}`.
 *
 * Vùng chưa tính trả 404 — đó KHÔNG phải lỗi, chỉ là chưa có, nên bỏ qua. Nhưng chỉ bỏ qua
 * ĐÚNG 404: mọi lỗi khác phải ném ra, nếu không thì hỏng đường mạng cũng hiện y như "chưa tính"
 * và không ai biết. (Bản đầu bắt hết mọi lỗi — và nuốt luôn một `ReferenceError` của chính nó.)
 */
export async function layVungAnToan(regionIds) {
  const cap = await Promise.all(regionIds.map(async (id) => {
    const res = await fetch(`${BASE}/regions/${id}/safe-area`)
    if (res.status === 404) return [id, null]
    return [id, await doc(res)]
  }))
  return Object.fromEntries(cap.filter(([, v]) => v))
}

export const tomTatVungAnToan = (pageId) => fetch(`${BASE}/pages/${pageId}/safe-area-summary`).then(doc)
export const tinhLaiVungAnToan = (pageId) =>
  fetch(`${BASE}/pages/${pageId}/retry-safe-area`, { method: 'POST' }).then(doc)

// ---------- E15: hướng chữ ----------

/** Lấy hướng chữ của nhiều vùng cùng lúc.
 *
 * Backend cố ý trả **404** cho vùng chưa phân tích thay vì `unknown` giả — nên ở đây 404 được
 * dịch thành `null` ("chưa kiểm"), khác hẳn `orientation: 'unknown'` ("kiểm rồi, không đủ
 * bằng chứng"). Giao diện phải nói được hai thứ đó khác nhau.
 */
export async function layHuongChu(regionIds) {
  const cap = await Promise.all(regionIds.map(async (id) => {
    const res = await fetch(`${BASE}/regions/${id}/orientation`)
    if (res.status === 404) return [id, null]
    // Chỉ nuốt ĐÚNG 404. Nuốt cả lỗi mạng thì "API chết" hiện y hệt "chưa kiểm" — đúng cái bẫy
    // mà `layVungAnToan` của E14 đã dính một lần rồi.
    return [id, await doc(res)]
  }))
  return Object.fromEntries(cap)
}

export const tomTatHuongChu = (pageId) =>
  fetch(`${BASE}/pages/${pageId}/orientation-summary`).then(doc)

export const chayLaiHuongChu = (pageId) =>
  fetch(`${BASE}/pages/${pageId}/retry-orientation`, { method: 'POST' }).then(doc)

// ---------- P3j: vì sao trang này đứng im ----------

/** Lịch sử job của một trang, mới nhất trước.
 *
 * Gọi KHI NGƯỜI DÙNG HỎI, không đưa vào vòng poll: màn chapter đã hỏi lại 7 endpoint mỗi 5 giây,
 * thêm một lượt cho mỗi trang nữa là nhân số request lên theo số trang để phục vụ một câu hỏi mà
 * phần lớn thời gian không ai đặt.
 */
export function layJobCuaTrang(pageId) {
  return fetch(`${BASE}/pages/${pageId}/jobs`).then(doc)
}

/** Job hỏng gần nhất của một trang, hoặc `null` nếu không có.
 *
 * Trả về nguyên bản ghi chứ không chỉ chuỗi lý do — bên gọi còn cần `type` để nói cho người dùng
 * biết BƯỚC NÀO hỏng, không chỉ "có gì đó hỏng".
 */
export async function layLyDoDung(pageId) {
  const js = await layJobCuaTrang(pageId)
  return js.find((j) => j.status === 'failed') ?? null
}
