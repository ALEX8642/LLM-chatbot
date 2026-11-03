import { useState, type FormEvent } from 'react'
import { ask, type Claim, type Turn } from './api'
import ClaimList from './ClaimList'
import { answerText, applyEvent, newTurn, type TurnState } from './turn'

interface Props {
  manual: string
  selected: Claim | null
  onSelect: (c: Claim) => void
  onPage: (page: number) => void
  onRemoved: (c: Claim) => void
}

export default function Conversation({ manual, selected, onSelect, onPage, onRemoved }: Props) {
  const [turns, setTurns] = useState<TurnState[]>([])
  const [question, setQuestion] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(e: FormEvent) {
    e.preventDefault()
    const q = question.trim()
    if (!q || busy) return
    const history: Turn[] = turns.flatMap((t) => [
      { role: 'user' as const, content: t.question },
      { role: 'assistant' as const, content: answerText(t) },
    ])
    const index = turns.length
    const update = (f: (t: TurnState) => TurnState) =>
      setTurns((ts) => ts.map((t, i) => (i === index ? f(t) : t)))
    setTurns((ts) => [...ts, newTurn(q)])
    setQuestion('')
    setBusy(true)
    try {
      for await (const ev of ask(q, manual, history)) {
        update((t) => applyEvent(t, ev))
        if (ev.event === 'claim_removed') onRemoved(ev.data)
      }
    } catch (err) {
      update((t) => ({ ...t, error: String(err) }))
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="flex h-full flex-col">
      <ol className="flex-1 space-y-6 overflow-y-auto p-4">
        {turns.map((t, i) => (
          <li key={i}>
            <p className="font-medium">{t.question}</p>
            {t.standalone && <p className="text-xs text-slate-500">Searched for: {t.standalone}</p>}
            <div className="mt-2">
              <ClaimList claims={t.claims} removed={t.removed} selected={selected} onSelect={onSelect} />
              {!t.done && !t.error && <p className="text-sm text-slate-400">Checking the manual…</p>}
              {t.done?.abstained && (
                <p className="text-slate-700">
                  {t.done.text}
                  {t.pages.length > 0 && !t.done.replay_miss && (
                    <span className="ml-1">
                      {t.pages.map((p) => (
                        <a
                          key={p}
                          href={`#page-${p}`}
                          onClick={(e) => {
                            e.preventDefault()
                            onPage(p)
                          }}
                          className="ml-2 text-blue-700 underline"
                        >
                          page {p}
                        </a>
                      ))}
                    </span>
                  )}
                </p>
              )}
              {t.error && <p className="text-red-700">Something went wrong: {t.error}</p>}
            </div>
          </li>
        ))}
      </ol>
      <form onSubmit={submit} className="flex gap-2 border-t p-3">
        <input
          type="text"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about this manual"
          className="flex-1 rounded border px-3 py-2"
        />
        <button type="submit" disabled={busy || !manual} className="rounded bg-slate-800 px-4 py-2 text-white disabled:opacity-50">
          Ask
        </button>
      </form>
    </section>
  )
}
