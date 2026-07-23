export const PAGE_SIZE = 50

export default function Pagination({ page, totalPages, onPageChange }) {
  if (totalPages <= 1) return null

  const pages = Array.from({ length: totalPages }, (_, i) => i + 1)

  return (
    <div className="mt-4 flex items-center justify-center gap-2">
      <button
        onClick={() => onPageChange(page - 1)}
        disabled={page <= 1}
        className="cursor-pointer rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
      >
        Previous
      </button>
      {pages.map((p) => (
        <button
          key={p}
          onClick={() => onPageChange(p)}
          className={`h-8 w-8 cursor-pointer rounded border text-sm ${
            p === page
              ? 'border-gray-900 bg-gray-900 text-white'
              : 'border-gray-300 hover:bg-gray-100'
          }`}
        >
          {p}
        </button>
      ))}
      <button
        onClick={() => onPageChange(page + 1)}
        disabled={page >= totalPages}
        className="cursor-pointer rounded border border-gray-300 px-3 py-1.5 text-sm hover:bg-gray-100 disabled:cursor-not-allowed disabled:opacity-40"
      >
        Next
      </button>
    </div>
  )
}
