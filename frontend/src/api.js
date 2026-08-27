const BASE = '/api/v1'

async function doc(res) {
  if (!res.ok) {
    let chiTiet = res.statusText
    try {
      const body = await res.json()
      chiTiet = body.detail ?? JSON.stringify(body)
    } catch {
      /* body không phải JSON — giữ statusText */
    }
    throw new Error(`${res.status}: ${chiTiet}`)
  }
  return res.json()
}

export const layProject = (id) => fetch(`${BASE}/projects/${id}`).then(doc)
export const layChiTietTrang = (id) => fetch(`${BASE}/pages/${id}/detail`).then(doc)
export const layJob = (id) => fetch(`${BASE}/jobs/${id}`).then(doc)

export const suaVung = (regionId, thayDoi) =>
  fetch(`${BASE}/regions/${regionId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(thayDoi),
  }).then(doc)

export const dichLaiVung = (regionId) =>
  fetch(`${BASE}/regions/${regionId}/re-translate`, { method: 'POST' }).then(doc)

export const docLaiVung = (regionId) =>
  fetch(`${BASE}/regions/${regionId}/re-ocr`, { method: 'POST' }).then(doc)

export const canhLaiVung = (regionId) =>
  fetch(`${BASE}/regions/${regionId}/re-fit`, { method: 'POST' }).then(doc)

/** Chờ job chạy xong. Trả job cuối cùng; ném lỗi nếu job `failed`. */
export async function choJobXong(jobId, { soLanToiDa = 60, nhipMs = 700 } = {}) {
  for (let i = 0; i < soLanToiDa; i++) {
    const job = await layJob(jobId)
    if (job.status === 'done') return job
    if (job.status === 'failed') throw new Error(job.error_log || 'Việc chạy nền bị lỗi')
    await new Promise((r) => setTimeout(r, nhipMs))
  }
  throw new Error('Việc chạy nền quá lâu, chưa xong')
}
