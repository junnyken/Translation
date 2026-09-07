/** Trang tuỳ chọn: đặt địa chỉ máy chủ và đăng nhập (E19-5).
 *
 * Đây là chỗ DUY NHẤT tiện ích nhận mật khẩu, và mật khẩu **không được lưu** — chỉ mã phiên do
 * máy chủ cấp mới nằm lại trong `chrome.storage.local`. Mã phiên thu hồi được (đăng xuất là
 * mất hiệu lực ngay), mật khẩu thì không.
 */
import { dangNhap, dangXuat, docCauHinh, toiLaAi } from '../lib/api.js'

const $ = (id) => document.getElementById(id)
const bao = (chu, loai) => {
  const h = $('bao')
  h.textContent = chu
  h.className = `hop ${loai}`
  h.hidden = false
}

async function ve() {
  const { diaChi, email } = await docCauHinh()
  $('dia-chi').value = diaChi
  $('email').value = email
  try {
    const nguoi = await toiLaAi()
    $('email-hien').textContent = nguoi.email
    $('da-dang-nhap').hidden = false
    $('dang-nhap').hidden = true
  } catch {
    // Chưa đăng nhập hoặc phiên hết hạn — hiện form, không báo lỗi đỏ cho một trạng thái bình thường.
    $('da-dang-nhap').hidden = true
    $('dang-nhap').hidden = false
  }
}

$('dang-nhap').addEventListener('submit', async (e) => {
  e.preventDefault()
  try {
    const nguoi = await dangNhap($('dia-chi').value.trim(), $('email').value.trim(), $('mat-khau').value)
    $('mat-khau').value = ''
    bao(`Đã đăng nhập: ${nguoi.email}`, 'ok')
    await ve()
  } catch (err) {
    bao(String(err?.message || err), 'loi')
  }
})

$('nut-thoat').addEventListener('click', async () => {
  await dangXuat()
  bao('Đã đăng xuất.', 'ok')
  await ve()
})

ve()
