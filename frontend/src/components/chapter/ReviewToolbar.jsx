import Icon from '../ui/Icon.jsx'
import StatusBadge from '../ui/StatusBadge.jsx'

/** Thanh điều hướng khi sửa tay: biết mình đang ở đâu và sang trang khác được.
 *
 * KHÔNG dựng trình sửa mới — M7 vẫn là chỗ sửa duy nhất. Đây chỉ là vỏ quanh nó.
 */
export default function ReviewToolbar({ tenChapter, projectId, trang, danhSachTrang, soCanXem }) {
  const i = danhSachTrang.findIndex((t) => t.id === trang.id)
  const truoc = i > 0 ? danhSachTrang[i - 1] : null
  const sau = i >= 0 && i < danhSachTrang.length - 1 ? danhSachTrang[i + 1] : null

  return (
    <div className="thanh-ra-soat">
      <nav className="duong-dan" aria-label="Đường dẫn">
        <a href="#">Chapter</a>
        <span aria-hidden="true">/</span>
        {projectId
          ? <a href={`#project=${projectId}`}>{tenChapter || 'Chapter'}</a>
          : <span>{tenChapter || 'Chapter'}</span>}
        <span aria-hidden="true">/</span>
        <span aria-current="page">Trang {trang.order ?? '?'}</span>
      </nav>

      <div className="thanh-ra-soat-phai">
        <StatusBadge loai="trang" trangThai={trang.status} />
        {soCanXem > 0 && (
          <span className="the-tt the-tt-canh">
            <Icon ten="canh" co={13} /><span>{soCanXem} vùng cần kiểm tra</span>
          </span>
        )}
        <div className="dieu-huong-trang">
          <a className={`nut nut-ghost${truoc ? '' : ' khoa'}`}
             href={truoc ? `#page=${truoc.id}` : undefined}
             aria-disabled={!truoc} title="Trang trước">
            <Icon ten="mui-ten-trai" co={14} />
          </a>
          <span className="ghi-chu">
            {i >= 0 ? `Trang ${i + 1} / ${danhSachTrang.length}` : `Trang ${trang.order ?? '?'}`}
          </span>
          <a className={`nut nut-ghost${sau ? '' : ' khoa'}`}
             href={sau ? `#page=${sau.id}` : undefined}
             aria-disabled={!sau} title="Trang sau">
            <Icon ten="mui-ten-phai" co={14} />
          </a>
        </div>
      </div>
    </div>
  )
}
