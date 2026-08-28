import { useCallback, useEffect, useState } from 'react'
import * as api from './api.js'
import BatchPanel from './components/BatchPanel.jsx'
import BboxOverlay from './components/BboxOverlay.jsx'
import ExportPanel from './components/ExportPanel.jsx'
import RegionPanel from './components/RegionPanel.jsx'
import ChapterCreateForm from './components/chapter/ChapterCreateForm.jsx'
import ChapterProgress from './components/chapter/ChapterProgress.jsx'
import ChapterRecentList from './components/chapter/ChapterRecentList.jsx'
import ChapterSummary from './components/chapter/ChapterSummary.jsx'
import ReviewToolbar from './components/chapter/ReviewToolbar.jsx'
import Alert from './components/ui/Alert.jsx'
import Button from './components/ui/Button.jsx'
import StatusBadge from './components/ui/StatusBadge.jsx'
import { tinhTienDoChapter } from './lib/chapter-progress.js'
import { MUC_DICH } from './lib/status-presentation.js'

/** Lấy id trang/chapter từ địa chỉ (#page=… hoặc #project=…) để chia sẻ link được.
 *  Giữ nguyên dạng địa chỉ cũ: link đã gửi cho nhau vẫn phải mở được. */
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
  const [canhBao, setCanhBao] = useState(null)
  const [chiTiet, setChiTiet] = useState(null)
  const [dangChon, setDangChon] = useState(null)
  const [hienCanhBaoAnh, setHienCanhBaoAnh] = useState(true)
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

  const napProject = useCallback(async (id) => {
    const p = await api.layProject(id)
    setProject(p)
    luuChapter(p.id, p.name)
    setGanDay(docChapterDaLuu())
    try {
      setCanhBao(await api.layCanhBaoXuat(id))
    } catch { /* chapter chưa có gì để cảnh báo thì thôi, không phải lỗi chặn */ }
    return p
  }, [])

  // Trang chi tiết cũng cần biết mình thuộc chapter nào (để có breadcrumb + điều hướng trang).
  const idChapter = projectId || chiTiet?.page?.project_id || ''
  useEffect(() => {
    if (!idChapter) return setProject(null)
    napProject(idChapter).catch((e) => setLoi(e.message))
  }, [idChapter, napProject])

  const mo = () => {
    const id = nhap.trim()
    if (!id) return
    // Đoán: mở như một chapter trước; không phải thì thử mở như một trang.
    api.layProject(id)
      .then(() => { window.location.hash = `project=${id}` })
      .catch(() => { window.location.hash = `page=${id}` })
  }

  /** Chạy một thao tác nền rồi nạp lại dữ liệu — khoá giao diện trong lúc chạy.
   *
   * Nói rõ đang CHỜ TỚI LƯỢT hay ĐANG CHẠY: worker xử lý từng việc một, nên lúc bận thì việc
   * nằm trong hàng đợi cả phút. Chỉ hiện "Đang…" đứng im khiến người dùng tưởng máy treo.
   */
  const chay = async (moTa, viec) => {
    setDangBan(true)
    setLoi(null)
    setThongBao(`Đang ${moTa}…`)
    try {
      const { job_id } = await viec()
      await api.choJobXong(job_id, {
        onTien: (job) => setThongBao(
          job.status === 'queued'
            ? `Đang chờ tới lượt (${moTa}) — máy chủ đang bận việc khác…`
            : `Đang ${moTa}…`,
        ),
      })
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
    chay('lưu và căn lại chữ', async () => {
      const kq = await api.suaVung(regionId, thayDoi)
      return { job_id: kq.refit_job_id }
    })

  const luuBbox = (regionId, bbox) =>
    chay('lưu khung chữ', async () => {
      const kq = await api.suaVung(regionId, {
        bbox: {
          x: Math.round(bbox.x), y: Math.round(bbox.y),
          w: Math.round(bbox.w), h: Math.round(bbox.h),
        },
      })
      return { job_id: kq.refit_job_id }
    })

  const vungDangChon = chiTiet?.regions.find((r) => r.id === dangChon) ?? null
  const soTran = chiTiet?.regions.filter((r) => r.fit_status === 'overflow_warning').length ?? 0
  const soCanXem = chiTiet?.regions.filter(
    (r) => r.ocr_status === 'needs_manual' || r.status === 'low_confidence',
  ).length ?? 0
  const dsTrang = project?.pages ?? []
  const tienDo = tinhTienDoChapter(dsTrang, {
    soTran: canhBao?.overflow_warning_count, soCanDocLai: canhBao?.needs_manual_count,
  })
  const oTrangChu = !projectId && !pageId

  return (
    <div className="app">
      <header className="dau-trang">
        <a className="hieu" href="#">
          <span className="hieu-dau">T</span>
          <span>
            <b>Translation</b>
            <small>Dịch truyện tranh sang tiếng Việt</small>
          </span>
        </a>

        <nav aria-label="Điều hướng chính" className="dieu-huong">
          <a href="#" className={oTrangChu ? 'dang-o' : ''}>Chapter</a>
          <a href="#" className="nut nut-phu" onClick={() => {
            document.getElementById('nut-tao')?.scrollIntoView({ block: 'center' })
          }}>Tạo chapter</a>
        </nav>

        <div className="o-tim">
          <label className="an-di" htmlFor="o-ma">Mã chapter hoặc mã trang</label>
          <input
            id="o-ma" value={nhap} onChange={(e) => setNhap(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && mo()}
            placeholder="Dán mã chapter hoặc mã trang…"
          />
          <Button kieu="phu" onClick={mo}>Mở</Button>
        </div>
      </header>

      <main className="than-trang">
        {loi && <Alert sac="loi" tieuDe="Có lỗi" onDong={() => setLoi(null)}>{loi}</Alert>}
        {thongBao && <Alert sac="tin" onDong={() => setThongBao(null)}>{thongBao}</Alert>}

        {oTrangChu && (
          <>
            <div className="tieu-de-man">
              <h1>Dịch truyện tranh</h1>
              <p>
                Tải ảnh PNG hoặc JPG. Hệ thống sẽ nhận diện chữ, dịch sang tiếng Việt và tự căn
                vào bong bóng — rồi bạn rà soát lại trước khi xuất.
              </p>
            </div>
            <div className="luoi-2-cot">
              <ChapterCreateForm onXong={(id) => { window.location.hash = `project=${id}` }} />
              <ChapterRecentList
                danhSach={ganDay}
                onTaoMoi={() => document.getElementById('nut-tao')?.scrollIntoView({ block: 'center' })}
              />
            </div>
          </>
        )}

        {project && !pageId && (
          <>
            <div className="tieu-de-man">
              <h1>{project.name}</h1>
              <p>
                Mục đích đã khai: <b>{MUC_DICH[project.intended_use] ?? project.intended_use}</b>
                {' '}· không sửa được sau khi tạo
              </p>
            </div>

            <ChapterSummary
              tienDo={tienDo} canhBao={canhBao} trangDau={dsTrang[0]?.id}
              onXuat={() => document.getElementById('bang-xuat')?.scrollIntoView({ block: 'start' })}
            />

            <div className="luoi-2-cot">
              <ChapterProgress
                project={project} canhBao={canhBao}
                onNapLai={() => napProject(project.id).catch((e) => setLoi(e.message))}
              />
              <div className="cot-phai">
                <BatchPanel projectId={project.id} soTrang={dsTrang.length} />
                <ExportPanel projectId={project.id} tenProject={project.name} />
              </div>
            </div>
          </>
        )}

        {chiTiet && (
          <>
            <ReviewToolbar
              tenChapter={project?.name} projectId={chiTiet.page?.project_id}
              trang={chiTiet.page} danhSachTrang={dsTrang} soCanXem={soCanXem}
            />

            <div className="bo-cuc">
              <section className="cot-anh">
                <div className="hang-cong-cu">
                  <label className="o-tick nho">
                    <input
                      type="checkbox" checked={hienCanhBaoAnh}
                      onChange={(e) => setHienCanhBaoAnh(e.target.checked)}
                    />
                    <span>Hiện cảnh báo trên ảnh</span>
                  </label>
                  <span className="ghi-chu">
                    {soTran} vùng tràn khung · {soCanXem} vùng cần xem lại ·{' '}
                    {chiTiet.regions.length} vùng
                  </span>
                </div>

                {chiTiet.preview_url ? (
                  <BboxOverlay
                    src={`${api.API_BASE}${chiTiet.preview_url}?v=${phienBanAnh}`}
                    regions={chiTiet.regions}
                    dangChon={dangChon}
                    onChon={setDangChon}
                    onLuuBbox={luuBbox}
                    hienCanhBao={hienCanhBaoAnh}
                  />
                ) : (
                  <Alert sac="tin" tieuDe="Chưa có ảnh xem thử">
                    Trang này cần chạy xong bước căn chữ mới có ảnh để xem.
                  </Alert>
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
                      <span className="tom-tat">
                        {r.translated_text || <i>chưa có bản dịch</i>}
                      </span>
                      <StatusBadge loai="canh_chu" trangThai={r.fit_status} />
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
                    onCanhLai={(id) => chay('căn lại chữ', () => api.canhLaiVung(id))}
                    onDocLai={(id) => chay('đọc lại chữ gốc', () => api.docLaiVung(id))}
                    onDichLai={(id) => chay('dịch lại', () => api.dichLaiVung(id))}
                  />
                )}
              </aside>
            </div>
          </>
        )}
      </main>
    </div>
  )
}
