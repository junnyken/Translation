/** Khuôn dữ liệu tiện ích được phép giữ trong `chrome.storage.local` — và chỉ chừng đó.
 *
 * `chrome.storage` sống dai hơn cả lệnh xoá lịch sử/bộ nhớ đệm của trình duyệt. Thứ lỡ ghi vào
 * đây thì người dùng gần như không có đường tự dọn. Nên khuôn này chặn theo **danh sách trắng**:
 * khoá nào không có trong khuôn thì bị loại lúc đọc VÀ lúc ghi, không phải chỉ nhắc trong tài liệu.
 *
 * Nguồn sự thật vẫn là backend. Ở đây chỉ có: địa chỉ local, lựa chọn giao diện, mã chapter đã
 * ghim, và bản chụp ngắn hạn (tên + trạng thái) để hiện lúc chờ làm mới.
 */

import { chuanHoaMa, kiemDiaChiLocal } from './local-url-validator.js'

export const KHOA_CAI_DAT = 'caiDatV1'
export const KHOA_GHIM = 'chapterGhimV1'

export const PHIEN_BAN_KHUON = 1
export const SO_GHIM_TOI_DA = 5
/** Bản chụp quá hạn thì bỏ đi chứ không hiện — số cũ không nhãn là số nói dối. */
export const HAN_BAN_CHUP_MS = 24 * 60 * 60 * 1000

export const MAT_TIEN_CHO_PHEP = new Set(['side_panel', 'popup'])

/** Khoá bị cấm tuyệt đối. Có test canh: đổi ý ở đây là phải sửa test. */
export const KHOA_CAM = [
  'apiKey', 'api_key', 'token', 'secret', 'password', 'credential',
  'image', 'anh', 'blob', 'binary', 'ocr', 'translation', 'ban_dich',
  'filePath', 'duong_dan_tep', 'fileName', 'sourceUrl', 'targetUrl', 'cookie',
]

const CAI_DAT_MAC_DINH = {
  schemaVersion: PHIEN_BAN_KHUON,
  translationBaseUrl: '',
  preferredLaunchSurface: 'side_panel',
  lastOpenedProjectId: undefined,
  lastOpenedPageId: undefined,
  lastConnectionCheckAt: undefined,
}

export function caiDatMacDinh() {
  return { ...CAI_DAT_MAC_DINH }
}

function laChuoiThoiGian(v) {
  if (typeof v !== 'string' || v.length > 40) return false
  const t = Date.parse(v)
  return Number.isFinite(t)
}

/** Đọc cài đặt từ kho. Dữ liệu hỏng/cũ/thiếu → về mặc định, KHÔNG ném lỗi, KHÔNG làm vỡ panel.
 *  @returns {{caiDat: object, phaiDon: boolean}} `phaiDon` = có thứ bị loại, nên ghi đè lại kho.
 */
export function docCaiDat(tho) {
  const mac_dinh = caiDatMacDinh()
  if (!tho || typeof tho !== 'object' || Array.isArray(tho)) {
    return { caiDat: mac_dinh, phaiDon: tho !== undefined && tho !== null }
  }
  if (tho.schemaVersion !== PHIEN_BAN_KHUON) {
    // E1 là khuôn đầu tiên nên chưa có đường nâng cấp: bản lạ thì bỏ, không đoán ý.
    return { caiDat: mac_dinh, phaiDon: true }
  }

  const ket_qua = caiDatMacDinh()
  let phai_don = false

  const dia_chi = kiemDiaChiLocal(tho.translationBaseUrl)
  if (dia_chi.ok) ket_qua.translationBaseUrl = dia_chi.dia_chi
  else if (tho.translationBaseUrl) phai_don = true

  if (MAT_TIEN_CHO_PHEP.has(tho.preferredLaunchSurface)) {
    ket_qua.preferredLaunchSurface = tho.preferredLaunchSurface
  } else if (tho.preferredLaunchSurface !== undefined) {
    phai_don = true
  }

  const du_an = chuanHoaMa(tho.lastOpenedProjectId)
  if (du_an) ket_qua.lastOpenedProjectId = du_an
  else if (tho.lastOpenedProjectId !== undefined) phai_don = true

  const trang = chuanHoaMa(tho.lastOpenedPageId)
  if (trang) ket_qua.lastOpenedPageId = trang
  else if (tho.lastOpenedPageId !== undefined) phai_don = true

  if (laChuoiThoiGian(tho.lastConnectionCheckAt)) {
    ket_qua.lastConnectionCheckAt = tho.lastConnectionCheckAt
  } else if (tho.lastConnectionCheckAt !== undefined) {
    phai_don = true
  }

  // Khoá lạ (kể cả khoá cấm) không được đi tiếp — `ket_qua` dựng từ mặc định nên đã loại sẵn.
  for (const k of Object.keys(tho)) {
    if (!(k in CAI_DAT_MAC_DINH)) { phai_don = true; break }
  }

  return { caiDat: ket_qua, phaiDon: phai_don }
}

