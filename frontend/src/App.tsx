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

  // on a phone the page sits below the answer: bring it into view when a claim is picked
  const reveal = () => {
    if (window.matchMedia?.('(max-width: 767px)').matches)
      document.getElementById('page')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
  const line = 'border-slate-200 dark:border-slate-800'

  return (
    <div className="md:grid md:h-dvh md:grid-cols-2">
      <div className={`flex flex-col md:min-h-0 md:border-r ${line}`}>
        <header className={`flex flex-wrap items-center gap-x-3 gap-y-2 border-b ${line} px-4 py-3`}>
          <div className="mr-auto flex items-center gap-2">
            <img src={`${import.meta.env.BASE_URL}favicon.svg`} alt="" className="h-7 w-7" />
            <div>
              <h1 className="text-lg font-semibold leading-tight">Manual Q&amp;A</h1>
              <p className="text-xs text-slate-500 dark:text-slate-400">Every claim quoted and checked against its page</p>
            </div>
          </div>
          <select
            aria-label="manual"
            value={manual}
            onChange={(e) => {
              setManual(e.target.value)
              setSelected(null)
              setPage(null)
            }}
            className={`order-last w-full min-w-0 rounded-md border ${line} bg-white px-2 py-1.5 text-sm sm:order-none sm:w-auto sm:max-w-xs dark:bg-slate-900`}
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
            className={`rounded-md border ${line} px-2.5 py-1.5 leading-none hover:bg-slate-100 dark:hover:bg-slate-800`}
          >
            {theme === 'dark' ? '☀' : '☾'}
          </button>
        </header>
        {recorded && <DemoNote recorded={recorded} />}
        <div className="flex min-h-0 flex-1 flex-col">
          <Conversation
            key={manual}
            manual={manual}
            selected={selected}
            onSelect={(c) => {
              select(c)
              reveal()
            }}
            onPage={(p) => {
              showPage(p)
              reveal()
            }}
            onRemoved={removed}
            questions={questions}
          />
        </div>
      </div>
      <div id="page" className="scroll-mt-2 bg-slate-100 p-4 md:overflow-y-auto dark:bg-slate-950">
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
    <p className="border-b border-amber-200 bg-amber-50 px-4 py-2 text-sm text-slate-700 dark:border-amber-900/50 dark:bg-amber-950/30 dark:text-slate-300">
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
