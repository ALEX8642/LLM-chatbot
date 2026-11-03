import { expect, it } from 'vitest'
import { boxStyle } from './boxes'

it('boxStyle maps normalised box to percentages', () => {
  expect(boxStyle({ x0: 0.1, y0: 0.25, x1: 0.5, y1: 0.3 })).toEqual({
    left: '10%',
    top: '25%',
    width: '40%',
    height: '5%',
  })
})
