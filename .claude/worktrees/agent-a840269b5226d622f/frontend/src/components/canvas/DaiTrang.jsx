/** Chấm trạng thái trang: xong / cần xem lại / lỗi — đúng ba màu của mockup, kèm chữ cho trình đọc màn hình. */
export function chamTrang(status) {
  if (status === 'typeset_done' || status === 'ready_for_export') return { lop: 'ok', chu: 'Xong' }
  if (status === 'detection_failed') return { lop: 'err', chu: 'Lỗi' }
  if (status === 'inpaint_needs_review') return { lop: 'warn', chu: 'Cần xem lại' }
  return { lop: 'dang', chu: 'Đang xử lý' }
}

export default function DaiTrang({ trang, dangMo }) {
  return (
    <aside className="cv-dai" aria-label="Dải trang">
      {trang.map((t) => {
        const c = chamTrang(t.status)
        const on = t.id === dangMo
        return (
          <a
            key={t.id} href={`#canvas=${t.id}`}
            className={`cv-trang${on ? ' on' : ''}`}
            aria-current={on ? 'page' : undefined}
            aria-label={`Trang ${t.order} — ${c.chu}`}
          >
            <span className="cv-the-trang">
              <span className={`cv-cham ${c.lop}`} aria-hidden="true" />
              {t.order}
            </span>
          </a>
        )
      })}
      <div className="cv-chu-giai" aria-label="Chú thích chấm trạng thái">
        <span><b className="ok" />Xong</span>
        <span><b className="warn" />Cần xem lại</span>
        <span><b className="err" />Lỗi</span>
      </div>
    </aside>
  )
}
