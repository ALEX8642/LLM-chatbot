import { useEffect, useState } from 'react'
import { DEMO, listManuals, listRecordings, type Claim, type Manual, type Recording } from './api'
import Conversation from './Conversation'
import PageViewer from './PageViewer'
import { useTheme } from './theme'
import { same } from './turn'

export default function App() {
  const [manuals, setManuals] = useState<Manual[]>([])
  const [manual, setManual] = useState('')
  const [selected, setSelected] = useState<Claim | null>(null)
  const [page, setPage] = useState<number | null>(null)
  const [recorded, setRecorded] = useState<Recording[] | null>(null)
  const [theme, toggleTheme] = useTheme()

  useEffect(() => {
    listManuals()
      .then((ms) => {
        setManuals(ms)
        setManual((m) => m || ms[0]?.file || '')
      })
      .catch(() => setManuals([]))
    if (DEMO) listRecordings().then(setRecorded, () => setRecorded([]))
  }, [])

  const select = (c: Claim) => {
    setSelected(c)
    setPage(c.page)
  }
  const showPage = (p: number) => {
    setSelected(null)
    setPage(p)
  }
  // a claim removed after it was selected takes its boxes with it; the page stays
  const removed = (c: Claim) => setSelected((s) => (s && same(s, c) ? null : s))
  const boxes = selected?.boxes ?? []
  const questions = recorded?.filter((r) => r.manual === manual).map((r) => r.question)

  return (
    <div className="grid h-screen grid-cols-1 md:grid-cols-2">
      <div className="flex min-h-0 flex-col border-r border-slate-200 dark:border-slate-700">
        <header className="flex items-center gap-2 border-b border-slate-200 dark:border-slate-700 p-3">
          <h1 className="text-lg font-semibold">Manual Q&amp;A</h1>
          <select
            aria-label="manual"
            value={manual}
            onChange={(e) => {
              setManual(e.target.value)
              setSelected(null)
              setPage(null)
            }}
            className="ml-auto min-w-0 max-w-xs rounded border border-slate-200 dark:border-slate-700 bg-white px-2 py-1 dark:bg-slate-800"
          >
            {manuals.map((m) => (
              <option key={m.file} value={m.file}>
                {m.title}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={toggleTheme}
            aria-label={theme === 'dark' ? 'Switch to light mode' : 'Switch to dark mode'}
            title={theme === 'dark' ? 'Light mode' : 'Dark mode'}
            className="rounded border border-slate-200 px-2 py-1 text-lg leading-none hover:bg-slate-100 dark:border-slate-700 dark:hover:bg-slate-800"
          >
            {theme === 'dark' ? '☀' : '☾'}
          </button>
        </header>
        {recorded && <DemoNote recorded={recorded} />}
        <div className="min-h-0 flex-1">
          <Conversation
            key={manual}
            manual={manual}
            selected={selected}
            onSelect={select}
            onPage={showPage}
            onRemoved={removed}
            questions={questions}
          />
        </div>
      </div>
      <div className="overflow-y-auto bg-slate-100 p-4 dark:bg-slate-950">
        {manual && <PageViewer manual={manual} page={page} boxes={boxes} />}
      </div>
    </div>
  )
}

const REPO = 'https://github.com/ALEX8642/LLM-chatbot'

/** What the static demo is: recordings, not a live model. */
function DemoNote({ recorded }: { recorded: Recording[] }) {
  const seconds = recorded.map((r) => r.events.at(-1)?.t ?? 0).filter((t) => t > 0)
  const span = seconds.length ? `${Math.floor(Math.min(...seconds))}–${Math.ceil(Math.max(...seconds))} s` : null
  return (
    <p className="border-b border-slate-200 dark:border-slate-700 bg-amber-50 px-3 py-2 text-sm text-slate-700 dark:bg-amber-950/40 dark:text-slate-300">
      A replay of {recorded.length} answers recorded from the running system, on questions from the development set
      (not the held-out test). They play back faster than live{span && `; each took ${span} on a 16 GB GPU`}. To ask your
      own questions,{' '}
      <a href={`${REPO}#running-it`} className="text-blue-700 underline dark:text-blue-400">
        run it yourself
      </a>
      .
    </p>
  )
}
