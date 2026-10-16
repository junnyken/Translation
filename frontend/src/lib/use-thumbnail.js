import { useEffect, useState } from 'react'
import * as api from '../api.js'

/** Tải thumbnail trang qua `taiVeBlobUrl` (có mã phiên — `<img src>` trần sẽ 401).
 *
 * Trả `{ tt: 'tai' | 'ok' | 'loi' | 'khong', url }`:
 *  - `khong` = chưa có trang để tải (pageId rỗng) hoặc chưa tới lượt (`bat` = false).
 *  - Blob URL được thu hồi khi đổi trang / gỡ component; kết quả về muộn sau khi gỡ cũng bị thu hồi.
 */
export function useThumbnail(pageId, bat = true) {
  const [kq, setKq] = useState({ tt: 'khong', url: null })
  useEffect(() => {
    if (!pageId || !bat) { setKq({ tt: 'khong', url: null }); return undefined }
    let huy = false
    let url = null
    setKq({ tt: 'tai', url: null })
    api.taiVeBlobUrl(api.duongDanThumbnail(pageId))
      .then((u) => {
        if (huy) { URL.revokeObjectURL(u); return }
        url = u
        setKq({ tt: 'ok', url: u })
      })
      .catch(() => { if (!huy) setKq({ tt: 'loi', url: null }) })
    return () => { huy = true; if (url) URL.revokeObjectURL(url) }
  }, [pageId, bat])
  return kq
}

/** true khi phần tử vào khung nhìn (một lần, rồi thôi theo dõi). Không có IntersectionObserver ⇒ true luôn. */
export function useVaoKhungNhin(ref) {
  const [thay, setThay] = useState(() => typeof IntersectionObserver === 'undefined')
  useEffect(() => {
    if (thay || !ref.current) return undefined
    const io = new IntersectionObserver((ds) => {
      if (ds.some((d) => d.isIntersecting)) { setThay(true); io.disconnect() }
    }, { rootMargin: '200px' })
    io.observe(ref.current)
    return () => io.disconnect()
  }, [thay, ref])
  return thay
}
