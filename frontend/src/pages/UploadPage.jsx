import { useEffect, useRef, useState } from 'react'
import {
  uploadImages,
  getPendingJobs,
  getErroredJobs,
  retryJob,
  deleteJob,
  getJobImageUrl,
} from '../lib/api'
import { formatDateTime } from '../lib/format'
import { StatusBadge } from '../components/JobTable'
import Pagination from '../components/Pagination'

const ERRORED_PAGE_SIZE = 20

function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

export default function UploadPage() {
  const [files, setFiles] = useState([])
  const [error, setError] = useState(null)
  const [pendingJobs, setPendingJobs] = useState(null)
  const [erroredJobs, setErroredJobs] = useState(null)
  const [busyJobId, setBusyJobId] = useState(null)
  const [bulkBusy, setBulkBusy] = useState(false)
  const [erroredPage, setErroredPage] = useState(1)
  const fileInputRef = useRef(null)

  async function loadJobs() {
    try {
      const [pending, errored] = await Promise.all([
        getPendingJobs(),
        getErroredJobs(),
      ])
      setPendingJobs(pending)
      setErroredJobs(errored)
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    loadJobs()
    const interval = setInterval(loadJobs, 2000)
    return () => clearInterval(interval)
  }, [])

  async function handleRetry(jobId) {
    setBusyJobId(jobId)
    setError(null)
    try {
      await retryJob(jobId)
      await loadJobs()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyJobId(null)
    }
  }

  async function handleDelete(jobId) {
    if (!window.confirm(`Delete job ${jobId}? This cannot be undone.`)) return
    setBusyJobId(jobId)
    setError(null)
    try {
      await deleteJob(jobId)
      await loadJobs()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyJobId(null)
    }
  }

  async function handleRetryAll() {
    if (!erroredJobs || erroredJobs.length === 0) return
    setBulkBusy(true)
    setError(null)
    try {
      await Promise.all(erroredJobs.map((item) => retryJob(item.job_id)))
      await loadJobs()
    } catch (err) {
      setError(err.message)
    } finally {
      setBulkBusy(false)
    }
  }

  async function handleDeleteAll() {
    if (!erroredJobs || erroredJobs.length === 0) return
    if (
      !window.confirm(
        `Delete all ${erroredJobs.length} errored jobs? This cannot be undone.`
      )
    )
      return
    setBulkBusy(true)
    setError(null)
    try {
      await Promise.all(erroredJobs.map((item) => deleteJob(item.job_id)))
      await loadJobs()
    } catch (err) {
      setError(err.message)
    } finally {
      setBulkBusy(false)
    }
  }

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
      loadJobs()
    } catch (err) {
      setError(err.message)
    }
  }

  const totalSize = files.reduce((sum, f) => sum + f.size, 0)

  const erroredTotalPages = erroredJobs
    ? Math.max(1, Math.ceil(erroredJobs.length / ERRORED_PAGE_SIZE))
    : 1
  const erroredCurrentPage = Math.min(erroredPage, erroredTotalPages)
  const erroredPageItems = erroredJobs
    ? erroredJobs.slice(
        (erroredCurrentPage - 1) * ERRORED_PAGE_SIZE,
        erroredCurrentPage * ERRORED_PAGE_SIZE
      )
    : null

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

      <div className="mt-10 mb-3 flex items-center justify-between">
        <h2 className="text-lg font-semibold">
          Errored jobs{erroredJobs && ` — ${erroredJobs.length}`}
        </h2>
        {erroredJobs && erroredJobs.length > 0 && (
          <div className="flex items-center gap-2">
            <button
              type="button"
              disabled={bulkBusy}
              onClick={handleRetryAll}
              className="cursor-pointer rounded border border-accent px-2 py-1 text-xs font-medium text-accent hover:bg-accent/10 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {bulkBusy ? 'Working…' : 'Retry all'}
            </button>
            <button
              type="button"
              disabled={bulkBusy}
              onClick={handleDeleteAll}
              className="cursor-pointer rounded bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {bulkBusy ? 'Working…' : 'Delete all'}
            </button>
          </div>
        )}
      </div>
      {erroredJobs && erroredJobs.length === 0 && (
        <p className="text-sm text-muted">Nothing has failed.</p>
      )}
      {erroredJobs && erroredJobs.length > 0 && (
        <>
          <ul className="divide-y divide-edge rounded border border-edge">
            {erroredPageItems.map((item) => (
              <li key={item.job_id} className="flex items-center gap-3 px-4 py-2 text-sm">
                <a
                  href={getJobImageUrl(item.job_id)}
                  target="_blank"
                  rel="noreferrer"
                  className="shrink-0"
                >
                  <img
                    src={getJobImageUrl(item.job_id)}
                    alt={`Document for job ${item.job_id}`}
                    loading="lazy"
                    className="h-10 w-10 rounded border border-edge object-cover"
                  />
                </a>
                <span className="font-medium">Job {item.job_id}</span>
                <span className="text-muted">{formatDateTime(item.created_at)}</span>
                <StatusBadge status={item.status} />
                <span className="flex-1 truncate text-xs text-muted" title={item.error}>
                  {item.error}
                </span>
                <button
                  type="button"
                  disabled={busyJobId === item.job_id || bulkBusy}
                  onClick={() => handleRetry(item.job_id)}
                  className="cursor-pointer rounded border border-accent px-2 py-1 text-xs font-medium text-accent hover:bg-accent/10 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Retry
                </button>
                <button
                  type="button"
                  disabled={busyJobId === item.job_id || bulkBusy}
                  onClick={() => handleDelete(item.job_id)}
                  className="cursor-pointer rounded bg-red-600 px-2 py-1 text-xs font-medium text-white hover:bg-red-500 disabled:cursor-not-allowed disabled:opacity-40"
                >
                  Delete
                </button>
              </li>
            ))}
          </ul>
          <Pagination
            page={erroredCurrentPage}
            totalPages={erroredTotalPages}
            onPageChange={setErroredPage}
          />
        </>
      )}
    </div>
  )
}
