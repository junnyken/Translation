import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import * as api from '../../api.js'
import Icon from '../ui/Icon.jsx'
import '../../styles/canvas.css'
import CanvasStage from './CanvasStage.jsx'
import DaiTrang from './DaiTrang.jsx'
import { vuaKhung, zoomQuanhDiem } from './hinh-hoc.js'
import { BangCo, LopPanel } from './LopVaCo.jsx'
import { taoMatNa } from './mat-na.js'
import { taiLop } from './tai-anh.js'
import ThuocTinh from './ThuocTinh.jsx'

const BUOC_ZOOM = 1.25
const LOP_MAC_DINH = {
  goc: { hien: false, doMo: 1 },
  sach: { hien: true, doMo: 1 },
  dich: { hien: true, doMo: 1 },
  matna: { hien: true, doMo: 0.6 },
}

const svg = (d) => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
       strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{d}</svg>
)
const CONG_CU = [
  { ma: 'keo', phim: 'H', nhan: 'Kéo / di chuyển', icon: svg(<><path d="M18 11V6a2 2 0 0 0-4 0v5M14 10V4a2 2 0 0 0-4 0v6M10 10.5V6a2 2 0 0 0-4 0v8" /><path d="M18 11a2 2 0 0 1 4 0v3a8 8 0 0 1-8 8h-2c-2.8 0-4.5-.9-5.9-2.4L3.4 16a2 2 0 0 1 3.2-2.4L8 15" /></>) },
  { ma: 'chon', phim: 'V', nhan: 'Chọn khung chữ', icon: svg(<path d="M5 3l14 8-6 2-2 6z" />) },
  { ma: 't', phim: 'T', nhan: 'Thêm chữ', tat: true, icon: <span className="cv-chu-t" aria-hidden="true">T</span> },
  { ma: 'but', phim: 'B', nhan: 'Cọ xoá chữ', icon: svg(<><path d="M18.4 2.6a2 2 0 0 1 2.8 2.8L12 14.6 8.5 15.5l.9-3.5z" /><path d="M8.5 15.5C7 15.5 5.5 17 5.5 19c0 1-1 1.5-2.5 1.5 1.5 1.3 6 2 7.5-1 .8-1.6.5-3-1-4z" /></>) },
  { ma: 'tay', phim: 'E', nhan: 'Tẩy mặt nạ', icon: svg(<><path d="M20 20H9L3.5 14.5a2 2 0 0 1 0-2.8L12 3.2a2 2 0 0 1 2.8 0l5.5 5.5a2 2 0 0 1 0 2.8L11 20.8" /><path d="M7 11l6 6" /></>) },
  { ma: 'hut', phim: 'I', nhan: 'Hút màu', icon: svg(<><path d="M2 22l1-1h3l9-9" /><path d="M3 21v-3l9-9" /><path d="M15 6l3.4-3.4a2 2 0 0 1 2.8 2.8L18 9l.4.4a2 2 0 0 1-2.8 2.8l-4.8-4.8a2 2 0 0 1 2.8-2.8z" /></>) },
]
const PHIM_CONG_CU = Object.fromEntries(CONG_CU.filter((c) => !c.tat).map((c) => [c.phim.toLowerCase(), c.ma]))

const docLoi = (e) => e?.cauNguoiDoc ?? e?.message ?? 'Có lỗi xảy ra, bạn thử lại sau.'
/** Việc chạy nền có thể nằm ở `refit_job_id` (sửa vùng) hoặc `job_id` (dịch/đọc lại, xoá vùng tô). */
const layMaViec = (kq) => kq?.refit_job_id ?? kq?.job_id ?? null
const lamTron = (b) => ({
  x: Math.round(b.x), y: Math.round(b.y), w: Math.round(b.w), h: Math.round(b.h),
})

const NOI_DUNG_WEBGPU = {
  'khong-co-webgpu': 'Máy này không hỗ trợ WebGPU — đang dùng chế độ thường (chậm hơn khi trang lớn).',
  'khong-co-adapter': 'Máy này không hỗ trợ WebGPU — đang dùng chế độ thường (chậm hơn khi trang lớn).',
  'loi-khoi-tao': 'WebGPU bị lỗi trên máy này — đang dùng chế độ thường (chậm hơn khi trang lớn).',
}

