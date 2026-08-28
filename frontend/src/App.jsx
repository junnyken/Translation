import { useCallback, useEffect, useState } from 'react'
import * as api from './api.js'
import BatchPanel from './components/BatchPanel.jsx'
import BboxOverlay from './components/BboxOverlay.jsx'
import ExportPanel from './components/ExportPanel.jsx'
import NewProjectPanel from './components/NewProjectPanel.jsx'
import RegionPanel from './components/RegionPanel.jsx'
import StatusBadge from './components/StatusBadge.jsx'

/** Lấy id trang/dự án từ địa chỉ (#page=… hoặc #project=…) để chia sẻ link được. */
function docDiaChi() {
  const p = new URLSearchParams(window.location.hash.slice(1))
  return { pageId: p.get('page') || '', projectId: p.get('project') || '' }
}

const KHOA_NHO = 'translation:chapter-gan-day'

function docChapterDaLuu() {
  try { return JSON.parse(localStorage.getItem(KHOA_NHO) || '[]') } catch { return [] }
}
function luuChapter(id, ten) {
  try {
    const cu = docChapterDaLuu().filter((c) => c.id !== id)
    localStorage.setItem(KHOA_NHO, JSON.stringify([{ id, ten }, ...cu].slice(0, 12)))
  } catch { /* trình duyệt chặn lưu thì bỏ qua, không phải lỗi */ }
}

