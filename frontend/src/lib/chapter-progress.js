/** Suy dòng thời gian pipeline của cả chapter từ trạng thái THẬT của từng trang (E11).
 *
 * Tách khỏi component để test được mà không cần dựng DOM — và để chỉ có MỘT chỗ quyết định
 * "bước này đã xong chưa", thay vì mỗi màn tự đoán.
 *
 * Không có phần trăm: backend không đo phần trăm cho một trang, nên ở đây cũng không bịa ra.
 * Cái đếm được là **số trang đã qua từng bước**, và đó là thứ được hiện.
 */

/** Thứ hạng của trạng thái trang trên đường pipeline. Trạng thái hỏng xử lý riêng. */
const HANG = {
  queued: 0,
  detecting: 1,
  detected: 2,
  ocr_done: 3,
  inpainted: 4,
  inpaint_needs_review: 4,
  translated: 5,
  typeset_done: 6,
  ready_for_export: 6,
}

/** Bước nào "đang chạy" khi trang ở trạng thái nào (trạng thái tạm duy nhất của M1 là `detecting`). */
const DANG_CHAY_TAI = { detecting: 'detect' }

export const BUOC = [
  { ma: 'tai_len', nhan: 'Đã tải lên', can_hang: 0 },
  { ma: 'detect', nhan: 'Nhận diện khung chữ', can_hang: 2 },
  { ma: 'ocr', nhan: 'Đọc chữ gốc', can_hang: 3 },
  { ma: 'inpaint', nhan: 'Xoá chữ gốc', can_hang: 4 },
  { ma: 'translate', nhan: 'Dịch sang tiếng Việt', can_hang: 5 },
  { ma: 'typeset', nhan: 'Căn chữ vào bong bóng', can_hang: 6 },
]

export function hangCuaTrang(trang_thai) {
  return HANG[trang_thai] ?? -1
}

/**
 * @param {{status: string}[]} trang danh sách trang của chapter
 * @param {{soTran?: number, soCanDocLai?: number}} canhBao số vùng còn lỗi (M10)
 */
export function tinhTienDoChapter(trang = [], canhBao = {}) {
  const tong = trang.length
  const buoc = BUOC.map((b) => {
    if (tong === 0) return { ...b, tinh_trang: 'chua', mo_ta: 'Chưa có trang nào.' }

    const xong = trang.filter((t) => hangCuaTrang(t.status) >= b.can_hang).length
    const hong = b.ma === 'detect'
      ? trang.filter((t) => t.status === 'detection_failed').length
      : 0
    const dang = trang.filter((t) => DANG_CHAY_TAI[t.status] === b.ma).length

    let tinh_trang = 'chua'
    if (xong === tong) tinh_trang = 'xong'
    else if (hong > 0 && xong + hong === tong) tinh_trang = 'hong'
    else if (dang > 0 || xong > 0 || hong > 0) tinh_trang = 'dang_chay'

    // Bước cuối: căn chữ xong nhưng còn vùng lỗi thì KHÔNG được gọi là xong xuôi.
    if (b.ma === 'typeset' && tinh_trang === 'xong'
        && ((canhBao.soTran ?? 0) > 0 || (canhBao.soCanDocLai ?? 0) > 0)) {
      tinh_trang = 'canh_bao'
    }

    const phan = [`${xong}/${tong} trang`]
    if (hong > 0) phan.push(`${hong} trang hỏng`)
    return { ...b, tinh_trang, mo_ta: phan.join(' · ') }
  })

  const san_sang = tong > 0 && trang.every((t) => hangCuaTrang(t.status) >= 6)
  return {
    tong,
    buoc,
    san_sang_ra_soat: san_sang,
    dang_chay: tong > 0 && !san_sang && trang.some((t) => t.status !== 'detection_failed'),
    so_hong: trang.filter((t) => t.status === 'detection_failed').length,
    so_xong: trang.filter((t) => hangCuaTrang(t.status) >= 6).length,
  }
}
