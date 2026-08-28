// Địa chỉ API, theo thứ tự ưu tiên:
//   1. `window.__API_BASE__` — sinh lúc CHẠY (config.js), cách dùng khi deploy
//   2. `VITE_API_BASE` — nhúng lúc build
//   3. rỗng — gọi đường dẫn tương đối, đúng khi chạy máy nhà (vite proxy sang API)
export const API_BASE =
  (typeof window !== 'undefined' && window.__API_BASE__) || import.meta.env.VITE_API_BASE || ''
const BASE = `${API_BASE}/api/v1`

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
