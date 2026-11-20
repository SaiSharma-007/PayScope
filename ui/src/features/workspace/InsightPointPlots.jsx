import { equityStatus, formatValue } from './insightViews'

const compact = new Intl.NumberFormat('en', {
  notation: 'compact',
  maximumFractionDigits: 1,
})
const position = (value, max) => 4 + (92 * Number(value)) / max
const ticks = [1, 0.5, 0]

function VerticalAxis({ max, label }) {
  return (
    <div className="insight-vertical-axis" aria-hidden="true">
      {label && <span className="insight-vertical-label">{label}</span>}
      {ticks.map((tick) => (
        <span key={tick} style={{ top: `${100 - position(tick, 1)}%` }}>
          {compact.format(max * tick)}
        </span>
      ))}
    </div>
  )
}

export function ScatterPlot({ rows, currency, isActive, markProps, onPin }) {
  const medianMax =
    Math.max(...rows.map((row) => Number(row.percentiles.p50))) || 1
  const spreadMax = Math.max(...rows.map((row) => Number(row.spread))) || 1
  return (
    <div className="insight-scatter">
      <VerticalAxis max={spreadMax} label={`Pay spread (${currency})`} />
      <div className="insight-scatter-area">
        {rows.map((row) => (
          <button
            type="button"
            className="insight-country-point"
            key={row.group_id}
            style={{
              '--x': `${position(row.percentiles.p50, medianMax)}%`,
              '--y': `${100 - position(row.spread, spreadMax)}%`,
            }}
            aria-label={`${row.group_name}, median ${formatValue(row.percentiles.p50, 'money', currency)}`}
            data-active={isActive(row.group_id)}
            {...markProps(row.group_id)}
            onClick={(event) => onPin(row.group_id, event)}
          >
            <span aria-hidden="true" />
            <small
              aria-hidden="true"
              data-align={
                Number(row.percentiles.p50) > medianMax / 2 ? 'left' : 'right'
              }
            >
              {row.group_id}
            </small>
          </button>
        ))}
      </div>
      <div className="insight-scatter-axis" aria-hidden="true">
        <div>
          {[...ticks].reverse().map((tick) => (
            <span key={tick}>{compact.format(medianMax * tick)}</span>
          ))}
        </div>
        <strong>Median pay ({currency})</strong>
      </div>
    </div>
  )
}

export function TimelinePlot({ rows, series, isActive, markProps, onPin }) {
  const max =
    Math.max(
      ...rows.flatMap((row) => row.awards.map((award) => Number(award.amount))),
    ) || 1
  const getAward = (row, kind) =>
    row.awards.find((award) => award.kind === kind)
  const x = (index) => (100 * (index + 0.5)) / rows.length
  const y = (award) => 100 - position(award.amount, max)
  return (
    <div className="insight-timeline-frame">
      <VerticalAxis max={max} />
      <div
        className="insight-timeline-scroll"
        role="region"
        aria-label="Equity chart calendar"
        tabIndex={0}
      >
        <div className="insight-timeline" style={{ '--years': rows.length }}>
          <svg
            className="insight-equity-lines"
            aria-hidden="true"
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
          >
            {ticks.map((tick) => (
              <line
                key={tick}
                className="insight-equity-guide"
                x1="0"
                x2="100"
                y1={100 - position(tick, 1)}
                y2={100 - position(tick, 1)}
                vectorEffect="non-scaling-stroke"
              />
            ))}
            {series.flatMap(([kind]) =>
              rows.slice(1).map((row, index) => {
                const start = getAward(rows[index], kind)
                const end = getAward(row, kind)
                return (
                  start?.amount != null &&
                  end?.amount != null && (
                    <line
                      key={`${row.year}:${kind}`}
                      data-series={kind}
                      x1={x(index)}
                      x2={x(index + 1)}
                      y1={y(start)}
                      y2={y(end)}
                      vectorEffect="non-scaling-stroke"
                      data-partial={
                        equityStatus(start) === 'partial' ||
                        equityStatus(end) === 'partial'
                      }
                    />
                  )
                )
              }),
            )}
          </svg>
          {rows.map((row) => (
            <button
              type="button"
              className="insight-year"
              key={row.year}
              data-active={isActive(row.year)}
              {...markProps(row.year)}
              onClick={(event) => onPin(row.year, event)}
            >
              <span className="insight-year-plot" aria-hidden="true">
                {series.map(([kind]) => {
                  const award = getAward(row, kind)
                  if (award?.amount == null) return null
                  return (
                    <span
                      className="insight-equity-point"
                      key={kind}
                      data-series={kind}
                      data-partial={equityStatus(award) === 'partial'}
                      data-zero={Number(award.amount) === 0}
                      style={{ top: `${y(award)}%` }}
                    />
                  )
                })}
              </span>
              <strong>{row.year}</strong>
            </button>
          ))}
        </div>
      </div>
    </div>
  )
}
