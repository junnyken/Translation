import { useEffect, useState } from 'react'
import { LY_DO_VUNG_AN_TOAN, NGUON_VUNG_AN_TOAN } from '../lib/status-presentation.js'
import StatusBadge from './ui/StatusBadge.jsx'
import ZoomCropModal from './ZoomCropModal.jsx'

/** Bảng sửa 1 vùng: chữ gốc, bản dịch, font, cỡ chữ + các nút chạy lại từng bước. */
export default function RegionPanel({
  pageId, region, vungAnToan, fontFamilies, coMin, coMax, dangBan,
  onLuu, onDichLai, onDocLai, onCanhLai, onTinhLaiVungAnToan,
  // E21b — báo "đang có thay đổi chưa lưu" lên App, và đưa hàm lưu ra ngoài qua `dieuKhien`.
  //
  // Vì sao cần: App gắn `key={region.id}` cho bảng này nên đổi vùng là REMOUNT — trước E21b chữ
  // đang gõ dở biến mất im lặng, không một lời hỏi. App phải biết còn thay đổi chưa lưu để chặn
  // lại, và phải gọi được `luu()` nếu người dùng chọn "Lưu" trong hộp thoại xác nhận.
  onDoiTrangThaiSua, dieuKhien,
}) {
  const [text, setText] = useState(region.translated_text ?? '')
  const [chuGoc, setChuGoc] = useState(region.raw_text ?? '')
  const [font, setFont] = useState(region.font_family ?? fontFamilies[0])
  const [ghimCo, setGhimCo] = useState(false)
  const [co, setCo] = useState(region.font_size ?? coMax)
  const [dangPhongTo, setDangPhongTo] = useState(false)

  // Đổi vùng đang chọn (hoặc dữ liệu mới về từ server) thì nạp lại form.
  useEffect(() => {
    setText(region.translated_text ?? '')
    setChuGoc(region.raw_text ?? '')
    setFont(region.font_family ?? fontFamilies[0])
    setCo(region.font_size ?? coMax)
    setGhimCo(false)
  }, [region.id, region.translated_text, region.raw_text, region.font_family, region.font_size,
      fontFamilies, coMax])

  const daDoi =
    text !== (region.translated_text ?? '')
    || chuGoc !== (region.raw_text ?? '')
    || font !== (region.font_family ?? fontFamilies[0]) || ghimCo

  const luu = () => {
    const thayDoi = {}
    if (text !== (region.translated_text ?? '')) thayDoi.translated_text = text
    if (chuGoc !== (region.raw_text ?? '')) thayDoi.raw_text = chuGoc
    if (font !== (region.font_family ?? fontFamilies[0])) thayDoi.font_family = font
    if (ghimCo) thayDoi.font_size = Number(co)
    if (Object.keys(thayDoi).length) onLuu(region.id, thayDoi)
  }

  // E21b — đẩy trạng thái "chưa lưu" lên App để nó chặn việc đổi vùng làm mất chữ đang gõ.
  useEffect(() => {
    onDoiTrangThaiSua?.(daDoi)
    // Gỡ bảng (đổi vùng / đóng) thì App không còn gì chưa lưu để giữ nữa.
    return () => onDoiTrangThaiSua?.(false)
  }, [daDoi, onDoiTrangThaiSua])

  // Giữ hàm `luu` mới nhất cho App gọi từ hộp thoại xác nhận. KHÔNG dùng mảng phụ thuộc: `luu`
  // đóng gói state của lần render này, cần cập nhật sau MỌI lần render thì App mới lưu đúng thứ
  // người dùng vừa gõ.
  useEffect(() => {
    if (dieuKhien) dieuKhien.current = { daDoi, luu }
  })

  return (
    <div className="bang-sua">
    {vungAnToan && (
      <div className="the-hinh-bong-bong">
        <b>{NGUON_VUNG_AN_TOAN[vungAnToan.source]?.nhan ?? vungAnToan.source}</b>
        <p className="ghi-chu">
          {(vungAnToan.reason_codes ?? [])
            .map((m) => LY_DO_VUNG_AN_TOAN[m] ?? m)
            .join(' · ')}
        </p>
        <p className="ghi-chu">
          Đây là <b>chuyện bố cục</b>, tách khỏi việc chữ có vừa khung hay không. Một vùng vẫn
          có thể vừa khít trong khung dự phòng mà vị trí trong bong bóng vẫn nên xem lại.
        </p>
        {onTinhLaiVungAnToan && (
          // A1: bố cục của một trang CHỈ được tính lúc xoá chữ. Không có nút này thì bản sửa
          // hình học nào cũng chỉ ăn vào trang tải lên MỚI, còn chapter đang làm dở thì không
          // có đường nào chạm tới — người dùng phải xoá đi tải lại từ đầu.
          <button type="button" className="nut nut-phu" disabled={dangBan}
                  onClick={onTinhLaiVungAnToan}>
            {dangBan ? 'Đang tính lại…' : 'Tính lại bố cục cả trang'}
          </button>
        )}
      </div>
    )}

      <div className="hang-tieu-de">
        <h3>Vùng {region.reading_order ?? '?'}</h3>
        <div className="nhom-nhan">
          <StatusBadge loai="canh_chu" trangThai={region.fit_status} />
          {region.ocr_status === 'needs_manual'
            && <StatusBadge loai="doc_chu" trangThai="needs_manual" />}
          {region.status === 'low_confidence'
            && <StatusBadge loai="vung" trangThai="low_confidence" />}
          {region.translation_status === 'fallback_used'
            && <StatusBadge loai="dich" trangThai="fallback_used" />}
        </div>
      </div>

      <div className="dong-lich-su">
        Chữ gốc: <b>{region.ocr_edited_by_user ? 'đã sửa tay' : 'máy đọc'}</b>
        {' · '}
        Bản dịch: <b>{region.translation_edited_by_user ? 'đã sửa tay' : 'máy dịch'}</b>
        {' · '}
        Canh chữ: <b>{region.typeset_edited_by_user ? 'đã sửa tay' : 'máy canh'}</b>
      </div>

      <div className="nhan">
        <div className="hang-nhan-nut">
          <label htmlFor={`chu-goc-${region.id}`}>Chữ gốc đọc được</label>
          <button type="button" className="lien-ket" disabled={dangBan}
                  onClick={() => setDangPhongTo(true)}>
            Phóng to đối chiếu
          </button>
        </div>
        <textarea
          id={`chu-goc-${region.id}`}
          rows={3}
          value={chuGoc}
          onChange={(e) => setChuGoc(e.target.value)}
          disabled={dangBan}
          placeholder="Chưa đọc được chữ nào…"
        />
        <p className="ghi-chu">
          Sửa chữ này <b>không</b> tự dịch lại — bấm "Dịch lại" bên dưới sau khi lưu.
        </p>
      </div>

      {dangPhongTo && (
        <ZoomCropModal pageId={pageId} bbox={region.bbox} onClose={() => setDangPhongTo(false)} />
      )}

      <label className="nhan">
        Bản dịch tiếng Việt
        <textarea
          rows={4}
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={dangBan}
          placeholder="Nhập bản dịch…"
        />
      </label>

      <div className="hang">
        <label className="nhan cot">
          Kiểu chữ
          <select value={font} onChange={(e) => setFont(e.target.value)} disabled={dangBan}>
            {fontFamilies.map((f) => (
              <option key={f} value={f}>{f}</option>
            ))}
          </select>
        </label>
        <label className="nhan cot">
          Cỡ chữ
          <div className="hang-co">
            <input
              type="checkbox"
              checked={ghimCo}
              onChange={(e) => setGhimCo(e.target.checked)}
              disabled={dangBan}
              id={`ghim-${region.id}`}
            />
            <label htmlFor={`ghim-${region.id}`} className="ghi-chu">tự chọn</label>
            <input
              type="number"
              min={coMin}
              max={coMax}
              value={co}
              onChange={(e) => setCo(e.target.value)}
              disabled={dangBan || !ghimCo}
            />
          </div>
        </label>
      </div>
      <p className="ghi-chu">
        Bỏ trống ô “tự chọn” thì hệ thống tự tìm cỡ lớn nhất còn vừa khung (từ {coMin} đến {coMax}).
      </p>

      <div className="hang nut">
        <button className="chinh" onClick={luu} disabled={dangBan || !daDoi}>
          Lưu &amp; canh lại
        </button>
        <button onClick={() => onCanhLai(region.id)} disabled={dangBan}>Canh lại</button>
        <button onClick={() => onDocLai(region.id)} disabled={dangBan}>Đọc lại chữ gốc</button>
        <button onClick={() => onDichLai(region.id)} disabled={dangBan}>Dịch lại</button>
      </div>
      <p className="ghi-chu">
        “Dịch lại” sẽ <b>ghi đè</b> bản dịch hiện tại, kể cả phần bạn vừa sửa tay.
      </p>
    </div>
  )
}
