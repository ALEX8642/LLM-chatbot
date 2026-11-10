import type { Claim } from './api'
import { same } from './turn'

interface Props {
  claims: Claim[]
  removed: Claim[]
  selected: Claim | null
  onSelect: (c: Claim) => void
}

function Mark({ status }: { status: Claim['status'] }) {
  if (status === 'pending')
    return <span aria-label="checking" className="text-slate-400">…</span>
  if (status === 'figure')
    return <span aria-label="read from a figure, not checked" className="text-slate-400">◦</span>
  return <span aria-label="verified" className="text-emerald-600 dark:text-emerald-400">✓</span>
}

export default function ClaimList({ claims, removed, selected, onSelect }: Props) {
  return (
    <>
      <ul aria-label="answer" className="space-y-1">
          {claims.map((c) => (
            <li key={`${c.block}|${c.quote}|${c.claim}`} className="flex gap-2">
              <Mark status={c.status} />
              <button
                type="button"
                onClick={() => onSelect(c)}
                onMouseEnter={() => onSelect(c)}
                className={`text-left rounded px-1 hover:bg-amber-100 dark:hover:bg-amber-400/15 ${selected && same(selected, c) ? 'bg-amber-100 dark:bg-amber-400/15' : ''}`}
              >
                <span>{c.claim}</span>
                {c.status === 'figure' && <span className="ml-2 text-xs text-slate-500">read from figure</span>}
                {c.page != null && <span className="ml-2 text-xs text-slate-400">p. {c.page}</span>}
              </button>
            </li>
          ))}
        </ul>
      {removed.length > 0 && (
        <details className="mt-2 text-sm text-slate-500 dark:text-slate-400">
          <summary className="cursor-pointer">
            {removed.length} {removed.length === 1 ? 'claim' : 'claims'} removed, see why
          </summary>
          <ul className="mt-1 space-y-1">
            {removed.map((c) => (
              <li key={`${c.block}|${c.quote}|${c.claim}`}>
                <span className="line-through">{c.claim}</span> — <em>{c.reason}</em>
              </li>
            ))}
          </ul>
        </details>
      )}
    </>
  )
}
