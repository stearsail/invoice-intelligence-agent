import { useEffect, useState } from 'react'
import { useParams, Link } from 'react-router-dom'
import { getJobDetail, getJobImageUrl } from '../lib/api'
import { CATEGORY_STYLES, toFormInvoice } from '../lib/invoiceForm'

const labelClass = 'block text-xs font-medium text-gray-600 mb-1'

function displayValue(value) {
  if (value === null || value === undefined || value === '') return '—'
  return String(value)
}

function ReadOnlyField({ label, value }) {
  return (
    <div>
      <label className={labelClass}>{label}</label>
      <p className="text-sm">{displayValue(value)}</p>
    </div>
  )
}

const DOCUMENT_TYPE_LABELS = {
  invoice: 'Invoice',
  receipt: 'Receipt',
  credit_note: 'Credit Note',
}

export default function JobDetailPage() {
  const { jobId } = useParams()
  const [form, setForm] = useState(null)
  const [error, setError] = useState(null)
  const [reviewInfo, setReviewInfo] = useState(null)

  useEffect(() => {
    async function load() {
      try {
        const item = await getJobDetail(jobId)
        setForm(toFormInvoice(item.ledger_entry?.invoice_data))
        setReviewInfo({
          jobError: item.error,
          reviewReason: item.ledger_entry?.review_reason ?? [],
        })
      } catch (err) {
        if (err.status === 404) {
          setForm(false)
        } else {
          setError(err.message)
        }
      }
    }
    load()
  }, [jobId])

  if (error) return <p className="p-10 text-sm text-red-600">{error}</p>
  if (form === null) return <p className="p-10 text-sm text-gray-500">Loading…</p>
  if (form === false) {
    return (
      <div className="p-10">
        <p className="text-sm text-amber-700">This job doesn't exist.</p>
        <Link
          to="/ledger"
          className="mt-4 inline-block rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        >
          &larr; Back to Ledger
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full px-[1%]">
      <div className="grid grid-cols-2 gap-4 bg-gray-100 p-2">
        <div className="sticky top-10 max-h-[90vh] space-y-2 self-start overflow-y-auto pr-2">
          <div>
            {reviewInfo &&
              (reviewInfo.jobError || reviewInfo.reviewReason.length > 0) && (
                <div className="mb-6 rounded border border-amber-200 bg-amber-50 px-4 py-2">
                  <h2 className="text-sm font-semibold text-amber-900">Issues:</h2>
                  {reviewInfo.jobError && (
                    <p className="text-sm text-red-700">{reviewInfo.jobError}</p>
                  )}
                  {reviewInfo.reviewReason.length > 0 && (
                    <ul className="list-disc space-y-1 pl-5 text-sm">
                      {reviewInfo.reviewReason.map((issue, idx) => (
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
                  )}
                </div>
              )}
          </div>
          <div className="grid grid-cols-2 gap-5">
            <div>
              <label className={labelClass}>Document type</label>
              <p className="text-sm">
                {DOCUMENT_TYPE_LABELS[form.document_type] || form.document_type}
              </p>
            </div>
            <ReadOnlyField label="Number" value={form.invoice_number} />
          </div>
          <div className="grid grid-cols-2 gap-5">
            <ReadOnlyField label="Issue date" value={form.issue_date} />
            <ReadOnlyField label="Due date" value={form.due_date} />
          </div>

          <div className="grid grid-cols-2 gap-5">
            <div>
              <h2 className="mb-2 text-sm font-semibold">Vendor</h2>
              <div className="space-y-2">
                <ReadOnlyField label="Name" value={form.vendor.name} />
                <ReadOnlyField label="Address" value={form.vendor.address} />
                <ReadOnlyField label="Tax ID" value={form.vendor.tax_id} />
                <ReadOnlyField label="IBAN" value={form.vendor.iban} />
              </div>
            </div>
            <div>
              <h2 className="mb-2 text-sm font-semibold">Customer</h2>
              <div className="space-y-2">
                <ReadOnlyField label="Name" value={form.customer.name} />
                <ReadOnlyField label="Address" value={form.customer.address} />
                <ReadOnlyField label="Tax ID" value={form.customer.tax_id} />
              </div>
            </div>
          </div>

          <div>
            <h2 className="mb-2 text-sm font-semibold">Line items</h2>
            <table className="w-full border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-gray-200">
                  <th className="py-1 pr-2 font-medium text-gray-600">#</th>
                  <th className="py-1 pr-2 font-medium text-gray-600">Description</th>
                  <th className="py-1 pr-2 font-medium text-gray-600">Unit price</th>
                  <th className="py-1 pr-2 font-medium text-gray-600">Quantity</th>
                  <th className="py-1 pr-2 font-medium text-gray-600">Line total</th>
                </tr>
              </thead>
              <tbody>
                {form.line_items.map((line, idx) => (
                  <tr key={idx} className="border-b border-gray-100">
                    <td className="py-1 pr-2 text-gray-500">{idx + 1}</td>
                    <td className="py-1 pr-2">{displayValue(line.description)}</td>
                    <td className="py-1 pr-2">{displayValue(line.unit_price)}</td>
                    <td className="py-1 pr-2">{displayValue(line.quantity)}</td>
                    <td className="py-1 pr-2">{displayValue(line.line_total)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid grid-cols-5 gap-4">
            <ReadOnlyField label="Currency" value={form.currency} />
            <ReadOnlyField label="Subtotal" value={form.subtotal} />
            <ReadOnlyField label="Tax" value={form.tax} />
            <ReadOnlyField label="Service charge" value={form.service_charge} />
            <ReadOnlyField label="Discount" value={form.discount} />
          </div>

          <div className="w-48">
            <ReadOnlyField label="Grand total" value={form.grand_total} />
          </div>

          <div className="mt-5 flex items-center gap-3">
            <Link
              to={`/job/${jobId}/edit`}
              className="rounded bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800"
            >
              Edit
            </Link>
            <Link
              to="/ledger"
              className="rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
            >
              Back
            </Link>
          </div>
        </div>

        <div className="flex justify-center">
          <a href={getJobImageUrl(jobId)} target="_blank" rel="noreferrer">
            <img
              src={getJobImageUrl(jobId)}
              alt={`Document for job ${jobId}`}
              className="rounded border border-gray-200"
            />
          </a>
        </div>
      </div>
    </div>
  )
}
