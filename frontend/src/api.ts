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

export const pageUrl = (manual: string, page: number) =>
  `/api/pages/${encodeURIComponent(manual.replace(/\.pdf$/i, ''))}/${page}`

export async function listManuals(): Promise<Manual[]> {
  const r = await fetch('/api/manuals')
  if (!r.ok) throw new Error(`manuals: HTTP ${r.status}`)
  return r.json()
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
  const r = await fetch('/api/ask', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, manual, history }),
  })
  if (!r.ok || !r.body) throw new Error(`ask: HTTP ${r.status}`)
  yield* parseSSE(text(r.body))
}
