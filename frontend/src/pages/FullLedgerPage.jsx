import { useEffect, useState } from 'react'
import { getResolvedLedger } from '../lib/api'
import JobTable from '../components/JobTable'

export default function FullLedgerPage() {
  const [items, setItems] = useState(null)
  const [error, setError] = useState(null)

  async function load() {
    try {
      setItems(await getResolvedLedger())
    } catch (err) {
      setError(err.message)
    }
  }

  useEffect(() => {
    load()
  }, [])

  return (
    <div className="mx-auto w-full px-[5%] py-10">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Ledger</h1>
        <button
          onClick={load}
          className="cursor-pointer rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100"
        >
          Refresh
        </button>
      </div>

      {error && <p className="text-sm text-red-600">{error}</p>}
      {items && (
        <JobTable items={items} linkLabel="View" linkTo={(id) => `/job/${id}`} />
      )}
    </div>
  )
}
