/** Gọi máy chủ Translation (E19-5).
 *
 * Mã phiên lấy từ `chrome.storage.local`, do người dùng đăng nhập ở trang tuỳ chọn. KHÔNG có
 * đường nào để tiện ích tự tạo tài khoản: việc đó cần khoá chung của hệ thống và nó thuộc về
 * bản web.
 */

export const KHOA_LUU = {
  dia_chi: 'diaChi', ma_phien: 'maPhien', email: 'email',
  //: Ngôn ngữ CHỮ TRÊN ẢNH (không phải ngôn ngữ đích) — quyết định chọn engine OCR. `ja` là mặc
  //: định trung thực nhất với hành vi trước khi có lựa chọn này, không phải "loại phổ biến nhất".
  ngon_ngu: 'ngonNgu',
}
export const NGON_NGU_MAC_DINH = 'ja'

export async function docCauHinh() {
  const d = await chrome.storage.local.get(Object.values(KHOA_LUU))
  return {
    diaChi: (d[KHOA_LUU.dia_chi] || '').replace(/\/+$/, ''),
    maPhien: d[KHOA_LUU.ma_phien] || '',
    email: d[KHOA_LUU.email] || '',
    ngonNgu: d[KHOA_LUU.ngon_ngu] || NGON_NGU_MAC_DINH,
  }
}

export async function luuCauHinh(c) {
  const hien = await docCauHinh()
  await chrome.storage.local.set({
    [KHOA_LUU.dia_chi]: c.diaChi ?? hien.diaChi,
    [KHOA_LUU.ma_phien]: c.maPhien ?? hien.maPhien,
    [KHOA_LUU.email]: c.email ?? hien.email,
    [KHOA_LUU.ngon_ngu]: c.ngonNgu ?? hien.ngonNgu,
  })
}

/** Lỗi mang theo mã HTTP, để bên gọi phân biệt "hết phiên" với "hỏng thật". */
export class LoiApi extends Error {
  constructor(ma, thongDiep) {
    super(thongDiep)
    this.ma = ma
  }
}

async function doc(res) {
  if (res.status === 204) return null
  let than = null
  try { than = await res.json() } catch { /* không phải JSON */ }
  if (!res.ok) {
    const chi_tiet = than?.detail
    throw new LoiApi(res.status, typeof chi_tiet === 'string' ? chi_tiet : res.statusText)
  }
  return than
}

async function goi(duong, opts = {}) {
  const { diaChi, maPhien } = await docCauHinh()
  if (!diaChi) throw new LoiApi(0, 'Chưa đặt địa chỉ máy chủ Translation.')
  const headers = { ...(opts.headers || {}) }
  if (maPhien) headers.Authorization = `Bearer ${maPhien}`
  return doc(await fetch(`${diaChi}/api/v1${duong}`, { ...opts, headers }))
}

export async function dangNhap(diaChi, email, matKhau) {
  const goc = diaChi.replace(/\/+$/, '')
  const res = await fetch(`${goc}/api/v1/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, mat_khau: matKhau }),
  })
  const d = await doc(res)
  await luuCauHinh({ diaChi: goc, maPhien: d.ma_phien, email: d.nguoi_dung.email })
  return d.nguoi_dung
}

export async function toiLaAi() {
  return goi('/auth/me')
}

export async function dangXuat() {
  try { await goi('/auth/logout', { method: 'POST' }) } finally {
    await luuCauHinh({ diaChi: (await docCauHinh()).diaChi, maPhien: '', email: '' })
  }
}

/** Gửi BYTE ảnh lên. Nhận `Blob` chứ không nhận URL: máy chủ không với tới trang truyện được,
 *  và cũng không nên với tới.
 *
 * `ngonNgu` là chữ TRÊN ẢNH (chọn ở trang Tuỳ chọn), không phải ngôn ngữ đích — chọn sai không
 * báo lỗi gì, chỉ ra chữ vô nghĩa (đo được 07/09 trên MangaPlus bản tiếng Anh với mặc định `ja`).
 */
export async function guiTrang(blob, ngonNgu) {
  const form = new FormData()
  form.append('file', blob, 'trang.png')
  form.append('source_lang', ngonNgu || NGON_NGU_MAC_DINH)
  return goi('/doc-truyen/trang', { method: 'POST', body: form })
}

export async function layTrang(pageId) {
  return goi(`/doc-truyen/trang/${pageId}`)
}


/** Thiếu cấu hình thì thiếu cái gì — trả câu nói cho người dùng, hoặc `null` nếu đủ.
 *
 * Tách khỏi phần gọi Chrome API để test được bằng số. Câu chữ ở đây quan trọng hơn nó trông:
 * bản đầu chỉ nói "Chưa đặt địa chỉ máy chủ Translation." — đúng nhưng vô dụng, vì nó không
 * đưa người dùng tới chỗ sửa được, và người dùng thật đã không tìm ra trang tuỳ chọn.
 */
export function lyDoThieuCauHinh({ diaChi, maPhien }) {
  if (!diaChi) {
    return 'Chưa đặt địa chỉ máy chủ Translation. Đã mở trang cài đặt — nhập địa chỉ rồi đăng nhập.'
  }
  if (!maPhien) {
    return 'Chưa đăng nhập. Đã mở trang cài đặt — đăng nhập rồi bấm dịch lại.'
  }
  return null
}
