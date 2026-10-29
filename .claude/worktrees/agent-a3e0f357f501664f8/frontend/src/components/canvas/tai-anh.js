import { taiVeBlobUrl } from '../../api.js'

/** Tải một ảnh có mã phiên rồi giải mã thành thứ vẽ được lên canvas.
 *
 * Trả `{ source, w, h }`; trả `null` khi máy chủ báo 404 (lớp đó chưa có ảnh — không phải lỗi).
 * Lỗi khác (401, 500, ảnh hỏng) thì ném, để giao diện nói được lớp nào hỏng.
 */
export async function taiLop(url) {
  let blobUrl
  try {
    blobUrl = await taiVeBlobUrl(url)
  } catch (e) {
    if (/^404\b/.test(e?.message ?? '')) return null
    throw e
  }
  try {
    const anh = await new Promise((xong, hong) => {
      const i = new Image()
      i.onload = () => xong(i)
      i.onerror = () => hong(new Error('Ảnh bị hỏng, không mở được'))
      i.src = blobUrl
    })
    return { source: anh, w: anh.naturalWidth, h: anh.naturalHeight }
  } finally {
    // Ảnh đã giải mã xong, giữ blob lại chỉ tốn bộ nhớ (mỗi trang vài MB).
    URL.revokeObjectURL(blobUrl)
  }
}
