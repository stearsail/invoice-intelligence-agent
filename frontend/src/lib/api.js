const API_BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8001'

async function request(path, options) {
  const response = await fetch(`${API_BASE}${path}`, options)
  if (!response.ok) {
    const text = await response.text()
    throw new Error(`${response.status}: ${text}`)
  }
  return response.json()
}

export function uploadImage(file) {
  const formData = new FormData()
  formData.append('file', file)
  return request('/extraction/upload_image', { method: 'POST', body: formData })
}

export function getJobStatus(jobId) {
  return request(`/extraction/status/${jobId}`)
}

export function getReviewQueue() {
  return request('/ledger/review')
}

export function getFullLedger() {
  return request('/ledger/full')
}