import { describe, expect, it } from 'vitest'
import type { Claim } from './api'
import { applyEvent, newTurn } from './turn'

const claim = (status: Claim['status']): Claim => ({
  claim: 'c-' + status, block: 'b', quote: status, page: 1, boxes: [], status, reason: null,
})

describe('an answer that fails', () => {
  it('drops unchecked claims and keeps checked ones', () => {
    let t = newTurn('q')
    t = applyEvent(t, { event: 'claim_settled', data: claim('verified') })
    t = applyEvent(t, { event: 'claim_shown', data: claim('pending') })
    t = applyEvent(t, { event: 'error', data: { message: 'generator down' } })
    expect(t.error).toBe('generator down')
    expect(t.claims.map((c) => c.status)).toEqual(['verified'])
  })
})
