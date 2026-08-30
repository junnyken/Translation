/** Dựng địa chỉ mở web app — và mở nó.
 *
 * Giao diện Translation KHÔNG có router: `frontend/src/App.jsx` chọn màn bằng hash
 * (`#project=`, `#page=`). Bảng dưới là đường THẬT đo được ngày 2026-08-30, không phải đường
 * đặt ra cho đẹp. Xem `extension/README.md` §1.2.
 *
 * Địa chỉ chỉ được ghép từ: (địa chỉ gốc đã qua `kiemDiaChiLocal`) + (mã đã qua `chuanHoaMa`).
 * Không có chỗ nào nhận chuỗi tự do của người dùng nối vào query/hash.
 */

import { chuanHoaMa, kiemDiaChiLocal } from './local-url-validator.js'

function goc(dia_chi) {
  const kq = kiemDiaChiLocal(dia_chi)
  if (!kq.ok) throw new Error(`Địa chỉ Translation không hợp lệ: ${kq.ly_do}`)
  return kq.dia_chi
}

function maHopLe(gia_tri, ten) {
  const ma = chuanHoaMa(gia_tri)
  if (!ma) throw new Error(`Mã ${ten} không hợp lệ.`)
  return ma
}

/** Màn tạo chapter = trang chủ (form tạo + danh sách gần đây nằm ngay đó). */
export function duongDanTaoChapter(dia_chi) {
  return `${goc(dia_chi)}/`
}

/** Trang chủ web app. */
export function duongDanTrangChu(dia_chi) {
  return `${goc(dia_chi)}/`
}

/** Màn chapter: tiến độ các trang + khối xuất + rà soát nhất quán. */
export function duongDanChapter(dia_chi, project_id) {
  return `${goc(dia_chi)}/#project=${maHopLe(project_id, 'chapter')}`
}

/** Màn rà soát tay từng trang (M7). */
export function duongDanRaSoat(dia_chi, page_id) {
  return `${goc(dia_chi)}/#page=${maHopLe(page_id, 'trang')}`
}

/** Xuất (M8) KHÔNG có route riêng — khối xuất nằm trong màn chapter.
 *  Trả đúng màn chapter thay vì bịa ra `#export=`. */
export function duongDanXuat(dia_chi, project_id) {
  return duongDanChapter(dia_chi, project_id)
}

/** Hướng dẫn khởi động nằm trong repo, mở ngay trong gói tiện ích — không gọi ra internet. */
export function duongDanHuongDan() {
  return globalThis.chrome?.runtime?.getURL?.('src/sidepanel/huong-dan.html') ?? ''
}

/** Mở một tab mới. `chrome.tabs.create` KHÔNG cần quyền `tabs` (quyền đó chỉ để đọc url/title). */
export async function moTab(dia_chi_day_du) {
  const tabs = globalThis.chrome?.tabs
  if (!tabs?.create) throw new Error('Không mở được tab trong môi trường này.')
  await tabs.create({ url: dia_chi_day_du })
}
