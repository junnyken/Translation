/** Bộ icon SVG tối thiểu — vẽ tay, không kéo thêm thư viện icon cho 6 hình.
 *
 * Icon LUÔN đi kèm nhãn chữ: nó là lớp thông tin thứ hai bên cạnh chữ và màu, để người không
 * phân biệt được màu vẫn đọc được trạng thái.
 */
const DUONG = {
  'dong-ho': <><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></>,
  quay: <path d="M21 12a9 9 0 1 1-6.2-8.6" />,
  tich: <path d="m20 6-11 11-5-5" />,
  canh: <><path d="M12 9v4" /><path d="M12 17h.01" /><path d="M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z" /></>,
  'tam-dung': <><rect x="6" y="5" width="4" height="14" rx="1" /><rect x="14" y="5" width="4" height="14" rx="1" /></>,
  x: <><path d="M18 6 6 18" /><path d="m6 6 12 12" /></>,
  'tai-len': <><path d="M12 16V4" /><path d="m6 10 6-6 6 6" /><path d="M4 20h16" /></>,
  sach: <><path d="M4 5a2 2 0 0 1 2-2h12v18H6a2 2 0 0 1-2-2Z" /><path d="M8 3v18" /></>,
  'mui-ten-phai': <><path d="M5 12h14" /><path d="m12 5 7 7-7 7" /></>,
  'mui-ten-trai': <><path d="M19 12H5" /><path d="m12 19-7-7 7-7" /></>,
  tai_ve: <><path d="M12 4v12" /><path d="m6 12 6 6 6-6" /><path d="M4 20h16" /></>,
}

export default function Icon({ ten, co = 16, className = '' }) {
  const duong = DUONG[ten]
  if (!duong) return null
  return (
    <svg
      className={`icon ${ten === 'quay' ? 'icon-quay' : ''} ${className}`}
      width={co} height={co} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true" focusable="false"
    >
      {duong}
    </svg>
  )
}
