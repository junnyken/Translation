/** Gọi máy chủ Translation (E19-5).
 *
 * Mã phiên lấy từ `chrome.storage.local`, do người dùng đăng nhập ở trang tuỳ chọn. KHÔNG có
 * đường nào để tiện ích tự tạo tài khoản: việc đó cần khoá chung của hệ thống và nó thuộc về
 * bản web.
 */

export const KHOA_LUU = { dia_chi: 'diaChi', ma_phien: 'maPhien', email: 'email' }

export async function docCauHinh() {
  const d = await chrome.storage.local.get(Object.values(KHOA_LUU))
  return {
    diaChi: (d[KHOA_LUU.dia_chi] || '').replace(/\/+$/, ''),
    maPhien: d[KHOA_LUU.ma_phien] || '',
    email: d[KHOA_LUU.email] || '',
  }
}

export async function luuCauHinh(c) {
  await chrome.storage.local.set({
    [KHOA_LUU.dia_chi]: c.diaChi ?? '',
    [KHOA_LUU.ma_phien]: c.maPhien ?? '',
    [KHOA_LUU.email]: c.email ?? '',
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
 *  và cũng không nên với tới. */
export async function guiTrang(blob) {
  const form = new FormData()
  form.append('file', blob, 'trang.png')
  return goi('/doc-truyen/trang', { method: 'POST', body: form })
}

export async function layTrang(pageId) {
  return goi(`/doc-truyen/trang/${pageId}`)
}
