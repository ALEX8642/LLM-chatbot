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
    <section className="flex flex-1 flex-col md:min-h-0">
      <ol className="flex-1 space-y-4 p-4 md:overflow-y-auto">
        {turns.length === 0 && <Guide picking={!!questions} />}
        {turns.map((t, i) => (
          <li key={i} className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-slate-900">
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
      <form
        onSubmit={submit}
        className="sticky bottom-0 flex gap-2 border-t border-slate-200 bg-white/95 p-3 backdrop-blur dark:border-slate-800 dark:bg-slate-950/95"
      >
        {questions ? (
          <select
            aria-label="question"
            value={question}
            onChange={(e) => setQuestion(e.target.value)}
            className="min-w-0 flex-1 rounded-md border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"
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
            className="flex-1 rounded-md border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900"
          />
        )}
        <button type="submit" disabled={busy || !manual} className="rounded-md bg-slate-800 px-4 py-2 font-medium text-white hover:bg-slate-700 disabled:opacity-50 dark:bg-slate-200 dark:text-slate-900 dark:hover:bg-white">
          Ask
        </button>
      </form>
    </section>
  )
}

/** Shown before the first question: how to read an answer. */
function Guide({ picking }: { picking: boolean }) {
  return (
    <li className="space-y-2 text-sm text-slate-600 dark:text-slate-400">
      <p>{picking ? 'Pick a question below.' : 'Ask a question about this manual.'} An answer comes as claims, each with a quote
        from the manual that is checked before the claim is shown.</p>
      <ul className="space-y-1">
        <li>
          <span className="text-emerald-600 dark:text-emerald-400">✓</span> checked against the cited text; tap or hover to
          see it highlighted on the page
        </li>
        <li>
          <span className="text-slate-400">◦</span> read from a figure, which the checks cannot match word for word
        </li>
        <li>Claims that fail a check are removed, and you can see why.</li>
      </ul>
    </li>
  )
}
