/** Popup khi bấm icon (E19-4 + E104 — Giao diện hiện đại, cố định chế độ Xoá chữ & căn chữ LaMa). */
import { docCauHinh, layHanMuc, luuCauHinh, moTrangWebThongMinh } from '../lib/api.js'

const $ = (id) => document.getElementById(id)
const bao = (chu, loai) => {
  const h = $('bao')
  if (!h) return
  h.textContent = chu
  h.className = `hop ${loai}`
  h.hidden = false
}

function dongBoNutNgonNgu(nn) {
  document.querySelectorAll('#nhom-nut-nn .nut-nn').forEach((btn) => {
    btn.classList.toggle('dang-chon', btn.dataset.nn === nn)
  })
}

function dongBoNutDichRa(dich) {
  document.querySelectorAll('#nhom-nut-dich .nut-dich-ra').forEach((btn) => {
    btn.classList.toggle('dang-chon', btn.dataset.dich === dich)
  })
  const nhanPhu = $('nhan-phu-eng')
  if (nhanPhu) {
    nhanPhu.textContent = dich === 'en' ? 'Sang Tiếng Anh' : 'Sang Tiếng Việt'
  }
}

function dongBoNutEngine(eng) {
  document.querySelectorAll('#nhom-nut-eng .nut-eng').forEach((btn) => {
    btn.classList.toggle('dang-chon', btn.dataset.eng === eng)
  })
}

function dongBoNutFont(font) {
  document.querySelectorAll('#nhom-nut-font .nut-font').forEach((btn) => {
    btn.classList.toggle('dang-chon', btn.dataset.font === font)
  })
}

async function ve() {
  const { ngonNgu, ngonNguDich, engine, fontChu } = await docCauHinh()
  await luuCauHinh({ cheDo: 'chi_chu' })
  if ($('ngon-ngu')) $('ngon-ngu').value = ngonNgu
  if ($('ngon-ngu-dich')) $('ngon-ngu-dich').value = ngonNguDich || 'vi'
  if ($('engine')) $('engine').value = engine
  if ($('font-chu')) $('font-chu').value = fontChu || 'bangers'
  if ($('che-do')) $('che-do').value = 'chi_chu'
  dongBoNutNgonNgu(ngonNgu)
  dongBoNutDichRa(ngonNguDich || 'vi')
  dongBoNutEngine(engine)
  dongBoNutFont(fontChu || 'bangers')
  veHanMuc()
  veMayChu()
}

async function veHanMuc() {
  const o = $('han-muc')
  if (!o) return
  try {
    const { diaChi, engine } = await docCauHinh()
    if (engine === 'local_gguf') {
      o.textContent = '💻 Chế độ GGUF Cục bộ (Ollama / LM Studio trên máy bạn) · Không giới hạn lượt!'
      o.className = 'hop ok'
      o.hidden = false
      $('nut-dich').disabled = false
      $('nut-dich-chapter').disabled = false
      if ($('nut-tu-dich-cuon')) $('nut-tu-dich-cuon').disabled = false
      if ($('nut-khoanh-vung')) $('nut-khoanh-vung').disabled = false
      return
    }
    if (!diaChi) {
      o.textContent = '⚠️ Chưa đặt máy chủ. Bấm "⚙️ Tài khoản" góc phải trên để cài đặt.'
      o.className = 'hop canh-bao'
      o.hidden = false
      return
    }
    const hm = await layHanMuc()
    const vaiTro = hm.co_tai_khoan ? '✅ Đã đăng nhập' : '👤 Khách (đăng nhập nhận 20 trang/ngày)'
    const tichLuy = hm.so_luot_mua_them > 0 ? ` (+${hm.so_luot_mua_them} VIP)` : ''
    o.textContent = `${vaiTro} · Còn ${hm.con_lai}/${hm.tran} trang hôm nay${tichLuy}`
    o.className = hm.con_lai <= 0
      ? 'hop loi'
      : (hm.con_lai < hm.tran && hm.con_lai <= 2) ? 'hop canh-bao' : 'hop ok'
    o.hidden = false
    if (hm.con_lai <= 0) {
      $('nut-dich').disabled = true
      $('nut-dich-chapter').disabled = true
      if ($('nut-tu-dich-cuon')) $('nut-tu-dich-cuon').disabled = true
      if ($('nut-khoanh-vung')) $('nut-khoanh-vung').disabled = true
    } else {
      $('nut-dich').disabled = false
      $('nut-dich-chapter').disabled = false
      if ($('nut-tu-dich-cuon')) $('nut-tu-dich-cuon').disabled = false
      if ($('nut-khoanh-vung')) $('nut-khoanh-vung').disabled = false
    }
  } catch {
    o.hidden = true
  }
}

async function veMayChu() {
  const o = $('may-chu')
  if (!o) return
  try {
    const { diaChi, engine } = await docCauHinh()
    if (engine === 'local_gguf') {
      o.textContent = 'Chạy Offline 100% trên phần cứng máy bạn (127.0.0.1:11434 / 1234).'
      o.hidden = false
      return
    }
    if (!diaChi) return
    const r = await fetch(`${diaChi}/healthz`, { cache: 'no-store' })
    if (!r.ok) return
    const d = await r.json()
    const ton_tien = []
    if (d.detect_engine && d.detect_engine !== 'ctd') ton_tien.push('nhận diện')
    if ($('engine').value === 'llm_context') ton_tien.push('dịch')
    o.textContent = ton_tien.length
      ? `Máy chủ AI: ${ton_tien.join(' + ')} bằng mô hình đám mây (${d.detect_engine}).`
      : `Máy chủ: chạy hoàn toàn cục bộ.`
    o.hidden = false
  } catch {
    /* bỏ qua nếu không đọc được */
  }
}

