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

  const hienThiLon = (a.clientWidth || 0) >= 320 && (a.clientHeight || 0) >= 420
  const canhToiThieu = hienThiLon ? 280 : CANH_TOI_THIEU
  const dienTichToiThieu = hienThiLon ? 280 * 400 : DIEN_TICH_TOI_THIEU

  if (w < canhToiThieu && h < canhToiThieu) ly_do.push('quá nhỏ')
  if (w * h < dienTichToiThieu) ly_do.push('diện tích quá nhỏ')
  // Banner quảng cáo là ảnh NGANG dẹt (`w > h` và `h / w < 0.45`).
  // Trang truyện dọc hoặc dải Webtoon (`h >= w`) có thể rất dài theo chiều dọc (`w / h` xuống tới 0.08).
  const tiLe = w > h ? (h / Math.max(w, 1)) : (w / Math.max(h, 1))
  const nguongTiLe = w > h ? TI_LE_TOI_THIEU : 0.08
  if (tiLe < nguongTiLe) ly_do.push('quá dẹt — nhiều khả năng là banner')
  // Ảnh bị CSS thu nhỏ hẳn xuống kích thước tem thư (< 240px) thường là thumbnail trong danh sách.
  // Không loại nếu ảnh đang hiển thị đủ rộng trên màn hình (`clientWidth >= 240`), vì trên MangaDex
  // hoặc màn hình Windows DPI 125%-150%, bản scan gốc 1800px-2400px hiển thị vừa chiều cao khung nhìn
  // (`clientWidth` ~ 450px-600px) sẽ có `w / clientWidth` đạt 3.2 - 4.5 dù chính là trang truyện đang đọc!
  if (a.clientWidth && a.clientWidth < 240 && w / a.clientWidth > 3) {
    ly_do.push('bị thu nhỏ nhiều — nhiều khả năng là ảnh thu nhỏ')
  }
  // Lightbox hay dựng nền bằng CHÍNH ảnh đang xem, phóng to + làm mờ để lấp khung.
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

/**
 * E98 — Chọn tối đa `toiDa` (mặc định 2) trang kế tiếp đã nạp sẵn trong DOM theo thứ tự từ trên xuống.
 * Dùng để xếp hàng dịch đón đầu tuần tự (N+1 -> N+2): vừa giúp cuộn trang hiện bản dịch tức thì (0s),
 * vừa bảo đảm trang N+1 dịch xong trước để truyền ngữ cảnh trượt (xưng hô, tên riêng) sang trang N+2.
 */
export function chonCacTrangKeTiep(anh, { caoKhungNhin, boQuaSrc, toiDa = 2 }) {
  const bo_qua = boQuaSrc instanceof Set ? boQuaSrc : new Set(boQuaSrc ? [boQuaSrc] : [])
  const da_thay = new Set()
  const ung_vien = []

  for (const a of anh) {
    if (!a.src || bo_qua.has(a.src) || da_thay.has(a.src)) continue
    if (a.top < caoKhungNhin) continue
    if (loaiDoChatLuong(a).length > 0) continue
    da_thay.add(a.src)
    ung_vien.push(a)
  }

  ung_vien.sort((a, b) => a.top - b.top)
  return ung_vien.slice(0, Math.max(0, toiDa))
}

/**
 * MỌI ảnh trông giống trang truyện trên trang, xếp theo thứ tự đọc (trên → dưới) — nền của chế độ
 * "dịch cả chapter" (E59).
 *
 * Khác `chonTrangTruyen` ở đúng MỘT điều: **không lọc theo khung nhìn**. Dùng lại nguyên
 * `loaiDoChatLuong` chứ không viết luật mới — docstring đầu tệp đã chốt lý do: hai nơi có hai bảng
 * luật là sớm muộn lệch nhau, và lúc đó "vì sao trang này bị bỏ" không trả lời được.
 *
 * Lọc trùng theo `src`: lightbox dựng nền bằng CHÍNH ảnh đang xem nên cùng một `src` xuất hiện hai
 * lần. Dịch hai lần cùng một ảnh là tiêu hai lượt hạn mức cho một kết quả.
 *
 * @param {Array<object>} anh mô tả ảnh như `chonTrangTruyen` nhận
 */
export function chonMoiTrang(anh) {
  const bi_loai = []
  const ung_vien = []
  const da_thay = new Set()

  for (const a of anh) {
    const ly_do = loaiDoChatLuong(a)
    if (ly_do.length) { bi_loai.push({ src: a.src, ly_do }); continue }
    if (da_thay.has(a.src)) { bi_loai.push({ src: a.src, ly_do: ['trùng src'] }); continue }
    da_thay.add(a.src)
    ung_vien.push(a)
  }

  // Thứ tự ĐỌC, không phải thứ tự trong DOM: trang web có thể đặt ảnh trong DOM theo thứ tự khác
  // thứ tự hiển thị. Dịch xuôi theo mắt đọc để trang đầu có bản dịch trước.
  ung_vien.sort((a, b) => a.top - b.top)
  return { danh_sach: ung_vien, bi_loai }
}
