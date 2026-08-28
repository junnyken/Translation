import { useEffect, useRef, useState } from 'react'

/** Nhắc trách nhiệm bản quyền + chất lượng, hiện MỘT LẦN cho mỗi chapter trước khi xuất.
 *
 * Cố ý **không** chặn cứng chức năng: đây là công cụ cá nhân, chặn chỉ khiến người ta đi đường
 * vòng. Nhưng cũng không im lặng cho qua — phải tự tick thì nút xuất mới sáng, và việc tick được
 * ghi lại kèm đúng những con số đang hiện trên màn hình này.
 */
export default function ExportWarningModal({ canhBao, dinhDang, onHuy, onDongY }) {
  const [daTick, setDaTick] = useState(false)
  const hopRef = useRef(null)

  // Đóng bằng phím Esc — hộp thoại không có lối thoát bằng bàn phím là hộp thoại bẫy người dùng.
  useEffect(() => {
    const nghe = (e) => e.key === 'Escape' && onHuy()
    window.addEventListener('keydown', nghe)
    hopRef.current?.focus()
    return () => window.removeEventListener('keydown', nghe)
  }, [onHuy])

  const soTran = canhBao?.overflow_warning_count ?? 0
  const soCanDoc = canhBao?.needs_manual_count ?? 0

  return (
    <div className="lop-phu" onClick={(e) => e.target === e.currentTarget && onHuy()}>
      <div className="hop-thoai" role="dialog" aria-modal="true"
           aria-labelledby="tieu-de-canh-bao" tabIndex={-1} ref={hopRef}>
        <h2 id="tieu-de-canh-bao">Trước khi tải file về</h2>

        <p className="loi-ban-quyen">
          <b>Bạn chịu trách nhiệm về bản quyền nội dung gốc.</b> Công cụ này dành cho mục đích
          cá nhân / học tập. File xuất ra chỉ nằm trên máy của bạn — hệ thống <b>không</b> tự
          đăng công khai hay chia sẻ cho bất kỳ ai.
        </p>

        <h3>Chất lượng bản đang xuất</h3>
        {soTran === 0 && soCanDoc === 0 ? (
          <p className="ghi-chu on">Không có vùng nào cần xem lại.</p>
        ) : (
          <ul className="tom-tat-xuat">
            {soTran > 0 && (
              <li className="canh-bao">
                <b>{soTran}</b> vùng chữ <b>tràn ra ngoài khung</b> — chữ dịch dài hơn chỗ trống
                trong bong bóng. Xuất vẫn được, nhưng nhìn sẽ lộ.
              </li>
            )}
            {soCanDoc > 0 && (
              <li className="canh-bao">
                <b>{soCanDoc}</b> vùng <b>chưa đọc được chữ gốc</b> — những bong bóng này sẽ
                <b> trống</b> trong file xuất ra.
              </li>
            )}
            <li className="ghi-chu">
              Muốn sửa thì mở từng trang ở màn sửa tay rồi quay lại đây.
            </li>
          </ul>
        )}

        <label className="o-tick">
          <input type="checkbox" checked={daTick} onChange={(e) => setDaTick(e.target.checked)} />
          <span>Tôi đã đọc và chấp nhận trách nhiệm về bản quyền nội dung gốc.</span>
        </label>

        <div className="hang nut">
          <button onClick={onHuy}>Để sau</button>
          <button className="chinh" disabled={!daTick} onClick={() => onDongY(true)}>
            Xuất chapter ({dinhDang.toUpperCase()})
          </button>
        </div>
        {!daTick && (
          <p className="ghi-chu">Cần tick vào ô trên thì nút xuất mới bấm được.</p>
        )}
      </div>
    </div>
  )
}
