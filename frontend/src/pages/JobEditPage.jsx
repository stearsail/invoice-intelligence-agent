import { useEffect, useState } from 'react'
import { useParams, useNavigate, Link } from 'react-router-dom'
import { getJobDetail, submitJobEdit, deleteJob, getJobImageUrl } from '../lib/api'
import {
  CATEGORY_STYLES,
  toFormInvoice,
  BLANK_LINE_ITEM,
  lineItemHasData,
} from '../lib/invoiceForm'

function blankToNull(value) {
  return value === '' ? null : value
}

function toPayload(form) {
  const vendor = form.vendor.name.trim()
    ? {
      name: form.vendor.name,
      address: blankToNull(form.vendor.address),
      tax_id: blankToNull(form.vendor.tax_id),
      iban: blankToNull(form.vendor.iban),
    }
    : null
  const customer = form.customer.name.trim()
    ? {
      name: form.customer.name,
      address: blankToNull(form.customer.address),
      tax_id: blankToNull(form.customer.tax_id),
      iban: blankToNull(form.customer.iban),
    }
    : null

  return {
    document_type: form.document_type,
    vendor,
    customer,
    invoice_number: blankToNull(form.invoice_number),
    issue_date: blankToNull(form.issue_date),
    due_date: blankToNull(form.due_date),
    currency: form.currency.toUpperCase(),
    line_items: form.line_items
      .filter((line) => line.description.trim() !== '' && !line.marked)
      .map((line) => ({
        description: blankToNull(line.description),
        unit_price: blankToNull(line.unit_price),
        quantity: blankToNull(line.quantity),
        line_total: blankToNull(line.line_total),
      })),
    grand_total: form.grand_total,
    subtotal: blankToNull(form.subtotal),
    tax: blankToNull(form.tax),
    service_charge: blankToNull(form.service_charge),
    discount: blankToNull(form.discount),
    confidence_notes: form.confidence_notes,
  }
}

const inputClass =
  'w-full rounded border border-gray-300 px-2 py-1 text-sm focus:border-blue-500 focus:outline-none'
const labelClass = 'block text-xs font-medium text-gray-600 mb-1'

function Field({ label, ...props }) {
  return (
    <div>
      <label className={labelClass}>{label}</label>
      <input className={inputClass} {...props} />
    </div>
  )
}

