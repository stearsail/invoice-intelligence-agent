import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom'
import UploadPage from './pages/UploadPage'
import ReviewQueuePage from './pages/ReviewQueuePage'
import FullLedgerPage from './pages/FullLedgerPage'
import JobDetailPage from './pages/JobDetailPage'
import JobEditPage from './pages/JobEditPage'

const navLinkClass = ({ isActive }) =>
  `px-3 py-2 text-sm font-medium rounded ${
    isActive ? 'bg-accent text-white' : 'text-muted hover:bg-surface-hover'
  }`

function Nav() {
  return (
    <nav className="border-b border-edge">
      <div className="mx-auto flex max-w-3xl items-center gap-2 px-4 py-3">
        <span className="mr-4 text-sm font-semibold">Invoice Agent</span>
        <NavLink to="/" end className={navLinkClass}>
          Upload
        </NavLink>
        <NavLink to="/review" className={navLinkClass}>
          Review Queue
        </NavLink>
        <NavLink to="/ledger" className={navLinkClass}>
          Ledger
        </NavLink>
      </div>
    </nav>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <Nav />
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/review" element={<ReviewQueuePage />} />
        <Route path="/ledger" element={<FullLedgerPage />} />
        <Route path="/job/:jobId" element={<JobDetailPage />} />
        <Route path="/job/:jobId/edit" element={<JobEditPage />} />
      </Routes>
    </BrowserRouter>
  )
}
