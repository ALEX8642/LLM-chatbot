import { useEffect, useState } from 'react'
import { listManuals, type Claim, type Manual } from './api'
import Conversation from './Conversation'
import PageViewer from './PageViewer'
import { same } from './turn'

export default function App() {
  const [manuals, setManuals] = useState<Manual[]>([])
  const [manual, setManual] = useState('')
  const [selected, setSelected] = useState<Claim | null>(null)
  const [page, setPage] = useState<number | null>(null)

  useEffect(() => {
    listManuals()
      .then((ms) => {
        setManuals(ms)
        setManual((m) => m || ms[0]?.file || '')
      })
      .catch(() => setManuals([]))
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

  return (
    <div className="grid h-screen grid-cols-1 md:grid-cols-2">
      <div className="flex min-h-0 flex-col border-r">
        <header className="flex items-center gap-2 border-b p-3">
          <h1 className="text-lg font-semibold">Manual Q&amp;A</h1>
          <select
            aria-label="manual"
            value={manual}
            onChange={(e) => {
              setManual(e.target.value)
              setSelected(null)
              setPage(null)
            }}
            className="ml-auto max-w-xs rounded border px-2 py-1"
          >
            {manuals.map((m) => (
              <option key={m.file} value={m.file}>
                {m.title}
              </option>
            ))}
          </select>
        </header>
        <div className="min-h-0 flex-1">
          <Conversation key={manual} manual={manual} selected={selected} onSelect={select} onPage={showPage} onRemoved={removed} />
        </div>
      </div>
      <div className="overflow-y-auto bg-slate-100 p-4">
        {manual && <PageViewer manual={manual} page={page} boxes={boxes} />}
      </div>
    </div>
  )
}
