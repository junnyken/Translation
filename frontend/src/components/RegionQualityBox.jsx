import Button from './ui/Button.jsx'
import Icon from './ui/Icon.jsx'
import {
  MUC_CHAT_LUONG,
  PHAN_LOAI_VUNG,
  QUYET_DINH_VUNG,
  TINH_TRANG_DIEM,
} from '../lib/status-presentation.js'

/** Phần "vì sao vùng này cần rà soát" trong màn sửa tay (E12).
 *
 * Hai nút quyết định là của NGƯỜI: "Giữ để dịch" và "Bỏ qua vùng này". Bỏ qua **không xoá** gì —
 * khung chữ, chữ gốc và bản dịch vẫn nằm nguyên trong cơ sở dữ liệu.
 */
export default function RegionQualityBox({ danhGia, dangBan, onQuyetDinh }) {
  if (!danhGia) {
    return (
      <div className="hop-chat-luong">
        <div className="hang-tieu-de">
          <h4>Đánh giá chất lượng</h4>
          <span className="the-tt the-tt-trung">
            <Icon ten="dong-ho" co={13} /><span>Chưa đánh giá</span>
          </span>
        </div>
        <p className="ghi-chu">
          Vùng này chưa được chấm. Chạy lại bước căn chữ để có đánh giá — chưa chấm{' '}
          <b>không</b> có nghĩa là không có vấn đề.
        </p>
      </div>
    )
  }

  const loai = PHAN_LOAI_VUNG[danhGia.relevance] ?? { nhan: danhGia.relevance, sac: 'trung', icon: 'dong-ho' }
  const quyet = QUYET_DINH_VUNG[danhGia.review_status] ?? { nhan: danhGia.review_status, sac: 'trung', icon: 'dong-ho' }
  const muc = MUC_CHAT_LUONG[danhGia.overall_band]
  const daQuyet = danhGia.review_status === 'reviewed_keep' || danhGia.review_status === 'reviewed_skip'

  return (
    <div className="hop-chat-luong">
      <div className="hang-tieu-de">
        <h4>Đánh giá chất lượng</h4>
        <div className="nhom-nhan">
          <span className={`the-tt the-tt-${loai.sac}`}>
            <Icon ten={loai.icon} co={13} /><span>{loai.nhan}</span>
          </span>
          <span className={`the-tt the-tt-${quyet.sac}`}>
            <Icon ten={quyet.icon} co={13} /><span>{quyet.nhan}</span>
          </span>
        </div>
      </div>

      {danhGia.ly_do.length > 0 ? (
        <>
          <p className="ghi-chu">Vì sao cần rà soát:</p>
          <ul className="ds-ly-do">
            {danhGia.ly_do.map((l) => <li key={l.ma}>{l.nhan}</li>)}
          </ul>
        </>
      ) : (
        <p className="ghi-chu">{muc?.mo_ta ?? 'Không có dấu hiệu bất thường.'}</p>
      )}

      {/* "Không có điểm tin cậy" phải nói đúng là không có — hiện 0% là bịa ra một con số. */}
      {danhGia.ocr_confidence_state === 'unavailable' && (
        <p className="ghi-chu">{TINH_TRANG_DIEM.unavailable}.</p>
      )}

      <div className="hang nut">
        <Button
          kieu={daQuyet ? 'phu' : 'chinh'} disabled={dangBan}
          onClick={() => onQuyetDinh('keep')}
        >
          Giữ để dịch
        </Button>
        <Button kieu="phu" disabled={dangBan} onClick={() => onQuyetDinh('skip')}>
          Bỏ qua vùng này
        </Button>
      </div>
      <p className="ghi-chu">
        “Bỏ qua” chỉ ghi lại quyết định của bạn — khung chữ, chữ gốc và bản dịch <b>vẫn được giữ</b>.
      </p>
    </div>
  )
}
