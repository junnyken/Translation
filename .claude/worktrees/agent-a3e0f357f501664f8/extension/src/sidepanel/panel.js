/** Bộ điều khiển Side Panel: nạp kho → hỏi máy chủ → vẽ lại.
 *
 * Không có `setInterval` nào ở đây. Panel hỏi máy chủ đúng hai lúc: khi vừa mở, và khi người
 * dùng bấm làm mới. Spec E1 §B4 — "no hidden background polling".
 */

import { chuanHoaMa, kiemDiaChiLocal } from '../lib/local-url-validator.js'
import {
  boGhim, ghiCaiDat, ghiGhim, ghimChapter, layCaiDat, layGhim, xoaHet,
} from '../lib/settings.js'
import {
  duongDanChapter, duongDanHuongDan, duongDanRaSoat, duongDanTaoChapter,
  duongDanTrangChu, duongDanXuat, moTab,
} from '../lib/navigation.js'
import { kiemKetNoi, layChapter } from '../lib/translation-client.js'
import { manChinh, manDau } from './panel-view.js'

const than = document.getElementById('than')
const loa = document.getElementById('loa')

/** Trạng thái CỦA MÀN HÌNH, không phải nguồn sự thật. Nguồn sự thật là kho + máy chủ. */
const tt = {
  caiDat: null,
  ghim: [],
  duLieu: {},      // projectId -> chapter vừa lấy được từ máy chủ
  noiDuoc: null,   // null = chưa kiểm xong; true/false = đã có câu trả lời từ máy chủ
  dangBan: false,
  dangLamMoi: false,
  loiDiaChi: '',
  loiGhim: '',
  hoiXoa: false,
}

function noi(chu) {
  if (loa) loa.textContent = chu
}

function ve() {
  than.replaceChildren()
  if (!tt.caiDat?.translationBaseUrl) {
    than.append(manDau({
      dia_chi: tt.caiDat?.translationBaseUrl ?? '',
      ly_do: tt.loiDiaChi,
      dang_ban: tt.dangBan,
      khi_luu: luuDiaChi,
      khi_mo_huong_dan: moHuongDan,
    }))
    return
  }
  than.append(manChinh({
    dia_chi: tt.caiDat.translationBaseUrl,
    noi_duoc: tt.noiDuoc,
    dang_lam_moi: tt.dangLamMoi,
    loi_ghim: tt.loiGhim,
    ghim: tt.ghim,
    du_lieu: tt.duLieu,
    da_kiem_luc: tt.caiDat.lastConnectionCheckAt,
    hoi_xoa: tt.hoiXoa,
    bay_gio: Date.now(),
  }, {
    khi_tao_chapter: () => mo(() => duongDanTaoChapter(tt.caiDat.translationBaseUrl)),
    khi_mo_trang_chu: () => mo(() => duongDanTrangChu(tt.caiDat.translationBaseUrl)),
    khi_mo_chapter: (id) => mo(() => duongDanChapter(tt.caiDat.translationBaseUrl, id), id),
    khi_mo_ra_soat: (id) => mo(() => duongDanRaSoat(tt.caiDat.translationBaseUrl, id), null, id),
    khi_xuat: (id) => mo(() => duongDanXuat(tt.caiDat.translationBaseUrl, id), id),
    khi_bo_ghim: boGhimRoiVe,
    khi_ghim: themGhim,
    khi_lam_moi: lamMoi,
    khi_mo_cai_dat: () => chrome.runtime.openOptionsPage(),
    khi_hoi_xoa: () => { tt.hoiXoa = true; ve() },
    khi_huy_xoa: () => { tt.hoiXoa = false; ve() },
    khi_xac_nhan_xoa: xoaDuLieu,
  }))
}

/** Mở tab + ghi lại "chỗ vừa mở" để lần sau panel biết người dùng đang làm dở ở đâu. */
async function mo(dung_dia_chi, project_id, page_id) {
  let dia_chi
  try {
    dia_chi = dung_dia_chi()
  } catch (e) {
    tt.loiGhim = e.message
    ve()
    return
  }
  try {
    await moTab(dia_chi)
    const cap_nhat = { ...tt.caiDat }
    if (project_id) cap_nhat.lastOpenedProjectId = project_id
    if (page_id) cap_nhat.lastOpenedPageId = page_id
    if (project_id || page_id) {
      tt.caiDat = await ghiCaiDat(cap_nhat)
    }
  } catch (e) {
    console.error('[Translation Companion] không mở được tab:', e)
  }
}

function moHuongDan() {
  const d = duongDanHuongDan()
  if (d) moTab(d).catch((e) => console.error(e))
}

async function luuDiaChi(gia_tri) {
  const kq = kiemDiaChiLocal(gia_tri)
  if (!kq.ok) {
    tt.loiDiaChi = kq.ly_do
    ve()
    noi(`Địa chỉ chưa hợp lệ. ${kq.ly_do}`)
    return
  }
  tt.loiDiaChi = ''
  tt.dangBan = true
  ve()
  tt.caiDat = await ghiCaiDat({ ...tt.caiDat, translationBaseUrl: kq.dia_chi })
  tt.dangBan = false
  await lamMoi()
}