export default function App() {
  const [{ pageId, projectId }, setDiaChi] = useState(docDiaChi)
  const [nhap, setNhap] = useState(projectId || pageId)
  const [project, setProject] = useState(null)
  const [chiTiet, setChiTiet] = useState(null)
  const [dangChon, setDangChon] = useState(null)
  const [hienCanhBao, setHienCanhBao] = useState(true)
  const [dangBan, setDangBan] = useState(false)
  const [loi, setLoi] = useState(null)
  const [thongBao, setThongBao] = useState(null)
  // Đổi mỗi lần vẽ lại preview để trình duyệt không dùng ảnh cũ trong bộ nhớ đệm.
  const [phienBanAnh, setPhienBanAnh] = useState(0)
  const [ganDay, setGanDay] = useState(docChapterDaLuu)

  useEffect(() => {
    const doi = () => setDiaChi(docDiaChi())
    window.addEventListener('hashchange', doi)
    return () => window.removeEventListener('hashchange', doi)
  }, [])

  const napTrang = useCallback(async (id) => {
    setLoi(null)
    try {
      const data = await api.layChiTietTrang(id)
      setChiTiet(data)
      setPhienBanAnh((v) => v + 1)
      setDangChon((cu) => (data.regions.some((r) => r.id === cu) ? cu : data.regions[0]?.id ?? null))
    } catch (e) {
      setLoi(e.message)
    }
  }, [])

  useEffect(() => {
    if (pageId) napTrang(pageId)
    else setChiTiet(null)
  }, [pageId, napTrang])

  useEffect(() => {
    if (!projectId) return setProject(null)
    api.layProject(projectId).then((p) => {
      setProject(p)
      luuChapter(p.id, p.name)
      setGanDay(docChapterDaLuu())
    }).catch((e) => setLoi(e.message))
  }, [projectId])

  const mo = () => {
    const id = nhap.trim()
    if (!id) return
    // Đoán: mở như một dự án trước; không phải thì thử mở như một trang.
    api
      .layProject(id)
      .then(() => { window.location.hash = `project=${id}` })
      .catch(() => { window.location.hash = `page=${id}` })
  }

  /** Chạy một thao tác nền rồi nạp lại dữ liệu — khoá giao diện trong lúc chạy. */
  const chay = async (moTa, viec) => {
    setDangBan(true)
    setLoi(null)
    setThongBao(`Đang ${moTa}…`)
    try {
      const { job_id } = await viec()
      await api.choJobXong(job_id)
      await napTrang(pageId)
      setThongBao(`Xong: ${moTa}.`)
    } catch (e) {
      setLoi(e.message)
      setThongBao(null)
    } finally {
      setDangBan(false)
    }
  }

  const luuVung = (regionId, thayDoi) =>
    chay('lưu và canh lại', async () => {
      const kq = await api.suaVung(regionId, thayDoi)
      return { job_id: kq.refit_job_id }
    })

  const luuBbox = (regionId, bbox) =>
    chay('lưu khung chữ', async () => {
      const kq = await api.suaVung(regionId, {
        bbox: { x: Math.round(bbox.x), y: Math.round(bbox.y), w: Math.round(bbox.w), h: Math.round(bbox.h) },
      })
      return { job_id: kq.refit_job_id }
    })

  const vungDangChon = chiTiet?.regions.find((r) => r.id === dangChon) ?? null
  const soTran = chiTiet?.regions.filter((r) => r.fit_status === 'overflow_warning').length ?? 0
  const soCanXem = chiTiet?.regions.filter(
    (r) => r.ocr_status === 'needs_manual' || r.status === 'low_confidence',
  ).length ?? 0

  return (
    <div className="app">
      <header>
        <h1>Sửa tay bản dịch</h1>
        <div className="hang">
          <input
            value={nhap}
            onChange={(e) => setNhap(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && mo()}
            placeholder="Dán mã dự án hoặc mã trang…"
            size={40}
          />
          <button onClick={mo}>Mở</button>
        </div>
      </header>

      {loi && <div className="bang-loi">Lỗi: {loi}</div>}
      {thongBao && <div className="bang-tin">{thongBao}</div>}

      {!projectId && !pageId && (
        <div className="bo-cuc-project">
          <NewProjectPanel onXong={(id) => { window.location.hash = `project=${id}` }} />
          <section className="danh-sach">
            <h2>Chapter gần đây</h2>
            {ganDay.length === 0 ? (
              <p className="ghi-chu">
                Chưa có chapter nào. Tạo một chapter ở bên trái để bắt đầu — hoặc dán mã chapter
                vào ô trên cùng nếu bạn đã có sẵn.
              </p>
            ) : (
              <ul>
                {ganDay.map((c) => (
                  <li key={c.id}>
                    <a href={`#project=${c.id}`}>{c.ten}</a>
                    <span className="ghi-chu">{c.id.slice(0, 8)}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      )}

      {project && !pageId && (
        <div className="bo-cuc-project">
          <section className="danh-sach">
            <h2>{project.name}</h2>
            <p className="ghi-chu">Chọn một trang để sửa:</p>
            <ul>
              {(project.pages ?? []).map((p) => (
                <li key={p.id}>
                  <a href={`#page=${p.id}`}>Trang {p.order ?? '?'} — {p.id.slice(0, 8)}</a>
                  <StatusBadge trangThai={p.status} />
                </li>
              ))}
            </ul>
          </section>
          <div className="cot-phai">
            <BatchPanel projectId={projectId} soTrang={(project.pages ?? []).length} />
            <ExportPanel projectId={projectId} tenProject={project.name} />
          </div>
        </div>
      )}

      {chiTiet && chiTiet.page?.project_id && (
        <p className="ghi-chu">
          <a href={`#project=${chiTiet.page.project_id}`}>← Về danh sách trang &amp; xuất chapter</a>
        </p>
      )}

      {chiTiet && (
        <main className="bo-cuc">
          <section className="cot-anh">
            <div className="hang-cong-cu">
              <label>
                <input
                  type="checkbox"
                  checked={hienCanhBao}
                  onChange={(e) => setHienCanhBao(e.target.checked)}
                />{' '}
                Hiện cảnh báo trên ảnh
              </label>
              <span className="ghi-chu">
                {soTran} vùng tràn khung · {soCanXem} vùng cần xem lại · {chiTiet.regions.length} vùng
              </span>
            </div>

            {chiTiet.preview_url ? (
              <BboxOverlay
                src={`${api.API_BASE}${chiTiet.preview_url}?v=${phienBanAnh}`}
                regions={chiTiet.regions}
                dangChon={dangChon}
                onChon={setDangChon}
                onLuuBbox={luuBbox}
                hienCanhBao={hienCanhBao}
              />
            ) : (
              <p className="ghi-chu">
                Trang này chưa có ảnh xem thử — cần chạy xong bước canh chữ trước.
              </p>
            )}
          </section>

          <aside className="cot-sua">
            <div className="danh-sach-vung">
              {chiTiet.regions.map((r) => (
                <button
                  key={r.id}
                  className={`the-vung ${dangChon === r.id ? 'dang-chon' : ''}`}
                  onClick={() => setDangChon(r.id)}
                >
                  <b>{r.reading_order ?? '?'}</b>
                  <span className="tom-tat">{r.translated_text || <i>chưa có bản dịch</i>}</span>
                  <StatusBadge trangThai={r.fit_status} />
                </button>
              ))}
            </div>

            {vungDangChon && (
              <RegionPanel
                key={vungDangChon.id}
                region={vungDangChon}
                fontFamilies={chiTiet.font_families}
                coMin={chiTiet.min_font_size}
                coMax={chiTiet.max_font_size}
                dangBan={dangBan}
                onLuu={luuVung}
                onCanhLai={(id) => chay('canh lại', () => api.canhLaiVung(id))}
                onDocLai={(id) => chay('đọc lại chữ gốc', () => api.docLaiVung(id))}
                onDichLai={(id) => chay('dịch lại', () => api.dichLaiVung(id))}
              />
            )}
          </aside>
        </main>
      )}
    </div>
  )
}