export default function JobEditPage() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const [form, setForm] = useState(null)
  const [error, setError] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [deleting, setDeleting] = useState(false)
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

  function updateField(key, value) {
    setForm((prev) => ({ ...prev, [key]: value }))
  }

  function updateParty(partyKey, field, value) {
    setForm((prev) => ({
      ...prev,
      [partyKey]: { ...prev[partyKey], [field]: value },
    }))
  }

  function updateLineItem(index, field, value) {
    setForm((prev) => ({
      ...prev,
      line_items: prev.line_items.map((line, i) =>
        i === index ? { ...line, [field]: value } : line
      ),
    }))
  }

  function toggleLineItemMarked(index) {
    setForm((prev) => ({
      ...prev,
      line_items: prev.line_items.map((line, i) =>
        i === index ? { ...line, marked: !line.marked } : line
      ),
    }))
  }

  function addLineItem() {
    setForm((prev) => ({
      ...prev,
      line_items: [...prev.line_items, { ...BLANK_LINE_ITEM }],
    }))
  }

  function removeLineItem(index) {
    setForm((prev) => ({
      ...prev,
      line_items: prev.line_items.filter((_, i) => i !== index),
    }))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await submitJobEdit(jobId, toPayload(form))
      navigate(`/job/${jobId}`)
    } catch (err) {
      setError(err.message)
      setSubmitting(false)
    }
  }

  async function handleDelete() {
    if (!window.confirm(`Delete job ${jobId}? This cannot be undone.`)) return
    setDeleting(true)
    setError(null)
    try {
      await deleteJob(jobId)
      navigate('/review')
    } catch (err) {
      setError(err.message)
      setDeleting(false)
    }
  }

  if (error) return <p className="p-10 text-sm text-red-600">{error}</p>
  if (form === null) return <p className="p-10 text-sm text-gray-500">Loading…</p>
  if (form === false) {
    return (
      <div className="p-10">
        <p className="text-sm text-amber-700">This job doesn't exist.</p>
        <Link
          to="/review"
          className="mt-4 inline-block rounded bg-blue-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
        >
          &larr; Back to Review Queue
        </Link>
      </div>
    )
  }

  return (
    <div className="mx-auto w-full px-[1%]">
      <div className="grid grid-cols-2 gap-4 bg-gray-100 p-2">
        <form
          onSubmit={handleSubmit}
          className="sticky top-10 max-h-[90vh] space-y-2 self-start overflow-y-auto pr-2"
        >
          <div>
          {reviewInfo &&
            (reviewInfo.jobError || reviewInfo.reviewReason.length > 0) && (
              <div className="mb-6 rounded border border-amber-200 bg-amber-50 px-4 py-2">
                <h2 className="text-sm font-semibold text-amber-900">
                  Issues:
                </h2>
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
              <select
                className={inputClass}
                value={form.document_type}
                onChange={(e) => updateField('document_type', e.target.value)}
              >
                <option value="invoice">Invoice</option>
                <option value="receipt">Receipt</option>
                <option value="credit_note">Credit Note</option>
              </select>
            </div>
            <Field
              label="Number"
              value={form.invoice_number}
              onChange={(e) => updateField('invoice_number', e.target.value)}
            />

          </div>
          <div className='grid grid-cols-2 gap-5'>
            <Field
              label="Issue date"
              type="date"
              value={form.issue_date}
              onChange={(e) => updateField('issue_date', e.target.value)}
            />
            <Field
              label="Due date"
              type="date"
              value={form.due_date}
              onChange={(e) => updateField('due_date', e.target.value)}
            />
          </div>

          <div className="grid grid-cols-2 gap-5 mt-5 border-t border-gray-300 pt-3 pb-3">
            <div>
              <h2 className="mb-2 text-sm font-semibold">Vendor</h2>
              <div className="space-y-2">
                <Field
                  label="Name"
                  value={form.vendor.name}
                  onChange={(e) => updateParty('vendor', 'name', e.target.value)}
                />
                <Field
                  label="Address"
                  value={form.vendor.address}
                  onChange={(e) => updateParty('vendor', 'address', e.target.value)}
                />
                <Field
                  label="Tax ID"
                  value={form.vendor.tax_id}
                  onChange={(e) => updateParty('vendor', 'tax_id', e.target.value)}
                />
                <Field
                  label="IBAN"
                  value={form.vendor.iban}
                  onChange={(e) => updateParty('vendor', 'iban', e.target.value)}
                />
              </div>
            </div>
            <div>
              <h2 className="mb-2 text-sm font-semibold">Customer</h2>
              <div className="space-y-2">
                <Field
                  label="Name"
                  value={form.customer.name}
                  onChange={(e) => updateParty('customer', 'name', e.target.value)}
                />
                <Field
                  label="Address"
                  value={form.customer.address}
                  onChange={(e) => updateParty('customer', 'address', e.target.value)}
                />
                <Field
                  label="Tax ID"
                  value={form.customer.tax_id}
                  onChange={(e) => updateParty('customer', 'tax_id', e.target.value)}
                />
              </div>
            </div>
          </div>
          <div className="border-t border-gray-300 pt-3 pb-3">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-sm font-semibold">Line items</h2>
              <button
                type="button"
                onClick={addLineItem}
                className="cursor-pointer rounded border border-gray-300 px-2 py-1 text-xs hover:bg-gray-100"
              >
                + Add line item
              </button>
            </div>
            <table className="w-full border-collapse text-left text-sm">
              <thead>
                <tr>
                  <th className="py-1 pr-2 font-medium text-gray-600">#</th>
                  <th className="py-1 pr-2 font-medium text-gray-600">Description</th>
                  <th className="py-1 pr-2 font-medium text-gray-600">Unit price</th>
                  <th className="py-1 pr-2 font-medium text-gray-600">Quantity</th>
                  <th className="py-1 pr-2 font-medium text-gray-600">Line total</th>
                  <th className="py-1"></th>
                </tr>
              </thead>
              <tbody>
                {form.line_items.map((line, idx) => (
                  <tr
                    key={idx}
                    className={`border-b border-gray-100 ${line.marked ? 'opacity-40' : ''}`}
                  >
                    <td className="py-1 pr-2 text-gray-500">{idx + 1}</td>
                    <td className={`py-1 pr-2 ${line.marked ? 'line-through' : ''}`}>
                      <input
                        className={inputClass}
                        value={line.description}
                        disabled={line.marked}
                        onChange={(e) => updateLineItem(idx, 'description', e.target.value)}
                      />
                    </td>
                    <td className={`py-1 pr-2 ${line.marked ? 'line-through' : ''}`}>
                      <input
                        className={inputClass}
                        value={line.unit_price}
                        disabled={line.marked}
                        onChange={(e) => updateLineItem(idx, 'unit_price', e.target.value)}
                      />
                    </td>
                    <td className={`py-1 pr-2 ${line.marked ? 'line-through' : ''}`}>
                      <input
                        className={inputClass}
                        value={line.quantity}
                        disabled={line.marked}
                        onChange={(e) => updateLineItem(idx, 'quantity', e.target.value)}
                      />
                    </td>
                    <td className={`py-1 pr-2 ${line.marked ? 'line-through' : ''}`}>
                      <input
                        className={inputClass}
                        value={line.line_total}
                        disabled={line.marked}
                        onChange={(e) => updateLineItem(idx, 'line_total', e.target.value)}
                      />
                    </td>
                    <td className="py-1 text-center">
                      {lineItemHasData(line) ? (
                        <label className="flex cursor-pointer items-center gap-1 text-xs text-red-600">
                          <input
                            type="checkbox"
                            checked={line.marked}
                            onChange={() => toggleLineItemMarked(idx)}
                          />
                          {line.marked ? 'Marked' : 'Remove'}
                        </label>
                      ) : (
                        <button
                          type="button"
                          onClick={() => removeLineItem(idx)}
                          className="cursor-pointer text-xs text-red-600 hover:underline"
                        >
                          Remove
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid grid-cols-5 gap-4 border-t border-gray-300 pt-3">
            <Field
              label="Currency"
              value={form.currency}
              onChange={(e) => updateField('currency', e.target.value)}
            />
            <Field
              label="Subtotal"
              value={form.subtotal}
              onChange={(e) => updateField('subtotal', e.target.value)}
            />
            <Field
              label="Tax"
              value={form.tax}
              onChange={(e) => updateField('tax', e.target.value)}
            />
            <Field
              label="Service charge"
              value={form.service_charge}
              onChange={(e) => updateField('service_charge', e.target.value)}
            />
            <Field
              label="Discount"
              value={form.discount}
              onChange={(e) => updateField('discount', e.target.value)}
            />
          </div>

          <div className="w-48">
            <Field
              label="Grand total"
              value={form.grand_total}
              onChange={(e) => updateField('grand_total', e.target.value)}
              required
            />
          </div>

          {error && <p className="text-sm text-red-600">{error}</p>}
          <div className='flex items-center gap-3 mt-5'>
            <button
              type="submit"
              disabled={submitting}
              className="cursor-pointer rounded bg-gray-900 px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-40"
            >
              {submitting ? 'Saving…' : 'Save'}
            </button>
            <button
              type="button"
              disabled={submitting}
              onClick={() => navigate('/review')}
              className="cursor-pointer rounded border border-gray-300 px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-300 disabled:cursor-not-allowed disabled:opacity-40"
            >
              Cancel
            </button>
            <button
              type="button"
              disabled={deleting}
              onClick={handleDelete}
              className="ml-auto cursor-pointer rounded bg-red-500 px-4 py-2 text-sm font-medium text-white hover:bg-red-300 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {deleting ? 'Deleting…' : 'Delete'}
            </button>
          </div>
        </form>
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
