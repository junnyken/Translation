import Icon from './Icon.jsx'

/** Nút dùng chung — 4 kiểu, có trạng thái đang chạy và **lý do bị khoá hiện ngay cạnh nút**.
 *
 * Nút mờ mà không nói vì sao là chỗ người dùng đứng lại lâu nhất: họ không biết còn thiếu gì.
 */
export default function Button({
  kieu = 'phu', dangChay = false, lyDoKhoa, icon, children, disabled, ...rest
}) {
  const khoa = disabled || dangChay || Boolean(lyDoKhoa)
  return (
    <>
      <button
        type="button"
        className={`nut nut-${kieu}${dangChay ? ' dang-chay' : ''}`}
        disabled={khoa}
        aria-describedby={lyDoKhoa ? `${rest.id || 'nut'}-ly-do` : undefined}
        {...rest}
      >
        {dangChay && <Icon ten="quay" />}
        {!dangChay && icon && <Icon ten={icon} />}
        {children}
      </button>
      {lyDoKhoa && !dangChay && (
        <p className="ly-do-khoa" id={`${rest.id || 'nut'}-ly-do`}>{lyDoKhoa}</p>
      )}
    </>
  )
}
