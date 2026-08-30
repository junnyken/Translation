/** Gọi API Translation local. Chỉ ĐỌC, chỉ hai endpoint đã có sẵn, chỉ khi người dùng bấm.
 *
 * Không có vòng hỏi ngầm nào chạy nền: mọi lượt gọi ở đây đều bắt nguồn từ một cú bấm hoặc từ
 * lúc panel vừa mở. Spec E1 §B4.
 *
 * Chỗ khó nhất của tệp này là **nói thật khi hỏng**. Từ trong trình duyệt, "máy chủ chưa chạy"
 * và "máy chủ chạy nhưng CORS chặn" rơi vào CÙNG một `TypeError` — không có cách nào phân biệt.
 * Nên `LOI.khong_noi_duoc` cố ý kể cả hai khả năng thay vì đoán bừa một cái rồi nói chắc nịch.
 */

import { chuanHoaMa, kiemDiaChiLocal } from './local-url-validator.js'

export const HET_GIO_MS = 5000

export const LOI = {
  dia_chi_sai: 'dia_chi_sai',
  khong_noi_duoc: 'khong_noi_duoc',
  het_gio: 'het_gio',
  khong_thay: 'khong_thay',
  loi_may_chu: 'loi_may_chu',
  du_lieu_la: 'du_lieu_la',
}

export const MO_TA_LOI = {
  [LOI.dia_chi_sai]: 'Địa chỉ Translation không hợp lệ.',
  [LOI.khong_noi_duoc]:
    'Không nối được tới Translation. Có thể: ứng dụng chưa chạy, sai địa chỉ/cổng, '
    + 'hoặc máy chủ chưa cho tiện ích đọc dữ liệu (CORS).',
  [LOI.het_gio]: 'Translation không trả lời trong 5 giây.',
  [LOI.khong_thay]: 'Không tìm thấy chapter này trên máy chủ.',
  [LOI.loi_may_chu]: 'Máy chủ Translation báo lỗi.',
  [LOI.du_lieu_la]: 'Máy chủ trả về dữ liệu không đúng khuôn mong đợi.',
}

function loi(ma, chi_tiet) {
  return { ok: false, ma, mo_ta: MO_TA_LOI[ma] ?? 'Lỗi không rõ.', chi_tiet }
}

/** `fetch` có hạn giờ. Không đính header lạ, không gửi cookie: đây là lượt đọc trần. */
async function goi(dia_chi_day_du, { het_gio = HET_GIO_MS, fetchFn = globalThis.fetch } = {}) {
  const bo_dieu_khien = new AbortController()
  const dong_ho = setTimeout(() => bo_dieu_khien.abort(), het_gio)
  try {
    return await fetchFn(dia_chi_day_du, {
      method: 'GET',
      credentials: 'omit',
      cache: 'no-store',
      signal: bo_dieu_khien.signal,
    })
  } finally {
    clearTimeout(dong_ho)
  }
}

async function docJson(res) {
  try {
    return await res.json()
  } catch {
    return null
  }
}

async function thu(dia_chi_day_du, tuy_chon) {
  let res
  try {
    res = await goi(dia_chi_day_du, tuy_chon)
  } catch (e) {
    if (e?.name === 'AbortError') return loi(LOI.het_gio)
    // TypeError ở đây gộp cả "không nối được" lẫn "bị CORS chặn" — trình duyệt cố ý không nói rõ.
    return loi(LOI.khong_noi_duoc)
  }
  if (res.status === 404) return loi(LOI.khong_thay)
  if (!res.ok) return loi(LOI.loi_may_chu, `HTTP ${res.status}`)
  const than = await docJson(res)
  if (than === null) return loi(LOI.du_lieu_la)
  return { ok: true, than }
}

/** Kiểm máy chủ sống chưa.
 *
 * Dùng `GET /api/v1/health` chứ KHÔNG dùng `/healthz`, và đây là bài học đo được ngày
 * 2026-08-30: địa chỉ người dùng nhập là địa chỉ **giao diện** (cổng 5174), không phải địa chỉ
 * API (cổng 8010). Máy chủ giao diện trả 200 kèm `Access-Control-Allow-Origin: *` cho MỌI đường
 * dẫn lạ — `/healthz` ở cổng 5174 trả về trang HTML của web app chứ không phải JSON của API.
 * Một bộ kiểm chỉ nhìn mã 200 sẽ báo "đã kết nối" trong khi API đã chết.
 *
 * `/api/v1/health` thì đi qua proxy `/api` của giao diện xuống đúng backend, và còn kiểm cả CSDL.
 * Ở đây vẫn bắt buộc thân trả về đúng `{"status":"ok"}` — 200 không phải bằng chứng.
 */
export async function kiemKetNoi(dia_chi, tuy_chon) {
  const g = kiemDiaChiLocal(dia_chi)
  if (!g.ok) return loi(LOI.dia_chi_sai, g.ly_do)
  const kq = await thu(`${g.dia_chi}/api/v1/health`, tuy_chon)
  if (!kq.ok) return kq
  const than = kq.than
  if (!than || typeof than !== 'object' || than.status !== 'ok') {
    return loi(LOI.du_lieu_la)
  }
  return { ok: true }
}

/** Lấy chi tiết một chapter. Chỉ nhận đúng các trường cần hiển thị — phần còn lại bỏ đi luôn
 *  để không có đường nào cho nội dung nhạy cảm chui vào kho. */
export async function layChapter(dia_chi, project_id, tuy_chon) {
  const g = kiemDiaChiLocal(dia_chi)
  if (!g.ok) return loi(LOI.dia_chi_sai, g.ly_do)
  const ma = chuanHoaMa(project_id)
  if (!ma) return loi(LOI.dia_chi_sai, 'Mã chapter không hợp lệ.')

  const kq = await thu(`${g.dia_chi}/api/v1/projects/${ma}`, tuy_chon)
  if (!kq.ok) return kq

  const t = kq.than
  if (!t || typeof t !== 'object' || typeof t.id !== 'string') return loi(LOI.du_lieu_la)

  const trang = Array.isArray(t.pages) ? t.pages : []
  return {
    ok: true,
    chapter: {
      projectId: ma,
      title: typeof t.name === 'string' ? t.name.slice(0, 120) : '',
      status: typeof t.status === 'string' ? t.status : '',
      updatedAt: typeof t.updated_at === 'string' ? t.updated_at : '',
      soTrang: trang.length,
      trang: trang
        .filter((p) => p && typeof p.id === 'string')
        .map((p) => ({
          id: chuanHoaMa(p.id),
          thuTu: Number.isInteger(p.order) ? p.order : null,
          trangThai: typeof p.status === 'string' ? p.status : '',
        }))
        .filter((p) => p.id),
    },
  }
}
