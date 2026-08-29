import { useEffect, useRef, useState } from 'react'

/** Nhắc trách nhiệm bản quyền + chất lượng, hiện MỘT LẦN cho mỗi chapter trước khi xuất.
 *
 * Cố ý **không** chặn cứng chức năng: đây là công cụ cá nhân, chặn chỉ khiến người ta đi đường
 * vòng. Nhưng cũng không im lặng cho qua — phải tự tick thì nút xuất mới sáng, và việc tick được
 * ghi lại kèm đúng những con số đang hiện trên màn hình này.
 */
export default function ExportWarningModal({ canhBao, nhatQuan, dinhDang, onHuy, onDongY, onRaSoat }) {
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
  // Số của E12 để RIÊNG: chất lượng là một chuyện, trách nhiệm bản quyền là chuyện khác —
  // trộn vào nhau sẽ khiến người dùng tưởng tick một ô là xong cả hai.
  const soRaSoat = canhBao?.quality_needs_review_count ?? 0
  const soChuaCham = canhBao?.quality_unassessed_count ?? 0
  const soBoQua = canhBao?.quality_reviewed_skip_count ?? 0
  // E13 để RIÊNG một khối nữa: "chưa nhất quán thuật ngữ" là chuyện khác hẳn với "chữ tràn
  // khung" (bố cục) và với "trách nhiệm bản quyền" (pháp lý). Gộp lại thì tick một ô xong người
  // dùng tưởng đã xử lý cả ba.
  const soNQMo = nhatQuan?.open_count ?? 0
  const soNQCu = nhatQuan?.stale_count ?? 0
  const soNQBo = (nhatQuan?.rejected_count ?? 0) + (nhatQuan?.resolved_no_change_count ?? 0)

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
        {soTran === 0 && soCanDoc === 0 && soRaSoat === 0 && soChuaCham === 0 ? (
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
            {soRaSoat > 0 && (
              <li className="canh-bao">
                <b>{soRaSoat}</b> vùng được đánh dấu <b>cần rà soát</b>
              </li>
            )}
            {soChuaCham > 0 && (
              <li className="canh-bao">
                <b>{soChuaCham}</b> vùng <b>chưa đánh giá được</b> — chưa chấm khác với chấm sạch
              </li>
            )}
            {soBoQua > 0 && (
              <li className="ghi-chu"><b>{soBoQua}</b> vùng bạn đã chủ động bỏ qua</li>
            )}
            <li className="ghi-chu">
              Muốn sửa thì mở từng trang ở màn sửa tay rồi quay lại đây.
            </li>
          </ul>
        )}

        {(soNQMo > 0 || soNQCu > 0 || soNQBo > 0) && (
          <>
            <h3>Nhất quán thuật ngữ</h3>
            <ul className="tom-tat-xuat">
              {soNQMo > 0 && (
                <li className="canh-bao">
                  <b>{soNQMo}</b> chỗ <b>chưa rà soát</b> theo thuật ngữ bạn đã chốt
                </li>
              )}
              {soNQCu > 0 && (
                <li className="canh-bao">
                  <b>{soNQCu}</b> gợi ý <b>đã cũ</b> vì bản dịch đổi sau lần rà soát — cần rà soát lại
                </li>
              )}
              {soNQBo > 0 && (
                <li className="ghi-chu">
                  <b>{soNQBo}</b> gợi ý bạn đã xem và quyết định không dùng — không tính là việc còn tồn
                </li>
              )}
            </ul>
            {onRaSoat && soNQMo > 0 && (
              <p className="ghi-chu">
                <button className="lien-ket" onClick={onRaSoat}>Rà soát trước khi xuất</button>
                {' '}— hoặc cứ xuất, file vẫn tải về được.
              </p>
            )}
          </>
        )}

        <label className="o-tick">
          <input type="checkbox" checked={daTick} onChange={(e) => setDaTick(e.target.checked)} />
          <span>Tôi đã đọc và chấp nhận trách nhiệm về bản quyền nội dung gốc.</span>
        </label>

        <div className="hang nut">
          <button onClick={onHuy}>Để sau</button>
          <button className="chinh" disabled={!daTick} onClick={() => onDongY(true)}>
            {soNQMo > 0
              ? `Xuất dù còn ${soNQMo} chỗ cần rà soát (${dinhDang.toUpperCase()})`
              : `Xuất chapter (${dinhDang.toUpperCase()})`}
          </button>
        </div>
        {!daTick && (
          <p className="ghi-chu">Cần tick vào ô trên thì nút xuất mới bấm được.</p>
        )}
      </div>
    </div>
  )
}
