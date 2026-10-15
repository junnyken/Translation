import Icon from '../ui/Icon.jsx'

export const TEN_HIEN_THI = {
  goc: 'Ảnh gốc', sach: 'Đã xoá chữ', dich: 'Chữ dịch', matna: 'Mặt nạ cọ',
}
const THU_TU_HIEN_THI = ['goc', 'sach', 'dich', 'matna']

const MAT = (
  <><path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z" /><circle cx="12" cy="12" r="3" /></>
)
const MAT_GACH = (
  <><path d="M3 3l18 18" /><path d="M10.6 5.1A9.7 9.7 0 0 1 12 5c6.4 0 10 7 10 7a17 17 0 0 1-3.2 4.1M6.6 6.6A17 17 0 0 0 2 12s3.6 7 10 7a9.7 9.7 0 0 0 4.4-1" /></>
)

/** Bảng Lớp: mỗi lớp có ẩn/hiện và độ mờ. `ghiChu[ten]` là dòng nhỏ khi lớp trống/lỗi. */
export function LopPanel({ trangThaiLop, onDoi, ghiChu }) {
  return (
    <div className="cv-muc">
      <h3>Lớp</h3>
      {THU_TU_HIEN_THI.map((ten) => {
        const tt = trangThaiLop[ten]
        const nhan = TEN_HIEN_THI[ten]
        return (
          <div key={ten} className={`cv-lop${tt.hien ? '' : ' tat'}`}>
            <button
              type="button" className="nut nut-ghost cv-mat"
              aria-label={`${tt.hien ? 'Ẩn' : 'Hiện'} lớp ${nhan}`}
              aria-pressed={tt.hien}
              onClick={() => onDoi(ten, { hien: !tt.hien })}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor"
                   strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
                {tt.hien ? MAT : MAT_GACH}
              </svg>
            </button>
            <span className="cv-ten-lop">
              {nhan}
              {!tt.hien && <span className="cv-nho"> (đang ẩn)</span>}
              {ghiChu?.[ten] && <span className="cv-nho cv-ghi-chu-lop">{ghiChu[ten]}</span>}
            </span>
            <input
              type="range" min="0" max="100" value={Math.round(tt.doMo * 100)}
              aria-label={`Độ mờ ${nhan}`}
              onChange={(e) => onDoi(ten, { doMo: Number(e.target.value) / 100 })}
            />
          </div>
        )
      })}
    </div>
  )
}

/** Bảng Cọ xoá chữ: cỡ cọ, Tô/Tẩy, nút xoá. Cách xoá (LaMa/SDXL) do máy chủ quyết, ở đây chỉ báo. */
export function BangCo({
  co, onCo, cheDo, onCheDo, dangBan, coTo, onXoa, onBo,
}) {
  return (
    <div className="cv-muc">
      <h3>Cọ xoá chữ</h3>
      <div className="cv-f">
        <label htmlFor="cv-co-co">
          Cỡ cọ <b className="cv-gia-tri">{co}px</b>
        </label>
        <input id="cv-co-co" type="range" min="4" max="120" value={co}
               onChange={(e) => onCo(Number(e.target.value))} className="cv-keo" />
      </div>
      <div className="cv-f">
        <span className="cv-nhan">Chế độ</span>
        <div className="cv-seg" role="radiogroup" aria-label="Chế độ cọ">
          <label>
            <input type="radio" name="cv-che-do" checked={cheDo === 'but'} onChange={() => onCheDo('but')} />
            Tô
          </label>
          <label>
            <input type="radio" name="cv-che-do" checked={cheDo === 'tay'} onChange={() => onCheDo('tay')} />
            Tẩy
          </label>
        </div>
      </div>
      <p className="cv-nho cv-thong-tin">
        <Icon ten="dong-ho" co={13} />{' '}
        Máy chủ tự chọn cách xoá chữ (LaMa hoặc SDXL) theo cấu hình, bạn không cần chọn.
      </p>
      <div className="cv-nut-doc">
        <button type="button" className="nut nut-chinh" disabled={dangBan || !coTo} onClick={onXoa}>
          Xoá vùng đã tô
        </button>
        <button type="button" className="nut nut-phu" disabled={dangBan || !coTo} onClick={onBo}>
          Bỏ mặt nạ
        </button>
      </div>
      {!coTo && <p className="cv-nho">Tô lên phần chữ còn sót rồi bấm “Xoá vùng đã tô”.</p>}
    </div>
  )
}
