import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getFullLedger } from '../lib/api'

function displayValue(value) {
  if (value === null || value === undefined || value === '') return '—'
  if (Array.isArray(value)) return value.length > 0 ? value.join(', ') : '—'
  return String(value)
}

function humanizeKey(key) {
  return key
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

const CATEGORY_STYLES = {
  unverifiable: 'text-amber-700',
  mismatch: 'text-red-700',
  duplicate: 'text-purple-700',
}

export default function JobDetailPage() {
  const { jobId } = useParams()
  const [item, setItem] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function load() {
      try {
        const items = await getFullLedger()
        const match = items.find((i) => String(i.job_id) === jobId)
        setItem(match || false)
      } catch (err) {
        setError(err.message)
      }
    }
    load()
  }, [jobId])

  if (error) return <p className="p-10 text-sm text-red-600">{error}</p>
  if (item === null) return <p className="p-10 text-sm text-gray-500">Loading…</p>
  if (item === false) {
    return (
      <div className="p-10">
        <p className="text-sm text-amber-700">
          This job isn't in the ledger (it may still be pending).
        </p>
        <Link
          to="/ledger"
          className="mt-4 inline-block rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        >
          &larr; Back to Full Ledger
        </Link>
      </div>
    )
  }

  const entry = item.ledger_entry

  return (
    <div className="mx-auto w-full px-[5%] py-10">
      <Link
        to="/ledger"
        className="inline-block rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
      >
        &larr; Back to Full Ledger
      </Link>
      <h1 className="mt-6 mb-6 text-2xl font-semibold">Job {item.job_id}</h1>

      <p className="text-sm">
        <span className="font-medium">Status:</span> {item.status}
      </p>
      {item.error && (
        <p className="mt-1 text-sm text-red-600">
          <span className="font-medium">Error:</span> {item.error}
        </p>
      )}
      {item.ledger_entry_error && (
        <p className="mt-1 text-sm text-red-600">
          <span className="font-medium">Ledger decode error:</span>{' '}
          {item.ledger_entry_error}
        </p>
      )}

      {!entry && (
        <p className="mt-4 text-sm text-gray-500">
          No ledger entry — nothing was extracted for this job.
        </p>
      )}

      {entry && (
        <>
          <p className="mt-4 flex items-center gap-2 text-sm">
            <span className="font-medium">Needs review:</span>
            {entry.needs_review ? (
              <span className="inline-block rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-700">
                Yes
              </span>
            ) : (
              <span className="inline-block rounded-full bg-green-100 px-2 py-0.5 text-xs font-medium text-green-700">
                No
              </span>
            )}
          </p>
          {entry.review_reason && entry.review_reason.length > 0 && (
            <div className="mt-2 text-sm">
              <span className="font-medium">Review reasons:</span>
              <ul className="mt-1 list-disc space-y-1 pl-5">
                {entry.review_reason.map((issue, idx) => (
                  <li
                    key={idx}
                    className={CATEGORY_STYLES[issue.category] || 'text-gray-700'}
                  >
                    <span className="text-xs font-medium uppercase opacity-70">
                      {issue.category}
                    </span>{' '}
                    — {issue.message}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <h2 className="mt-8 mb-2 text-lg font-semibold">Fields</h2>
          <table className="w-full border-collapse text-left text-sm">
            <tbody>
              {Object.entries(entry.invoice_data)
                .filter(([key]) => key !== 'line_items')
                .map(([key, value]) => (
                  <tr key={key} className="border-b border-gray-100">
                    <td className="w-48 py-1.5 pr-4 font-medium text-gray-600">
                      {humanizeKey(key)}
                    </td>
                    <td className="py-1.5">{displayValue(value)}</td>
                  </tr>
                ))}
            </tbody>
          </table>

          <h2 className="mt-8 mb-2 text-lg font-semibold">Line items</h2>
          {entry.invoice_data.line_items && entry.invoice_data.line_items.length > 0 ? (
            <table className="w-full border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="py-2 pr-4 font-medium text-gray-600">#</th>
                  <th className="py-2 pr-4 font-medium text-gray-600">Description</th>
                  <th className="py-2 pr-4 font-medium text-gray-600">Unit price</th>
                  <th className="py-2 pr-4 font-medium text-gray-600">Quantity</th>
                  <th className="py-2 font-medium text-gray-600">Line total</th>
                </tr>
              </thead>
              <tbody>
                {entry.invoice_data.line_items.map((line, idx) => (
                  <tr key={idx} className="border-b border-gray-100">
                    <td className="py-1.5 pr-4 text-gray-500">{idx + 1}</td>
                    <td className="py-1.5 pr-4">{displayValue(line.description)}</td>
                    <td className="py-1.5 pr-4">{displayValue(line.unit_price)}</td>
                    <td className="py-1.5 pr-4">{displayValue(line.quantity)}</td>
                    <td className="py-1.5">{displayValue(line.line_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="text-sm text-gray-500">No line items.</p>
          )}
        </>
      )}
    </div>
  )
}
