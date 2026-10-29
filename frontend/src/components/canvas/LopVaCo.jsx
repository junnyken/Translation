import Icon from '../ui/Icon.jsx'

export const TEN_HIEN_THI = {
  goc: 'Ảnh gốc', sach: 'Đã xoá chữ', dich: 'Chữ dịch', matna: 'Mặt nạ cọ',
}
const THU_TU_HIEN_THI = ['goc', 'sach', 'dich', 'matna']

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
              title={`${tt.hien ? 'Ẩn' : 'Hiện'} lớp ${nhan}`}
              aria-pressed={tt.hien}
              onClick={() => onDoi(ten, { hien: !tt.hien })}
            >
              <Icon ten={tt.hien ? 'eye' : 'eye-off'} co={16} />
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

/** Bảng Cọ xoá chữ: cỡ cọ, Tô/Tẩy, nút xoá. Cách xoá do máy chủ quyết, ở đây chỉ báo. */
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
        <Icon ten="dong-ho" co={16} />{' '}
        Hệ thống tự động chọn mô hình tái tạo nền thông minh theo cấu hình, bạn không cần chọn.
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
