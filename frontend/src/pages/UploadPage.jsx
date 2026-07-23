import { useEffect, useRef, useState } from 'react'
import { uploadImages, getPendingJobs } from '../lib/api'
import { formatDateTime } from '../lib/format'

export default function UploadPage() {
  const [files, setFiles] = useState([])
  const [error, setError] = useState(null)
  const [pendingJobs, setPendingJobs] = useState(null)
  const fileInputRef = useRef(null)

  async function loadPendingJobs() {
    try {
      setPendingJobs(await getPendingJobs())
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    loadPendingJobs()
    const interval = setInterval(loadPendingJobs, 2000)
    return () => clearInterval(interval)
  }, [])

  async function handleSubmit(event) {
    event.preventDefault()
    if (files.length === 0) return
    setError(null)
    try {
      await uploadImages(files)
      setFiles([])
      if (fileInputRef.current) fileInputRef.current.value = ''
      loadPendingJobs()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="mx-auto w-full px-[5%] py-10">
      <h1 className="mb-6 text-2xl font-semibold">Upload — OCR Extraction</h1>

      <form onSubmit={handleSubmit} className="flex items-center gap-3">
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg"
          multiple
          onChange={(e) => setFiles(Array.from(e.target.files))}
          className="hidden"
        />
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="flex cursor-pointer items-center gap-2 rounded bg-blue-600 px-4 py-2 text-sm font-medium text-white hover:bg-blue-700"
        >
          <svg
            className="h-4 w-4"
            viewBox="0 0 20 20"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
          >
            <path
              d="M10 13V3m0 0L6 7m4-4l4 4M4 14v1.5A1.5 1.5 0 0 0 5.5 17h9a1.5 1.5 0 0 0 1.5-1.5V14"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          Choose file
        </button>
        <button
          type="submit"
          disabled={files.length === 0}
          className="cursor-pointer rounded bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          Submit for processing
        </button>
        {files.length > 0 && (
          <span className="text-sm text-gray-600">
            {files.length === 1
              ? files[0].name
              : `${files.length} files selected`}
          </span>
        )}

      </form>

      {error && <p className="mt-4 text-sm text-red-600">{error}</p>}

      <h2 className="mt-10 mb-3 text-lg font-semibold">
        Pending jobs{pendingJobs && ` — ${pendingJobs.length}`}
      </h2>
      {pendingJobs && pendingJobs.length === 0 && (
        <p className="text-sm text-gray-500">Nothing currently processing.</p>
      )}
      {pendingJobs && pendingJobs.length > 0 && (
        <ul className="divide-y divide-gray-100 rounded border border-gray-200">
          {pendingJobs.map((item) => (
            <li
              key={item.job_id}
              className="flex items-center justify-between px-4 py-2 text-sm"
            >
              <span className="font-medium">Job {item.job_id}</span>
              <span className="text-gray-500">{formatDateTime(item.created_at)}</span>
              <span className="text-gray-500">still processing…</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
