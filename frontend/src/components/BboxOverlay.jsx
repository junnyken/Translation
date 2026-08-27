import { useCallback, useEffect, useRef, useState } from 'react'

const CAN_DUOI = 8 // không cho kéo khung nhỏ hơn ngần này (pixel ảnh thật)

/**
 * Vẽ khung chữ chồng lên ảnh xem thử, cho kéo/co giãn.
 *
 * Toạ độ khung lưu theo **pixel của ảnh gốc**, còn ảnh hiển thị bị thu nhỏ theo bề rộng màn hình,
 * nên mọi thao tác chuột phải quy đổi qua `tyLe`. Tính sai chỗ này là khung lệch hẳn khỏi bubble.
 */
export default function BboxOverlay({ src, regions, dangChon, onChon, onLuuBbox, hienCanhBao }) {
  const anhRef = useRef(null)
  // `null` = CHƯA đo được tỷ lệ. Không được mặc định 1: ảnh hiển thị bị thu nhỏ so với ảnh gốc,
  // vẽ khung ở tỷ lệ 1 sẽ lệch hẳn khỏi bubble (và tràn ra ngoài ảnh).
  const [tyLe, setTyLe] = useState(null)
  const [keo, setKeo] = useState(null)
  const [tam, setTam] = useState(null)

  const doTyLe = useCallback(() => {
    const anh = anhRef.current
    // `naturalWidth` chỉ có sau khi ảnh tải xong — đo sớm hơn là ra 0.
    if (anh?.naturalWidth) setTyLe(anh.clientWidth / anh.naturalWidth)
  }, [])

  useEffect(() => {
    doTyLe()
    const quanSat = new ResizeObserver(doTyLe)
    if (anhRef.current) quanSat.observe(anhRef.current)
    window.addEventListener('resize', doTyLe)
    return () => {
      quanSat.disconnect()
      window.removeEventListener('resize', doTyLe)
    }
  }, [doTyLe, src])

  useEffect(() => {
    if (!keo) return
    const diChuyen = (e) => {
      const dx = (e.clientX - keo.batDauX) / tyLe
      const dy = (e.clientY - keo.batDauY) / tyLe
      setTam(
        keo.kieu === 'move'
          ? { ...keo.bbox, x: Math.max(0, keo.bbox.x + dx), y: Math.max(0, keo.bbox.y + dy) }
          : {
              ...keo.bbox,
              w: Math.max(CAN_DUOI, keo.bbox.w + dx),
              h: Math.max(CAN_DUOI, keo.bbox.h + dy),
            },
      )
    }
    const nha = () => {
      if (tam) onLuuBbox(keo.regionId, tam)
      setKeo(null)
      setTam(null)
    }
    window.addEventListener('pointermove', diChuyen)
    window.addEventListener('pointerup', nha)
    return () => {
      window.removeEventListener('pointermove', diChuyen)
      window.removeEventListener('pointerup', nha)
    }
  }, [keo, tam, tyLe, onLuuBbox])

  const batDauKeo = (e, region, kieu) => {
    e.preventDefault()
    e.stopPropagation()
    onChon(region.id)
    setKeo({
      regionId: region.id,
      kieu,
      batDauX: e.clientX,
      batDauY: e.clientY,
      bbox: { ...region.bbox },
    })
  }

  return (
    <div className="khung-anh">
      <img ref={anhRef} src={src} alt="Trang truyện đã chèn bản dịch" onLoad={doTyLe} />
      {/* Chưa đo được tỷ lệ thì KHÔNG vẽ khung — thà chưa hiện còn hơn hiện sai chỗ. */}
      <div className="lop-khung" hidden={tyLe === null}>
      {tyLe !== null && regions.map((r) => {
        const b = keo?.regionId === r.id && tam ? tam : r.bbox
        const tran = r.fit_status === 'overflow_warning'
        const canXem = r.ocr_status === 'needs_manual' || r.status === 'low_confidence'
        const lop = [
          'khung',
          dangChon === r.id ? 'dang-chon' : '',
          hienCanhBao && tran ? 'tran' : '',
          hienCanhBao && canXem ? 'can-xem' : '',
        ].join(' ')
        return (
          <div
            key={r.id}
            className={lop}
            style={{
              left: b.x * tyLe,
              top: b.y * tyLe,
              width: b.w * tyLe,
              height: b.h * tyLe,
            }}
            onPointerDown={(e) => batDauKeo(e, r, 'move')}
            title={`Vùng ${r.reading_order ?? '?'} — kéo để dời, kéo góc dưới-phải để đổi cỡ`}
          >
            <span className="so-thu-tu">{r.reading_order ?? '?'}</span>
            <span
              className="tay-nam"
              onPointerDown={(e) => batDauKeo(e, r, 'resize')}
              title="Kéo để đổi kích thước khung"
            />
          </div>
        )
      })}
      </div>
    </div>
  )
}
