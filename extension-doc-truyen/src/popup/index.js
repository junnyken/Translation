/** Popup khi bấm icon (E19-4 + E104 — Giao diện hiện đại, cố định chế độ Xoá chữ & căn chữ LaMa). */
import { docCauHinh, kiemTraByok, layHanMuc, luuCauHinh, moTrangWebThongMinh } from '../lib/api.js'

const $ = (id) => document.getElementById(id)
let _capDoHienTai = 0
let _choPhepByok = false

function dangCoByokHopLe(byokBat, byokKey, choPhep = _choPhepByok) {
  return Boolean(choPhep && byokBat && String(byokKey || '').trim().length >= 12)
}
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

const NHAN_NGON_NGU_DICH = {
  vi: 'Sang Tiếng Việt',
  en: 'Sang Tiếng Anh',
  zh: 'Sang Trung Giản thể (简体)',
  'zh-TW': 'Sang Trung Phồn thể (繁體)',
  id: 'Sang Tiếng Indonesia',
  es: 'Sang Tiếng Tây Ban Nha',
  pt: 'Sang Tiếng Bồ Đào Nha',
  th: 'Sang Tiếng Thái (ไทย)',
  fr: 'Sang Tiếng Pháp',
}

function dongBoNutDichRa(dich) {
  document.querySelectorAll('#nhom-nut-dich .nut-dich-ra').forEach((btn) => {
    btn.classList.toggle('dang-chon', btn.dataset.dich === dich)
  })
}

function dongBoNutEngine(eng, coByok = false) {
  document.querySelectorAll('#nhom-nut-eng .nut-eng').forEach((btn) => {
    btn.classList.toggle('dang-chon', btn.dataset.eng === eng)
  })
  const nhanPhu = $('nhan-phu-eng')
  if (nhanPhu) {
    if (eng === 'local_hybrid_pro') {
      nhanPhu.textContent = coByok
        ? '🔑 1 lượt/trang (-50% BYOK) · OCR + Dịch AI'
        : '🧠 2 lượt/trang · Tách chữ OCR + Dịch AI'
    } else if (eng === 'llm_context') {
      nhanPhu.textContent = coByok
        ? '🔑 1,5 lượt/trang (-50% BYOK) · SoM Vision + LaMa'
        : '✨ 3 lượt/trang · SoM Vision + LaMa Đám Mây'
    } else {
      nhanPhu.textContent = '⚡ 1 lượt/trang · Nhanh & Tiết kiệm'
    }
  }
}

function capNhatKhoaModelTheoCapDo(capDo = 0, coByok = false) {
  const sel = $('engine')
  if (!sel) return
  const cap = Number(capDo || 0)
  Array.from(sel.options).forEach((opt) => {
    const goi = Number(opt.dataset?.goi || 0)
    const tenGoc = opt.dataset?.tenGoc || ''
    if (!goi || !tenGoc) return
    if (coByok && cap >= 1) {
      if (opt.value === 'local_hybrid_pro') {
        opt.textContent = '🧠 OCR + GPU Pro · 1 lượt/trang (🔑 BYOK -50%)'
      } else if (opt.value === 'llm_context') {
        opt.textContent = '✨ SoM Vision + LaMa · 1,5 lượt/trang (🔑 BYOK -50%)'
      }
      return
    }
    const capYeuCau = goi === 2 ? 3 : 1
    if (cap >= capYeuCau) {
      opt.textContent = tenGoc
    } else {
      opt.textContent = `${tenGoc} (mở khóa: gói ${goi})`
    }
  })
}

function dongBoKhungByok(byokBat, byokProvider, byokKey) {
  const khoi = $('khoi-byok')
  const than = $('than-byok')
  const chk = $('byok-bat')
  const selProv = $('byok-provider')
  const inpKey = $('byok-key')
  const nhan = $('nhan-trang-thai-byok')
  if (selProv && byokProvider) selProv.value = byokProvider
  if (inpKey && typeof byokKey === 'string' && document.activeElement !== inpKey) {
    inpKey.value = byokKey
  }
  const duocMo = _choPhepByok || _capDoHienTai >= 1
  if (chk) chk.checked = Boolean(byokBat)
  if (than) than.hidden = !byokBat
  const kichHoat = dangCoByokHopLe(byokBat, byokKey, duocMo)
  if (khoi) khoi.classList.toggle('dang-bat', kichHoat)
  if (nhan) {
    if (!duocMo) {
      nhan.textContent = '🔒 Mở từ Gói 1'
    } else if (kichHoat) {
      nhan.textContent = '✅ Đang giảm 50%'
    } else {
      nhan.textContent = 'Giảm 50% lượt'
    }
  }
}

