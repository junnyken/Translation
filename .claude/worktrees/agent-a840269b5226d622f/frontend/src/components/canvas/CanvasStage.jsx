import { useEffect, useRef, useState } from 'react'
import { bboxSauKeo, manSangAnh, zoomQuanhDiem } from './hinh-hoc.js'
import { layMauTai } from './lay-mau.js'
import { TEN_LOP } from './renderer-2d.js'
import { taoRenderer } from './renderer.js'

const GOC = ['nw', 'ne', 'sw', 'se']
const CON_TRO_GOC = { nw: 'nwse-resize', se: 'nwse-resize', ne: 'nesw-resize', sw: 'nesw-resize' }
const VI_TRI_GOC = {
  nw: { left: -7, top: -7 }, ne: { right: -7, top: -7 },
  sw: { left: -7, bottom: -7 }, se: { right: -7, bottom: -7 },
}
const TEN_GOC = {
  nw: 'trên-trái', ne: 'trên-phải', sw: 'dưới-trái', se: 'dưới-phải',
}

/**
 * Vùng vẽ: canvas (WebGPU hoặc 2D) + lớp khung chữ + các công cụ chuột.
 *
 * Mọi toạ độ gửi ra ngoài (`onKeoXong`, `onNetMoi`) đều theo pixel ẢNH GỐC. Khung nhìn
 * (`view`) do cha giữ, vì thanh trên cũng đổi zoom.
 */
