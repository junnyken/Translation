import { useEffect, useState } from 'react'
import Icon from '../ui/Icon.jsx'

/** Nhãn + màu của tình trạng khung chữ — đúng câu của mockup. */
export function tinhTrangKhung(fit) {
  if (fit === 'overflow_warning') return { nhan: 'Tràn khung', sac: 'canh' }
  if (fit === 'font_missing_glyph') return { nhan: 'Font thiếu chữ', sac: 'loi' }
  return { nhan: 'Vừa khung', sac: 'ok' }
}

const LOI_NHAN = {
  overflow_warning: 'Chữ dài hơn khung. Thử nới khung, giảm cỡ chữ hoặc rút gọn bản dịch.',
  font_missing_glyph: 'Font này thiếu một số chữ trong bản dịch. Hãy chọn font khác.',
}

function Mau({ nhan, ma, ghiChu }) {
  return (
    <div className="cv-f">
      <span className="cv-nhan">{nhan}{ghiChu && <span className="cv-nho"> · {ghiChu}</span>}</span>
      <div className="cv-mau">
        {ma
          ? <><span className="cv-o-mau" style={{ background: ma }} aria-hidden="true" /><span className="cv-nho">{ma}</span></>
          : <span className="cv-nho">mặc định</span>}
      </div>
    </div>
  )
}

/** Bảng Thuộc tính của khung chữ đang chọn. */
export default function ThuocTinh({
  region, fontFamilies, coMin, coMax, dangBan, ban, onBan, onLuu,
  onDoiFont, onGhim, onBoGhim, daGhim, onDichLai, onDocLai,
}) {
  const [co, setCo] = useState(region?.font_size ?? coMax)
  useEffect(() => { setCo(region?.font_size ?? coMax) }, [region?.id, region?.font_size, coMax])

  if (!region) {
    return (
      <div className="cv-muc">
        <h3>Thuộc tính</h3>
        <p className="cv-nho">Chọn một khung chữ trên trang để sửa chữ gốc, bản dịch, font và màu.</p>
      </div>
    )
  }

  const raw = ban?.raw ?? region.raw_text ?? ''
  const text = ban?.text ?? region.translated_text ?? ''
  const daDoi = raw !== (region.raw_text ?? '') || text !== (region.translated_text ?? '')
  const tt = tinhTrangKhung(region.fit_status)
  const font = region.font_family ?? fontFamilies?.[0] ?? ''
  const fonts = fontFamilies?.includes(font) || !font ? fontFamilies ?? [] : [font, ...fontFamilies]

  return (
    <div className="cv-muc">
      <h3>
        Thuộc tính
        <span className={`the-tt the-tt-${tt.sac}`}>{tt.nhan}</span>
      </h3>
      {LOI_NHAN[region.fit_status] && (
        <div className="cv-canh" role="alert">
          <Icon ten="canh" co={16} />
          <span>{LOI_NHAN[region.fit_status]}</span>
        </div>
      )}
      <div className="cv-f">
        <label htmlFor="cv-chu-goc">Chữ gốc</label>
        <textarea
          id="cv-chu-goc" className="cv-o" rows={2} value={raw} disabled={dangBan}
          onChange={(e) => onBan({ raw: e.target.value, text })}
          placeholder="Chưa đọc được chữ nào…"
        />
      </div>
      <div className="cv-f">
        <label htmlFor="cv-ban-dich">Bản dịch</label>
        <textarea
          id="cv-ban-dich" className="cv-o" rows={3} value={text} disabled={dangBan}
          onChange={(e) => onBan({ raw, text: e.target.value })}
          placeholder="Nhập bản dịch…"
        />
        {daDoi && (
          <button type="button" className="nut nut-chinh cv-nut-luu" disabled={dangBan}
                  onClick={onLuu}>
            Lưu thay đổi
          </button>
        )}
      </div>
      <div className="cv-f">
        <label htmlFor="cv-font">Font</label>
        <select id="cv-font" className="cv-o" value={font} disabled={dangBan}
                onChange={(e) => onDoiFont(e.target.value)}>
          {fonts.map((f) => <option key={f} value={f}>{f}</option>)}
        </select>
      </div>
      <div className="cv-f">
        <label htmlFor="cv-co-chu">Cỡ chữ</label>
        <div className="cv-hang">
          <input
            id="cv-co-chu" className="cv-o cv-o-so" type="number" min={coMin} max={coMax}
            value={co ?? region.font_size ?? coMax ?? ''} disabled={dangBan || daGhim}
            onChange={(e) => setCo(e.target.value)}
          />
          <span className="cv-nho">px</span>
          {daGhim
            ? (
              <button type="button" className="nut nut-phu" disabled={dangBan}
                      title="Cho máy tự chọn cỡ chữ vừa khung" onClick={onBoGhim}>
                Bỏ ghim
              </button>
            )
            : (
              <button type="button" className="nut nut-phu" disabled={dangBan || !(Number(co) > 0)}
                      title="Giữ cỡ chữ này, máy sẽ không tự đổi nữa"
                      onClick={() => onGhim(Number(co))}>
                Ghim cỡ
              </button>
            )}
        </div>
        <p className="cv-nho">Chưa ghim thì máy tự chọn cỡ lớn nhất còn vừa khung ({coMin}–{coMax}).</p>
      </div>
      <Mau nhan="Màu chữ" ma={region.text_color} ghiChu="đo từ chữ gốc" />
      <div className="cv-f">
        <span className="cv-nhan">Màu viền &amp; độ dày <span className="cv-nho">· đo từ chữ gốc</span></span>
        <div className="cv-mau">
          {region.stroke_color
            ? <><span className="cv-o-mau" style={{ background: region.stroke_color }} aria-hidden="true" /><span className="cv-nho">{region.stroke_color}</span></>
            : <span className="cv-nho">mặc định</span>}
          {region.stroke_width != null && <span className="cv-nho">· {region.stroke_width} px</span>}
        </div>
      </div>
      {region.xep_theo_hinh && <p className="cv-nho">Chữ đang xếp theo hình bong bóng.</p>}
      <div className="cv-nut-doc">
        <button type="button" className="nut nut-phu" disabled={dangBan} onClick={onDichLai}>
          Dịch lại vùng này
        </button>
        <button type="button" className="nut nut-phu" disabled={dangBan} onClick={onDocLai}>
          Đọc lại chữ gốc
        </button>
      </div>
      <p className="cv-nho">“Dịch lại” sẽ ghi đè bản dịch hiện tại, kể cả phần bạn vừa sửa tay.</p>
    </div>
  )
}
