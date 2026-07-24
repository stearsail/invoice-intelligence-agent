import { Link } from 'react-router-dom'
import { formatDateTime } from '../lib/format'

const STATUS_STYLES = {
  pending: 'bg-surface-hover text-muted',
  complete: 'bg-green-500/15 text-green-300',
  extraction_failed: 'bg-amber-500/15 text-amber-300',
  error: 'bg-red-500/15 text-red-300',
}

function humanizeStatus(status) {
  return status
    .split('_')
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(' ')
}

function StatusBadge({ status }) {
  const style = STATUS_STYLES[status] || 'bg-surface-hover text-muted'
  return (
    <span className={`inline-block rounded-full px-2 py-0.5 text-xs font-medium ${style}`}>
      {humanizeStatus(status)}
    </span>
  )
}

export default function JobTable({ items, linkLabel, linkTo }) {
  if (!items || items.length === 0) {
    return <p className="text-muted">Nothing to show.</p>
  }

  return (
    <table className="w-full border-collapse text-center text-sm">
      <thead>
        <tr className="border-b border-edge">
          <th className="py-2 pr-4 font-medium text-muted">Job ID</th>
          <th className="py-2 pr-4 font-medium text-muted">Status</th>
          <th className="py-2 pr-4 font-medium text-muted">Created</th>
          <th className="py-2 font-medium text-muted">Details</th>
        </tr>
      </thead>
      <tbody>
        {items.map((item) => (
          <tr key={item.job_id} className="border-b border-edge hover:bg-surface-hover">
            <td className="py-2 pr-4">{item.job_id}</td>
            <td className="py-2 pr-4">
              <StatusBadge status={item.status} />
            </td>
            <td className="py-2 pr-4 text-muted">{formatDateTime(item.created_at)}</td>
            <td className="py-2">
              <Link
                to={linkTo(item.job_id)}
                className="inline-block rounded bg-accent px-2 py-1 text-xs font-medium text-white hover:bg-accent-hover"
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