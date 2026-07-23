import { useEffect, useState } from 'react'
import { getReviewQueue } from '../lib/api'
import JobTable from '../components/JobTable'
import Pagination, { PAGE_SIZE } from '../components/Pagination'

export default function ReviewQueuePage() {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)
  const [page, setPage] = useState(1)

  async function load() {
    try {
      setItems(await getReviewQueue())
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    load()
  }, [])

  const totalPages = items ? Math.max(1, Math.ceil(items.length / PAGE_SIZE)) : 1
  const currentPage = Math.min(page, totalPages)
  const pageItems = items
    ? items.slice((currentPage - 1) * PAGE_SIZE, currentPage * PAGE_SIZE)
    : null

  return (
    <div className="mx-auto w-full px-[5%] py-10">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">
          Verification{items && ` — ${items.length}`}
        </h1>
        <button
          onClick={load}
          className="cursor-pointer rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100"
        >
          Refresh
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {pageItems && (
        <>
          <JobTable
            items={pageItems}
            linkLabel="Edit"
            linkTo={(id) => `/job/${id}/edit`}
          />
          <Pagination
            page={currentPage}
            totalPages={totalPages}
            onPageChange={setPage}
          />
        </>
      )}
    </div>
  )
}
