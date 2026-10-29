import { useEffect, useState } from 'react'
import * as api from '../api.js'
import { hangCuaTrang } from './chapter-progress.js'

/** Hạng của `ready_for_export` — trang đi tới đây là xong cả chuỗi. Lấy từ `chapter-progress`
 *  thay vì gõ lại con số: thêm một bước vào pipeline mà quên sửa chỗ này sẽ làm màn Dịch nhanh
 *  báo "xong" sớm hơn sự thật. */
const HANG_XONG = hangCuaTrang('ready_for_export')

/** P1 — đếm số vùng chữ đáng xem lại từ cảnh báo xuất ĐÃ CÓ của backend.
 *
 * Dùng lại đúng `/projects/{id}/export-warnings` (E12/E14/F1) thay vì dựng phép đếm mới: dựng
 * mới sẽ tạo **nguồn sự thật thứ hai** cho cùng một khái niệm, và hai nguồn sẽ lệch nhau.
 *
 * Đếm theo **VÙNG CHỮ**, không theo trang — đó là thứ backend thật sự đo được. Viết "N trang"
 * sẽ là một con số không ai kiểm chứng được.
 *
 * Bốn loại gộp lại vì với người đi đường nhanh chúng dẫn tới cùng một hành động (mở màn rà
 * soát); chi tiết từng loại đã có sẵn ở đường đầy đủ.
 */
export function demVungDangNgo(canhBao) {
  if (!canhBao) return 0
  return (canhBao.needs_manual_count ?? 0)
    + (canhBao.quality_needs_review_count ?? 0)
    + (canhBao.overflow_warning_count ?? 0)
    + (canhBao.font_missing_count ?? 0)
}

/** Đếm trang đã xong / hỏng trong một danh sách trang.
 *
 * `hong` tính riêng chứ không gộp vào `xong`: gộp vào sẽ làm thanh tiến độ chạy tới 100% rồi
 * người dùng nhận một file thiếu trang mà không hiểu vì sao.
 */
export function demTienDo(trang = []) {
  const xong = trang.filter((t) => hangCuaTrang(t.status) >= HANG_XONG).length
  const hong = trang.filter((t) => t.status === 'detection_failed').length
  return { xong, hong, tong: trang.length, chayXong: trang.length > 0 && xong + hong === trang.length }
}

/** Hỏi lại chapter tới khi mọi trang đã xong hoặc hỏng.
 *
 * Nhịp 3 giây: một trang mất trung vị ~107 giây (E23), hỏi mỗi giây chỉ tạo tải vô ích.
 * Có trần số lần hỏi để một chapter kẹt không làm tab quay vòng mãi mãi.
 */
export async function choChapterXong(
  projectId, onTien, { soLanToiDa = 2400, nhipMs = 3000, nenDung } = {},
) {
  let cuoi = { xong: 0, hong: 0, tong: 0, chayXong: false }
  for (let i = 0; i < soLanToiDa; i++) {
    if (nenDung?.()) return cuoi   // người dùng rời màn — dừng hẳn, đừng hỏi thêm lượt nào
    const ct = await api.layProject(projectId)
    cuoi = demTienDo(ct.pages || [])
    onTien?.(cuoi)
    if (cuoi.chayXong) return cuoi
    await new Promise((r) => setTimeout(r, nhipMs))
  }
  // Hết trần mà chưa xong: trả về số đo THẬT tại thời điểm bỏ cuộc, không báo là đã xong.
  return cuoi
}

// ---------------------------------------------------------------------------------------------
// Tự xuất + tải về SAU KHI form đã chuyển sang màn chapter.
//
// Form gộp mở màn chapter ngay khi tải lên xong, nên component form bị tháo. Việc "chờ dịch xong
// rồi xuất + tải về" vì vậy KHÔNG được nằm trong component form (tháo là dừng), mà nằm ở đây:
// một tác vụ cấp module, có trạng thái đọc được bằng `useTuTaiVe(projectId)` ở màn chapter.
// Đóng tab / tải lại trang thì tác vụ mất — chapter vẫn chạy ở máy chủ, tự xuất tay được.
// ---------------------------------------------------------------------------------------------

const tacVu = new Map()      // projectId -> { giaiDoan, tien, ketQua, loi }
const nguoiNghe = new Set()
const phat = () => nguoiNghe.forEach((f) => f())
const dat = (id, v) => { tacVu.set(id, { ...tacVu.get(id), ...v }); phat() }

/** Bắt đầu chờ + xuất + tải về cho một chapter. Gọi lại với cùng id khi đang chạy thì bỏ qua. */
export async function chayTuTaiVe(projectId, { boQua = 0, nhipMs = 3000, soLanToiDa = 2400 } = {}) {
  const cu = tacVu.get(projectId)
  if (cu && (cu.giaiDoan === 'cho' || cu.giaiDoan === 'xuat')) return
  tacVu.set(projectId, { giaiDoan: 'cho', tien: { xong: 0, hong: 0, tong: 0 }, ketQua: null, loi: null })
  phat()
  try {
    const dem = await choChapterXong(
      projectId, (t) => dat(projectId, { tien: t }), { nhipMs, soLanToiDa },
    )
    let taiVe = null
    if (dem.xong > 0) {
      dat(projectId, { giaiDoan: 'xuat' })
      // ZIP chứ không CBZ: E40 đo được người dùng tải `.cbz` về KHÔNG mở được trên Windows.
      const job = await api.xuatChapter(projectId, 'zip')
      await api.choXuatXong(job.job_id)
      taiVe = await api.taiFileXuatVe(job.job_id, 'zip')
    }
    // P1 — hỏi cảnh báo SAU KHI file đã về máy (hiện thông tin, KHÔNG chặn tải). Hỏng thì bỏ qua:
    // người dùng đã có file, không nuốt cả kết quả vì một lời gọi phụ.
    let canhBao = null
    try { canhBao = await api.layCanhBaoXuat(projectId) } catch { canhBao = null }
    dat(projectId, {
      giaiDoan: 'xong',
      ketQua: { ...dem, boQua, taiVe, soVungDangNgo: demVungDangNgo(canhBao) },
    })
  } catch (e) {
    dat(projectId, { giaiDoan: 'loi', loi: e.message })
  }
}

export function boTuTaiVe(projectId) { tacVu.delete(projectId); phat() }

/** Chỉ dùng cho test. */
export function datLaiTuTaiVe() { tacVu.clear(); phat() }

export function useTuTaiVe(projectId) {
  const [, buoc] = useState(0)
  useEffect(() => {
    const f = () => buoc((n) => n + 1)
    nguoiNghe.add(f)
    return () => { nguoiNghe.delete(f) }
  }, [])
  return projectId ? tacVu.get(projectId) ?? null : null
}
