import { useEffect, useRef, useState } from 'react'
import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'
import EmptyState from '../ui/EmptyState.jsx'
import { Input } from '../ui/Field.jsx'
import { LOAI_THUAT_NGU } from '../../lib/status-presentation.js'

/** Ba trạng thái rỗng KHÔNG được gộp — "chưa chạy" và "đã chạy mà trống" là hai chuyện khác nhau. */
const RONG = {
  chua_doc_chu: {
    tieuDe: 'Chưa đọc được chữ trong chapter',
    moTa: 'Bước đọc chữ chưa chạy xong, hoặc chữ đọc được đều chưa chắc chắn. Chạy xong bước đọc chữ rồi tìm lại — lúc này chưa thể kết luận chapter có hay không có danh xưng nào.',
  },
  khong_thay: {
    tieuDe: 'Đã tìm, không thấy danh xưng nào lặp lại',
    moTa: 'Chữ trong chapter đã được quét nhưng không có từ nào đủ dấu hiệu là tên riêng hay thuật ngữ. Bạn vẫn thêm tay được như bình thường.',
  },
  deu_da_co: {
    tieuDe: 'Mọi danh xưng tìm được đều đã có trong danh sách',
    moTa: 'Không còn gì mới để thêm — những gì máy tìm ra đều đã nằm trong bảng thuật ngữ của bạn.',
  },
}

const CHU_KY_HOI = 2000
const SO_LAN_HOI_TOI_DA = 30

/** E17 — máy tìm danh xưng trong CHÍNH chapter, người quyết cách dịch.
 *
 * Ranh giới của bảng này: nó **không tạo thuật ngữ nào**. Bấm một ứng viên chỉ mở form "Thêm
 * thuật ngữ" đã điền sẵn phần máy biết (thuật ngữ gốc, loại, trích dẫn) — hai ô quyết định
 * (cách dịch, giải nghĩa) vẫn để trống cho bạn. Vì thế cố ý **không có nút "Duyệt tất cả"**.
 */
