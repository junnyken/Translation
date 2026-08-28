import Icon from './Icon.jsx'

/** Dòng thời gian pipeline — vẽ từ trạng thái THẬT của trang, không có thanh phần trăm giả.
 *
 * Backend không có "phần trăm hoàn thành" cho một trang, nên ở đây cũng không bịa ra: chỉ hiện
 * bước nào xong, bước nào đang chạy, bước nào chưa tới.
 */
const ICON = {
  chua: 'dong-ho', dang_chay: 'quay', xong: 'tich', canh_bao: 'canh', hong: 'canh',
}

export default function ProgressStage({ buoc }) {
  return (
    <ol className="dong-tg">
      {buoc.map((b) => (
        <li key={b.ma} className={`buoc buoc-${b.tinh_trang}`}>
          <span className="buoc-cham"><Icon ten={ICON[b.tinh_trang]} co={13} /></span>
          <div className="buoc-noi-dung">
            <b>{b.nhan}</b>
            {b.mo_ta && <span>{b.mo_ta}</span>}
          </div>
        </li>
      ))}
    </ol>
  )
}
