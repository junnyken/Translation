/** Danh sách trắng origin cho MÁY CHỦ DEV của Vite — chặn mặc định, chỉ mở đúng thứ được khai.
 *
 * Vì sao tệp này tồn tại: Vite 6.0.7 mặc định `server.cors: true`, tức là gắn
 * `Access-Control-Allow-Origin: *` vào **mọi** phản hồi — kể cả phản hồi đã đi qua proxy `/api`
 * xuống backend. Đo thật ngày 2026-08-30: bất kỳ website nào đang mở cũng đọc được
 * `GET /api/v1/projects/{id}` của Translation local. Xem `docs/SECURITY.md`.
 *
 * Tệp này chạy ở phía Node (được `vite.config.js` nạp), KHÔNG đi vào gói trình duyệt.
 *
 * Hai việc tách bạch:
 *   - `kiemMucKhaiBao()` — kiểm một dòng CẤU HÌNH có hợp lệ không (lúc khởi động).
 *   - `laOriginDuocPhep()` — kiểm một Origin của REQUEST có nằm trong danh sách không.
 * Lẫn hai việc này là cách người ta vô tình cho `https://evil.example` qua: nó là một origin
 * đúng khuôn, nhưng không có mặt trong danh sách.
 */

/** Giao thức được phép khai báo. `chrome-extension:` chỉ để dành cho tiện ích E1 nếu người dùng
 *  tự khai đúng ID thật của bản cài trên máy mình. */
const GIAO_THUC_CHO_PHEP = new Set(['http:', 'https:', 'chrome-extension:'])

/** Máy được phép với http/https — khớp TUYỆT ĐỐI, không đuôi, không mẫu. */
const MAY_CHO_PHEP = new Set(['localhost', '127.0.0.1'])

export const LY_DO = {
  rong: 'Mục rỗng.',
  co_dai_dien: 'Không nhận ký tự đại diện (*) — phải khai từng origin một.',
  khong_doc_duoc: 'Không đọc được origin. Cần dạng đầy đủ, ví dụ http://127.0.0.1:5174',
  sai_giao_thuc: 'Chỉ nhận http://, https:// hoặc chrome-extension://',
  co_tai_khoan: 'Origin không được chứa tên đăng nhập hay mật khẩu.',
  co_duong_dan: 'Origin không được kèm đường dẫn, dấu ? hoặc #.',
  sai_may: 'Máy chủ dev chỉ nhận localhost hoặc 127.0.0.1.',
  sai_ma_tien_ich: 'ID tiện ích phải là 32 chữ cái a-p.',
}

const MAU_ID_TIEN_ICH = /^[a-p]{32}$/

/**
 * Kiểm MỘT mục trong cấu hình danh sách trắng.
 * @returns {{ok: true, origin: string} | {ok: false, ly_do: string}}
 */
export function kiemMucKhaiBao(gia_tri) {
  if (typeof gia_tri !== 'string' || !gia_tri.trim()) {
    return { ok: false, ly_do: LY_DO.rong }
  }
  const tho = gia_tri.trim()

  // Chặn trước khi phân tích: `new URL` chấp nhận `*` làm một phần tên máy hợp lệ.
  if (tho.includes('*')) return { ok: false, ly_do: LY_DO.co_dai_dien }

  let u
  try {
    u = new URL(tho)
  } catch {
    return { ok: false, ly_do: LY_DO.khong_doc_duoc }
  }

  if (!GIAO_THUC_CHO_PHEP.has(u.protocol)) return { ok: false, ly_do: LY_DO.sai_giao_thuc }
  if (u.username || u.password) return { ok: false, ly_do: LY_DO.co_tai_khoan }
  if (u.search || u.hash) return { ok: false, ly_do: LY_DO.co_duong_dan }
  if (u.pathname !== '/' && u.pathname !== '') return { ok: false, ly_do: LY_DO.co_duong_dan }

  if (u.protocol === 'chrome-extension:') {
    if (!MAU_ID_TIEN_ICH.test(u.hostname)) return { ok: false, ly_do: LY_DO.sai_ma_tien_ich }
    return { ok: true, origin: `chrome-extension://${u.hostname}` }
  }

  // http/https: chỉ máy của chính mình. LAN/private/public đều bị loại ở đây.
  if (!MAY_CHO_PHEP.has(u.hostname)) return { ok: false, ly_do: LY_DO.sai_may }
  return { ok: true, origin: u.port ? `${u.protocol}//${u.hostname}:${u.port}`
    : `${u.protocol}//${u.hostname}` }
}

/**
 * Đọc danh sách trắng từ chuỗi cấu hình (CSV). Mục hỏng bị LOẠI kèm lý do, không làm sập
 * máy chủ dev — nhưng cũng không im lặng: `bi_loai` được in ra lúc khởi động.
 * @returns {{origins: string[], bi_loai: {gia_tri: string, ly_do: string}[]}}
 */
export function docDanhSachTrang(tho) {
  const origins = []
  const bi_loai = []
  const da_co = new Set()

  for (const phan of String(tho ?? '').split(',')) {
    const muc = phan.trim()
    if (!muc) continue
    const kq = kiemMucKhaiBao(muc)
    if (!kq.ok) {
      bi_loai.push({ gia_tri: muc, ly_do: kq.ly_do })
      continue
    }
    // Chuẩn hoá rồi mới chống trùng: `http://localhost:5174/` và `http://localhost:5174`
    // là một, khai hai lần không được sinh ra hai mục.
    if (da_co.has(kq.origin)) continue
    da_co.add(kq.origin)
    origins.push(kq.origin)
  }
  return { origins, bi_loai }
}

/**
 * Origin của một REQUEST có được phép không. So khớp TUYỆT ĐỐI với danh sách đã chuẩn hoá.
 *
 * Mọi thứ không nằm trong danh sách đều bị từ chối — kể cả `null`, `file://`, `data:`,
 * `javascript:`, LAN IP, tên miền công cộng, và origin trông giống localhost.
 */
export function laOriginDuocPhep(origin, danh_sach) {
  if (typeof origin !== 'string' || !origin) return false
  if (!Array.isArray(danh_sach) || danh_sach.length === 0) return false
  // KHÔNG chuẩn hoá origin của request trước khi so: trình duyệt gửi origin đã chuẩn hoá sẵn,
  // còn tự chuẩn hoá lại là mở đường cho khác biệt giữa bộ kiểm và bộ so.
  return danh_sach.includes(origin)
}
