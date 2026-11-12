import { ShieldAlert } from 'lucide-react'
import { Link } from 'react-router'

export default function ForbiddenPage() {
  return (
    <div className="card mx-auto mt-10 max-w-lg p-10 text-center">
      <span className="mx-auto mb-4 inline-flex rounded-full bg-amber-50 p-3 text-amber-600">
        <ShieldAlert className="size-7" aria-hidden="true" />
      </span>
      <h1 className="text-lg font-semibold text-slate-900">Access restricted</h1>
      <p className="mt-2 text-sm text-slate-500">
        Your role does not have access to this section. Contact an administrator if you need it.
      </p>
      <Link to="/" className="btn-primary mt-6">
        Back to dashboard
      </Link>
    </div>
  )
}
