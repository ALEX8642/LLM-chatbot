import { useState, type FormEvent } from 'react'
import { ask, type Claim, type Turn } from './api'
import ClaimList from './ClaimList'
import { answerText, applyEvent, newTurn, stopped, type TurnState } from './turn'

interface Props {
  manual: string
  selected: Claim | null
  onSelect: (c: Claim) => void
  onPage: (page: number) => void
  onRemoved: (c: Claim) => void
  questions?: string[] // a fixed list to pick from, in place of free text
}

export default function Conversation({ manual, selected, onSelect, onPage, onRemoved, questions }: Props) {
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
    let finished = false
    try {
      for await (const ev of ask(q, manual, history)) {
        update((t) => applyEvent(t, ev))
        if (ev.event === 'claim_removed') onRemoved(ev.data)
        if (ev.event === 'done' || ev.event === 'error') finished = true
      }
      if (!finished) update((t) => stopped(t, 'The answer stopped before it was checked.'))
    } catch (err) {
      update((t) => stopped(t, String(err)))
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
            {t.standalone && t.standalone !== t.question && <p className="text-xs text-slate-500 dark:text-slate-400">Searched for: {t.standalone}</p>}
            <div className="mt-2">
              <ClaimList claims={t.claims} removed={t.removed} selected={selected} onSelect={onSelect} />
              {!t.done && !t.error && <p className="text-sm text-slate-400">Checking the manual…</p>}
              {t.done?.abstained && (
                <p className="text-slate-700 dark:text-slate-300">
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
                          className="ml-2 text-blue-700 underline dark:text-blue-400"
                        >
                          page {p}
                        </a>
                      ))}
                    </span>
                  )}
                </p>
              )}
              {t.error && <p className="text-red-700 dark:text-red-400">Something went wrong: {t.error}</p>}
            </div>
          </li>
        ))}
      </ol>
      <form onSubmit={submit} className="flex gap-2 border-t border-slate-200 dark:border-slate-700 p-3">
        {questions ? (
          <select
            aria-label="question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            className="min-w-0 flex-1 rounded border border-slate-200 dark:border-slate-700 bg-white px-3 py-2 dark:bg-slate-800"
          >
            <option value="">Choose a recorded question</option>
            {questions.map((q) => (
              <option key={q} value={q}>
                {q}
              </option>
            ))}
          </select>
        ) : (
          <input
            type="text"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            placeholder="Ask about this manual"
            className="flex-1 rounded border border-slate-200 dark:border-slate-700 bg-white px-3 py-2 dark:bg-slate-800"
          />
        )}
        <button type="submit" disabled={busy || !manual} className="rounded bg-slate-800 px-4 py-2 text-white disabled:opacity-50 dark:bg-slate-200 dark:text-slate-900">
          Ask
        </button>
      </form>
    </section>
  )
}
