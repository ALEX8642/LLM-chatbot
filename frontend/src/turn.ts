import type { AnswerEvent, Claim } from './api'

export interface TurnState {
  question: string
  standalone: string | null
  pages: number[]
  claims: Claim[] // shown or settled, in arrival order
  removed: Claim[]
  done: { text: string; abstained: boolean; replay_miss?: boolean } | null
  error: string | null
}

export const newTurn = (question: string): TurnState => ({
  question,
  standalone: null,
  pages: [],
  claims: [],
  removed: [],
  done: null,
  error: null,
})

export const same = (a: Claim, b: Claim) => a.block === b.block && a.quote === b.quote && a.claim === b.claim

/** Applies one answer event to a turn. */
export function applyEvent(t: TurnState, { event, data }: AnswerEvent): TurnState {
  switch (event) {
    case 'retrieved':
      return { ...t, pages: data.pages ?? [], standalone: data.standalone_question ?? null }
    case 'claim_shown':
      return { ...t, claims: [...t.claims, data] }
    case 'claim_settled':
      return t.claims.some((c) => same(c, data))
        ? { ...t, claims: t.claims.map((c) => (same(c, data) ? data : c)) }
        : { ...t, claims: [...t.claims, data] }
    case 'claim_removed':
      return { ...t, claims: t.claims.filter((c) => !same(c, data)), removed: [...t.removed, data] }
    case 'done':
      return { ...t, done: data, pages: data.pages ?? t.pages }
    case 'error':
      return stopped(t, data.message ?? 'The answer failed.')
    default:
      return t
  }
}

/** The text a later turn sends back as this turn's answer. */
export const answerText = (t: TurnState) => t.done?.text ?? t.claims.map((c) => c.claim).join('\n')

/** An answer that ended without finishing: unchecked claims are not left on screen. */
export const stopped = (t: TurnState, message: string): TurnState => ({
  ...t,
  error: message,
  claims: t.claims.filter((c) => c.status !== 'pending'),
})
