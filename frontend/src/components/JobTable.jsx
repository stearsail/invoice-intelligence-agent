import { Link } from 'react-router-dom'
import { formatDateTime } from '../lib/format'

const STATUS_STYLES = {
  pending: 'bg-gray-100 text-gray-700',
  complete: 'bg-green-100 text-green-700',
  extraction_failed: 'bg-amber-100 text-amber-700',
  error: 'bg-red-100 text-red-700',
}

function humanizeStatus(status) {
  return status
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || 'bg-gray-100 text-gray-700'
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${style}`}>
      {humanizeStatus(status)}
    </span>
  )
}

export default function JobTable({ items, linkLabel, linkTo }) {
  if (!items || items.length === 0) {
    return <p className="text-gray-500">Nothing to show.</p>
  }

  return (
    <table className="w-full border-collapse text-center text-sm">
      <thead>
        <tr className="border-b border-gray-300">
          <th className="py-2 pr-4 font-medium text-gray-600">Job ID</th>
          <th className="py-2 pr-4 font-medium text-gray-600">Status</th>
          <th className="py-2 pr-4 font-medium text-gray-600">Created</th>
          <th className="py-2 font-medium text-gray-600">Details</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.job_id} className="border-b border-gray-100 hover:bg-gray-100">
            <td className="py-2 pr-4">{item.job_id}</td>
            <td className="py-2 pr-4">
              <StatusBadge status={item.status} />
            </td>
            <td className="py-2 pr-4 text-gray-600">{formatDateTime(item.created_at)}</td>
            <td className="py-2">
              <Link
                to={linkTo(item.job_id)}
                className="inline-block rounded bg-blue-600 px-2 py-1 text-xs font-medium text-white hover:bg-blue-700"
              >
                {linkLabel}
              </Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}