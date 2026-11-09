import type { Box } from './boxes'
import { parseSSE } from './sse'

export interface Manual {
  file: string
  title: string
  pages: number
}

export interface Claim {
  claim: string
  block: string
  quote: string
  page: number | null
  boxes: Box[]
  status: 'pending' | 'verified' | 'figure' | 'removed'
  reason: string | null
}

export interface Turn {
  role: 'user' | 'assistant'
  content: string
}

export interface AnswerEvent {
  event: string
  data: any // eslint-disable-line @typescript-eslint/no-explicit-any -- shape depends on event
}

/** Built with `--mode demo`: a static page that replays recorded answers, with no server. */
export const DEMO = import.meta.env.VITE_DEMO === '1'
const STATIC = `${import.meta.env.BASE_URL}demo/`

const stem = (manual: string) => encodeURIComponent(manual.replace(/\.pdf$/i, ''))

export const pageUrl = (manual: string, page: number) =>
  DEMO ? `${STATIC}pages/${stem(manual)}/p${String(page).padStart(3, '0')}.jpg` : `/api/pages/${stem(manual)}/${page}`

export async function listManuals(): Promise<Manual[]> {
  const r = await fetch(DEMO ? `${STATIC}manuals.json` : '/api/manuals')
  if (!r.ok) throw new Error(`manuals: HTTP ${r.status}`)
  return r.json()
}

export interface Recording {
  question: string
  manual: string
  events: (AnswerEvent & { t?: number })[]
}

let recordings: Promise<Recording[]> | null = null

/** The recorded answers the static demo can replay. */
export function listRecordings(): Promise<Recording[]> {
  recordings ??= fetch(`${STATIC}answers.json`).then((r) => {
    if (!r.ok) throw new Error(`answers: HTTP ${r.status}`)
    return r.json()
  })
  return recordings
}

export const REPLAY_GAP_MS = 300 // as the server's replay mode: the recorded order, sped up

const pause = (ms: number) => new Promise((r) => setTimeout(r, ms))

/** A recording's events, paced as the server's replay mode paces them. */
export async function* replay(
  all: Recording[],
  question: string,
  manual: string,
  wait: (ms: number) => Promise<unknown> = pause,
): AsyncIterable<AnswerEvent> {
  const found = all.find((r) => r.manual === manual && r.question === question)
  if (!found) {
    yield { event: 'done', data: { text: 'This question is not in the recording.', replay_miss: true, abstained: true } }
    return
  }
  let previous = 0
  for (const { event, data, t = 0 } of found.events) {
    await wait(Math.min(REPLAY_GAP_MS, Math.max(0, (t - previous) * 1000)))
    previous = t
    yield { event, data }
  }
}

async function* text(body: ReadableStream<Uint8Array>): AsyncIterable<string> {
  const reader = body.getReader()
  const decoder = new TextDecoder()
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    yield decoder.decode(value, { stream: true })
  }
  const rest = decoder.decode()
  if (rest) yield rest
}

/** The answer events for one question, as the server streams them. */
export async function* ask(question: string, manual: string, history: Turn[]): AsyncIterable<AnswerEvent> {
  if (DEMO) {
    yield* replay(await listRecordings(), question, manual)
    return
  }
  const r = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, manual, history }),
  })
  if (!r.ok || !r.body) throw new Error(`ask: HTTP ${r.status}`)
  yield* parseSSE(text(r.body))
}
