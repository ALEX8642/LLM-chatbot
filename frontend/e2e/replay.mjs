// End-to-end check in replay mode: the built frontend against the server serving a
// recording. Uses the pre-installed Playwright library (no test-runner install).
// Usage: node e2e/replay.mjs <app url> <screenshot dir>
import { createRequire } from 'node:module'
import assert from 'node:assert/strict'

const { chromium } = createRequire(import.meta.url)('playwright')
const [url = 'http://localhost:4173', shots = '.'] = process.argv.slice(2)
const PARTS_Q = 'What is the part number of the air cleaner filter element, item 17 in figure 15?'
const ABSTAIN_Q = 'What is the torque for the cylinder head bolts?'

const browser = await chromium.launch()
const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 2 })
const ask = async (q) => {
  await page.getByRole('textbox').fill(q)
  await page.getByRole('button', { name: 'Ask' }).click()
}
try {
  await page.goto(url)
  await page.locator('option').first().waitFor({ state: 'attached' }) // replay lists only recorded manuals

  await ask(PARTS_Q)
  const answer = page.getByRole('list', { name: 'answer' }).last()
  await answer.getByText('The part number is P14-8969.').waitFor()
  await answer.getByLabel('verified').waitFor()
  const removed = page.getByText('1 claim removed, see why')
  await removed.waitFor()
  assert.equal(await answer.getByText(/is 18265/).count(), 0, 'removed claim still in the answer')
  await removed.click()
  await page.getByText(/value 18265 in column \(3\) FSCM/).waitFor()

  await answer.getByText('The part number is P14-8969.').click()
  const img = page.getByRole('img', { name: 'page 59' })
  await img.waitFor()
  await page.waitForFunction(() => document.querySelector('img')?.complete)
  const boxes = page.getByTestId('box')
  await boxes.first().waitFor()
  assert.ok((await boxes.count()) >= 1, 'no highlight boxes drawn')
  // the box must lie inside the page image
  const ib = await img.boundingBox()
  const bb = await boxes.first().boundingBox()
  assert.ok(bb.x >= ib.x && bb.y >= ib.y && bb.x + bb.width <= ib.x + ib.width + 1, 'box outside the page')
  await page.screenshot({ path: `${shots}/parts-row-highlight.png` })

  await ask(ABSTAIN_Q)
  await page.getByText(/could not find the answer in the manual/).waitFor()
  const link = page.getByRole('link', { name: /^page \d+$/ }).first()
  await link.waitFor()
  const target = (await link.textContent()).trim()
  await link.click()
  await page.getByRole('img', { name: target }).waitFor()
  await page.screenshot({ path: `${shots}/abstention.png` })

  await ask('A question that was never recorded')
  await page.getByText('This question is not in the recording.').waitFor()
  console.log('E2E-OK')
} finally {
  await browser.close()
}
