/** Chọn đâu là TRANG TRUYỆN trong một mớ ảnh trên web (E19-4).
 *
 * Người dùng chọn "bất kỳ trang nào", nghĩa là không có bảng luật riêng cho từng trang web.
 * Nên phải đoán — và đoán sai là chuyện sẽ xảy ra, không phải chuyện có thể xảy ra.
 *
 * Hàm này THUẦN: nhận danh sách mô tả ảnh, trả về lựa chọn kèm **lý do**. Không đụng DOM, nên
 * test được mà không cần trình duyệt, và khi nó chọn nhầm thì mở ra xem lý do chứ không phải
 * ngồi đoán.
 */

/** Ảnh nhỏ hơn mức này gần như chắc chắn là icon, nút, avatar — không phải trang truyện. */
export const CANH_TOI_THIEU = 400
/** Diện tích tối thiểu (pixel thật, không phải pixel hiển thị). */
export const DIEN_TICH_TOI_THIEU = 400 * 600
/**
 * Trang truyện cao hơn rộng, hoặc gần vuông với trang đôi. Banner quảng cáo thì rất ngang.
 * Ngưỡng 0,45 nhận được cả trang đôi (~1,4 rộng/cao) lẫn trang dọc thường.
 */
export const TI_LE_TOI_THIEU = 0.45

/**
 * @param {Array<{src:string,naturalWidth:number,naturalHeight:number,
 *                clientWidth:number,clientHeight:number,top:number,bottom:number}>} anh
 * @param {{caoKhungNhin:number}} ngu_canh
 */
export function chonTrangTruyen(anh, { caoKhungNhin }) {
  const bi_loai = []
  const ung_vien = []

  for (const a of anh) {
    const w = a.naturalWidth || 0
    const h = a.naturalHeight || 0
    const ly_do = []

    if (w < CANH_TOI_THIEU && h < CANH_TOI_THIEU) ly_do.push('quá nhỏ')
    if (w * h < DIEN_TICH_TOI_THIEU) ly_do.push('diện tích quá nhỏ')
    // Tỉ lệ tính bằng CẠNH NGẮN / CẠNH DÀI nên nó không phụ thuộc ảnh dọc hay ngang.
    if (Math.min(w, h) / Math.max(w, h, 1) < TI_LE_TOI_THIEU) ly_do.push('quá dẹt — nhiều khả năng là banner')
    // Ảnh bị CSS thu nhỏ hẳn so với kích thước thật thường là thumbnail trong danh sách.
    if (a.clientWidth && w / a.clientWidth > 3) ly_do.push('bị thu nhỏ nhiều — nhiều khả năng là ảnh thu nhỏ')
    // Hoàn toàn nằm ngoài khung nhìn ⇒ không phải trang người dùng đang đọc.
    if (a.bottom <= 0 || a.top >= caoKhungNhin) ly_do.push('ngoài khung nhìn')

    if (ly_do.length) bi_loai.push({ src: a.src, ly_do })
    else ung_vien.push(a)
  }

  if (!ung_vien.length) {
    return { anh: null, ly_do: 'không có ảnh nào trông giống trang truyện', bi_loai }
  }

  // Trong số ứng viên, lấy ảnh CHIẾM NHIỀU KHUNG NHÌN NHẤT — không phải ảnh to nhất theo pixel
  // thật. Một ảnh 4000px nằm khuất dưới chân trang không phải thứ người dùng đang đọc.
  const diem = (a) => {
    const hien = Math.max(0, Math.min(a.bottom, caoKhungNhin) - Math.max(a.top, 0))
    return hien * (a.clientWidth || 1)
  }
  const tot = ung_vien.reduce((a, b) => (diem(b) > diem(a) ? b : a))
  return {
    anh: tot,
    ly_do: ung_vien.length === 1
      ? 'chỉ có một ảnh đủ lớn'
      : `chiếm nhiều khung nhìn nhất trong ${ung_vien.length} ảnh đủ lớn`,
    bi_loai,
  }
}
