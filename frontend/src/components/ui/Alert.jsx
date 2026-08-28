import Icon from './Icon.jsx'

/** Thông báo tại chỗ (thành công / lỗi / cảnh báo). Có `role` đúng để trình đọc màn hình
 *  đọc lên khi nội dung đổi — thông báo mà chỉ nhìn thấy thì người dùng bàn phím bỏ lỡ. */
export default function Alert({ sac = 'tin', tieuDe, children, onDong }) {
  const icon = sac === 'loi' ? 'canh' : sac === 'ok' ? 'tich' : sac === 'canh' ? 'canh' : 'dong-ho'
  return (
    <div className={`bao bao-${sac}`} role={sac === 'loi' ? 'alert' : 'status'} aria-live="polite">
      <Icon ten={icon} co={16} />
      <div className="bao-noi-dung">
        {tieuDe && <b className="bao-tieu-de">{tieuDe}</b>}
        <div>{children}</div>
      </div>
      {onDong && (
        <button type="button" className="nut-bo" aria-label="Đóng thông báo" onClick={onDong}>
          <Icon ten="x" co={14} />
        </button>
      )}
    </div>
  )
}
