/** Cổng vào DUY NHẤT cho địa chỉ Translation local.
 *
 * Vì sao phải gắt tới mức này: địa chỉ ở đây do người dùng gõ, rồi được dùng cho cả `fetch`
 * lẫn `chrome.tabs.create`. Một chuỗi lọt qua đây là một chuỗi tiện ích sẽ tự tay mở hoặc tự
 * tay gọi. Kiểm bằng `startsWith('http://localhost')` thì `http://localhost.evil.example` đi
 * lọt ngay — nên ở đây **phân tích bằng `new URL()` rồi soi từng phần**, không so tiền tố.
 *
 * Chỉ cho: `http://localhost:<cổng>` và `http://127.0.0.1:<cổng>`, không tài khoản nhúng,
 * không query/hash, đường dẫn rỗng hoặc `/`.
 */

/** Tên máy được phép — so KHỚP TUYỆT ĐỐI, không phải so đuôi. */
const MAY_CHO_PHEP = new Set(['localhost', '127.0.0.1'])

const DAI_TOI_DA = 200

export const LY_DO = {
  rong: 'Chưa nhập địa chỉ.',
  qua_dai: 'Địa chỉ quá dài.',
  khong_phan_tich_duoc:
    'Không đọc được địa chỉ. Cần dạng đầy đủ, ví dụ http://127.0.0.1:5174',
  sai_giao_thuc:
    'Chỉ nhận địa chỉ bắt đầu bằng http:// (không nhận https, file, javascript, data).',
  sai_may: 'Chỉ nhận máy của chính bạn: localhost hoặc 127.0.0.1.',
  co_tai_khoan: 'Địa chỉ không được chứa tên đăng nhập hay mật khẩu.',
  thieu_cong: 'Thiếu số cổng. Ví dụ đúng: http://127.0.0.1:5174',
  sai_cong: 'Số cổng không hợp lệ.',
  co_duong_dan: 'Địa chỉ chỉ được gồm máy và cổng, không kèm đường dẫn.',
  co_tham_so: 'Địa chỉ không được kèm dấu ? hoặc #.',
}

/** Khoảng trắng + ký tự điều khiển: `new URL` có chỗ tự cắt bỏ chúng, nên chặn từ trước. */
const KY_TU_CAM = /[\s\u0000-\u001f\u007f]/

/**
 * @param {unknown} gia_tri
 * @returns {{ok: true, dia_chi: string} | {ok: false, ly_do: string}}
 *   `dia_chi` đã chuẩn hoá về dạng `http://<máy>:<cổng>` (không dấu / ở cuối).
 */
export function kiemDiaChiLocal(gia_tri) {
  if (typeof gia_tri !== 'string') return { ok: false, ly_do: LY_DO.rong }
  const tho = gia_tri.trim()
  if (!tho) return { ok: false, ly_do: LY_DO.rong }
  if (tho.length > DAI_TOI_DA) return { ok: false, ly_do: LY_DO.qua_dai }
  if (KY_TU_CAM.test(tho)) return { ok: false, ly_do: LY_DO.khong_phan_tich_duoc }

  let u
  try {
    // KHÔNG truyền base — chuỗi kiểu `//127.0.0.1:8010` hay `/duong-dan` phải ném lỗi ở đây
    // chứ không được âm thầm ghép vào gốc của trang tiện ích.
    u = new URL(tho)
  } catch {
    return { ok: false, ly_do: LY_DO.khong_phan_tich_duoc }
  }

  if (u.protocol !== 'http:') return { ok: false, ly_do: LY_DO.sai_giao_thuc }
  if (u.username || u.password) return { ok: false, ly_do: LY_DO.co_tai_khoan }
  if (!MAY_CHO_PHEP.has(u.hostname)) return { ok: false, ly_do: LY_DO.sai_may }
  if (u.search || u.hash) return { ok: false, ly_do: LY_DO.co_tham_so }

  // `new URL` đã gộp `..` rồi, nên `http://127.0.0.1:8010/../quan-tri` tới đây là `/quan-tri`
  // — rơi đúng vào nhánh này.
  if (u.pathname !== '/' && u.pathname !== '') return { ok: false, ly_do: LY_DO.co_duong_dan }

  if (!u.port) return { ok: false, ly_do: LY_DO.thieu_cong }
  const cong = Number(u.port)
  if (!Number.isInteger(cong) || cong < 1 || cong > 65535) {
    return { ok: false, ly_do: LY_DO.sai_cong }
  }

  return { ok: true, dia_chi: `${u.protocol}//${u.hostname}:${u.port}` }
}

/** Mã UUID do máy chủ sinh ra. Dùng cho id chapter/trang trước khi ghép vào địa chỉ. */
const MAU_UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i

/** @returns {string|null} mã đã chuẩn hoá chữ thường, hoặc null nếu không phải UUID. */
export function chuanHoaMa(gia_tri) {
  if (typeof gia_tri !== 'string') return null
  const tho = gia_tri.trim().toLowerCase()
  return MAU_UUID.test(tho) ? tho : null
}
