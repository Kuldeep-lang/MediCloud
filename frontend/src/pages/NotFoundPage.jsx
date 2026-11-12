import { Compass } from 'lucide-react'
import { Link } from 'react-router'

export default function NotFoundPage() {
  return (
    <div className="card mx-auto mt-10 max-w-lg p-10 text-center">
      <span className="mx-auto mb-4 inline-flex rounded-full bg-brand-50 p-3 text-brand-600">
        <Compass className="size-7" aria-hidden="true" />
      </span>
      <h1 className="text-lg font-semibold text-slate-900">Page not found</h1>
      <p className="mt-2 text-sm text-slate-500">The page you are looking for does not exist.</p>
      <Link to="/" className="btn-primary mt-6">
        Back to dashboard
      </Link>
    </div>
  )
}