document.querySelectorAll('#nhom-nut-nn .nut-nn').forEach((btn) => {
  btn.addEventListener('click', async () => {
    const nn = btn.dataset.nn
    if ($('ngon-ngu')) $('ngon-ngu').value = nn
    dongBoNutNgonNgu(nn)
    await luuCauHinh({ ngonNgu: nn, cheDo: 'chi_chu' })
  })
})

document.querySelectorAll('#nhom-nut-dich .nut-dich-ra').forEach((btn) => {
  btn.addEventListener('click', async () => {
    const dich = btn.dataset.dich
    if ($('ngon-ngu-dich')) $('ngon-ngu-dich').value = dich
    dongBoNutDichRa(dich)
    await luuCauHinh({ ngonNguDich: dich, cheDo: 'chi_chu' })
  })
})

document.querySelectorAll('#nhom-nut-eng .nut-eng').forEach((btn) => {
  btn.addEventListener('click', async () => {
    const eng = btn.dataset.eng
    if ($('engine')) $('engine').value = eng
    dongBoNutEngine(eng)
    await luuCauHinh({ engine: eng, cheDo: 'chi_chu' })
    veHanMuc()
    veMayChu()
  })
})

document.querySelectorAll('#nhom-nut-font .nut-font').forEach((btn) => {
  btn.addEventListener('click', async () => {
    const font = btn.dataset.font
    if ($('font-chu')) $('font-chu').value = font
    dongBoNutFont(font)
    await luuCauHinh({ fontChu: font, cheDo: 'chi_chu' })
  })
})

$('ngon-ngu')?.addEventListener('change', async (e) => {
  dongBoNutNgonNgu(e.target.value)
  await luuCauHinh({ ngonNgu: e.target.value, cheDo: 'chi_chu' })
})

$('ngon-ngu-dich')?.addEventListener('change', async (e) => {
  dongBoNutDichRa(e.target.value)
  await luuCauHinh({ ngonNguDich: e.target.value, cheDo: 'chi_chu' })
})

$('engine')?.addEventListener('change', async (e) => {
  dongBoNutEngine(e.target.value)
  await luuCauHinh({ engine: e.target.value, cheDo: 'chi_chu' })
  veHanMuc()
  veMayChu()
})

$('font-chu')?.addEventListener('change', async (e) => {
  dongBoNutFont(e.target.value)
  await luuCauHinh({ fontChu: e.target.value, cheDo: 'chi_chu' })
})

$('mo-cai-dat')?.addEventListener('click', (e) => {
  e.preventDefault()
  chrome.runtime.openOptionsPage()
  window.close()
})

document.querySelectorAll('a[href^="https://comic.io.vn"]').forEach((a) => {
  a.addEventListener('click', (e) => {
    e.preventDefault()
    moTrangWebThongMinh()
  })
})

async function tiem(cheDoChay = 'don') {
  await luuCauHinh({ cheDo: 'chi_chu' })
  await chrome.storage.local.remove(['__e59_bulk', '__e60_snip', '__e102_auto_scroll'])
  if (cheDoChay === 'bulk') await chrome.storage.local.set({ __e59_bulk: true })
  if (cheDoChay === 'snip') await chrome.storage.local.set({ __e60_snip: true })
  if (cheDoChay === 'auto_scroll') await chrome.storage.local.set({ __e102_auto_scroll: true })

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true })
  await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ['src/content/index.js'] })
}

$('nut-dich-chapter')?.addEventListener('click', async () => {
  const nut = $('nut-dich-chapter')
  nut.disabled = true
  try {
    await tiem('bulk')
    window.close()
  } catch (err) {
    nut.disabled = false
    await chrome.storage.local.remove('__e59_bulk')
    bao(`Không chạy được trên trang này.\n${err?.message || err}`, 'loi')
  }
})

$('nut-tu-dich-cuon')?.addEventListener('click', async () => {
  const nut = $('nut-tu-dich-cuon')
  nut.disabled = true
  try {
    await tiem('auto_scroll')
    window.close()
  } catch (err) {
    nut.disabled = false
    await chrome.storage.local.remove('__e102_auto_scroll')
    bao(`Không chạy được trên trang này.\n${err?.message || err}`, 'loi')
  }
})

$('nut-khoanh-vung')?.addEventListener('click', async () => {
  const nut = $('nut-khoanh-vung')
  nut.disabled = true
  try {
    await tiem('snip')
    window.close()
  } catch (err) {
    nut.disabled = false
    await chrome.storage.local.remove('__e60_snip')
    bao(`Không chạy được trên trang này.\n${err?.message || err}`, 'loi')
  }
})

$('nut-dich')?.addEventListener('click', async () => {
  const nut = $('nut-dich')
  nut.disabled = true
  try {
    await tiem('don')
    window.close()
  } catch (err) {
    nut.disabled = false
    bao(`Không chạy được trên trang này.\n${err?.message || err}`, 'loi')
  }
})

ve()
