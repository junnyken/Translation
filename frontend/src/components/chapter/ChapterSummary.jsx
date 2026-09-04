import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'

/** Tóm tắt "làm gì tiếp" cho cả chapter — hành động chính là RÀ SOÁT, không phải xuất.
 *
 * Cố ý không để nút xuất cùng cấp với nút rà soát khi còn vùng lỗi: đưa hai lựa chọn ngang nhau
 * là ngầm nói "xuất luôn cũng được như nhau", trong khi bản đó còn bong bóng trống.
 */
export default function ChapterSummary({ tienDo, canhBao, trangDau, onXuat }) {
  const soTran = canhBao?.overflow_warning_count ?? 0
  const soCanDoc = canhBao?.needs_manual_count ?? 0
  // F1 — vùng máy KHÔNG chèn được chữ vì font thiếu ký tự. Đếm riêng: hai số trên là "chữ có
  // mà chưa đẹp / chưa đọc được", còn số này là bong bóng chắc chắn trống.
  const soThieuFont = canhBao?.font_missing_count ?? 0
  const co_canh_bao = soTran > 0 || soCanDoc > 0 || soThieuFont > 0

  if (!tienDo.san_sang_ra_soat) {
    return (
      <Alert sac="tin" tieuDe="Đang xử lý">
        {tienDo.so_xong}/{tienDo.tong} trang đã căn chữ xong.
        {tienDo.so_hong > 0 && ` ${tienDo.so_hong} trang hỏng ở bước nhận diện.`}
        {' '}Xử lý chạy nền — bạn có thể rời trang rồi quay lại.
      </Alert>
    )
  }

  return (
    <div className="tom-tat-xong">
      {co_canh_bao ? (
        <Alert sac="canh" tieuDe="Đã căn chữ xong, nhưng còn chỗ cần sửa">
          <ul className="ds-canh-bao">
            {soTran > 0 && (
              <li><b>{soTran}</b> vùng chữ tràn ra ngoài bong bóng</li>
            )}
            {soCanDoc > 0 && (
              <li><b>{soCanDoc}</b> bong bóng sẽ <b>trống</b> vì chưa đọc được chữ gốc</li>
            )}
            {soThieuFont > 0 && (
              <li>
                <b>{soThieuFont}</b> bong bóng sẽ <b>trống</b> vì font không có ký tự trong bản
                dịch (thường là chữ Nhật còn sót) — sửa lại chữ ở vùng đó rồi căn lại
              </li>
            )}
          </ul>
          Xuất vẫn được, nhưng nên rà soát trước.
        </Alert>
      ) : (
        <Alert sac="ok" tieuDe="Đã căn chữ xong">
          Không có vùng nào bị đánh dấu cần sửa. Nên xem qua một lượt trước khi xuất.
        </Alert>
      )}
      <div className="hang nut">
        {trangDau && (
          <Button kieu="chinh" onClick={() => { window.location.hash = `page=${trangDau}` }}>
            Mở để rà soát
          </Button>
        )}
        <Button kieu="phu" onClick={onXuat}>
          Xuất chapter{co_canh_bao ? ` (còn ${soTran + soCanDoc + soThieuFont} vùng cần sửa)` : ''}
        </Button>
      </div>
    </div>
  )
}
