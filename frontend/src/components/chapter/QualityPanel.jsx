import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'
import Icon from '../ui/Icon.jsx'
import { PHAN_LOAI_VUNG } from '../../lib/status-presentation.js'

/** Bảng "chất lượng bản dịch" của cả chapter (E12).
 *
 * Cố ý KHÔNG dùng chữ "bản dịch chuẩn" hay "đạt chất lượng": đây chỉ là kết quả của một bộ luật
 * đọc bằng chứng có sẵn, không phải lời bảo đảm dịch đúng nghĩa.
 */
export default function QualityPanel({ tomTat, trangDau }) {
  if (!tomTat || tomTat.tong_vung === 0) return null

  const { ro_rang, can_ra_soat, chua_danh_gia, da_bo_qua, tong_vung } = tomTat
  const loai = Object.entries(tomTat.theo_phan_loai || {})
    .filter(([, n]) => n > 0)
    .sort((a, b) => b[1] - a[1])

  return (
    <section className="the-lon" aria-labelledby="tieu-de-chat-luong">
      <header className="the-dau">
        <h2 id="tieu-de-chat-luong">Vùng cần rà soát</h2>
        <p>
          Máy đọc lại bằng chứng của từng vùng (điểm nhận diện, kết quả đọc chữ, bản dịch, cách
          căn chữ) rồi chỉ ra chỗ nên xem. Đây <b>không phải</b> lời bảo đảm dịch đúng nghĩa.
        </p>
      </header>

      <ul className="tom-tat-xuat">
        <li><b>{tong_vung}</b> vùng chữ trong chapter</li>
        {can_ra_soat > 0 && (
          <li className="canh-bao"><b>{can_ra_soat}</b> vùng <b>cần rà soát</b></li>
        )}
        <li className="on"><b>{ro_rang}</b> vùng không có dấu hiệu bất thường</li>
        {chua_danh_gia > 0 && (
          <li className="canh-bao">
            <b>{chua_danh_gia}</b> vùng <b>chưa đánh giá được</b> — chưa chấm khác với chấm sạch
          </li>
        )}
        {da_bo_qua > 0 && (
          <li><b>{da_bo_qua}</b> vùng bạn đã chủ động bỏ qua</li>
        )}
      </ul>

      {loai.length > 0 && (
        <>
          <h3 className="tieu-de-nho">Máy đoán từng vùng là gì</h3>
          <ul className="ds-phan-loai">
            {loai.map(([ma, n]) => (
              <li key={ma}>
                <Icon ten={PHAN_LOAI_VUNG[ma]?.icon ?? 'dong-ho'} co={13} />
                <span>{PHAN_LOAI_VUNG[ma]?.nhan ?? ma}</span>
                <b>{n}</b>
              </li>
            ))}
          </ul>
        </>
      )}

      {can_ra_soat > 0 && trangDau && (
        <div className="hang nut">
          <Button kieu="chinh" onClick={() => { window.location.hash = `page=${trangDau}` }}>
            Rà soát {can_ra_soat} vùng
          </Button>
        </div>
      )}
      {can_ra_soat === 0 && chua_danh_gia === 0 && (
        <Alert sac="ok">Không vùng nào bị đánh dấu cần rà soát.</Alert>
      )}
    </section>
  )
}
