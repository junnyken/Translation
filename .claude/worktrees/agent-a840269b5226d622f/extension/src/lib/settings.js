/** Lớp bọc `chrome.storage.local`. Mọi lượt đọc đều đi qua khuôn, mọi lượt ghi đều qua chốt chặn.
 *
 * Service worker của MV3 bị Chrome tắt sau một lúc không việc, nên **không** có trạng thái nào
 * quan trọng được sống trong biến toàn cục. Chỗ nhớ duy nhất là kho này.
 */

import {
  KHOA_CAI_DAT, KHOA_GHIM, SO_GHIM_TOI_DA,
  caiDatMacDinh, chotChanGhi, docCaiDat, docGhim, donDeGhi,
} from './storage-schema.js'

/** Cho phép test tiêm kho giả; lúc chạy thật thì là `chrome.storage.local`. */
export function khoMacDinh() {
  return globalThis.chrome?.storage?.local ?? null
}

async function doc(kho, khoa) {
  const ra = await kho.get(khoa)
  return ra?.[khoa]
}

export async function layCaiDat(kho = khoMacDinh()) {
  if (!kho) return caiDatMacDinh()
  let tho
  try {
    tho = await doc(kho, KHOA_CAI_DAT)
  } catch {
    return caiDatMacDinh()
  }
  const { caiDat, phaiDon } = docCaiDat(tho)
  if (phaiDon) {
    // Dọn ngay: để dữ liệu hỏng nằm lại thì lần mở sau lại phải lọc lần nữa.
    try { await ghiCaiDat(caiDat, kho) } catch { /* ghi hỏng thì vẫn dùng bản đã lọc */ }
  }
  return caiDat
}

export async function ghiCaiDat(cai_dat, kho = khoMacDinh()) {
  const sach = donDeGhi(cai_dat)
  chotChanGhi(KHOA_CAI_DAT, sach)
  if (!kho) return sach
  await kho.set({ [KHOA_CAI_DAT]: sach })
  return sach
}

export async function layGhim(kho = khoMacDinh(), bay_gio = Date.now()) {
  if (!kho) return []
  let tho
  try {
    tho = await doc(kho, KHOA_GHIM)
  } catch {
    return []
  }
  const { ghim, phaiDon } = docGhim(tho, bay_gio)
  if (phaiDon) {
    try { await ghiGhim(ghim, kho) } catch { /* ghi hỏng thì vẫn dùng bản đã lọc */ }
  }
  return ghim
}

export async function ghiGhim(ds, kho = khoMacDinh()) {
  const cat = ds.slice(0, SO_GHIM_TOI_DA)
  chotChanGhi(KHOA_GHIM, cat)
  if (!kho) return cat
  await kho.set({ [KHOA_GHIM]: cat })
  return cat
}

/** Ghim thêm/cập nhật một chapter, đẩy lên đầu danh sách. */
export async function ghimChapter(muc, kho = khoMacDinh(), bay_gio = Date.now()) {
  const cu = await layGhim(kho, bay_gio)
  const moi = [{ ...muc, cachedAt: new Date(bay_gio).toISOString() },
    ...cu.filter((c) => c.projectId !== muc.projectId)]
  return ghiGhim(moi, kho)
}

export async function boGhim(project_id, kho = khoMacDinh(), bay_gio = Date.now()) {
  const cu = await layGhim(kho, bay_gio)
  return ghiGhim(cu.filter((c) => c.projectId !== project_id), kho)
}

/** Xoá sạch dữ liệu tiện ích. KHÔNG đụng tới chapter/ảnh trong backend. */
export async function xoaHet(kho = khoMacDinh()) {
  if (!kho) return
  await kho.remove([KHOA_CAI_DAT, KHOA_GHIM])
}