/**
 * Màn "Sửa tay kiểu canvas" (E76). Mở bằng `#canvas=<page_id>`.
 * Màn sửa tay cũ (`#page=<id>`) vẫn còn nguyên làm đường lùi.
 */
export default function CanvasEditor({ pageId, projectId }) {
  const [project, setProject] = useState(null)
  const [chiTiet, setChiTiet] = useState(null)
  const [loiTrang, setLoiTrang] = useState(null)
  const [dangTai, setDangTai] = useState(false)
  const [dangChon, setDangChon] = useState(null)
  const [congCu, setCongCu] = useState('chon')
  const [coCo, setCoCo] = useState(24)
  const [lop, setLop] = useState({ goc: null, sach: null, dich: null })
  const [loiLop, setLoiLop] = useState({})
  const [trangThaiLop, setTrangThaiLop] = useState(LOP_MAC_DINH)
  const [viec, setViec] = useState(null)
  const [loiViec, setLoiViec] = useState(null)
  const [thongBao, setThongBao] = useState(null)
  const [view, setView] = useState({ zoom: 1, panX: 0, panY: 0 })
  const [kt, setKt] = useState(null)
  const [renderInfo, setRenderInfo] = useState(null)
  const [bannerDong, setBannerDong] = useState(false)
  const [giaiThich, setGiaiThich] = useState(false)
  const [mauHut, setMauHut] = useState(null)
  const [ban, setBan] = useState({})
  const [daGhim, setDaGhim] = useState({})
  const [bboxTam, setBboxTam] = useState({})
  const [lichSu, setLichSu] = useState({ lam: [], lai: [] })
  const [phienMatNa, setPhienMatNa] = useState(0)
  const [phienSach, setPhienSach] = useState(0)
  const [phienDich, setPhienDich] = useState(0)
  const [lanThu, setLanThu] = useState(0)
  const matNaRef = useRef(null)
  const bangCho = useRef({ goc: 0, sach: 0, dich: 0 })
  const daVua = useRef('')

  // ---------- Dữ liệu trang ----------
  useEffect(() => {
    if (!pageId) { setChiTiet(null); return undefined }
    let huy = false
    setDangTai(true)
    setLoiTrang(null)
    api.layChiTietTrang(pageId)
      .then((d) => {
        if (huy) return
        setChiTiet(d)
        setDangChon((cu) => (d.regions.some((r) => r.id === cu) ? cu : d.regions[0]?.id ?? null))
      })
      .catch((e) => { if (!huy) { setChiTiet(null); setLoiTrang(docLoi(e)) } })
      .finally(() => { if (!huy) setDangTai(false) })
    return () => { huy = true }
  }, [pageId, lanThu])

  // Đổi trang: bỏ hết thứ của trang cũ (lịch sử hoàn tác gắn với vùng của trang cũ).
  useEffect(() => {
    setChiTiet(null)
    setLop({ goc: null, sach: null, dich: null })
    setLoiLop({})
    setLichSu({ lam: [], lai: [] })
    setBan({})
    setDaGhim({})
    setBboxTam({})
    setLoiViec(null)
    setThongBao(null)
    setMauHut(null)
    matNaRef.current = null
    for (const k of Object.keys(bangCho.current)) bangCho.current[k] += 1
  }, [pageId])

  const idChapter = projectId || chiTiet?.page?.project_id || ''
  useEffect(() => {
    if (!idChapter) { setProject(null); return undefined }
    let huy = false
    api.layProject(idChapter).then((p) => { if (!huy) setProject(p) }).catch(() => { if (!huy) setProject(null) })
    return () => { huy = true }
  }, [idChapter])

  const dsTrang = useMemo(
    () => [...(project?.pages ?? [])].sort((a, b) => a.order - b.order), [project],
  )
  // Mở chapter mà không nói trang nào ⇒ vào trang đầu tiên (chapter rỗng thì hiện màn rỗng).
  useEffect(() => {
    if (!pageId && dsTrang.length) window.location.hash = `canvas=${dsTrang[0].id}`
  }, [pageId, dsTrang])

  // ---------- Ảnh các lớp ----------
  const napLop = useCallback(async (ten, url) => {
    const luot = ++bangCho.current[ten]
    try {
      const r = await taiLop(url)
      if (luot !== bangCho.current[ten]) return
      setLop((l) => ({ ...l, [ten]: r }))
      setLoiLop((l) => ({ ...l, [ten]: r ? '' : 'chưa có ảnh' }))
    } catch {
      if (luot !== bangCho.current[ten]) return
      setLop((l) => ({ ...l, [ten]: null }))
      setLoiLop((l) => ({ ...l, [ten]: 'không tải được' }))
    }
  }, [])

  useEffect(() => { if (pageId) napLop('goc', api.duongDanAnhGoc(pageId)) }, [pageId, napLop])
  useEffect(() => {
    if (pageId) napLop('sach', `${api.duongDanAnhSach(pageId)}?v=${phienSach}`)
  }, [pageId, phienSach, napLop])
  const duongXemThu = chiTiet?.preview_url
  useEffect(() => {
    if (!pageId) return
    if (duongXemThu) napLop('dich', `${api.API_BASE}${duongXemThu}?v=${phienDich}`)
    else if (chiTiet) {
      bangCho.current.dich += 1
      setLop((l) => ({ ...l, dich: null }))
      setLoiLop((l) => ({ ...l, dich: 'chưa có ảnh' }))
    }
  }, [pageId, duongXemThu, phienDich, napLop, !!chiTiet]) // eslint-disable-line react-hooks/exhaustive-deps

  // ---------- Cỡ trang (pixel ẢNH GỐC) ----------
  const { W, H } = useMemo(() => {
    const goc = lop.goc ?? lop.sach
    if (goc) return { W: goc.w, H: goc.h }
    if (lop.dich) {
      const k = chiTiet?.page?.he_so_ve || 1
      return { W: Math.round(lop.dich.w / k), H: Math.round(lop.dich.h / k) }
    }
    if (chiTiet) {
      // Không có ảnh nào: dựng khung trống vừa đủ chứa các khung chữ để vẫn thao tác được.
      const rs = chiTiet.regions
      return {
        W: Math.max(600, ...rs.map((r) => r.bbox.x + r.bbox.w + 40)),
        H: Math.max(800, ...rs.map((r) => r.bbox.y + r.bbox.h + 40)),
      }
    }
    return { W: 0, H: 0 }
  }, [lop, chiTiet])

  // Mặt nạ cùng cỡ ảnh gốc; đổi cỡ (ảnh vừa tải xong) mà chưa tô gì thì dựng lại cho khớp.
  useEffect(() => {
    if (!W || !H) return
    const mn = matNaRef.current
    if (mn && mn.W === W && mn.H === H) return
    if (mn && mn.nets.length) return
    matNaRef.current = taoMatNa(W, H)
    setPhienMatNa((v) => v + 1)
  }, [W, H])

  useEffect(() => {
    if (!kt || !W) return
    const khoa = `${pageId}:${W}x${H}`
    if (daVua.current === khoa) return
    daVua.current = khoa
    setView(vuaKhung(kt.rong, kt.cao, W, H))
  }, [kt, W, H, pageId])

  // ---------- Chạy một việc nền ----------
  const napLaiChiTiet = useCallback(async () => {
    const d = await api.layChiTietTrang(pageId)
    setChiTiet(d)
    setPhienDich((v) => v + 1)
    return d
  }, [pageId])

  const chayViec = useCallback(async (moTa, lam) => {
    setViec(`Đang ${moTa}…`)
    setLoiViec(null)
    setThongBao(null)
    try {
      const kq = await lam()
      const maViec = layMaViec(kq)
      if (maViec) {
        await api.choJobXong(maViec, {
          onTien: (job) => setViec(job.status === 'queued'
            ? `Đang chờ tới lượt (${moTa})…` : `Đang ${moTa}…`),
        })
      }
      await napLaiChiTiet()
      setThongBao('Đã xong.')
      return true
    } catch (e) {
      setLoiViec(docLoi(e))
      return false
    } finally {
      setViec(null)
    }
  }, [napLaiChiTiet])

  const vung = useMemo(() => (chiTiet?.regions ?? []).map((r) => (
    bboxTam[r.id] ? { ...r, bbox: bboxTam[r.id] } : r
  )), [chiTiet, bboxTam])
  const vungChon = chiTiet?.regions.find((r) => r.id === dangChon) ?? null

  const ghiLichSu = (muc) => setLichSu((h) => ({ lam: [...h.lam, muc], lai: [] }))

  /** Sửa một vùng và nhớ giá trị cũ để hoàn tác (hoàn tác = gửi lại giá trị cũ). */
  const suaCoLichSu = async (regionId, truoc, sau, moTa) => {
    const ok = await chayViec(moTa, () => api.suaVung(regionId, sau))
    if (ok) ghiLichSu({ loai: 'vung', regionId, truoc, sau })
    return ok
  }

  const keoXong = async (id, bbox) => {
    const r = chiTiet.regions.find((x) => x.id === id)
    const sau = lamTron(bbox)
    setBboxTam((t) => ({ ...t, [id]: sau }))
    await suaCoLichSu(id, { bbox: lamTron(r.bbox) }, { bbox: sau }, 'lưu khung chữ')
    setBboxTam((t) => { const m = { ...t }; delete m[id]; return m })
  }

  const luuChu = async () => {
    const r = vungChon
    const b = ban[r.id]
    if (!b) return
    const sau = {}
    const truoc = {}
    if (b.raw !== (r.raw_text ?? '')) { sau.raw_text = b.raw; truoc.raw_text = r.raw_text ?? '' }
    if (b.text !== (r.translated_text ?? '')) { sau.translated_text = b.text; truoc.translated_text = r.translated_text ?? '' }
    if (!Object.keys(sau).length) return
    const ok = await suaCoLichSu(r.id, truoc, sau, 'lưu và canh lại chữ')
    if (ok) setBan((x) => { const m = { ...x }; delete m[r.id]; return m })
  }

  const doiFont = (font) => {
    if (font === vungChon.font_family) return
    return suaCoLichSu(vungChon.id, { font_family: vungChon.font_family }, { font_family: font }, 'đổi font')
  }
  const ghimCo = async (co) => {
    const r = vungChon
    const ok = await suaCoLichSu(r.id, r.font_size ? { font_size: r.font_size } : {}, { font_size: co }, 'ghim cỡ chữ')
    if (ok) setDaGhim((g) => ({ ...g, [r.id]: true }))
  }
  const boGhim = async () => {
    const id = vungChon.id
    // Bỏ ghim = cho máy canh lại tự dò cỡ (PATCH không có cách gỡ ghim).
    const ok = await chayViec('canh lại chữ', () => api.canhLaiVung(id))
    if (ok) setDaGhim((g) => ({ ...g, [id]: false }))
  }

  // ---------- Hoàn tác / làm lại ----------
  const hoanTac = async () => {
    if (viec) return
    const muc = lichSu.lam[lichSu.lam.length - 1]
    if (!muc) return
    if (muc.loai === 'net') {
      matNaRef.current?.boNetCuoi()
      setPhienMatNa((v) => v + 1)
    } else if (!(await chayViec('hoàn tác', () => api.suaVung(muc.regionId, muc.truoc)))) return
    setLichSu((h) => ({ lam: h.lam.slice(0, -1), lai: [...h.lai, muc] }))
  }
  const lamLai = async () => {
    if (viec) return
    const muc = lichSu.lai[lichSu.lai.length - 1]
    if (!muc) return
    if (muc.loai === 'net') {
      matNaRef.current?.themLai(muc.net)
      setPhienMatNa((v) => v + 1)
    } else if (!(await chayViec('làm lại', () => api.suaVung(muc.regionId, muc.sau)))) return
    setLichSu((h) => ({ lam: [...h.lam, muc], lai: h.lai.slice(0, -1) }))
  }

  // ---------- Cọ ----------
  const netMoi = (net) => {
    matNaRef.current?.them(net)
    ghiLichSu({ loai: 'net', net })
    setPhienMatNa((v) => v + 1)
  }
  const xoaMatNa = () => {
    matNaRef.current?.xoaHet()
    setLichSu((h) => ({
      lam: h.lam.filter((m) => m.loai !== 'net'), lai: h.lai.filter((m) => m.loai !== 'net'),
    }))
    setPhienMatNa((v) => v + 1)
  }
  const xoaVungDaTo = async () => {
    const mn = matNaRef.current
    if (!mn?.coTo()) return
    setViec('Đang xoá chữ ở vùng đã tô…')
    setLoiViec(null)
    setThongBao(null)
    try {
      const blob = await mn.xuatPng()
      const kq = await api.xoaVungTo(pageId, blob)
      if (kq?.job_id) {
        await api.choJobXong(kq.job_id, {
          onTien: (job) => setViec(job.status === 'queued'
            ? 'Đang chờ tới lượt xoá chữ…' : 'Đang xoá chữ ở vùng đã tô…'),
        })
      }
      await napLaiChiTiet()
      setPhienSach((v) => v + 1)
      xoaMatNa()
      setCongCu('chon')
      setThongBao('Đã xoá chữ ở vùng đã tô.')
    } catch (e) {
      // Giữ nguyên mặt nạ: lỗi (vd tô quá rộng) thì người dùng sửa nét rồi bấm lại.
      setLoiViec(docLoi(e))
    } finally {
      setViec(null)
    }
  }

  // ---------- Thu phóng ----------
  const doiZoom = (z) => {
    if (!kt) return
    setView((v) => zoomQuanhDiem(v, z(v.zoom), kt.rong / 2, kt.cao / 2))
  }

  // ---------- Phím tắt ----------
  const phimRef = useRef({})
  phimRef.current = { hoanTac, lamLai, doiZoom, coCo }
  useEffect(() => {
    const khiBam = (e) => {
      if (e.target?.closest?.('input:not([type=range]), textarea, select, [contenteditable]')) return
      const p = phimRef.current
      const k = e.key.toLowerCase()
      if ((e.ctrlKey || e.metaKey) && k === 'z') { e.preventDefault(); (e.shiftKey ? p.lamLai : p.hoanTac)(); return }
      if ((e.ctrlKey || e.metaKey) && k === 'y') { e.preventDefault(); p.lamLai(); return }
      if (e.ctrlKey || e.metaKey || e.altKey) return
      if (PHIM_CONG_CU[k]) { setCongCu(PHIM_CONG_CU[k]); return }
      if (e.key === '[') setCoCo((c) => Math.max(4, c - 4))
      else if (e.key === ']') setCoCo((c) => Math.min(120, c + 4))
      else if (e.key === '+' || e.key === '=') p.doiZoom((z) => z * BUOC_ZOOM)
      else if (e.key === '-') p.doiZoom((z) => z / BUOC_ZOOM)
    }
    window.addEventListener('keydown', khiBam)
    return () => window.removeEventListener('keydown', khiBam)
  }, [])

  // ---------- Dựng giao diện ----------
  const chi = dsTrang.findIndex((t) => t.id === pageId)
  const soTrang = chi >= 0 ? chi + 1 : null
  const rong = !pageId && project && dsTrang.length === 0
  const khoaSua = !!viec
  const idQuayLai = idChapter ? `#project=${idChapter}` : '#'
  const ghiChuLop = Object.fromEntries(
    Object.entries(loiLop).filter(([, v]) => v).map(([k, v]) => [k, ` — ${v}`]),
  )
  const dangBut = congCu === 'but' || congCu === 'tay'
  const hienBanner = renderInfo && renderInfo.loai !== 'webgpu' && renderInfo.lyDoLui && !bannerDong

  return (
    <div className="cv">
      <header className="cv-tren">
        <a className="nut nut-ghost" href={idQuayLai} title="Quay lại danh sách chapter">
          &larr; Chapter
        </a>
        <span className="cv-tieu-de">{project?.name ?? 'Chapter'}</span>
        <span className="the-tt the-tt-tin">
          {soTrang ? `Trang ${soTrang}/${dsTrang.length}` : `Trang 0/${dsTrang.length}`}
        </span>
        <span className="cv-cach" />
        <button type="button" className="nut nut-phu" onClick={hoanTac}
                disabled={!lichSu.lam.length || khoaSua} title="Hoàn tác (Ctrl+Z)">
          Hoàn tác
        </button>
        <button type="button" className="nut nut-phu" onClick={lamLai}
                disabled={!lichSu.lai.length || khoaSua} title="Làm lại (Ctrl+Shift+Z)">
          Làm lại
        </button>
        <span className="cv-day" />
        <span className="cv-zoom" role="group" aria-label="Thu phóng">
          <button type="button" className="nut nut-ghost" aria-label="Thu nhỏ" title="Thu nhỏ (−)"
                  disabled={!W} onClick={() => doiZoom((z) => z / BUOC_ZOOM)}>&minus;</button>
          <button type="button" className="nut nut-ghost cv-phan-tram" disabled={!W}
                  title="Về 100%" aria-label="Về 100%"
                  onClick={() => doiZoom(() => 1)}>
            {Math.round(view.zoom * 100)}%
          </button>
          <button type="button" className="nut nut-ghost" aria-label="Phóng to" title="Phóng to (+)"
                  disabled={!W} onClick={() => doiZoom((z) => z * BUOC_ZOOM)}>+</button>
          <button type="button" className="nut nut-ghost" title="Vừa khung màn hình" disabled={!W || !kt}
                  onClick={() => kt && setView(vuaKhung(kt.rong, kt.cao, W, H))}>Vừa khung</button>
        </span>
        <span className="cv-day" />
        {pageId && (
          <a className="nut nut-ghost" href={`#page=${pageId}`}
             title="Mở màn sửa tay kiểu cũ">Màn sửa cũ</a>
        )}
        {idChapter
          ? <a className="nut nut-chinh" href={idQuayLai} title="Xuất chapter ở trang chapter">Xuất</a>
          : <button type="button" className="nut nut-chinh" disabled title="Cần có ít nhất một trang để xuất">Xuất</button>}
      </header>

      <div className="cv-chinh">
        <nav className="cv-cong-cu" aria-label="Công cụ">
          {CONG_CU.map((c) => (
            <button
              key={c.ma} type="button"
              className={`nut cv-cc${congCu === c.ma ? ' on' : ''}`}
              title={c.tat ? `${c.nhan} (${c.phim}) — chưa hỗ trợ` : `${c.nhan} (${c.phim})`}
              aria-label={`${c.nhan}, phím ${c.phim}`}
              aria-pressed={congCu === c.ma}
              aria-disabled={c.tat || undefined}
              disabled={c.tat || !pageId}
              onClick={() => setCongCu(c.ma)}
            >
              {c.icon}<small>{c.phim}</small>
            </button>
          ))}
        </nav>

        {dsTrang.length > 0 && <DaiTrang trang={dsTrang} dangMo={pageId} />}

        <section className="cv-khu-canvas" aria-label="Canvas trang truyện">
          {hienBanner && (
            <div className="cv-banner" role="status">
              <Icon ten="dong-ho" co={16} />
              <span className="cv-banner-chu">{NOI_DUNG_WEBGPU[renderInfo.lyDoLui] ?? NOI_DUNG_WEBGPU['loi-khoi-tao']}</span>
              <button type="button" className="nut-chu cv-lien-ket" aria-expanded={giaiThich}
                      onClick={() => setGiaiThich((v) => !v)}>Vì sao?</button>
              <button type="button" className="nut nut-phu" onClick={() => setBannerDong(true)}>
                Dùng chế độ thường
              </button>
              {giaiThich && (
                <div className="cv-banner-giai-thich">
                  <p>WebGPU là công nghệ giúp trình duyệt dùng card đồ hoạ để vẽ và xoá chữ trên trang nhanh hơn.</p>
                  <p>Trình duyệt hoặc máy của bạn chưa hỗ trợ nên công cụ tự chuyển sang <b>chế độ thường</b>. Mọi tính năng vẫn dùng được, chỉ chậm hơn khi trang truyện có kích thước lớn.</p>
                  <p>Muốn nhanh hơn, hãy thử bản Chrome hoặc Edge mới nhất.</p>
                </div>
              )}
            </div>
          )}
          {viec && <div className="cv-trang-thai" role="status"><Icon ten="quay" co={14} /> {viec}</div>}
          {!viec && thongBao && <div className="cv-trang-thai ok" role="status">{thongBao}</div>}
          {loiViec && (
            <div className="cv-trang-thai loi" role="alert">
              <span>{loiViec}</span>
              <button type="button" className="nut-bo" aria-label="Đóng thông báo lỗi"
                      onClick={() => setLoiViec(null)}><Icon ten="x" co={14} /></button>
            </div>
          )}

          <div className="cv-khung-ve">
            <CanvasStage
              rongTrang={W} caoTrang={H} lop={lop} trangThaiLop={trangThaiLop}
              matNa={matNaRef.current} phienBanMatNa={phienMatNa}
              view={view} onView={setView} onKichThuoc={setKt}
              congCu={congCu} coCo={coCo} regions={vung} dangChon={dangChon} onChon={setDangChon}
              khoa={khoaSua} onKeoXong={keoXong} onNetMoi={netMoi}
              onHutMau={(m) => setMauHut(m ?? 'Không đọc được màu ở điểm này')}
              onRenderer={setRenderInfo}
            />
            {mauHut && (
              <div className="cv-mau-hut" role="status">
                {mauHut.startsWith('#') && <span className="cv-o-mau" style={{ background: mauHut }} aria-hidden="true" />}
                {mauHut}
              </div>
            )}
            {pageId && loiTrang && (
              <div className="cv-phu">
                <div className="cv-hop-loi" role="alert">
                  <h2>{soTrang ? `Không tải được trang ${soTrang}` : 'Không tải được trang này'}</h2>
                  <p>{loiTrang}</p>
                  <div className="cv-nut-doc ngang">
                    <button type="button" className="nut nut-chinh" onClick={() => setLanThu((v) => v + 1)}>
                      Thử lại
                    </button>
                    <a className="nut nut-phu" href={idQuayLai}>Về chapter</a>
                  </div>
                </div>
              </div>
            )}
            {pageId && !loiTrang && dangTai && !chiTiet && (
              <div className="cv-phu"><p className="cv-nho-sang">Đang tải trang…</p></div>
            )}
            {rong && (
              <div className="cv-phu">
                <div className="cv-hop-loi">
                  <h2>Chapter này chưa có trang nào</h2>
                  <p>Thêm ảnh trang truyện để bắt đầu dịch và sửa tay. Máy sẽ tự đọc chữ và dịch sau khi bạn thêm trang.</p>
                  <a className="nut nut-chinh" href={`#project=${idChapter}`}>Thêm trang</a>
                </div>
              </div>
            )}
            {!rong && !pageId && !project && !projectId && (
              <div className="cv-phu"><p className="cv-nho-sang">Chưa chọn trang nào để sửa.</p></div>
            )}
          </div>
          <p className="cv-goi-y">
            {dangBut
              ? 'Tô lên phần chữ còn sót · [ và ] đổi cỡ cọ · giữ Alt để tẩy'
              : 'Kéo để di chuyển · kéo góc để đổi cỡ · cuộn chuột để phóng to'}
          </p>
        </section>

        <aside className="cv-ben" aria-label="Thuộc tính và lớp">
          {rong || (!pageId && !chiTiet) ? (
            <div className="cv-muc">
              <h3>Thuộc tính</h3>
              <p className="cv-nho">Chọn một khung chữ trên trang để sửa chữ gốc, bản dịch, font và màu.</p>
              <h3>Lớp</h3>
              <p className="cv-nho">Các lớp sẽ hiện ra khi chapter có trang.</p>
            </div>
          ) : loiTrang ? (
            <>
              <div className="cv-muc">
                <h3>Thuộc tính</h3>
                <p className="cv-nho">Chưa có khung chữ nào để chỉnh vì trang chưa tải được.</p>
              </div>
              <LopPanel trangThaiLop={trangThaiLop} ghiChu={ghiChuLop}
                        onDoi={(ten, p) => setTrangThaiLop((s) => ({ ...s, [ten]: { ...s[ten], ...p } }))} />
            </>
          ) : (
            <>
              {dangBut && (
                <BangCo
                  co={coCo} onCo={setCoCo} cheDo={congCu} onCheDo={setCongCu}
                  dangBan={khoaSua} coTo={!!matNaRef.current?.coTo()}
                  onXoa={xoaVungDaTo} onBo={xoaMatNa}
                />
              )}
              <ThuocTinh
                region={vungChon}
                fontFamilies={chiTiet?.font_families ?? []}
                coMin={chiTiet?.min_font_size} coMax={chiTiet?.max_font_size}
                dangBan={khoaSua}
                ban={vungChon ? ban[vungChon.id] : null}
                onBan={(b) => setBan((x) => ({ ...x, [vungChon.id]: b }))}
                onLuu={luuChu}
                onDoiFont={doiFont}
                onGhim={ghimCo} onBoGhim={boGhim} daGhim={!!(vungChon && daGhim[vungChon.id])}
                onDichLai={() => chayViec('dịch lại vùng này', () => api.dichLaiVung(vungChon.id))}
                onDocLai={() => chayViec('đọc lại chữ gốc', () => api.docLaiVung(vungChon.id))}
              />
              <LopPanel trangThaiLop={trangThaiLop} ghiChu={ghiChuLop}
                        onDoi={(ten, p) => setTrangThaiLop((s) => ({ ...s, [ten]: { ...s[ten], ...p } }))} />
            </>
          )}
        </aside>
      </div>
    </div>
  )
}