export default function CanvasStage({
  rongTrang, caoTrang, lop, trangThaiLop, matNa, phienBanMatNa,
  view, onView, onKichThuoc, congCu, coCo, regions, dangChon, onChon, khoa,
  onKeoXong, onNetMoi, onHutMau, onRenderer,
}) {
  const stageRef = useRef(null)
  const canvasRef = useRef(null)
  const rdRef = useRef(null)
  const daNap = useRef({})
  const [khoaCanvas, setKhoaCanvas] = useState(0)
  const [tuChoiGpu, setTuChoiGpu] = useState(false)
  const [san, setSan] = useState(false)
  const [kt, setKt] = useState(null)
  const [conTro, setConTro] = useState(null)
  const [tam, setTam] = useState(null) // khung đang kéo dở: { id, bbox }
  const thao = useRef(null)
  const viewRef = useRef(view)
  viewRef.current = view

  // ---- Khởi tạo bộ vẽ: WebGPU nếu có, không thì 2D ----
  useEffect(() => {
    let huy = false
    let rd = null
    setSan(false)
    daNap.current = {}
    taoRenderer(canvasRef.current, { tuChoiGpu })
      .then(({ renderer, lyDoLui }) => {
        if (huy) { renderer.huy(); return }
        rd = renderer
        rdRef.current = renderer
        onRenderer?.({ loai: renderer.loai, lyDoLui })
        setSan(true)
      })
      .catch(() => {
        if (huy) return
        // Thẻ canvas có thể đã bị WebGPU chiếm ngữ cảnh: dựng thẻ mới rồi ép dùng 2D.
        if (!tuChoiGpu) {
          setTuChoiGpu(true)
          setKhoaCanvas((k) => k + 1)
        } else {
          onRenderer?.({ loai: null, lyDoLui: 'loi-khoi-tao' })
        }
      })
    return () => { huy = true; rd?.huy(); rdRef.current = null }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [khoaCanvas, tuChoiGpu])

  // ---- Đo khung vẽ ----
  useEffect(() => {
    const el = stageRef.current
    const do_ = () => {
      const r = el.getBoundingClientRect()
      const moi = { rong: Math.round(r.width), cao: Math.round(r.height) }
      setKt((cu) => (cu && cu.rong === moi.rong && cu.cao === moi.cao ? cu : moi))
    }
    do_()
    let qs = null
    if (typeof ResizeObserver !== 'undefined') {
      qs = new ResizeObserver(do_)
      qs.observe(el)
    }
    window.addEventListener('resize', do_)
    return () => { qs?.disconnect(); window.removeEventListener('resize', do_) }
  }, [])
  useEffect(() => { if (kt) onKichThuoc?.(kt) }, [kt, onKichThuoc])

  // ---- Đồng bộ dữ liệu sang bộ vẽ ----
  useEffect(() => {
    const rd = rdRef.current
    if (!san || !rd || !kt) return
    rd.datKichThuoc(kt.rong, kt.cao, window.devicePixelRatio || 1)
    rd.datTheGioi(rongTrang, caoTrang)
    rd.datKhungNhin(view)
    for (const ten of TEN_LOP) {
      const nguon = ten === 'matna' ? matNa?.canvas ?? null : lop[ten]?.source ?? null
      const dau = ten === 'matna' ? `${nguon ? 1 : 0}:${phienBanMatNa}` : null
      const cu = daNap.current[ten]
      if (!cu || cu.nguon !== nguon || cu.dau !== dau) {
        rd.datLop(ten, nguon)
        daNap.current[ten] = { nguon, dau }
      }
      rd.datTrangThaiLop(ten, trangThaiLop[ten])
    }
    rd.ve()
  }, [san, kt, rongTrang, caoTrang, view, lop, trangThaiLop, matNa, phienBanMatNa])

  // ---- Cuộn chuột = zoom quanh con trỏ (phải là listener không-thụ-động mới chặn được cuộn trang) ----
  useEffect(() => {
    const el = stageRef.current
    const khiCuon = (e) => {
      e.preventDefault()
      const r = el.getBoundingClientRect()
      const v = viewRef.current
      onView(zoomQuanhDiem(v, v.zoom * Math.exp(-e.deltaY * 0.0015), e.clientX - r.left, e.clientY - r.top))
    }
    el.addEventListener('wheel', khiCuon, { passive: false })
    return () => el.removeEventListener('wheel', khiCuon)
  }, [onView])

  const viTri = (e) => {
    const r = stageRef.current.getBoundingClientRect()
    return { px: e.clientX - r.left, py: e.clientY - r.top }
  }

  const veNetMoi = (net, tuDiem) => {
    matNa.veNet(net, tuDiem)
    const rd = rdRef.current
    if (!rd) return
    rd.datLop('matna', matNa.canvas)
    rd.ve()
  }

  const khiNhan = (e) => {
    if (e.button > 0 || (khoa && congCu !== 'keo' && congCu !== 'hut')) return
    const { px, py } = viTri(e)
    const diem = manSangAnh(view, px, py)
    const batDau = (t) => {
      try { stageRef.current.setPointerCapture?.(e.pointerId) } catch { /* jsdom/cũ: bỏ qua */ }
      thao.current = t
    }
    if (congCu === 'keo') {
      batDau({ loai: 'pan', px, py, v: view })
    } else if (congCu === 'but' || congCu === 'tay') {
      if (!matNa) return
      const net = { diem: [{ x: diem.x, y: diem.y }], co: coCo, tay: congCu === 'tay' || e.altKey }
      batDau({ loai: 'net', net })
      veNetMoi(net, 0)
    } else if (congCu === 'hut') {
      const nguon = ['dich', 'sach', 'goc']
        .map((k) => (trangThaiLop[k]?.hien ? lop[k]?.source : null)).find(Boolean)
      const mau = nguon ? layMauTai(nguon, rongTrang, caoTrang, diem.x, diem.y) : null
      onHutMau?.(mau, px, py)
    } else if (congCu === 'chon') {
      const vung = e.target.closest?.('[data-vung]')
      if (!vung) return
      const id = vung.getAttribute('data-vung')
      const r = regions.find((x) => x.id === id)
      if (!r) return
      onChon(id)
      const kieu = e.target.closest('[data-goc]')?.getAttribute('data-goc') ?? 'move'
      batDau({ loai: 'khung', id, kieu, px, py, bbox: { ...r.bbox } })
    }
  }

  const khiDiChuyen = (e) => {
    const { px, py } = viTri(e)
    setConTro({ px, py })
    const t = thao.current
    if (!t) return
    if (t.loai === 'pan') {
      onView({ ...t.v, panX: t.v.panX + (px - t.px), panY: t.v.panY + (py - t.py) })
    } else if (t.loai === 'net') {
      const d = manSangAnh(view, px, py)
      t.net.diem.push({ x: d.x, y: d.y })
      veNetMoi(t.net, t.net.diem.length - 1)
    } else if (t.loai === 'khung') {
      const dx = (px - t.px) / view.zoom
      const dy = (py - t.py) / view.zoom
      t.moi = bboxSauKeo(t.kieu, t.bbox, dx, dy, rongTrang, caoTrang)
      setTam({ id: t.id, bbox: t.moi })
    }
  }

  const khiNha = () => {
    const t = thao.current
    thao.current = null
    if (!t) return
    if (t.loai === 'net') {
      onNetMoi?.(t.net)
    } else if (t.loai === 'khung') {
      setTam(null)
      const m = t.moi
      if (m && (m.x !== t.bbox.x || m.y !== t.bbox.y || m.w !== t.bbox.w || m.h !== t.bbox.h)) {
        onKeoXong?.(t.id, m)
      }
    }
  }

  const conBut = congCu === 'but' || congCu === 'tay'
  const dau = {
    keo: 'grab', chon: 'default', but: 'none', tay: 'none', hut: 'crosshair', t: 'not-allowed',
  }[congCu]

  return (
    <div
      ref={stageRef}
      className={`cv-stage cv-cong-cu-${congCu}`}
      style={{ cursor: dau }}
      data-testid="cv-stage"
      onPointerDown={khiNhan}
      onPointerMove={khiDiChuyen}
      onPointerUp={khiNha}
      onPointerCancel={khiNha}
      onPointerLeave={() => setConTro(null)}
    >
      <canvas
        key={khoaCanvas}
        ref={canvasRef}
        className="cv-canvas"
        role="img"
        aria-label="Trang truyện"
      />
      {/* Lớp khung chữ: DOM đặt theo bbox × zoom + dịch. Không nhận chuột trừ khi đang ở công cụ Chọn. */}
      <div className="cv-khung-lop" hidden={!san}>
        {regions.map((r) => {
          const b = tam?.id === r.id ? tam.bbox : r.bbox
          const chon = dangChon === r.id
          const tran = r.fit_status === 'overflow_warning'
          const thieu = r.fit_status === 'font_missing_glyph'
          return (
            <div
              key={r.id}
              data-vung={r.id}
              role="button"
              tabIndex={-1}
              aria-label={`Khung chữ ${r.reading_order ?? ''}`.trim()}
              aria-pressed={chon}
              className={`cv-khung${chon ? ' dang-chon' : ''}${tran ? ' tran' : ''}${thieu ? ' thieu' : ''}`}
              style={{
                left: view.panX + b.x * view.zoom,
                top: view.panY + b.y * view.zoom,
                width: b.w * view.zoom,
                height: b.h * view.zoom,
                pointerEvents: congCu === 'chon' ? 'auto' : 'none',
                cursor: congCu === 'chon' ? 'move' : 'inherit',
              }}
            >
              {r.reading_order != null && <span className="cv-so-thu-tu">{r.reading_order}</span>}
              {chon && congCu === 'chon' && (
                <>
                  <span className="cv-xoay-day" aria-hidden="true" />
                  <span
                    className="cv-xoay"
                    title="Chưa hỗ trợ xoay"
                    aria-label="Tay xoay (chưa hỗ trợ)"
                    aria-disabled="true"
                  />
                  {GOC.map((g) => (
                    <span
                      key={g}
                      data-goc={g}
                      className="cv-tay-nam"
                      role="button"
                      aria-label={`Kéo góc ${TEN_GOC[g]} để đổi cỡ`}
                      style={{ ...VI_TRI_GOC[g], cursor: CON_TRO_GOC[g] }}
                    />
                  ))}
                </>
              )}
            </div>
          )
        })}
      </div>

      {conBut && conTro && (
        <span
          className="cv-vong-co"
          aria-hidden="true"
          style={{
            left: conTro.px, top: conTro.py,
            width: coCo * view.zoom, height: coCo * view.zoom,
          }}
        />
      )}
    </div>
  )
}
