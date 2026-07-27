import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom'
import { LegacyRedirect } from '../App'

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="redirected-location">{location.pathname}{location.search}{location.hash}</output>
}

describe('legacy generation entry compatibility', () => {
  it('is represented by the workbench redirect instead of an upload UI', () => {
    render(
      <MemoryRouter initialEntries={['/electronic-inspection/generate?source=legacy#review']}>
        <Routes>
          <Route path="/electronic-inspection/generate" element={<LegacyRedirect to="/electronic-inspection/workbench" />} />
          <Route path="/electronic-inspection/workbench" element={<LocationProbe />} />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByTestId('redirected-location').textContent).toBe('/electronic-inspection/workbench?source=legacy#review')
  })
})
