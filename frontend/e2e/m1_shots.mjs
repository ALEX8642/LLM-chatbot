// M1 screenshots: replays each recorded question in a fresh page, clicks its first claim,
// and saves the highlight (or the abstention).
// Usage: node e2e/m1_shots.mjs <app url> <recording.jsonl> <screenshot dir>
import { createRequire } from 'node:module'
import { readFileSync } from 'node:fs'

const { chromium } = createRequire(import.meta.url)('playwright')
const [url, recording, shots] = process.argv.slice(2)
const entries = readFileSync(recording, 'utf8').trim().split('\n').map((l) => JSON.parse(l))

const browser = await chromium.launch()
try {
  for (const [i, e] of entries.entries()) {
    const page = await browser.newPage({ viewport: { width: 1400, height: 900 }, deviceScaleFactor: 2 })
    await page.goto(url)
    await page.locator(`option[value="${e.manual}"]`).waitFor({ state: 'attached' })
    await page.getByRole('combobox', { name: 'manual' }).selectOption(e.manual)
    await page.getByRole('textbox').fill(e.question)
    await page.getByRole('button', { name: 'Ask' }).click()
    await page.getByText('Checking the manual…').waitFor({ state: 'detached', timeout: 60000 })
    const claims = page.getByRole('list', { name: 'answer' }).getByRole('button')
    let drawn = 0
    if (await claims.count()) {
      await claims.first().click()
      await page.getByTestId('box').first().waitFor()
      drawn = await page.getByTestId('box').count()
    }
    const n = String(i + 1).padStart(2, '0')
    await page.screenshot({ path: `${shots}/${n}.png` })
    console.log(n, `claims=${await claims.count()}`, `boxes=${drawn}`, e.question.slice(0, 60))
    await page.close()
  }
} finally {
  await browser.close()
}