function dongBoNutFont(font) {
  document.querySelectorAll('#nhom-nut-font .nut-font').forEach((btn) => {
    btn.classList.toggle('dang-chon', btn.dataset.font === font)
  })
}

async function ve() {
  const { ngonNgu, ngonNguDich, engine, fontChu, byokBat, byokProvider, byokKey } = await docCauHinh()
  await luuCauHinh({ cheDo: 'chi_chu' })
  if ($('ngon-ngu')) $('ngon-ngu').value = ngonNgu
  if ($('ngon-ngu-dich')) $('ngon-ngu-dich').value = ngonNguDich || 'vi'
  if ($('engine')) $('engine').value = engine
  if ($('font-chu')) $('font-chu').value = fontChu || 'bangers'
  if ($('che-do')) $('che-do').value = 'chi_chu'
  dongBoNutNgonNgu(ngonNgu)
  dongBoNutDichRa(ngonNguDich || 'vi')
  dongBoKhungByok(byokBat, byokProvider, byokKey)
  dongBoNutEngine(engine, dangCoByokHopLe(byokBat, byokKey))
  dongBoNutFont(fontChu || 'bangers')
  await veHanMuc()
  veMayChu()
}

async function veHanMuc() {
  const o = $('han-muc')
  if (!o) return
  try {
    const { diaChi, engine, byokBat, byokProvider, byokKey } = await docCauHinh()
    if (engine === 'local_gguf') {
      o.textContent = '💻 Chế độ Lõi AI Cục bộ (Xử lý trên phần cứng máy bạn)'
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
    _capDoHienTai = hm.la_quan_tri ? 5 : Number(hm.cap_do || 0)
    _choPhepByok = Boolean(hm.cho_phep_byok ?? (_capDoHienTai >= 1))
    const coByok = dangCoByokHopLe(byokBat, byokKey, _choPhepByok)
    dongBoKhungByok(byokBat, byokProvider, byokKey)
    capNhatKhoaModelTheoCapDo(_capDoHienTai, coByok)
    dongBoNutEngine(engine, coByok)
    const muaThem = Number(hm.so_luot_mua_them || 0)
    const conLaiNgay = Math.max(0, Number(hm.con_lai || 0) - muaThem)
    const vaiTro = hm.co_tai_khoan ? '✅ Đã đăng nhập' : '👤 Khách (đăng ký nhận 20 Credits miễn phí)'
    const tichLuy = muaThem > 0 ? ` + Ví VIP: ${muaThem} lượt (Tổng ${hm.con_lai})` : ''
    const soLuotMoiTrang = coByok
      ? (engine === 'llm_context' ? 1.5 : 1)
      : (engine === 'llm_context'
          ? 3
          : (['local_hybrid_pro', 'gpt_6_sol', 'gemini_3_1_pro'].includes(engine) ? 2 : 1))
    const nhanChiPhi = coByok
      ? (engine === 'llm_context' ? ' · [🔑 BYOK: 1,5 lượt/trang]' : ' · [🔑 BYOK: 1 lượt/trang]')
      : (engine === 'llm_context'
          ? ' · [SoM Vision + LaMa: 3 lượt/trang]'
          : (soLuotMoiTrang === 2 ? ' · [GPU Pro: 2 lượt/trang]' : ' · [1 lượt/trang]'))
    o.textContent = `${vaiTro} · Hôm nay: ${conLaiNgay}/${hm.tran} lượt${tichLuy}${nhanChiPhi}`
    o.className = hm.con_lai < soLuotMoiTrang
      ? 'hop loi'
      : (hm.con_lai < hm.tran && hm.con_lai <= soLuotMoiTrang * 2) ? 'hop canh-bao' : 'hop ok'
    o.hidden = false
    if (hm.con_lai < soLuotMoiTrang) {
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
      o.textContent = 'Chạy trực tiếp trên phần cứng máy tính của bạn.'
      o.hidden = false
      return
    }
    if (engine === 'local_ocr_gpu') {
      o.textContent = '⚡ Model 1 (1 lượt/trang): Tốc độ siêu tốc, tiết kiệm lượt tối đa, tối ưu cho 85% truyện chữ in rõ.'
      o.hidden = false
      return
    }
    if (engine === 'local_hybrid_pro') {
      const { byokBat, byokKey } = await docCauHinh()
      const coByok = dangCoByokHopLe(byokBat, byokKey)
      o.textContent = coByok
        ? '🔑 Model 2 BYOK (1 lượt/trang): Tách chữ OCR cục bộ + Gọi thẳng API Key của bạn (-50% lượt).'
        : '🧠 Model 2 (2 lượt/trang): Quét 2 tầng chữ viết tay + Bảo vệ nét vẽ nhân vật khỏi SFX + Tự học 60 từ điển.'
      o.hidden = false
      return
    }
    if (engine === 'llm_context') {
      const { byokBat, byokKey } = await docCauHinh()
      const coByok = dangCoByokHopLe(byokBat, byokKey)
      o.textContent = coByok
        ? '🔑 Model 3 BYOK (1,5 lượt/trang): Khóa tọa độ Set-of-Mark [#1..#N] + LaMa xóa nét tranh + Vision Key riêng (-50% lượt).'
        : '✨ Model 3 SoM Vision + LaMa (3 lượt/trang): Khóa tọa độ 0px + AI nhìn biểu cảm tranh & tái tạo nét vẽ LaMa.'
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

$('byok-bat')?.addEventListener('change', async (e) => {
  const bat = Boolean(e.target.checked)
  if (bat && !_choPhepByok && _capDoHienTai < 1) {
    e.target.checked = false
    bao('🔒 Tính năng cắm API Key riêng (BYOK — giảm 50% lượt: Model 2 còn 1 lượt, Model 3 còn 1,5 lượt) mở khóa từ Gói 1 trở lên.', 'canh-bao')
    return
  }
  const prov = $('byok-provider')?.value || 'gemini'
  const key = ($('byok-key')?.value || '').trim()
  await luuCauHinh({ byokBat: bat, byokProvider: prov, byokKey: key })
  dongBoKhungByok(bat, prov, key)
  await veHanMuc()
  veMayChu()
})

$('byok-provider')?.addEventListener('change', async (e) => {
  const prov = e.target.value
  const bat = Boolean($('byok-bat')?.checked)
  const key = ($('byok-key')?.value || '').trim()
  await luuCauHinh({ byokProvider: prov })
  dongBoKhungByok(bat, prov, key)
})

$('byok-key')?.addEventListener('input', async (e) => {
  const key = e.target.value.trim()
  const bat = Boolean($('byok-bat')?.checked)
  const prov = $('byok-provider')?.value || 'gemini'
  await luuCauHinh({ byokKey: key })
  dongBoKhungByok(bat, prov, key)
  await veHanMuc()
  veMayChu()
})

$('nut-thu-byok')?.addEventListener('click', async () => {
  const nut = $('nut-thu-byok')
  const kqEl = $('byok-ket-qua')
  const prov = $('byok-provider')?.value || 'gemini'
  const key = ($('byok-key')?.value || '').trim()
  if (key.length < 12) {
    if (kqEl) kqEl.textContent = '⚠️ Vui lòng dán API Key hợp lệ (AIza..., sk-..., sk-ant-...).'
    return
  }
  await luuCauHinh({ byokBat: true, byokProvider: prov, byokKey: key })
  if (nut) nut.disabled = true
  if (kqEl) kqEl.textContent = '⏳ Đang kiểm tra kết nối trực tiếp tới hãng AI...'
  try {
    const res = await kiemTraByok(prov, key, '')
    if (kqEl) {
      kqEl.textContent = `✅ ${res.thong_diep || 'Kết nối Key thành công!'} (Model 2 = 1 lượt · Model 3 = 1,5 lượt)`
    }
    await veHanMuc()
    veMayChu()
  } catch (err) {
    if (kqEl) kqEl.textContent = `❌ ${err?.message || err}`
  } finally {
    if (nut) nut.disabled = false
  }
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
