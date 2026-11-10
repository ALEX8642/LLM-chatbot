import { act, fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, it, vi } from 'vitest'
import type { AnswerEvent } from './api'

const PARTS = 'Army_5kW_Generator_Parts_Manual.pdf'

// Events the test pushes one at a time, so the UI can be checked between them.
let push: (e: AnswerEvent | null) => void
function scriptedStream(): AsyncIterable<AnswerEvent> {
  const queue: (AnswerEvent | null)[] = []
  let wake: (() => void) | null = null
  push = (e) => {
    queue.push(e)
    wake?.()
  }
  return {
    async *[Symbol.asyncIterator]() {
      for (;;) {
        while (!queue.length) await new Promise<void>((r) => (wake = r))
        const e = queue.shift()!
        if (e === null) return
        yield e
      }
    },
  }
}

const ask = vi.fn()
vi.mock('./api', async (original) => ({
  ...(await original<typeof import('./api')>()),
  ask: (...args: unknown[]) => ask(...args),
  listManuals: async () => [{ file: PARTS, title: 'Parts manual', pages: 120 }],
}))

const { default: App } = await import('./App')

const box = { x0: 0.1, y0: 0.2, x1: 0.4, y1: 0.25 }
const claim = (text: string, page: number, status: string, reason: string | null = null) => ({
  event: '',
  data: { claim: text, block: `b-${text}`, quote: text, page, boxes: [box], status, reason },
})
const ev = (event: string, c: ReturnType<typeof claim>): AnswerEvent => ({ event, data: c.data })
const send = async (e: AnswerEvent | null) => act(async () => push(e))

async function askQuestion(q = 'What is the oil filter part number?') {
  await screen.findByRole('option', { name: 'Parts manual' })
  await userEvent.type(screen.getByRole('textbox'), q)
  await userEvent.click(screen.getByRole('button', { name: /ask/i }))
}

beforeEach(() => {
  ask.mockReset()
  ask.mockImplementation(() => scriptedStream())
})

it('claim shows checking mark until settled', async () => {
  render(<App />)
  await askQuestion()
  await send({ event: 'retrieved', data: { pages: [59] } })
  await send(ev('claim_shown', claim('Filter is 5-1', 59, 'pending')))
  const item = screen.getByText('Filter is 5-1').closest('li')!
  expect(within(item).getByLabelText('checking')).toBeInTheDocument()
  await send(ev('claim_settled', claim('Filter is 5-1', 59, 'verified')))
  expect(within(item).queryByLabelText('checking')).toBeNull()
  expect(within(item).getByLabelText('verified')).toBeInTheDocument()
  expect(ask).toHaveBeenCalledWith('What is the oil filter part number?', PARTS, [])
})

it('removed claim leaves the answer', async () => {
  render(<App />)
  await askQuestion()
  await send(ev('claim_shown', claim('CAGE 12345 is the part', 59, 'pending')))
  await userEvent.click(screen.getByText('CAGE 12345 is the part'))
  expect(document.querySelectorAll('[data-testid="box"]')).toHaveLength(0) // page not loaded yet
  fireEvent.load(screen.getByRole('img', { name: /page 59/i }))
  expect(document.querySelectorAll('[data-testid="box"]')).toHaveLength(1)

  await send(ev('claim_removed', claim('CAGE 12345 is the part', 59, 'removed', 'number not in quote: 12345')))
  const answer = screen.getByRole('list', { name: 'answer' })
  expect(within(answer).queryByText('CAGE 12345 is the part')).toBeNull()
  expect(document.querySelectorAll('[data-testid="box"]')).toHaveLength(0)
  const removed = screen.getByText('1 claim removed, see why').closest('details')!
  expect(within(removed).getByText('CAGE 12345 is the part')).toBeInTheDocument()
  expect(within(removed).getByText('number not in quote: 12345')).toBeInTheDocument()
})

it('click switches page then highlights', async () => {
  render(<App />)
  await askQuestion()
  await send(ev('claim_settled', claim('On page 12', 12, 'verified')))
  await send(ev('claim_settled', claim('On page 40', 40, 'verified')))
  await userEvent.click(screen.getByText('On page 12'))
  fireEvent.load(screen.getByRole('img', { name: /page 12/i }))
  expect(document.querySelectorAll('[data-testid="box"]')).toHaveLength(1)

  await userEvent.click(screen.getByText('On page 40'))
  const img = screen.getByRole('img', { name: /page 40/i })
  expect(img).toHaveAttribute('src', '/api/pages/Army_5kW_Generator_Parts_Manual/40')
  // the old page's boxes must not be drawn over the new page before it loads
  expect(document.querySelectorAll('[data-testid="box"]')).toHaveLength(0)
  fireEvent.load(img)
  const drawn = document.querySelectorAll<HTMLElement>('[data-testid="box"]')
  expect(drawn).toHaveLength(1)
  expect(drawn[0].style.left).toBe('10%')
})

it('abstention lists pages as links', async () => {
  render(<App />)
  await askQuestion()
  await send({ event: 'retrieved', data: { pages: [7, 9] } })
  await send({
    event: 'done',
    data: { text: 'I could not find the answer in the manual. I looked at pages 7, 9.', abstained: true, pages: [7, 9], removed: 0 },
  })
  await send(null)
  expect(screen.getByText(/could not find the answer/)).toBeInTheDocument()
  await userEvent.click(screen.getByRole('link', { name: 'page 9' }))
  expect(screen.getByRole('img', { name: /page 9/i })).toBeInTheDocument()
})

it('figure claim says read from figure', async () => {
  render(<App />)
  await askQuestion()
  await send(ev('claim_settled', claim('Rated 5 kW', 3, 'figure')))
  expect(screen.getByText('read from figure')).toBeInTheDocument()
})

it('follow-up sends history and shows the rewritten question', async () => {
  render(<App />)
  await askQuestion('What oil?')
  await send(ev('claim_settled', claim('Use OE/HDO 30', 20, 'verified')))
  await send({ event: 'done', data: { text: 'Use OE/HDO 30', abstained: false, pages: [20], removed: 0 } })
  await send(null)
  await askQuestion('How much?')
  expect(ask).toHaveBeenLastCalledWith('How much?', PARTS, [
    { role: 'user', content: 'What oil?' },
    { role: 'assistant', content: 'Use OE/HDO 30' },
  ])
  await send({ event: 'retrieved', data: { pages: [20], standalone_question: 'How much OE/HDO 30 oil?' } })
  expect(screen.getByText(/How much OE\/HDO 30 oil\?/)).toBeInTheDocument()
})

it('the theme button switches to dark and back, and remembers the choice', async () => {
  render(<App />)
  await userEvent.click(screen.getByRole('button', { name: 'Switch to dark mode' }))
  expect(document.documentElement.classList.contains('dark')).toBe(true)
  expect(localStorage.getItem('theme')).toBe('dark')
  await userEvent.click(screen.getByRole('button', { name: 'Switch to light mode' }))
  expect(document.documentElement.classList.contains('dark')).toBe(false)
  expect(localStorage.getItem('theme')).toBe('light')
})

it('the button starts from the theme the page already shows', async () => {
  document.documentElement.classList.add('dark')
  render(<App />)
  expect(screen.getByRole('button', { name: 'Switch to light mode' })).toBeTruthy()
  await userEvent.click(screen.getByRole('button', { name: 'Switch to light mode' }))
  expect(document.documentElement.classList.contains('dark')).toBe(false)
})
