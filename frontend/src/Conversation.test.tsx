import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, it, vi } from 'vitest'

const ask = vi.fn()
vi.mock('./api', async (original) => ({
  ...(await original<typeof import('./api')>()),
  ask: (...args: unknown[]) => ask(...args),
}))

const { default: Conversation } = await import('./Conversation')

it('with a fixed list, a question is picked, not typed', async () => {
  ask.mockImplementation(async function* () {
    yield { event: 'done', data: { text: 'Not found.', abstained: true } }
  })
  const none = () => {}
  render(
    <Conversation manual="M.pdf" selected={null} onSelect={none} onPage={none} onRemoved={none} questions={['First?', 'Second?']} />,
  )
  expect(screen.queryByRole('textbox')).toBeNull()
  await userEvent.selectOptions(screen.getByRole('combobox', { name: 'question' }), 'Second?')
  await userEvent.click(screen.getByRole('button', { name: /ask/i }))
  expect(ask).toHaveBeenCalledWith('Second?', 'M.pdf', [])
  expect(await screen.findByText('Not found.')).toBeTruthy()
})
