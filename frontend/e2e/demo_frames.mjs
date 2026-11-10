// Demo frames for the README GIF: replays recorded answers, one frame per step.
// Usage: node e2e/demo_frames.mjs <app url> <recording.jsonl> <frame dir>
// Each frame's name carries how long the GIF holds it, in ms: long enough to read.
import { createRequire } from 'node:module'
import { readFileSync } from 'node:fs'

const { chromium } = createRequire(import.meta.url)('playwright')
const [url, recording, dir] = process.argv.slice(2)
const entries = readFileSync(recording, 'utf8').trim().split('\n').map((l) => JSON.parse(l))

const browser = await chromium.launch()
let n = 0
const shot = async (page, hold) => {
  n += 1
  await page.screenshot({ path: `${dir}/${String(n).padStart(3, '0')}-${hold}.png` })
}
try {
  for (const e of entries) {
    const page = await browser.newPage({ viewport: { width: 1280, height: 760 }, deviceScaleFactor: 1 })
    await page.goto(url)
    await page.locator(`option[value="${e.manual}"]`).waitFor({ state: 'attached' })
    await page.getByRole('combobox', { name: 'manual' }).selectOption(e.manual)
    await page.getByRole('textbox').fill(e.question)
    await shot(page, 3500)
    await page.getByRole('button', { name: 'Ask' }).click()
    await page.waitForTimeout(400)
    await shot(page, 1500)
    await page.getByText('Checking the manual…').waitFor({ state: 'detached', timeout: 60000 })
    await shot(page, 4500)
    const claims = page.getByRole('list', { name: 'answer' }).getByRole('button')
    for (let i = 0; i < Math.min(2, await claims.count()); i++) {
      await claims.nth(i).click()
      await page.getByTestId('box').first().waitFor()
      await page.waitForTimeout(300)
      await shot(page, 6000)
    }
    await page.close()
  }
} finally {
  await browser.close()
}
console.log(n, 'frames')
