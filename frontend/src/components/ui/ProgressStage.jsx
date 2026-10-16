import Icon from './Icon.jsx'

/** Thanh bước pipeline — vẽ từ trạng thái THẬT của trang, không có thanh phần trăm giả.
 *
 * Backend không có "phần trăm hoàn thành" cho một trang, nên ở đây cũng không bịa ra: chỉ hiện
 * bước nào xong, bước nào đang chạy, bước nào chưa tới (kèm "x/y trang" từ `mo_ta`).
 * ĐỢT 2: dạng lưới các ô bước (mockup-v2/chapter) thay cho dòng thời gian dọc; mỗi ô vẫn có
 * icon + chữ, màu không là nguồn thông tin duy nhất.
 */
const ICON = {
  chua: 'clock', dang_chay: 'loader', xong: 'circle-check', canh_bao: 'triangle-alert', hong: 'circle-x',
}
const LOP = {
  chua: 'cho', dang_chay: 'chay', xong: 'xong', canh_bao: 'canh', hong: 'loi',
}

export default function ProgressStage({ buoc }) {
  return (
    <ol className="cac-buoc cac-buoc-6" aria-label="Các bước xử lý">
      {buoc.map((b) => (
        <li key={b.ma} className={`buoc-the buoc-the-${LOP[b.tinh_trang] ?? 'cho'} buoc-${b.tinh_trang}`}>
          <span className="buoc-the-tren"><Icon ten={ICON[b.tinh_trang] ?? 'clock'} />{b.nhan}</span>
          {b.mo_ta && <span className="buoc-the-tt">{b.mo_ta}</span>}
        </li>
      ))}
    </ol>
  )
}
