/** Trang tuỳ chọn: đặt địa chỉ máy chủ và đăng nhập (E19-5).
 *
 * Đây là chỗ DUY NHẤT tiện ích nhận mật khẩu, và mật khẩu **không được lưu** — chỉ mã phiên do
 * máy chủ cấp mới nằm lại trong `chrome.storage.local`. Mã phiên thu hồi được (đăng xuất là
 * mất hiệu lực ngay), mật khẩu thì không.
 */
import { chuanHoaDiaChi, dangKy, dangNhap, dangXuat, docCauHinh, kiemTraByok, layHanMuc, luuCauHinh, moTrangWebThongMinh, toiLaAi } from '../lib/api.js'

const $ = (id) => document.getElementById(id)
const MAY_CHU_GOI_Y = 'https://translation-api.vibe1.tinhgon.xyz'

const bao = (chu, loai) => {
  const h = $('bao')
  h.textContent = chu
  h.className = `hop ${loai}`
  h.hidden = false
}

// Hiện phiên bản ngay đầu trang: người dùng tải gói .zip về máy nên bản đang chạy có thể cũ
// hơn bản mới nhất, và không có cách nào biết ngoài việc nhìn số này.
document.getElementById('phien-ban').textContent = `v${chrome.runtime.getManifest().version}`

function chonTab(cheDo) {
  const cacTab = ['dang-nhap', 'dang-ky', 'khach']
  for (const ma of cacTab) {
    const nut = $(`tab-${ma}`)
    if (nut) nut.classList.toggle('dang-chon', ma === cheDo)
  }
  const laKhach = cheDo === 'khach'
  const laDangKy = cheDo === 'dang-ky'

  if ($('khoi-tai-khoan')) $('khoi-tai-khoan').hidden = laKhach
  if ($('nhom-ten-hien')) $('nhom-ten-hien').hidden = !laDangKy
  if ($('khoi-nut-dang-nhap')) $('khoi-nut-dang-nhap').hidden = cheDo !== 'dang-nhap'
  if ($('khoi-nut-dang-ky')) $('khoi-nut-dang-ky').hidden = !laDangKy
  if ($('khoi-nut-khach')) $('khoi-nut-khach').hidden = !laKhach

  const oEmail = $('email')
  if (oEmail) oEmail.required = laDangKy
}

$('tab-dang-nhap')?.addEventListener('click', () => chonTab('dang-nhap'))
$('tab-dang-ky')?.addEventListener('click', () => chonTab('dang-ky'))
$('tab-khach')?.addEventListener('click', () => chonTab('khach'))

$('nut-dien-vibe')?.addEventListener('click', () => {
  $('dia-chi').value = MAY_CHU_GOI_Y
  $('dia-chi').focus()
})

$('nut-an-hien-mk')?.addEventListener('click', () => {
  const o = $('mat-khau')
  const nut = $('nut-an-hien-mk')
  if (!o || !nut) return
  const dangAn = o.type === 'password'
  o.type = dangAn ? 'text' : 'password'
  nut.textContent = dangAn ? 'Ẩn' : 'Hiện'
})

async function ve() {
  const { diaChi, email, byokBat, byokProvider, byokKey } = await docCauHinh()
  $('dia-chi').value = diaChi || MAY_CHU_GOI_Y
  $('email').value = email
  if ($('opt-byok-bat')) $('opt-byok-bat').checked = Boolean(byokBat)
  if ($('opt-byok-provider') && byokProvider) $('opt-byok-provider').value = byokProvider
  if ($('opt-byok-key') && typeof byokKey === 'string') $('opt-byok-key').value = byokKey
  try {
    const nguoi = await toiLaAi()
    $('email-hien').textContent = nguoi.email
    $('da-dang-nhap').hidden = false
    $('dang-nhap').hidden = true
    const oSoDu = $('so-du-hien')
    if (oSoDu) {
      try {
        const hm = await layHanMuc()
        const muaThem = Number(hm.so_luot_mua_them || 0)
        const conNgay = Math.max(0, Number(hm.con_lai || 0) - muaThem)
        oSoDu.textContent = `💎 Khả dụng: ${hm.con_lai} trang (Miễn phí hôm nay: ${conNgay}/${hm.tran} + Ví gói: ${muaThem} trang)`
      } catch {
        oSoDu.textContent = ''
      }
    }
  } catch {
    // Chưa đăng nhập hoặc phiên hết hạn — hiện form, không báo lỗi đỏ cho một trạng thái bình thường.
    $('da-dang-nhap').hidden = true
    $('dang-nhap').hidden = false
  }
}

