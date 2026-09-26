/** Đếm ngược tới một mốc thời gian, định dạng cho người đọc.
 *
 * ## Vì sao nhận MỐC chứ không nhận SỐ GIÂY
 *
 * Máy chủ trả cả `reset_luc` (mốc tuyệt đối, có phần bù `+07:00`) lẫn `reset_sau_giay`. Dùng số
 * giây là dùng một ảnh chụp: tab để mở 20 phút thì con số đó sai 20 phút, mà nhìn vẫn hợp lý.
 * Mốc tuyệt đối tự đúng mãi.
 *
 * ## Vì sao KHÔNG tự tính mốc ở trình duyệt
 *
 * Máy người dùng có thể lệch múi giờ hoặc lệch giờ. Mốc do máy chủ gửi đã mang sẵn `+07:00` nên
 * `new Date(...)` quy đổi đúng, không cần biết máy đang ở đâu.
 */

/** Số milli-giây còn lại tới `moc`. Không bao giờ âm. */
export function conLaiMs(moc, bayGio = Date.now()) {
  if (!moc) return 0
  const dich = new Date(moc).getTime()
  if (Number.isNaN(dich)) return 0
  return Math.max(0, dich - bayGio)
}

/** "2 giờ 15 phút" · "45 phút" · "30 giây" · "hết giờ".
 *
 * Cố ý KHÔNG hiện giây khi còn trên một phút: một con số nhảy từng giây kéo mắt người dùng khỏi
 * việc họ đang làm, mà độ chính xác đó chẳng giúp gì cho một mốc cách đây hàng giờ.
 */
export function chuDemNguoc(moc, bayGio = Date.now()) {
  const ms = conLaiMs(moc, bayGio)
  if (ms <= 0) return 'hết giờ'
  const giay = Math.ceil(ms / 1000)
  if (giay < 60) return `${giay} giây`
  const phut = Math.floor(giay / 60)
  if (phut < 60) return `${phut} phút`
  const gio = Math.floor(phut / 60)
  const phutLe = phut % 60
  return phutLe ? `${gio} giờ ${phutLe} phút` : `${gio} giờ`
}

/** Mốc hết hạn giữ tệp: `xongLuc + soPhut`. `null` khi chưa xong — CHƯA XONG thì KHÔNG có mốc.
 *
 * Trả `null` thay vì "bây giờ + 30 phút" có chủ đích: đồng hồ đếm từ lúc XONG (§2.3 đặc tả).
 * Bắt đầu đếm từ lúc tải lên thì một chapter 24 trang hết hạn trước khi dịch xong.
 */
export function mocHetHanGiuTep(xongLuc, soPhut = 30) {
  if (!xongLuc) return null
  const t = new Date(xongLuc).getTime()
  if (Number.isNaN(t)) return null
  return new Date(t + soPhut * 60_000).toISOString()
}
