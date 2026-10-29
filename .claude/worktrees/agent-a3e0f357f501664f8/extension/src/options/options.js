/** Trang cài đặt: đặt địa chỉ local, thử kết nối, xoá dữ liệu tiện ích.
 *
 * Kết quả thử kết nối chỉ nói được hai điều: nối được, hoặc không — kèm danh sách lý do CÓ THỂ.
 * Trình duyệt cố tình không phân biệt "máy chủ tắt" với "bị CORS chặn", nên ở đây không đoán.
 */

import { kiemDiaChiLocal } from '../lib/local-url-validator.js'
import { ghiCaiDat, layCaiDat, xoaHet } from '../lib/settings.js'
import { kiemKetNoi } from '../lib/translation-client.js'

const form = document.getElementById('form-dia-chi')
const o = document.getElementById('o-dia-chi')
const nut_luu = document.getElementById('nut-luu')
const ket_qua = document.getElementById('ket-qua')
const vung_xoa = document.getElementById('vung-xoa')
const o_id = document.getElementById('id-tien-ich')

function bao(chu, sac, them = []) {
  ket_qua.replaceChildren()
  const khoi = document.createElement('div')
  khoi.className = 'khoi'
  khoi.setAttribute('data-sac', sac)
  const b = document.createElement('b')
  b.textContent = chu
  khoi.append(b)
  if (them.length) {
    const ul = document.createElement('ul')
    for (const d of them) {
      const li = document.createElement('li')
      li.textContent = d
      ul.append(li)
    }
    khoi.append(ul)
  }
  ket_qua.append(khoi)
}

form.addEventListener('submit', async (ev) => {
  ev.preventDefault()
  const kq = kiemDiaChiLocal(o.value)
  if (!kq.ok) {
    bao(kq.ly_do, 'loi')
    o.focus()
    return
  }
  nut_luu.disabled = true
  nut_luu.textContent = 'Đang kiểm tra…'
  try {
    const cu = await layCaiDat()
    await ghiCaiDat({ ...cu, translationBaseUrl: kq.dia_chi,
      lastConnectionCheckAt: new Date().toISOString() })
    o.value = kq.dia_chi

    const suc_khoe = await kiemKetNoi(kq.dia_chi)
    if (suc_khoe.ok) {
      bao(`Đã lưu và kết nối được tới ${kq.dia_chi}.`, 'tin',
        ['Máy chủ Translation trả lời và cho tiện ích đọc dữ liệu.'])
    } else {
      bao(`Đã lưu địa chỉ, nhưng chưa đọc được dữ liệu từ ${kq.dia_chi}.`, 'canh', [
        'Ứng dụng Translation chưa chạy trên máy.',
        'Sai địa chỉ hoặc sai cổng.',
        'Máy chủ chạy nhưng chưa cho tiện ích đọc dữ liệu (CORS) — xem mục bên dưới.',
        'Tiện ích vẫn mở được web app bình thường, chỉ là không hiện được trạng thái.',
      ])
    }
  } finally {
    nut_luu.disabled = false
    nut_luu.textContent = 'Lưu & kiểm tra kết nối'
  }
})

/** Xoá dữ liệu: hai bước, xác nhận ngay trong trang. */
function veVungXoa(hoi = false) {
  vung_xoa.replaceChildren()
  if (!hoi) {
    const b = document.createElement('button')
    b.className = 'nut'
    b.type = 'button'
    b.textContent = 'Xoá cài đặt và metadata extension'
    b.addEventListener('click', () => veVungXoa(true))
    vung_xoa.append(b)
    return
  }
  const khoi = document.createElement('div')
  khoi.className = 'khoi'
  khoi.setAttribute('data-sac', 'canh')
  khoi.setAttribute('role', 'alertdialog')
  khoi.setAttribute('aria-label', 'Xác nhận xoá dữ liệu tiện ích')
  const b = document.createElement('b')
  b.textContent = 'Chắc chắn xoá? Chapter và ảnh trong ứng dụng Translation KHÔNG bị xoá.'
  khoi.append(b)

  const hang = document.createElement('div')
  hang.className = 'hang'
  hang.style.marginTop = '8px'

  const xoa = document.createElement('button')
  xoa.className = 'nut nut-nho'
  xoa.type = 'button'
  xoa.textContent = 'Xoá'
  xoa.addEventListener('click', async () => {
    await xoaHet()
    o.value = ''
    bao('Đã xoá cài đặt và danh sách chapter đã ghim của tiện ích.', 'tin')
    veVungXoa(false)
  })

  const huy = document.createElement('button')
  huy.className = 'nut nut-nho'
  huy.type = 'button'
  huy.textContent = 'Huỷ'
  huy.addEventListener('click', () => veVungXoa(false))

  hang.append(xoa, huy)
  khoi.append(hang)
  vung_xoa.append(khoi)
}

async function khoiDong() {
  const cai_dat = await layCaiDat()
  o.value = cai_dat.translationBaseUrl ?? ''
  veVungXoa(false)
  const id = globalThis.chrome?.runtime?.id
  if (id && o_id) o_id.textContent = `ID tiện ích của bản cài này: chrome-extension://${id}`
}

khoiDong().catch((e) => {
  console.error('[Translation Companion] lỗi mở trang cài đặt:', e)
  bao('Không đọc được cài đặt đã lưu. Nhập lại địa chỉ rồi lưu là được.', 'loi')
})