/** Hỏi lại máy chủ: sống chưa, rồi từng chapter đã ghim. Đây là chỗ DUY NHẤT gọi mạng. */
async function lamMoi() {
  if (!tt.caiDat?.translationBaseUrl) return
  tt.dangLamMoi = true
  tt.noiDuoc = null
  ve()

  const suc_khoe = await kiemKetNoi(tt.caiDat.translationBaseUrl)
  tt.noiDuoc = suc_khoe.ok

  // Nối không được thì KHÔNG xoá bản chụp cũ — nhưng cũng không giả vờ nó là số mới.
  // Giao diện tự gắn nhãn "cập nhật lần cuối" cho những mục thiếu dữ liệu tươi.
  tt.duLieu = {}
  if (tt.noiDuoc) {
    const ds = await Promise.all(
      tt.ghim.map((g) => layChapter(tt.caiDat.translationBaseUrl, g.projectId)),
    )
    const ghim_moi = []
    ds.forEach((kq, i) => {
      const g = tt.ghim[i]
      if (kq.ok) {
        tt.duLieu[g.projectId] = kq.chapter
        ghim_moi.push({
          projectId: g.projectId,
          title: kq.chapter.title,
          status: kq.chapter.status,
          updatedAt: kq.chapter.updatedAt,
          cachedAt: new Date().toISOString(),
        })
      } else if (kq.ma === 'khong_thay') {
        // Chapter đã bị xoá khỏi máy chủ: bỏ ghim luôn thay vì hiện mãi một mục chết.
        return
      } else {
        ghim_moi.push(g)
      }
    })
    tt.ghim = await ghiGhim(ghim_moi)
  }

  try {
    tt.caiDat = await ghiCaiDat({
      ...tt.caiDat,
      lastConnectionCheckAt: new Date().toISOString(),
    })
  } catch (e) {
    console.error('[Translation Companion] không ghi được mốc kiểm tra:', e)
  }

  tt.dangLamMoi = false
  ve()
  noi(tt.noiDuoc
    ? `Đã kết nối. ${tt.ghim.length} chapter đã ghim.`
    : 'Chưa kết nối được Translation local.')
}

async function themGhim(gia_tri, xong) {
  const ma = chuanHoaMa(gia_tri)
  if (!ma) {
    tt.loiGhim = 'Mã chapter phải là chuỗi UUID lấy từ địa chỉ web app.'
    ve()
    return
  }
  if (tt.ghim.some((g) => g.projectId === ma)) {
    tt.loiGhim = 'Chapter này đã được ghim rồi.'
    ve()
    return
  }
  if (tt.ghim.length >= 5) {
    tt.loiGhim = 'Đã ghim đủ 5 chapter. Bỏ bớt một cái trước đã.'
    ve()
    return
  }
  tt.loiGhim = ''

  // Ghim trước, lấy dữ liệu sau: máy chủ không nối được thì mã vẫn được giữ để lần sau thử lại.
  const kq = await layChapter(tt.caiDat.translationBaseUrl, ma)
  const muc = kq.ok
    ? { projectId: ma, title: kq.chapter.title, status: kq.chapter.status,
      updatedAt: kq.chapter.updatedAt }
    : { projectId: ma }

  if (!kq.ok && kq.ma === 'khong_thay') {
    tt.loiGhim = 'Không tìm thấy chapter này trên máy chủ. Kiểm lại mã.'
    ve()
    return
  }

  tt.ghim = await ghimChapter(muc)
  if (kq.ok) tt.duLieu[ma] = kq.chapter
  xong?.()
  ve()
  noi(kq.ok ? `Đã ghim chapter ${kq.chapter.title}.` : 'Đã ghim mã chapter, chưa lấy được trạng thái.')
}

async function boGhimRoiVe(id) {
  tt.ghim = await boGhim(id)
  delete tt.duLieu[id]
  ve()
  noi('Đã bỏ ghim.')
}

async function xoaDuLieu() {
  await xoaHet()
  tt.hoiXoa = false
  tt.caiDat = await layCaiDat()
  tt.ghim = []
  tt.duLieu = {}
  tt.noiDuoc = null
  ve()
  noi('Đã xoá dữ liệu tiện ích.')
}

/** Mở panel = nạp lại từ kho rồi đối chiếu với máy chủ. Không tin bộ nhớ của lần trước. */
async function khoiDong() {
  tt.caiDat = await layCaiDat()
  tt.ghim = await layGhim()
  ve()
  if (tt.caiDat.translationBaseUrl) await lamMoi()
}

khoiDong().catch((e) => {
  console.error('[Translation Companion] lỗi khởi động panel:', e)
  than.replaceChildren()
  const p = document.createElement('p')
  p.className = 'khoi'
  p.setAttribute('data-sac', 'loi')
  p.textContent = 'Panel gặp lỗi khi khởi động. Thử đóng và mở lại.'
  than.append(p)
})
