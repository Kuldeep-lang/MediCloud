// Chart tokens. Categorical order is fixed (validated for colour-vision deficiency):
// slot 1 blue, 2 orange, 3 aqua, 4 yellow. Single-series charts always use slot 1.
export const SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100']
export const GRID = '#e6e9ef'
export const AXIS = '#8a8f98'
export const SURFACE = '#ffffff'

export const axisProps = {
  stroke: GRID,
  tick: { fill: AXIS, fontSize: 12 },
  tickLine: false,
  axisLine: { stroke: GRID },
}

export const gridProps = { stroke: GRID, vertical: false }

export const tooltipProps = {
  cursor: { fill: 'rgba(42, 120, 214, 0.06)', stroke: GRID },
  contentStyle: {
    borderRadius: 12,
    border: '1px solid #e2e8f0',
    boxShadow: '0 4px 16px rgba(15, 30, 60, 0.08)',
    fontSize: 12,
    color: '#0f172a',
  },
  labelStyle: { color: '#475569', fontWeight: 600, marginBottom: 4 },
}

export const legendProps = {
  iconType: 'circle',
  iconSize: 8,
  wrapperStyle: { fontSize: 12, color: '#475569', paddingTop: 8 },
}

// 2px surface gap between adjacent / stacked fills (no borders around marks).
export const barGap = { stroke: SURFACE, strokeWidth: 2 }
