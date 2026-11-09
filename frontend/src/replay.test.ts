import { expect, it } from 'vitest'
import { REPLAY_GAP_MS, pageUrl, replay, type AnswerEvent, type Recording } from './api'

const PARTS = 'Army_5kW_Generator_Parts_Manual.pdf'
const recording: Recording = {
  question: 'What is the part number?',
  manual: PARTS,
  events: [
    { event: 'retrieved', data: { pages: [59] }, t: 0 },
    { event: 'claim_shown', data: { claim: 'a' }, t: 0.1 },
    { event: 'done', data: { text: 'a' }, t: 12 },
  ],
}

async function run(question: string, manual = PARTS) {
  const waits: number[] = []
  const out: AnswerEvent[] = []
  for await (const e of replay([recording], question, manual, async (ms) => waits.push(ms))) out.push(e)
  return { out, waits }
}

it('replays the recorded events in order, without their times', async () => {
  const { out } = await run(recording.question)
  expect(out.map((e) => e.event)).toEqual(['retrieved', 'claim_shown', 'done'])
  expect(out[0]).toEqual({ event: 'retrieved', data: { pages: [59] } })
})

it('keeps short gaps and shortens long ones, as the server replay does', async () => {
  const { waits } = await run(recording.question)
  expect(waits.map(Math.round)).toEqual([0, 100, REPLAY_GAP_MS])
})

it('a question that was not recorded says so', async () => {
  const { out } = await run('Something else?')
  expect(out).toEqual([
    { event: 'done', data: { text: 'This question is not in the recording.', replay_miss: true, abstained: true } },
  ])
  expect((await run(recording.question, 'Other.pdf')).out[0].data.replay_miss).toBe(true)
})

it('live pages come from the server', () => {
  expect(pageUrl(PARTS, 7)).toBe('/api/pages/Army_5kW_Generator_Parts_Manual/7')
})