export default function TermCandidatePanel({ dangBan, onTim, onChon, onXinGoiY, onDocGoiY }) {
  const [duLieu, setDuLieu] = useState(null)
  const [dangTim, setDangTim] = useState(false)
  const [loi, setLoi] = useState(null)

  const [tenTruyen, setTenTruyen] = useState('')
  const [luot, setLuot] = useState(null)
  const [dangHoi, setDangHoi] = useState(false)
  const dongHo = useRef(null)

  useEffect(() => () => clearInterval(dongHo.current), [])

  const tim = async () => {
    setLoi(null)
    setDangTim(true)
    try {
      setDuLieu(await onTim())
    } catch (e) {
      setLoi(e.message)
    } finally {
      setDangTim(false)
    }
  }

  const xinGoiY = async () => {
    if (!tenTruyen.trim()) return setLoi('Nhập tên bộ truyện trước đã.')
    setLoi(null)
    setDangHoi(true)
    setLuot(null)
    try {
      const bat_dau = await onXinGoiY(tenTruyen.trim())
      setLuot(bat_dau)
      let lan = 0
      clearInterval(dongHo.current)
      dongHo.current = setInterval(async () => {
        lan += 1
        try {
          const moi = await onDocGoiY(bat_dau.id)
          setLuot(moi)
          if (moi.status === 'done' || moi.status === 'failed' || lan >= SO_LAN_HOI_TOI_DA) {
            clearInterval(dongHo.current)
            setDangHoi(false)
          }
        } catch (e) {
          clearInterval(dongHo.current)
          setDangHoi(false)
          setLoi(e.message)
        }
      }, CHU_KY_HOI)
    } catch (e) {
      setDangHoi(false)
      setLoi(e.message)
    }
  }

  const rong = duLieu && duLieu.ung_vien.length === 0 ? RONG[duLieu.trang_thai] : null
  const goiYTheoTen = {}
  for (const g of luot?.suggestions || []) goiYTheoTen[g.source_term] = g

  return (
    <section className="the-lon" aria-labelledby="tieu-de-ung-vien">
      <header className="the-dau">
        <h2 id="tieu-de-ung-vien">Tìm danh xưng trong chapter</h2>
        <p>
          Máy đọc lại chữ đã nhận được của chapter rồi liệt kê những danh xưng lặp lại, kèm{' '}
          <b>số lần xuất hiện và câu trích nguyên văn</b>. Nó <b>không tự thêm thuật ngữ nào</b> —
          bạn vẫn là người quyết cách dịch.
        </p>
      </header>

      <div className="hang-cong-cu">
        <span className="ghi-chu">
          {duLieu
            ? `Đã quét ${duLieu.so_vung_co_chu}/${duLieu.so_vung_da_quet} vùng chữ`
            : 'Chưa tìm lần nào'}
        </span>
        <Button kieu="chinh" icon="quay" dangChay={dangTim} disabled={dangBan} onClick={tim}>
          {dangTim ? 'Đang tìm…' : 'Tìm trong chapter'}
        </Button>
      </div>

      {loi && <Alert sac="loi" tieuDe="Không tìm được">{loi}</Alert>}

      {duLieu?.so_vung_khong_chac > 0 && (
        <Alert sac="canh" tieuDe={`Bỏ qua ${duLieu.so_vung_khong_chac} vùng chữ đọc chưa chắc chắn`}>
          Những vùng máy tự khai là đọc không chắc <b>không được dùng để gợi ý</b> — rút thuật ngữ
          từ chữ đọc sai sẽ đẻ ra danh sách rác mà bạn không có cách nào biết.
        </Alert>
      )}

      {duLieu?.ghi_chu_ngon_ngu && (
        <p className="ghi-chu">Cách tìm cho ngôn ngữ này: {duLieu.ghi_chu_ngon_ngu}.</p>
      )}

      {rong && <EmptyState icon="sach" tieuDe={rong.tieuDe} moTa={rong.moTa} />}

      {duLieu && duLieu.ung_vien.length > 0 && (
        <>
          <div className="bang-cuon">
            <table className="bang">
              <thead>
                <tr>
                  <th scope="col">Danh xưng</th>
                  <th scope="col">Số lần</th>
                  <th scope="col">Trang</th>
                  <th scope="col">Vì sao được nêu</th>
                  <th scope="col">Trích dẫn</th>
                  <th scope="col"><span className="an-nhin">Thao tác</span></th>
                </tr>
              </thead>
              <tbody>
                {duLieu.ung_vien.map((uv) => (
                  <tr key={uv.term_key}>
                    <td><b>{uv.source_term}</b></td>
                    <td>{uv.count}</td>
                    <td>{uv.pages.join(', ')}</td>
                    <td className="ghi-chu">{uv.reasons.join(' · ')}</td>
                    <td className="ghi-chu">
                      {uv.quotes.map((q) => (
                        <div key={`${q.region_id}`}>“{q.text}” <i>(trang {q.page_order})</i></div>
                      ))}
                    </td>
                    <td className="o-thao-tac">
                      <Button icon="cong" disabled={dangBan}
                              onClick={() => onChon(uv, goiYTheoTen[uv.source_term])}>
                        Thêm thành thuật ngữ
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <h3 className="tieu-de-nho">Nhờ gợi ý cách dịch theo tên bộ truyện</h3>
          <p className="ghi-chu">
            Máy sẽ hỏi mô hình cách dịch quen thuộc cho <b>đúng những danh xưng ở bảng trên</b> —
            không hỏi “truyện này có nhân vật nào”, vì câu đó mô hình luôn trả lời kể cả khi không
            biết. Mục nào mô hình trả về mà không khớp danh sách trên sẽ bị loại thẳng.
          </p>
          <div className="hang-cong-cu">
            <Input nhan="Tên bộ truyện" value={tenTruyen}
                   onChange={(e) => setTenTruyen(e.target.value)}
                   moTa="Ví dụ: Pepper&Carrot" />
            <Button icon="quay" dangChay={dangHoi} disabled={dangBan} onClick={xinGoiY}>
              {dangHoi ? 'Đang hỏi…' : 'Xin gợi ý'}
            </Button>
          </div>

          {luot?.status === 'failed' && (
            <Alert sac="loi" tieuDe="Không hỏi được">
              {luot.error_log || 'Mô hình không trả lời.'} Bảng danh xưng ở trên{' '}
              <b>vẫn dùng bình thường</b> — nó không phụ thuộc vào mô hình.
            </Alert>
          )}

          {luot?.status === 'done' && (
            <Alert
              sac={luot.suggestions?.length ? 'tin' : 'canh'}
              tieuDe={luot.suggestions?.length
                ? `${luot.suggestions.length}/${luot.asked_count} mục có gợi ý — chưa duyệt`
                : 'Mô hình không đưa được gợi ý nào dùng được'}
            >
              {luot.suggestions?.length
                ? 'Gợi ý đã được điền vào bảng trên. Đây là chữ của mô hình, không phải quyết định của bạn — bấm “Thêm thành thuật ngữ” rồi tự sửa lại.'
                : 'Mô hình không biết bộ truyện này, hoặc mọi mục nó trả về đều không khớp danh xưng trong chapter. Cứ thêm tay như bình thường.'}
              {luot.dropped_count > 0 && (
                <div className="ghi-chu">
                  Đã <b>loại {luot.dropped_count} mục</b> mô hình đưa ra mà chapter này không có.
                </div>
              )}
            </Alert>
          )}

          {luot?.suggestions?.length > 0 && (
            <div className="bang-cuon">
              <table className="bang">
                <thead>
                  <tr>
                    <th scope="col">Danh xưng</th>
                    <th scope="col">Gợi ý tiếng Việt</th>
                    <th scope="col">Loại</th>
                    <th scope="col">Giải nghĩa gợi ý</th>
                  </tr>
                </thead>
                <tbody>
                  {luot.suggestions.map((g) => (
                    <tr key={g.source_term}>
                      <td><b>{g.source_term}</b></td>
                      <td>
                        {g.target_term} <span className="the-nho">gợi ý · chưa duyệt</span>
                      </td>
                      <td>{LOAI_THUAT_NGU[g.term_type] || g.term_type}</td>
                      <td className="ghi-chu">{g.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </section>
  )
}
