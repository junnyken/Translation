/** Quy đổi toạ độ bong bóng từ pixel ẢNH GỐC sang pixel HIỂN THỊ (E19-4).
 *
 * Máy chủ trả về toạ độ theo ảnh gốc vì nó chỉ thấy ảnh gốc. Trang web thì gần như luôn co ảnh
 * lại cho vừa màn. Không quy đổi thì lớp phủ lệch đúng bằng tỉ lệ co — và lệch nhiều nhất ở
 * chính những trang ảnh lớn, tức là mọi trang truyện.
 *
 * Thuần hàm để test được bằng số, không cần dựng trang web thật.
 */

/**
 * @param {{x:number,y:number,w:number,h:number}} vung  toạ độ theo ảnh gốc
 * @param {{naturalWidth:number,naturalHeight:number,clientWidth:number,clientHeight:number}} anh
 * @returns {{left:number,top:number,width:number,height:number}} theo pixel hiển thị
 */
export function quyDoi(vung, anh) {
  const tx = anh.clientWidth / (anh.naturalWidth || 1)
  const ty = anh.clientHeight / (anh.naturalHeight || 1)
  return {
    left: vung.x * tx,
    top: vung.y * ty,
    width: vung.w * tx,
    height: vung.h * ty,
  }
}

/** Ảnh chưa tải xong thì `naturalWidth` là 0 — quy đổi lúc đó cho ra vô nghĩa. */
export function sanSangQuyDoi(anh) {
  return Boolean(anh && anh.naturalWidth > 0 && anh.clientWidth > 0)
}

/**
 * Cỡ chữ cho một bong bóng: vừa khít chiều cao ô, chặn hai đầu.
 *
 * Chế độ phủ chữ KHÔNG chạy bước căn chữ của bản web, nên không có bảo đảm nào về việc chữ vừa
 * khung. Chữ Việt dài hơn chữ Nhật đáng kể, nên phải cho **tự xuống dòng và cuộn** bên trong ô
 * thay vì giả vờ mọi câu đều vừa.
 */
export function coChu({ height, width }, soKyTu) {
  const theo_o = Math.sqrt((height * width) / Math.max(soKyTu, 1)) * 1.1
  return Math.max(9, Math.min(22, Math.round(theo_o)))
}
