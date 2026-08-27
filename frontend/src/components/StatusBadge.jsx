const NHAN = {
  fit_ok: { chu: 'Vừa khung', lop: 'ok' },
  overflow_warning: { chu: 'Tràn khung', lop: 'loi' },
  pending: { chu: 'Chưa canh', lop: 'cho' },
  needs_manual: { chu: 'Cần đọc lại', lop: 'canh' },
  low_confidence: { chu: 'Khung kém tin cậy', lop: 'canh' },
  fallback_used: { chu: 'Dịch bằng bản dự phòng', lop: 'canh' },
  ok: { chu: 'Ổn', lop: 'ok' },
}

/** Hiện cảnh báo bằng chữ, KHÔNG chỉ bằng màu — người mù màu vẫn đọc được. */
export default function StatusBadge({ trangThai }) {
  if (!trangThai) return null
  const { chu, lop } = NHAN[trangThai] ?? { chu: trangThai, lop: 'cho' }
  return <span className={`badge ${lop}`}>{chu}</span>
}
