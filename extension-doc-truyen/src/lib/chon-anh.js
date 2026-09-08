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
 * Lý do loại MỘT ảnh khỏi danh sách ứng viên — dùng chung cho `chonTrangTruyen` (đang đọc) lẫn
 * `chonTrangKeTiep` (xếp hàng trước): cả hai đều cần "có phải trang truyện thật không", chỉ khác
 * ở ràng buộc VỊ TRÍ (đang hiện vs sắp hiện). Tách riêng để hai nơi không lệch luật chất lượng.
 */
function loaiDoChatLuong(a) {
  const w = a.naturalWidth || 0
  const h = a.naturalHeight || 0
  const ly_do = []

  if (w < CANH_TOI_THIEU && h < CANH_TOI_THIEU) ly_do.push('quá nhỏ')
  if (w * h < DIEN_TICH_TOI_THIEU) ly_do.push('diện tích quá nhỏ')
  // Tỉ lệ tính bằng CẠNH NGẮN / CẠNH DÀI nên nó không phụ thuộc ảnh dọc hay ngang.
  if (Math.min(w, h) / Math.max(w, h, 1) < TI_LE_TOI_THIEU) ly_do.push('quá dẹt — nhiều khả năng là banner')
  // Ảnh bị CSS thu nhỏ hẳn so với kích thước thật thường là thumbnail trong danh sách.
  if (a.clientWidth && w / a.clientWidth > 3) ly_do.push('bị thu nhỏ nhiều — nhiều khả năng là ảnh thu nhỏ')
  // Lightbox hay dựng nền bằng CHÍNH ảnh đang xem, phóng to + làm mờ để lấp khung. Cùng `src`
  // nên không phân biệt được bằng kích thước thật — chỉ CSS filter mới lộ ra nó không phải nội
  // dung mà là trang trí. Đo được trên trang thật 07/09: bản nền mờ 2304x1134, chiếm khung nhìn
  // NHIỀU hơn bản rõ 750x750 phóng vừa khung, nên phần "chấm điểm" bên dưới bị nó thắng.
  if (a.mo) ly_do.push('có hiệu ứng mờ — nhiều khả năng là ảnh nền trang trí của lightbox')

  return ly_do
}

/**
 * @param {Array<{src:string,naturalWidth:number,naturalHeight:number,
 *                clientWidth:number,clientHeight:number,top:number,bottom:number,mo?:boolean}>} anh
 * @param {{caoKhungNhin:number}} ngu_canh
 */
export function chonTrangTruyen(anh, { caoKhungNhin }) {
  const bi_loai = []
  const ung_vien = []

  for (const a of anh) {
    const ly_do = loaiDoChatLuong(a)
    // Hoàn toàn nằm ngoài khung nhìn ⇒ không phải trang người dùng đang đọc (nhưng có thể là
    // ứng viên tốt cho `chonTrangKeTiep` — xem hàm đó).
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

/**
 * Trang KẾ TIẾP để xếp hàng dịch trước, trong lúc người dùng còn đang đọc trang hiện tại.
 *
 * Chỉ nhận ảnh đã NẰM SẴN TRONG DOM (trang dùng cuộn dọc liên tục, giữ vài trang kế cận để cuộn
 * mượt — đo được trên MangaPlus: 22-36 `<img>` cùng lúc). Trang kiểu "bấm Tiếp" mới nạp ảnh mới
 * thì không có gì để xếp hàng trước — trả `null`, không đoán bừa.
 *
 * KHÔNG xếp hàng quá 1 trang mỗi lần gọi: đây là "dịch trước trong lúc đọc trang hiện tại", không
 * phải tự động quét cả chapter (cố ý loại ở `PLAN_E19` §8 — xem `docs/ARCH.md` §E19 vì sao).
 */
export function chonTrangKeTiep(anh, { caoKhungNhin, boQuaSrc }) {
  const ung_vien = anh.filter((a) => (
    a.src !== boQuaSrc
    && a.top >= caoKhungNhin // sắp hiện ra khi cuộn xuống — chưa hiện trên màn ngay lúc này
    && loaiDoChatLuong(a).length === 0
  ))
  if (!ung_vien.length) return { anh: null, ly_do: 'không có trang kế tiếp nào đã nạp sẵn' }

  // Gần khung nhìn nhất = đúng thứ đọc kế tiếp. Xa hơn có thể là trang xa hơn nữa trong danh sách
  // cuộn, hoặc nội dung không liên quan (bình luận, gợi ý) nằm dưới cùng bố cục.
  const gan_nhat = ung_vien.reduce((a, b) => (b.top < a.top ? b : a))
  return { anh: gan_nhat, ly_do: `gần khung nhìn nhất trong ${ung_vien.length} ảnh đã nạp sẵn` }
}