/** Bỏ các trường `undefined` để không ghi rác vào kho. */
export function donDeGhi(cai_dat) {
  const ra = {}
  for (const k of Object.keys(CAI_DAT_MAC_DINH)) {
    if (cai_dat[k] !== undefined) ra[k] = cai_dat[k]
  }
  ra.schemaVersion = PHIEN_BAN_KHUON
  return ra
}

const KHOA_GHIM_CHO_PHEP = ['projectId', 'title', 'status', 'updatedAt', 'cachedAt']

function catChuoi(v, dai) {
  return typeof v === 'string' && v ? v.slice(0, dai) : undefined
}

/** Một mục ghim hợp lệ. Trả null nếu không cứu được. */
export function docMotGhim(tho, bay_gio = Date.now()) {
  if (!tho || typeof tho !== 'object' || Array.isArray(tho)) return null
  const ma = chuanHoaMa(tho.projectId)
  if (!ma) return null
  if (!laChuoiThoiGian(tho.cachedAt)) return null
  const chup_luc = Date.parse(tho.cachedAt)
  if (chup_luc > bay_gio + 60_000) return null // mốc thời gian ở tương lai = dữ liệu hỏng

  const muc = { projectId: ma, cachedAt: tho.cachedAt }
  const het_han = bay_gio - chup_luc > HAN_BAN_CHUP_MS
  if (!het_han) {
    // Tên + trạng thái chỉ là bản chụp. Hết hạn thì giữ MỖI mã, phần mô tả bỏ đi.
    const ten = catChuoi(tho.title, 120)
    if (ten) muc.title = ten
    const tt = catChuoi(tho.status, 40)
    if (tt) muc.status = tt
    if (laChuoiThoiGian(tho.updatedAt)) muc.updatedAt = tho.updatedAt
  }
  return muc
}

/** Đọc danh sách ghim: lọc mục hỏng, bỏ trùng, cắt còn tối đa 5.
 *  @returns {{ghim: object[], phaiDon: boolean}}
 */
export function docGhim(tho, bay_gio = Date.now()) {
  if (!Array.isArray(tho)) {
    return { ghim: [], phaiDon: tho !== undefined && tho !== null }
  }
  const ra = []
  let phai_don = false
  const da_co = new Set()
  for (const muc of tho) {
    const sach = docMotGhim(muc, bay_gio)
    if (!sach) { phai_don = true; continue }
    if (da_co.has(sach.projectId)) { phai_don = true; continue }
    da_co.add(sach.projectId)
    if (ra.length < SO_GHIM_TOI_DA) ra.push(sach)
    else phai_don = true
  }
  if (!phai_don) {
    // Mục còn nguyên vẹn nhưng bản chụp vừa hết hạn cũng phải ghi lại kho.
    phai_don = JSON.stringify(ra) !== JSON.stringify(tho)
  }
  return { ghim: ra, phaiDon: phai_don }
}

/** Chốt chặn lúc GHI: ném lỗi nếu có khoá ngoài khuôn. Đây là lớp cuối, không phải lớp duy nhất. */
export function chotChanGhi(khoa, gia_tri) {
  const kiem_mot = (o, cho_phep, duong) => {
    if (!o || typeof o !== 'object') return
    for (const k of Object.keys(o)) {
      if (!cho_phep.includes(k)) {
        throw new Error(`Khoá không nằm trong khuôn, từ chối ghi: ${duong}.${k}`)
      }
    }
  }
  if (khoa === KHOA_CAI_DAT) {
    kiem_mot(gia_tri, Object.keys(CAI_DAT_MAC_DINH), KHOA_CAI_DAT)
  } else if (khoa === KHOA_GHIM) {
    if (!Array.isArray(gia_tri)) throw new Error('Danh sách ghim phải là mảng.')
    if (gia_tri.length > SO_GHIM_TOI_DA) throw new Error('Ghim quá 5 mục.')
    gia_tri.forEach((m, i) => kiem_mot(m, KHOA_GHIM_CHO_PHEP, `${KHOA_GHIM}[${i}]`))
  } else {
    throw new Error(`Khoá kho không được khai báo: ${khoa}`)
  }
  return true
}
