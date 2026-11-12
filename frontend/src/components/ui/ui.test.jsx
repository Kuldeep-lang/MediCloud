import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { DataTable, Pagination } from './DataTable'
import { ConfirmDialog } from './Modal'
import { Badge } from './primitives'
import { StatCard } from './StatCard'

describe('Badge', () => {
  it('always renders a text label, not colour alone', () => {
    render(<Badge status="partially_paid" />)
    expect(screen.getByText('Partially paid')).toBeInTheDocument()
  })
})

describe('StatCard', () => {
  it('shows label, value and hint', () => {
    render(<StatCard label="Total patients" value="120" hint="All time" />)
    expect(screen.getByText('Total patients')).toBeInTheDocument()
    expect(screen.getByText('120')).toBeInTheDocument()
    expect(screen.getByText('All time')).toBeInTheDocument()
  })
})

describe('DataTable', () => {
  const columns = [
    { key: 'name', header: 'Name' },
    { key: 'age', header: 'Age', align: 'right' },
  ]

  it('renders an empty state when there are no rows', () => {
    render(<DataTable columns={columns} rows={[]} />)
    expect(screen.getByText('No records found')).toBeInTheDocument()
  })

  it('renders rows and supports keyboard row activation', async () => {
    const onRowClick = vi.fn()
    const user = userEvent.setup()
    render(<DataTable columns={columns} rows={[{ id: 1, name: 'Meera', age: 41 }]} onRowClick={onRowClick} />)
    expect(screen.getByRole('columnheader', { name: 'Name' })).toBeInTheDocument()
    const row = screen.getByText('Meera').closest('tr')
    row.focus()
    await user.keyboard('{Enter}')
    expect(onRowClick).toHaveBeenCalledWith({ id: 1, name: 'Meera', age: 41 })
  })
})

describe('Pagination', () => {
  it('moves between pages', async () => {
    const onChange = vi.fn()
    const user = userEvent.setup()
    render(<Pagination page={1} pageSize={10} total={35} onChange={onChange} />)
    expect(screen.getByText('Page 1 of 4')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Previous page' })).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Next page' }))
    expect(onChange).toHaveBeenCalledWith(2)
  })
})

describe('ConfirmDialog', () => {
  it('passes the optional note to onConfirm', async () => {
    const onConfirm = vi.fn().mockResolvedValue(undefined)
    const user = userEvent.setup()
    render(
      <ConfirmDialog open title="Cancel appointment?" message="Sure?" confirmLabel="Yes, cancel"
        inputLabel="Reason" onConfirm={onConfirm} onClose={() => {}} />,
    )
    expect(screen.getByRole('dialog', { name: 'Cancel appointment?' })).toBeInTheDocument()
    await user.type(screen.getByLabelText('Reason'), 'Patient request')
    await user.click(screen.getByRole('button', { name: 'Yes, cancel' }))
    expect(onConfirm).toHaveBeenCalledWith('Patient request')
  })

  it('closes on Escape', async () => {
    const onClose = vi.fn()
    const user = userEvent.setup()
    render(<ConfirmDialog open title="Delete?" message="Sure?" onConfirm={() => {}} onClose={onClose} />)
    await user.keyboard('{Escape}')
    expect(onClose).toHaveBeenCalled()
  })
})
