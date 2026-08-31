import { useState } from 'react'
import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'
import Dialog from '../ui/Dialog.jsx'
import EmptyState from '../ui/EmptyState.jsx'
import { Input, Select, Field } from '../ui/Field.jsx'
import StatusBadge from '../ui/StatusBadge.jsx'
import { GIONG_NOI } from '../../lib/status-presentation.js'

const RONG = {
  character_name: '', speech_register: 'neutral',
  vietnamese_pronoun_guidance: '', tone_note: '', aliases: '',
}

/** Hồ sơ giọng nhân vật (E13 · D3).
 *
 * Đây là **hướng dẫn biên tập do bạn đặt**, không phải suy luận của máy — nên cố ý KHÔNG có
 * thanh "độ tin cậy của AI". Máy không đọc truyện rồi đoán tính cách nhân vật, và không dùng hồ
 * sơ này để tự sửa lời thoại; nó chỉ hiện ra làm ngữ cảnh khi bạn rà soát.
 */
export default function VoiceProfileManager({
  danhSach, dangBan, onThem, onBat, onCat, onTimTinHieu,
}) {
  const [moForm, setMoForm] = useState(false)
  const [form, setForm] = useState(RONG)
  const [loiForm, setLoiForm] = useState(null)
  const [tinHieu, setTinHieu] = useState(null)
  const [dangTim, setDangTim] = useState(false)
  const [loiTim, setLoiTim] = useState(null)

  const dat = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const tim = async () => {
    setLoiTim(null)
    setDangTim(true)
    try {
      setTinHieu(await onTimTinHieu())
    } catch (e) {
      setLoiTim(e.message)
    } finally {
      setDangTim(false)
    }
  }

  /** Mở form đã điền sẵn phần rút được TỪ BẢN GỐC. Bạn vẫn sửa và quyết như thường. */
  const moTuTinHieu = (th, ten) => {
    setForm({
      ...RONG,
      character_name: ten || '',
      speech_register: th.speech_register_goi_y,
      vietnamese_pronoun_guidance: th.goi_y_xung_ho,
      tone_note: `Rút từ bản gốc: ${th.nhan} (${th.count} lần).`,
    })
    setLoiForm(null)
    setMoForm(true)
  }

  const gui = async () => {
    setLoiForm(null)
    if (!form.character_name.trim()) return setLoiForm('Thiếu tên nhân vật.')
    try {
      await onThem({
        character_name: form.character_name.trim(),
        speech_register: form.speech_register,
        vietnamese_pronoun_guidance: form.vietnamese_pronoun_guidance.trim() || null,
        tone_note: form.tone_note.trim() || null,
        aliases: form.aliases.split(',').map((v) => v.trim()).filter(Boolean),
      })
      setMoForm(false)
      setForm(RONG)
    } catch (e) {
      setLoiForm(e.message)
    }
  }

  return (
    <section className="the-lon" aria-labelledby="tieu-de-giong">
      <header className="the-dau">
        <h2 id="tieu-de-giong">Giọng nhân vật</h2>
        <p>
          Ghi lại cách một nhân vật nói: xưng hô, giọng điệu. Đây là <b>hướng dẫn của bạn</b>,
          không phải suy luận của máy — hệ thống chỉ hiện nó ra khi bạn rà soát, <b>không</b> tự
          sửa lời thoại theo nó.
        </p>
      </header>

      <div className="hang-cong-cu">
        <span className="ghi-chu">{danhSach.length} hồ sơ</span>
        <Button kieu="chinh" icon="cong" disabled={dangBan}
                onClick={() => { setForm(RONG); setLoiForm(null); setMoForm(true) }}>
          Thêm nhân vật
        </Button>
      </div>

      {onTimTinHieu && (
        <div className="khoi-phu">
          <div className="hang-cong-cu">
            <span className="ghi-chu">
              {tinHieu
                ? `Đã quét ${tinHieu.so_vung_co_chu}/${tinHieu.so_vung_da_quet} vùng chữ`
                : 'Máy đọc bản gốc tìm hậu tố kính ngữ và đại từ nhân xưng có thật'}
            </span>
            <Button icon="quay" dangChay={dangTim} disabled={dangBan} onClick={tim}>
              {dangTim ? 'Đang tìm…' : 'Tìm tín hiệu xưng hô'}
            </Button>
          </div>

          {loiTim && <Alert sac="loi" tieuDe="Không tìm được">{loiTim}</Alert>}

          {tinHieu?.trang_thai === 'chua_doc_chu' && (
            <Alert sac="canh" tieuDe="Chưa đọc được chữ trong chapter">
              Chạy xong bước đọc chữ rồi tìm lại. Lúc này <b>chưa kết luận được</b> chapter có hay
              không có tín hiệu xưng hô nào.
            </Alert>
          )}
          {tinHieu?.trang_thai === 'khong_thay' && (
            <Alert sac="tin" tieuDe="Không thấy tín hiệu xưng hô nào trong bản gốc">
              Bản gốc không có hậu tố kính ngữ hay đại từ nhân xưng đặc trưng. Cứ tự đặt xưng hô
              như bình thường.
            </Alert>
          )}

          {tinHieu?.tin_hieu?.length > 0 && (
            <>
              <p className="ghi-chu">
                Đây là <b>tín hiệu có thật trong bản gốc</b>, không phải suy đoán tính cách. Hệ
                thống chưa biết ai nói câu nào, nên đây là “trong chapter có tín hiệu này”, không
                phải “nhân vật X xưng thế này với Y”.
              </p>
              <ul className="ds-vi-sao">
                {tinHieu.tin_hieu.map((th) => (
                  <li key={th.ma}>
                    <b className="so-viec">{th.count}</b>
                    <div>
                      <div>{th.nhan} → gợi ý xưng hô: <b>{th.goi_y_xung_ho}</b></div>
                      {th.quotes.map((q) => (
                        <div key={q.region_id} className="ghi-chu">
                          “{q.text}” (trang {q.page_order})
                        </div>
                      ))}
                      <div className="hang nut">
                        {th.ten_lien_quan.length > 0 ? th.ten_lien_quan.map((ten) => (
                          <Button key={ten} icon="cong" disabled={dangBan}
                                  onClick={() => moTuTinHieu(th, ten)}>
                            Tạo hồ sơ cho {ten}
                          </Button>
                        )) : (
                          <Button icon="cong" disabled={dangBan}
                                  onClick={() => moTuTinHieu(th, '')}>
                            Dùng gợi ý này cho một nhân vật
                          </Button>
                        )}
                      </div>
                    </div>
                  </li>
                ))}
              </ul>
            </>
          )}
        </div>
      )}

      {danhSach.length === 0 ? (
        <EmptyState
          icon="sach"
          tieuDe="Chưa có hồ sơ nhân vật nào"
          moTa="Tuỳ chọn. Thêm khi bạn muốn nhớ rõ một nhân vật xưng hô thế nào để rà soát cho nhất quán."
        />
      ) : (
        <ul className="ds-ho-so">
          {danhSach.map((h) => (
            <li key={h.id} className="the-ho-so">
              <div className="hang-tieu-de">
                <b>{h.character_name}</b>
                <StatusBadge loai="ho_so_giong" trangThai={h.status} />
              </div>
              <p className="ghi-chu">Giọng: {GIONG_NOI[h.speech_register] || h.speech_register}</p>
              {h.vietnamese_pronoun_guidance && (
                <p className="dong-huong-dan">Xưng hô: {h.vietnamese_pronoun_guidance}</p>
              )}
              {h.tone_note && <p className="dong-huong-dan">Ghi chú: {h.tone_note}</p>}
              <div className="hang nut">
                {h.status !== 'active' && (
                  <Button icon="tich" disabled={dangBan} onClick={() => onBat(h.id)}>Dùng</Button>
                )}
                {h.status !== 'archived' && (
                  <Button icon="tam-dung" disabled={dangBan} onClick={() => onCat(h.id)}>
                    Cất đi
                  </Button>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {moForm && (
        <Dialog
          tieuDe="Thêm hồ sơ nhân vật"
          onDong={() => setMoForm(false)}
          chan={[
            <Button key="huy" onClick={() => setMoForm(false)}>Huỷ</Button>,
            <Button key="luu" kieu="chinh" dangChay={dangBan} onClick={gui}>Thêm</Button>,
          ]}
        >
          <Alert sac="tin" tieuDe="Đây là hướng dẫn của bạn">
            Hệ thống <b>không</b> tự đoán tính cách nhân vật và <b>không</b> tự sửa lời thoại theo
            hồ sơ này. Nó chỉ hiện ra để bạn nhớ khi rà soát.
          </Alert>
          {loiForm && <Alert sac="loi" tieuDe="Chưa lưu được">{loiForm}</Alert>}

          <Input nhan="Tên nhân vật" batBuoc value={form.character_name}
                 onChange={dat('character_name')} />
          <Input nhan="Tên gọi khác" value={form.aliases} onChange={dat('aliases')}
                 moTa="Tuỳ chọn, ngăn nhau bằng dấu phẩy." />
          <Select nhan="Giọng điệu" value={form.speech_register}
                  onChange={dat('speech_register')}>
            {Object.entries(GIONG_NOI).map(([ma, nhan]) => (
              <option key={ma} value={ma}>{nhan}</option>
            ))}
          </Select>
          <Input nhan="Cách xưng hô tiếng Việt" value={form.vietnamese_pronoun_guidance}
                 onChange={dat('vietnamese_pronoun_guidance')}
                 moTa='Ví dụ: xưng "ta", gọi người khác là "ngươi".' />
          <Field nhan="Ghi chú giọng điệu" moTa="Tuỳ chọn.">
            {(a) => <textarea className="o" rows={2} {...a} value={form.tone_note}
                              onChange={dat('tone_note')} />}
          </Field>
        </Dialog>
      )}
    </section>
  )
}
