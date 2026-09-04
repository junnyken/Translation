import { useState } from 'react'
import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'
import Dialog from '../ui/Dialog.jsx'
import EmptyState from '../ui/EmptyState.jsx'
import { Input, Select, Field } from '../ui/Field.jsx'
import StatusBadge from '../ui/StatusBadge.jsx'
import TermCandidatePanel from './TermCandidatePanel.jsx'
import { LOAI_THUAT_NGU } from '../../lib/status-presentation.js'

const RONG = {
  source_term: '', target_term: '', term_type: 'character_name',
  definition: '', usage_note: '', prohibited_variants: '',
}

/** Bảng thuật ngữ của MỘT chapter (E13 · D2).
 *
 * Cố ý không phải "từ điển tìm-và-thay": mỗi mục bắt buộc có phần giải nghĩa, vì người duyệt sau
 * này cần biết thuật ngữ đó nghĩa là gì mới quyết được từng chỗ. Và thuật ngữ chỉ thuộc chapter
 * này — cách dịch hợp ở truyện này có thể sai hẳn ở truyện khác.
 */
export default function GlossaryManager({
  danhSach, dangBan, onThem, onDuyet, onCat, onSua,
  onTimUngVien, onXinGoiY, onDocGoiY, onDoiChieuTen,
}) {
  const [moForm, setMoForm] = useState(false)
  const [form, setForm] = useState(RONG)
  const [loiForm, setLoiForm] = useState(null)
  const [dangSua, setDangSua] = useState(null)
  // Bằng chứng của ứng viên đang mở form — hiện ngay trong form để quyết được mà không phải
  // nhớ lại bảng phía trên.
  const [bangChung, setBangChung] = useState(null)

  const dat = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const guiForm = async () => {
    setLoiForm(null)
    for (const [k, nhan] of [['source_term', 'Thuật ngữ gốc'], ['target_term', 'Cách dịch'],
                             ['definition', 'Giải nghĩa']]) {
      if (!form[k].trim()) return setLoiForm(`Thiếu ${nhan.toLowerCase()}.`)
    }
    const du_lieu = {
      source_term: form.source_term.trim(),
      target_term: form.target_term.trim(),
      term_type: form.term_type,
      definition: form.definition.trim(),
      usage_note: form.usage_note.trim() || null,
      prohibited_variants: form.prohibited_variants
        .split(',').map((v) => v.trim()).filter(Boolean),
    }
    try {
      if (dangSua) await onSua(dangSua, du_lieu)
      else await onThem(du_lieu)
      setMoForm(false)
      setForm(RONG)
      setDangSua(null)
    } catch (e) {
      setLoiForm(e.message)
    }
  }

  /** Mở form đã điền sẵn phần MÁY biết. Hai ô quyết định vẫn để trống cho người. */
  const moTuUngVien = (uv, goiY) => {
    setDangSua(null)
    setForm({
      ...RONG,
      source_term: uv.source_term,
      term_type: goiY?.term_type || uv.type_guess,
      // Gợi ý của mô hình (nếu có) chỉ là bản nháp để sửa — KHÔNG phải quyết định của bạn.
      target_term: goiY?.target_term || '',
      definition: goiY?.note || '',
    })
    setBangChung({ ...uv, goiY })
    setLoiForm(null)
    setMoForm(true)
  }

  const moSua = (m) => {
    setDangSua(m.id)
    setForm({
      source_term: m.source_term, target_term: m.target_term, term_type: m.term_type,
      definition: m.definition, usage_note: m.usage_note || '',
      prohibited_variants: (m.prohibited_variants || []).join(', '),
    })
    setLoiForm(null)
    setBangChung(null)
    setMoForm(true)
  }

  const daDuyet = danhSach.filter((m) => m.status === 'approved').length

  return (
    <section className="the-lon" aria-labelledby="tieu-de-thuat-ngu">
      <header className="the-dau">
        <h2 id="tieu-de-thuat-ngu">Thuật ngữ của chapter</h2>
        <p>
          Chốt cách dịch cho tên nhân vật, vật phẩm, chiêu thức… rồi hệ thống sẽ tìm những chỗ
          chưa theo. Thuật ngữ chỉ áp dụng cho <b>chapter này</b>.
        </p>
      </header>

      <div className="hang-cong-cu">
        <span className="ghi-chu">
          {danhSach.length} thuật ngữ · <b>{daDuyet}</b> đã duyệt (chỉ mục đã duyệt mới được dùng
          khi rà soát)
        </span>
        <Button kieu="chinh" icon="cong" disabled={dangBan}
                onClick={() => {
            setDangSua(null); setForm(RONG); setLoiForm(null); setBangChung(null); setMoForm(true)
          }}>
          Thêm thuật ngữ
        </Button>
      </div>

      {onTimUngVien && (
        <TermCandidatePanel
          dangBan={dangBan}
          onTim={onTimUngVien}
          onChon={moTuUngVien}
          onXinGoiY={onXinGoiY}
          onDocGoiY={onDocGoiY}
          onDoiChieuTen={onDoiChieuTen}
        />
      )}

      {danhSach.length === 0 ? (
        <EmptyState
          icon="sach"
          tieuDe="Chưa có thuật ngữ nào"
          moTa="Thêm vài thuật ngữ hay lặp lại trong chapter — tên nhân vật, vật phẩm, chiêu thức — rồi bấm rà soát để tìm chỗ dịch chưa nhất quán."
        />
      ) : (
        <div className="bang-cuon">
          <table className="bang">
            <thead>
              <tr>
                <th scope="col">Thuật ngữ gốc</th>
                <th scope="col">Cách dịch đã chốt</th>
                <th scope="col">Loại</th>
                <th scope="col">Trạng thái</th>
                <th scope="col"><span className="an-nhin">Thao tác</span></th>
              </tr>
            </thead>
            <tbody>
              {danhSach.map((m) => (
                <tr key={m.id}>
                  <td><b>{m.source_term}</b></td>
                  <td>{m.target_term}</td>
                  <td>{LOAI_THUAT_NGU[m.term_type] || m.term_type}</td>
                  <td><StatusBadge loai="thuat_ngu" trangThai={m.status} /></td>
                  <td className="o-thao-tac">
                    {m.status !== 'approved' && m.status !== 'archived' && (
                      <Button icon="tich" disabled={dangBan} onClick={() => onDuyet(m.id)}>
                        Duyệt
                      </Button>
                    )}
                    <Button icon="but" disabled={dangBan} onClick={() => moSua(m)}>Sửa</Button>
                    {m.status !== 'archived' && (
                      <Button icon="tam-dung" disabled={dangBan} onClick={() => onCat(m.id)}>
                        Cất đi
                      </Button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {moForm && (
        <Dialog
          tieuDe={dangSua ? 'Sửa thuật ngữ' : 'Thêm thuật ngữ'}
          onDong={() => setMoForm(false)}
          chan={[
            <Button key="huy" onClick={() => setMoForm(false)}>Huỷ</Button>,
            <Button key="luu" kieu="chinh" dangChay={dangBan} onClick={guiForm}>
              {dangSua ? 'Lưu' : 'Thêm'}
            </Button>,
          ]}
        >
          {dangSua && (
            <Alert sac="canh" tieuDe="Sửa nội dung đã duyệt sẽ cần duyệt lại">
              Đổi thuật ngữ gốc, cách dịch, loại hay phần giải nghĩa sẽ đưa mục này về <b>nháp</b> —
              vì cả chapter đang dựa vào luật này. Sửa riêng phần ghi chú thì không cần duyệt lại.
            </Alert>
          )}
          {loiForm && <Alert sac="loi" tieuDe="Chưa lưu được">{loiForm}</Alert>}

          {bangChung && (
            <Alert sac="tin" tieuDe={`Tìm thấy ${bangChung.count} lần trong chapter`}>
              {bangChung.quotes.map((q) => (
                <div key={q.region_id} className="ghi-chu">“{q.text}” (trang {q.page_order})</div>
              ))}
              {bangChung.goiY && (
                <div className="ghi-chu">
                  Phần tiếng Việt điền sẵn là <b>gợi ý của mô hình, chưa được duyệt</b> — sửa lại
                  cho đúng ý bạn trước khi lưu.
                </div>
              )}
            </Alert>
          )}

          <Input nhan="Thuật ngữ gốc" batBuoc value={form.source_term} onChange={dat('source_term')}
                 moTa="Đúng như xuất hiện trong chữ gốc, ví dụ: magic potion" />
          <Input nhan="Cách dịch đã chốt" batBuoc value={form.target_term} onChange={dat('target_term')}
                 moTa="Bản tiếng Việt bạn muốn dùng thống nhất cả chapter" />
          <Select nhan="Loại" value={form.term_type} onChange={dat('term_type')}>
            {Object.entries(LOAI_THUAT_NGU).map(([ma, nhan]) => (
              <option key={ma} value={ma}>{nhan}</option>
            ))}
          </Select>
          <Field nhan="Giải nghĩa" batBuoc
                 moTa="Bắt buộc. Một cặp chữ trần trụi không đủ — lúc rà soát bạn cần biết thuật ngữ này nghĩa là gì mới quyết được.">
            {(a) => <textarea className="o" rows={2} {...a} value={form.definition}
                              onChange={dat('definition')} />}
          </Field>
          <Field nhan="Ghi chú cách dùng"
                 moTa="Tuỳ chọn. Ví dụ: chỉ dùng khi nói với hoàng gia.">
            {(a) => <textarea className="o" rows={2} {...a} value={form.usage_note}
                              onChange={dat('usage_note')} />}
          </Field>
          <Input nhan="Cách dịch KHÔNG dùng" value={form.prohibited_variants}
                 onChange={dat('prohibited_variants')}
                 moTa="Tuỳ chọn, ngăn nhau bằng dấu phẩy. Chỉ để cảnh báo — hệ thống không bao giờ tự thay chữ." />
        </Dialog>
      )}
    </section>
  )
}
