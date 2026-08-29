import { useEffect, useState } from 'react'
import Alert from '../ui/Alert.jsx'
import Button from '../ui/Button.jsx'
import { Field } from '../ui/Field.jsx'
import StatusBadge from '../ui/StatusBadge.jsx'
import { GIONG_NOI } from '../../lib/status-presentation.js'

/** Hàng đợi rà soát từng chỗ (E13 · D4).
 *
 * Không dựng bộ sửa thứ hai: chỗ này chỉ sửa **bản dịch của một vùng**, rồi giao lại cho đúng
 * đường canh chữ của M7. Mỗi việc phải nói rõ **vì sao** nó được nêu và bản dịch hiện tại là gì —
 * người dùng cần đủ dữ kiện để quyết, chứ không phải bấm theo lời máy.
 */
export default function ConsistencyReviewQueue({ viec, hoSoGiong = [], dangBan, onAp, onGiuNguyen, onBoQua }) {
  const [chiSo, setChiSo] = useState(0)
  const [ban, setBan] = useState('')

  const v = viec[chiSo] || null
  const cu = v?.status === 'stale'

  useEffect(() => {
    setBan(v?.proposed_text || v?.current_text_snapshot || '')
  }, [v?.id, v?.proposed_text, v?.current_text_snapshot])

  useEffect(() => {
    if (chiSo >= viec.length) setChiSo(Math.max(viec.length - 1, 0))
  }, [viec.length, chiSo])

  if (viec.length === 0) {
    return (
      <section className="the-lon">
        <Alert sac="ok" tieuDe="Không còn chỗ nào cần xem">
          Theo các thuật ngữ đã duyệt thì bản dịch hiện tại đã nhất quán. Điều này{' '}
          <b>không</b> có nghĩa là bản dịch đã đúng nghĩa — chỉ là không còn chỗ lệch thuật ngữ.
        </Alert>
      </section>
    )
  }

  const e = v.evidence || {}
  const giongDangBat = hoSoGiong.filter((g) => g.status === 'active')
  const daDoi = ban.trim() !== (v.current_text_snapshot || '').trim()

  return (
    <section className="the-lon" aria-labelledby="tieu-de-hang-doi">
      <header className="the-dau">
        <div className="hang-tieu-de">
          <h2 id="tieu-de-hang-doi">Rà soát nhất quán</h2>
          <StatusBadge loai="viec_nhat_quan" trangThai={v.status} />
        </div>
        <p className="ghi-chu">Chỗ {chiSo + 1} / {viec.length}</p>
      </header>

      <div className="hang nut">
        <Button icon="mui-ten-trai" disabled={chiSo === 0}
                onClick={() => setChiSo((i) => i - 1)}>Trước</Button>
        <Button icon="mui-ten-phai" disabled={chiSo >= viec.length - 1}
                onClick={() => setChiSo((i) => i + 1)}>Sau</Button>
      </div>

      <div className="the-bang-chung">
        <StatusBadge loai="loai_viec_nhat_quan" trangThai={v.task_type} hienMoTa />
        {e.ly_do && <p className="dong-ly-do">{e.ly_do}</p>}

        <dl className="ds-bang-chung">
          {e.thuat_ngu_nguon && (
            <>
              <dt>Chữ gốc khớp</dt>
              <dd><code>{e.thuat_ngu_nguon}</code></dd>
            </>
          )}
          {e.thuat_ngu_da_duyet && (
            <>
              <dt>Cách dịch đã chốt</dt>
              <dd><b>{e.thuat_ngu_da_duyet}</b></dd>
            </>
          )}
          {e.bien_the_bi_cam && (
            <>
              <dt>Cách dịch bạn đã cấm</dt>
              <dd><b>{e.bien_the_bi_cam}</b></dd>
            </>
          )}
          {e.dinh_nghia && (
            <>
              <dt>Nghĩa</dt>
              <dd>{e.dinh_nghia}</dd>
            </>
          )}
          <dt>Bản dịch hiện tại</dt>
          <dd className="chu-goc">{v.current_text_snapshot || <i>(trống)</i>}</dd>
        </dl>
      </div>

      {cu ? (
        <Alert sac="canh" tieuDe="Bản dịch đã thay đổi từ lần quét">
          Gợi ý này tính trên một bản dịch không còn tồn tại. Áp nó vào sẽ xoá mất phần vừa sửa —
          hãy <b>rà soát lại</b> rồi xem lại chỗ này.
        </Alert>
      ) : (
        <>
          {giongDangBat.length > 0 && (
            <div className="the-nhac-giong">
              <h3 className="tieu-de-nho">Giọng nhân vật bạn đã đặt</h3>
              <ul className="ds-nhac-giong">
                {giongDangBat.map((g) => (
                  <li key={g.id}>
                    <b>{g.character_name}</b>
                    <span className="ghi-chu"> · {GIONG_NOI[g.speech_register]
                      ?? g.speech_register}</span>
                    {g.vietnamese_pronoun_guidance && <div>{g.vietnamese_pronoun_guidance}</div>}
                    {g.tone_note && <div className="ghi-chu">{g.tone_note}</div>}
                  </li>
                ))}
              </ul>
              <p className="ghi-chu">
                Hiện ra để bạn tự cân nhắc khi sửa. Hệ thống <b>không</b> tự sửa lời thoại theo
                những hồ sơ này, và cũng không đoán vùng này là ai đang nói.
              </p>
            </div>
          )}

          <Field
            nhan="Bản dịch cho vùng này"
            moTa="Sửa trực tiếp ở đây rồi bấm áp dụng. Hệ thống không tự viết thay bạn."
          >
            {(a) => (
              <textarea className="o" rows={3} {...a} value={ban}
                        onChange={(ev) => setBan(ev.target.value)} disabled={dangBan} />
            )}
          </Field>

          <Alert sac="tin" tieuDe="Sau khi áp dụng">
            Vùng này sẽ được <b>căn chữ lại</b> (chỉ vùng này, không phải cả trang). Cỡ chữ bạn đã
            ghim vẫn giữ nguyên; nếu chữ mới không vừa, hệ thống sẽ báo <b>tràn khung</b> chứ không
            tự thu nhỏ.
          </Alert>

          <div className="hang nut">
            <Button kieu="chinh" icon="tich" dangChay={dangBan}
                    lyDoKhoa={!ban.trim() ? 'Chưa có nội dung để áp dụng' : undefined}
                    onClick={() => onAp(v.id, ban)}>
              {daDoi ? 'Áp dụng bản đã sửa' : 'Áp dụng'}
            </Button>
            <Button icon="tam-dung" disabled={dangBan}
                    onClick={() => onGiuNguyen(v.id)}>Giữ bản hiện tại</Button>
            <Button icon="x" disabled={dangBan}
                    onClick={() => onBoQua(v.id)}>Không áp dụng</Button>
          </div>
        </>
      )}
    </section>
  )
}