$('dang-nhap').addEventListener('submit', async (e) => {
  e.preventDefault()
  try {
    const diaChi = chuanHoaDiaChi($('dia-chi').value)
    $('dia-chi').value = diaChi
    const nguoi = await dangNhap(diaChi, $('email').value.trim(), $('mat-khau').value)
    $('mat-khau').value = ''
    bao(`Đã đăng nhập: ${nguoi.email} (Tài khoản có 20 Credits miễn phí)`, 'ok')
    await ve()
  } catch (err) {
    bao(String(err?.message || err), 'loi')
  }
})

$('nut-dang-ky')?.addEventListener('click', async () => {
  const diaChi = chuanHoaDiaChi($('dia-chi').value)
  $('dia-chi').value = diaChi
  const email = $('email').value.trim()
  const matKhau = $('mat-khau').value
  const tenHien = $('ten-hien')?.value.trim() || ''
  if (!diaChi || !email || !matKhau) {
    bao('Vui lòng nhập Địa chỉ máy chủ, Email và Mật khẩu (tối thiểu 8 ký tự) để đăng ký.', 'loi')
    return
  }
  try {
    const nguoi = await dangKy(diaChi, email, tenHien, matKhau)
    $('mat-khau').value = ''
    bao(`Đã tạo tài khoản và đăng nhập: ${nguoi.email} (Đã nhận 20 Credits miễn phí!)`, 'ok')
    await ve()
  } catch (err) {
    bao(String(err?.message || err), 'loi')
  }
})

$('nut-khach')?.addEventListener('click', async () => {
  const diaChi = chuanHoaDiaChi($('dia-chi').value)
  $('dia-chi').value = diaChi
  if (!diaChi) {
    bao('Vui lòng nhập Địa chỉ máy chủ Translation.', 'loi')
    return
  }
  await luuCauHinh({ diaChi, maPhien: '', email: '' })
  bao(`Đã lưu máy chủ (${diaChi}). Bạn đang ở chế độ Khách vãng lai (2 trang/ngày).`, 'ok')
  await ve()
})

$('nut-thoat').addEventListener('click', async () => {
  await dangXuat()
  bao('Đã đăng xuất.', 'ok')
  await ve()
})

document.querySelectorAll('a[href^="https://comic.io.vn"]').forEach((a) => {
  a.addEventListener('click', (e) => {
    e.preventDefault()
    moTrangWebThongMinh()
  })
})

const baoByok = (chu, loai) => {
  const h = $('bao-byok')
  if (!h) return
  h.textContent = chu
  h.className = `hop ${loai}`
  h.hidden = false
}

$('nut-an-hien-byok')?.addEventListener('click', () => {
  const o = $('opt-byok-key')
  const nut = $('nut-an-hien-byok')
  if (!o || !nut) return
  const dangAn = o.type === 'password'
  o.type = dangAn ? 'text' : 'password'
  nut.textContent = dangAn ? 'Ẩn' : 'Hiện'
})

$('nut-luu-byok')?.addEventListener('click', async () => {
  const bat = Boolean($('opt-byok-bat')?.checked)
  const prov = $('opt-byok-provider')?.value || 'gemini'
  const key = ($('opt-byok-key')?.value || '').trim()
  await luuCauHinh({ byokBat: bat, byokProvider: prov, byokKey: key })
  baoByok(
    bat && key.length >= 12
      ? `✅ Đã lưu API Key (${prov.toUpperCase()}) và bật chế độ BYOK (-50% lượt: Model 2 còn 1 lượt, Model 3 còn 1,5 lượt).`
      : '💾 Đã lưu cấu hình BYOK trên trình duyệt này.',
    'ok',
  )
})

$('nut-kiem-tra-byok')?.addEventListener('click', async () => {
  const nut = $('nut-kiem-tra-byok')
  const prov = $('opt-byok-provider')?.value || 'gemini'
  const key = ($('opt-byok-key')?.value || '').trim()
  if (key.length < 12) {
    baoByok('Vui lòng dán API Key hợp lệ (tối thiểu 12 ký tự) trước khi kiểm tra.', 'loi')
    return
  }
  await luuCauHinh({ byokBat: true, byokProvider: prov, byokKey: key })
  if ($('opt-byok-bat')) $('opt-byok-bat').checked = true
  if (nut) nut.disabled = true
  baoByok('⏳ Đang kiểm tra kết nối trực tiếp tới máy chủ AI...', 'ok')
  try {
    const kq = await kiemTraByok(prov, key, '')
    baoByok(`✅ ${kq.thong_diep || 'Kết nối thành công!'} Đã kích hoạt BYOK giảm 50% lượt.`, 'ok')
  } catch (err) {
    baoByok(`❌ ${err?.message || err}`, 'loi')
  } finally {
    if (nut) nut.disabled = false
  }
})

chonTab('dang-nhap')
ve()
