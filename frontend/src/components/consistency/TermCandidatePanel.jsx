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
export default function TermCandidatePanel({
  dangBan, onTim, onChon, onXinGoiY, onDocGoiY, onDoiChieuTen,
}) {
  const [duLieu, setDuLieu] = useState(null)
  const [dangTim, setDangTim] = useState(false)
  const [loi, setLoi] = useState(null)

  const [tenTruyen, setTenTruyen] = useState('')
  const [luot, setLuot] = useState(null)
  const [dangHoi, setDangHoi] = useState(false)
  const dongHo = useRef(null)

  // Tầng 3b — tra CSDL nhân vật. Giữ state RIÊNG với tầng 3a: hai nguồn khác nhau về bản chất
  // (một cái hỏi mô hình, một cái tra CSDL), gộp trạng thái sẽ khiến kết quả của nguồn này ghi
  // đè lên nguồn kia và người dùng không biết mình đang đọc cái nào.
  const [ketQuaTra, setKetQuaTra] = useState(null)
  const [dangTra, setDangTra] = useState(false)

  useEffect(() => () => clearInterval(dongHo.current), [])

  const traCuu = async () => {
    if (!tenTruyen.trim() || !onDoiChieuTen) return
    setDangTra(true); setKetQuaTra(null)
    try {
      setKetQuaTra(await onDoiChieuTen(tenTruyen.trim()))
    } catch (e) {
      // Hỏng ở tầng mạng cũng phải hiện ra, đừng để ô kết quả trống trông như "không có gì".
      setKetQuaTra({ khong_dung_duoc: e.message })
    } finally {
      setDangTra(false)
    }
  }

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


          <h3 className="tieu-de-nho">Tra cách viết chính thức trong cơ sở dữ liệu</h3>
          <p className="ghi-chu">
            Dùng <b>chính tên bộ truyện đã nhập ở trên</b>, lấy <b>đúng những danh xưng ở bảng</b>{' '}
            đi tra CSDL nhân vật (AniList) để biết cách viết chính thức và tên gốc. Khác với gợi ý
            của mô hình ở trên: đây là <b>tra một CSDL có thật</b>, không phải hỏi máy đoán.
            Nhân vật nào CSDL có mà chapter không có sẽ bị <b>loại thẳng</b> — CSDL một bộ có thể
            tới 500 nhân vật trong khi chapter này chỉ có vài cái tên.
          </p>
          <div className="hang-cong-cu">
            <Button icon="quay" dangChay={dangTra}
                    disabled={dangBan || !onDoiChieuTen || !tenTruyen.trim()}
                    lyDoKhoa={!tenTruyen.trim() ? 'Nhập tên bộ truyện ở ô trên trước' : undefined}
                    onClick={traCuu}>
              {dangTra ? 'Đang tra…' : 'Tra CSDL nhân vật'}
            </Button>
          </div>

          {ketQuaTra?.khong_dung_duoc && (
            <Alert sac="canh" tieuDe="Không tra được">
              {ketQuaTra.khong_dung_duoc} Bảng danh xưng ở trên <b>vẫn dùng bình thường</b> — nó
              không phụ thuộc vào nguồn ngoài.
            </Alert>
          )}

          {ketQuaTra && !ketQuaTra.khong_dung_duoc && (
            <Alert sac={ketQuaTra.khop?.length ? 'tin' : 'canh'}
                   tieuDe={ketQuaTra.khop?.length
                     ? `${ketQuaTra.khop.length} danh xưng khớp CSDL`
                     : 'Không danh xưng nào của chapter khớp CSDL'}>
              {ketQuaTra.khop?.length ? (
                <ul className="tom-tat-xuat">
                  {ketQuaTra.khop.map((k) => (
                    <li key={k.danh_xung}>
                      <b>{k.danh_xung}</b> → {k.ten_day_du || '—'}
                      {k.ten_goc && <> · <i>{k.ten_goc}</i></>}
                      <span className="ghi-chu"> ({k.ly_do})</span>
                    </li>
                  ))}
                </ul>
              ) : (
                <>Có thể chapter này không có tên nhân vật, hoặc CSDL ghi khác cách chapter viết.
                Cứ thêm tay như bình thường.</>
              )}
              {ketQuaTra.bo_qua > 0 && (
                <div className="ghi-chu">
                  Đã loại <b>{ketQuaTra.bo_qua}</b> nhân vật CSDL có mà chapter này không có.
                </div>
              )}
            </Alert>
          )}

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
