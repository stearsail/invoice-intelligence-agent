import { useEffect, useRef, useState } from 'react'
import { uploadImages, getPendingJobs } from '../lib/api'
import { formatDateTime } from '../lib/format'
import { StatusBadge } from '../components/JobTable'

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

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

  function addFiles(fileList) {
    setFiles((prev) => {
      const seen = new Set(prev.map((f) => `${f.name}:${f.size}`))
      const additions = Array.from(fileList).filter(
        (f) => !seen.has(`${f.name}:${f.size}`)
      )
      return [...prev, ...additions]
    })
    // reset so picking the same file again (after removing it) still fires onChange
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  function removeFile(index) {
    setFiles((prev) => prev.filter((_, i) => i !== index))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    if (files.length === 0) return
    setError(null)
    try {
      await uploadImages(files)
      setFiles([])
      loadPendingJobs()
    } catch (err) {
      setError(err.message)
    }
  }

  const totalSize = files.reduce((sum, f) => sum + f.size, 0)

  return (
    <div className="mx-auto w-full px-[5%] py-10">
      <h1 className="mb-6 text-2xl font-semibold">Upload — OCR Extraction</h1>

      <form onSubmit={handleSubmit}>
        <input
          ref={fileInputRef}
          type="file"
          accept="image/png,image/jpeg"
          multiple
          onChange={(e) => addFiles(e.target.files)}
          className="hidden"
        />

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={() => fileInputRef.current?.click()}
            className="flex cursor-pointer items-center gap-2 rounded border border-edge-strong bg-surface-hover px-4 py-2 text-sm font-medium text-body hover:bg-elevated"
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
            Add file
          </button>
          <button
            type="submit"
            disabled={files.length === 0}
            className="cursor-pointer rounded bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40"
          >
            Submit{files.length > 0 ? ` ${files.length}` : ''} for processing
          </button>
        </div>

        {files.length > 0 && (
          <div className="mt-4 max-w-2xl rounded border border-edge">
            <div className="flex items-center justify-between border-b border-edge px-3 py-2">
              <span className="text-sm text-muted">
                {files.length} file{files.length !== 1 ? 's' : ''} · {formatSize(totalSize)}
              </span>
              <button
                type="button"
                onClick={() => setFiles([])}
                className="cursor-pointer text-xs font-medium text-red-400 hover:underline"
              >
                Clear all
              </button>
            </div>
            <div className="flex max-h-64 flex-wrap gap-2 overflow-y-auto p-3">
              {files.map((file, i) => (
                <span
                  key={`${file.name}:${file.size}:${i}`}
                  className="inline-flex max-w-[14rem] items-center gap-1.5 rounded-full border border-edge bg-surface-hover py-1 pr-1.5 pl-3 text-xs"
                >
                  <span className="truncate text-body">{file.name}</span>
                  <button
                    type="button"
                    onClick={() => removeFile(i)}
                    aria-label={`Remove ${file.name}`}
                    className="shrink-0 cursor-pointer rounded-full p-0.5 text-muted hover:bg-elevated hover:text-red-400"
                  >
                    <svg
                      className="h-3.5 w-3.5"
                      viewBox="0 0 20 20"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2"
                    >
                      <path d="M6 6l8 8M14 6l-8 8" strokeLinecap="round" />
                    </svg>
                  </button>
                </span>
              ))}
            </div>
          </div>
        )}
      </form>

      {error && <p className="mt-4 text-sm text-red-400">{error}</p>}

      <h2 className="mt-10 mb-3 text-lg font-semibold">
        Pending jobs{pendingJobs && ` — ${pendingJobs.length}`}
      </h2>
      {pendingJobs && pendingJobs.length === 0 && (
        <p className="text-sm text-muted">Nothing currently processing.</p>
      )}
      {pendingJobs && pendingJobs.length > 0 && (
        <ul className="divide-y divide-edge rounded border border-edge">
          {pendingJobs.map((item) => (
            <li
              key={item.job_id}
              className="flex items-center justify-between px-4 py-2 text-sm"
            >
              <span className="font-medium">Job {item.job_id}</span>
              <span className="text-muted">{formatDateTime(item.created_at)}</span>
              <StatusBadge status={item.status} attempts={item.attempts} />
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
