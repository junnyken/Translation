/** Số phút → chữ người đọc được: "30 phút", "2 giờ", "1 ngày", "1 giờ 30 phút".
 *
 * Máy chủ trả `han_muc.giu_ket_qua_phut` bằng PHÚT; in thẳng ra thì 1 ngày thành "1440 phút".
 * Chỉ đổi cách hiển thị — con số gốc không đổi nghĩa.
 */
export function chuThoiGianGiu(phut) {
  if (typeof phut !== 'number') return ''
  const n = Math.round(phut)
  if (!Number.isFinite(n) || n < 0) return ''
  if (n < 60) return `${n} phút`
  if (n % 1440 === 0) return `${n / 1440} ngày`
  if (n % 60 === 0) return `${n / 60} giờ`
  return `${Math.floor(n / 60)} giờ ${n % 60} phút`
}
