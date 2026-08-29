import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'
import EmptyState from '../ui/EmptyState.jsx'
import { LOAI_VIEC_NHAT_QUAN } from '../../lib/status-presentation.js'

/** Bảng "Nhất quán" của chapter (E13 · D1).
 *
 * Câu chữ ở đây cố ý dè dặt: đây là kết quả đối chiếu với thuật ngữ **bạn** đã chốt, không phải
 * phán quyết bản dịch đúng hay sai. Và **không có điểm chất lượng** — máy không đo được điều đó.
 */
export default function ConsistencyPanel({ tomTat, dangQuet, onQuet, onMoHangDoi }) {
  if (!tomTat) return null

  const {
    open_count = 0, accepted_count = 0, rejected_count = 0, stale_count = 0,
    resolved_no_change_count = 0, by_type = {}, approved_glossary_count = 0,
  } = tomTat
  const daXuLy = accepted_count + rejected_count + resolved_no_change_count

  return (
    <section className="the-lon" aria-labelledby="tieu-de-nhat-quan">
      <header className="the-dau">
        <h2 id="tieu-de-nhat-quan">Nhất quán thuật ngữ</h2>
        <p>
          Đối chiếu bản dịch với những thuật ngữ bạn đã chốt, rồi chỉ ra chỗ chưa theo.
          Đây là <b>gợi ý kiểm tra</b>, không khẳng định bản dịch sai.
        </p>
      </header>

      {approved_glossary_count === 0 ? (
        <EmptyState
          icon="sach"
          tieuDe="Chưa có thuật ngữ nào được duyệt"
          moTa="Chưa duyệt thuật ngữ thì chưa rà soát được — và 0 việc lúc này KHÔNG có nghĩa là bản dịch đã ổn."
        />
      ) : (
        <>
          <ul className="tom-tat-xuat">
            {open_count > 0 ? (
              <li className="canh-bao">
                <b>{open_count}</b> chỗ <b>cần bạn xem</b>
              </li>
            ) : (
              <li className="on">Không còn chỗ nào cần xem theo các thuật ngữ đã duyệt</li>
            )}
            {stale_count > 0 && (
              <li className="canh-bao">
                <b>{stale_count}</b> gợi ý <b>đã cũ</b> — bản dịch đổi sau lần quét, cần quét lại
              </li>
            )}
            {daXuLy > 0 && <li><b>{daXuLy}</b> chỗ bạn đã xử lý</li>}
            <li className="ghi-chu">
              Đang đối chiếu theo <b>{approved_glossary_count}</b> thuật ngữ đã duyệt
            </li>
          </ul>

          {open_count > 0 && (
            <>
              <h3 className="tieu-de-nho">Vì sao các chỗ này được nêu</h3>
              {/* Lưới riêng chứ không mượn `.ds-phan-loai` của E12: ở đó `<b>` là con số đứng
                  CUỐI dòng nên CSS đẩy nó sang phải, còn ở đây con số đứng đầu. */}
              <ul className="ds-vi-sao">
                {Object.entries(by_type)
                  .filter(([, n]) => n > 0)
                  .sort((a, b) => b[1] - a[1])
                  .map(([ma, n]) => (
                    <li key={ma}>
                      <b className="so-viec">{n}</b>
                      <div>
                        <div>{(LOAI_VIEC_NHAT_QUAN[ma] || {}).nhan || ma}</div>
                        <div className="ghi-chu">{(LOAI_VIEC_NHAT_QUAN[ma] || {}).mo_ta}</div>
                      </div>
                    </li>
                  ))}
              </ul>
            </>
          )}
        </>
      )}

      <div className="hang nut">
        <Button kieu="chinh" icon="quay" dangChay={dangQuet}
                lyDoKhoa={approved_glossary_count === 0
                  ? 'Duyệt ít nhất một thuật ngữ trước khi rà soát'
                  : undefined}
                onClick={onQuet}>
          {dangQuet ? 'Đang rà soát…' : 'Rà soát nhất quán'}
        </Button>
        {open_count > 0 && (
          <Button icon="mui-ten-phai" onClick={onMoHangDoi}>
            Xem {open_count} chỗ cần sửa
          </Button>
        )}
      </div>

      {stale_count > 0 && open_count === 0 && (
        <Alert sac="canh" tieuDe="Có gợi ý đã cũ">
          Bản dịch đã thay đổi kể từ lần rà soát trước nên những gợi ý cũ không dùng được nữa —
          bấm <b>Rà soát nhất quán</b> để tính lại.
        </Alert>
      )}
    </section>
  )
}
