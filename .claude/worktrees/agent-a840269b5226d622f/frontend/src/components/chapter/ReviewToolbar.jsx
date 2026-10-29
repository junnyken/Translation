import Icon from '../ui/Icon.jsx'
import StatusBadge from '../ui/StatusBadge.jsx'

/** Thanh trên của màn rà soát trang (mockup-v2/ra-soat): quay lại chapter · tên trang · huy hiệu
 *  · trang trước/sau · lối vào canvas.
 *
 * KHÔNG dựng trình sửa mới — M7 vẫn là chỗ sửa duy nhất. Đây chỉ là vỏ quanh nó.
 * Nút chỉ có icon (trước/sau) BẮT BUỘC có `aria-label` + `title`.
 */
export default function ReviewToolbar({ tenChapter, projectId, trang, danhSachTrang, soCanXem }) {
  const i = danhSachTrang.findIndex((t) => t.id === trang.id)
  const truoc = i > 0 ? danhSachTrang[i - 1] : null
  const sau = i >= 0 && i < danhSachTrang.length - 1 ? danhSachTrang[i + 1] : null
  const tong = danhSachTrang.length

  return (
    <div className="thanh-ra-soat">
      <a className="nut nut-ghost" href={projectId ? `#project=${projectId}` : '#'}>
        <Icon ten="arrow-left" /> {tenChapter || 'Chapter'}
      </a>
      <h1 className="tieu-de-ra-soat">
        Rà soát trang {trang.order ?? '?'}
        {tong > 0 && <span className="phu"> / {tong}</span>}
      </h1>
      <StatusBadge loai="trang" trangThai={trang.status} />
      {soCanXem > 0 && (
        <span className="the-tt the-tt-canh">
          <Icon ten="canh" co={16} /><span>{soCanXem} vùng cần kiểm tra</span>
        </span>
      )}

      <div className="thanh-ra-soat-phai">
        <div className="dieu-huong-trang">
          <a className={`nut nut-phu nut-icon${truoc ? '' : ' khoa'}`}
             href={truoc ? `#page=${truoc.id}` : undefined}
             aria-disabled={!truoc} aria-label="Trang trước" title="Trang trước">
            <Icon ten="chevron-left" />
          </a>
          <span className="ghi-chu t-so">
            {i >= 0 ? `Trang ${i + 1} / ${tong}` : `Trang ${trang.order ?? '?'}`}
          </span>
          <a className={`nut nut-phu nut-icon${sau ? '' : ' khoa'}`}
             href={sau ? `#page=${sau.id}` : undefined}
             aria-disabled={!sau} aria-label="Trang sau" title="Trang sau">
            <Icon ten="chevron-right" />
          </a>
        </div>
        {/* E76 — lối vào màn canvas đặt ở ĐẦU màn, dạng nút chính. Bản đầu để nó lẫn giữa các ô
            tick bên dưới, dạng nút phụ: chủ dự án mở màn sửa tay mà không tìm thấy (15-10-2026). */}
        <a className="nut nut-chinh" href={`#canvas=${trang.id}`}><Icon ten="brush" /> Mở chế độ canvas</a>
      </div>
    </div>
  )
}
