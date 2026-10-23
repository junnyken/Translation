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
  // Một ký tự tiếng Việt tỷ lệ (system-ui, line-height ~1.18) chiếm trung bình ~(0.52 * F) x (1.18 * F) ≈ 0.61 * F^2.
  // Nhân hệ số 1.38 để cỡ chữ ước lượng sát diện tích thực của ô trước khi đo DOM thật.
  const theo_o = Math.sqrt((height * width) / Math.max(soKyTu, 1)) * 1.38
  return Math.max(9, Math.min(22, Math.round(theo_o)))
}

/**
 * E101 — Mở rộng khung chữ bám sát (`quyDoi`) ra phần khoảng trắng của lòng bong bóng thoại,
 * đồng thời kẹp biên ảnh và chống đè lên các bong bóng lân cận.
 *
 * Vì sao cần:
 * Bộ nhận diện (CTD / Gemini) trả về khung BÁM SÁT NÉT CHỮ GỐC (để dùng làm mặt nạ xoá chữ LaMa
 * ở chế độ đầy đủ). Với truyện Nhật chữ dọc, khung chữ gốc chỉ là 1–2 cột hẹp nằm giữa bong bóng
 * tròn rộng gấp đôi. Nếu giữ nguyên khung chữ hẹp đó để nhét chữ Việt viết ngang, câu sẽ bị ngắt
 * vụn từng chữ và co về 8–10px trong khi lòng bong bóng xung quanh còn trống rất nhiều.
 *
 * @param {Array<{left:number,top:number,width:number,height:number,soKyTu?:number}>} dsO
 * @param {{width:number,height:number}} khungAnh
 * @returns {Array<{left:number,top:number,width:number,height:number}>}
 */
export function moRongKhungBongBong(dsO, khungAnh) {
  if (!Array.isArray(dsO) || !dsO.length) return []
  const rongAnh = Math.max(1, khungAnh?.width || 1)
  const caoAnh = Math.max(1, khungAnh?.height || 1)
  const leAnh = 2

  const coGiaoNhau = (a, b, dem = 0) => (
    a.left < b.left + b.width + dem &&
    a.left + a.width + dem > b.left &&
    a.top < b.top + b.height + dem &&
    a.top + a.height + dem > b.top
  )

  return dsO.map((o, idx) => {
    const w0 = Math.max(1, o.width)
    const h0 = Math.max(1, o.height)
    const cx = o.left + w0 / 2
    const cy = o.top + h0 / 2
    const tyLe = w0 / h0

    let heSoRong = 1.24
    let heSoCao = 1.20

    if (tyLe < 0.78) {
      // Cột chữ Nhật dọc hẹp (khi không đọc được canvas): chỉ nới vừa phải để không tràn qua viền hộp chữ nhật.
      heSoRong = Math.min(1.48, Math.max(1.28, (h0 * 0.65) / w0))
      heSoCao = 1.14
    } else if (tyLe > 2.1) {
      heSoRong = 1.18
      heSoCao = Math.min(1.65, Math.max(1.35, (w0 * 0.38) / h0))
    }

    const rongToiThieu = Math.min(48, rongAnh * 0.09)
    const caoToiThieu = Math.min(24, caoAnh * 0.035)

    let wMoi = Math.max(w0 * heSoRong, rongToiThieu)
    let hMoi = Math.max(h0 * heSoCao, caoToiThieu)

    let x0 = Math.max(leAnh, cx - wMoi / 2)
    let y0 = Math.max(leAnh, cy - hMoi / 2)
    let x1 = Math.min(rongAnh - leAnh, cx + wMoi / 2)
    let y1 = Math.min(caoAnh - leAnh, cy + hMoi / 2)

    // Luôn bảo đảm bao phủ trọn vẹn 100% khung chữ gốc để che kín nét chữ Nhật bên dưới
    x0 = Math.min(x0, o.left)
    y0 = Math.min(y0, o.top)
    x1 = Math.max(x1, o.left + w0)
    y1 = Math.max(y1, o.top + h0)

    // Chống lấn sang khung chữ của bong bóng khác nếu ban đầu hai khung tách rời nhau
    const kheHo = 4
    for (let j = 0; j < dsO.length; j += 1) {
      if (j === idx) continue
      const khac = dsO[j]
      if (coGiaoNhau(o, khac, 0)) continue

      const kx0 = khac.left
      const ky0 = khac.top
      const kx1 = khac.left + khac.width
      const ky1 = khac.top + khac.height

      const chongNgang = x0 < kx1 + kheHo && x1 + kheHo > kx0
      const chongDoc = y0 < ky1 + kheHo && y1 + kheHo > ky0
      if (!chongNgang || !chongDoc) continue

      if (o.left + w0 <= kx0) {
        x1 = Math.max(o.left + w0, Math.min(x1, kx0 - kheHo))
      } else if (o.left >= kx1) {
        x0 = Math.min(o.left, Math.max(x0, kx1 + kheHo))
      }
      if (o.top + h0 <= ky0) {
        y1 = Math.max(o.top + h0, Math.min(y1, ky0 - kheHo))
      } else if (o.top >= ky1) {
        y0 = Math.min(o.top, Math.max(y0, ky1 + kheHo))
      }
    }

    return {
      left: Math.round(x0 * 10) / 10,
      top: Math.round(y0 * 10) / 10,
      width: Math.max(w0, Math.round((x1 - x0) * 10) / 10),
      height: Math.max(h0, Math.round((y1 - y0) * 10) / 10),
    }
  })
}
