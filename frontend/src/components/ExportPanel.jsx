import { useCallback, useEffect, useState } from 'react'
import * as api from '../api.js'

const DINH_DANG = [
  { ma: 'cbz', ten: 'CBZ — 1 file cho cả chapter', goiY: 'Đọc bằng ứng dụng truyện tranh (Tachiyomi, Perfect Viewer…)' },
  { ma: 'zip', ten: 'ZIP — 1 file nén thường', goiY: 'Giống CBZ nhưng đuôi .zip, mở bằng phần mềm giải nén nào cũng được' },
  { ma: 'png_single', ten: 'PNG — mỗi trang một ảnh', goiY: 'Lưu thành nhiều ảnh rời trên máy chủ; không tải một lần được' },
]

/** Bảng xuất chapter: xem trước cảnh báo → chọn định dạng → theo dõi → tải về. */
export default function ExportPanel({ projectId, tenProject }) {
  const [xemTruoc, setXemTruoc] = useState(null)
  const [dinhDang, setDinhDang] = useState('cbz')
  const [job, setJob] = useState(null)
  const [dangChay, setDangChay] = useState(false)
  const [loi, setLoi] = useState(null)

  const nap = useCallback(() => {
    setLoi(null)
    api.xemTruocXuat(projectId).then(setXemTruoc).catch((e) => setLoi(e.message))
  }, [projectId])

  useEffect(() => { nap() }, [nap])

  const xuat = async () => {
    setDangChay(true)
    setLoi(null)
    setJob(null)
    try {
      const { job_id } = await api.xuatChapter(projectId, dinhDang)
      const xong = await api.choXuatXong(job_id, { onTien: setJob })
      setJob(xong)
      nap()
    } catch (e) {
      setLoi(e.message)
    } finally {
      setDangChay(false)
    }
  }

  if (!xemTruoc) {
    return <section className="bang-xuat">{loi ? <div className="bang-loi">Lỗi: {loi}</div> : <p className="ghi-chu">Đang xem trước…</p>}</section>
  }

  const khongCoGiDeXuat = xemTruoc.page_count === 0
  const chon = DINH_DANG.find((d) => d.ma === dinhDang)

  return (
    <section className="bang-xuat">
      <h2>Xuất chapter{tenProject ? ` — ${tenProject}` : ''}</h2>

      <ul className="tom-tat-xuat">
        <li><b>{xemTruoc.page_count}</b> / {xemTruoc.total_page_count} trang sẽ được xuất</li>
        {xemTruoc.skipped_page_count > 0 && (
          <li className="canh-bao">
            <b>{xemTruoc.skipped_page_count}</b> trang sẽ bị <b>bỏ qua</b> vì chưa chèn chữ xong
          </li>
        )}
        {xemTruoc.overflow_warning_count > 0 && (
          <li className="canh-bao">
            <b>{xemTruoc.overflow_warning_count}</b> vùng còn <b>tràn khung</b> — xuất vẫn được,
            nhưng nên sửa tay trước cho đẹp
          </li>
        )}
        {xemTruoc.skipped_page_count === 0 && xemTruoc.overflow_warning_count === 0 && (
          <li className="on">Không có cảnh báo nào.</li>
        )}
      </ul>

      <label className="nhan">
        Định dạng
        <select value={dinhDang} onChange={(e) => setDinhDang(e.target.value)} disabled={dangChay}>
          {DINH_DANG.map((d) => <option key={d.ma} value={d.ma}>{d.ten}</option>)}
        </select>
      </label>
      <p className="ghi-chu">{chon.goiY}</p>

      <button className="chinh" onClick={xuat} disabled={dangChay || khongCoGiDeXuat}>
        {dangChay ? 'Đang xuất…' : 'Xuất chapter'}
      </button>
      {khongCoGiDeXuat && (
        <p className="ghi-chu">Chưa có trang nào chèn chữ xong nên chưa xuất được.</p>
      )}

      {job && (
        <div className="ket-qua-xuat">
          <div className="thanh-tien">
            <div
              className="thanh-tien-trong"
              style={{
                width: `${Math.round(((job.page_count || 0) / Math.max(xemTruoc.page_count, 1)) * 100)}%`,
              }}
            />
          </div>
          <p className="ghi-chu">
            {job.status === 'done'
              ? `Đã xuất ${job.page_count}/${xemTruoc.page_count} trang.`
              : `Đang xử lý… (${job.status})`}
          </p>

          {job.status === 'done' && job.error_log && (
            <div className="bang-tin canh-bao-o">Xuất xong nhưng có cảnh báo: {job.error_log}</div>
          )}

          {job.status === 'done' && job.format !== 'png_single' && (
            <a className="nut-tai" href={api.duongDanTaiVe(job.id)}>Tải file về</a>
          )}
          {job.status === 'done' && job.format === 'png_single' && (
            <p className="ghi-chu">
              Ảnh rời đã lưu trên máy chủ tại <code>{job.output_path}</code> — muốn tải một file
              thì chọn định dạng CBZ hoặc ZIP.
            </p>
          )}
        </div>
      )}

      {loi && <div className="bang-loi">Lỗi: {loi}</div>}
    </section>
  )
}
