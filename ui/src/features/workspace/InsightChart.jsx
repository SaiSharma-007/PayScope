import { ArrowRight } from 'lucide-react'
import { InsightCard, InsightHelp } from './InsightHelp'
import { TimelinePlot } from './InsightPointPlots'
import { AWARDS, dash, difference, formatValue, helpFor } from './insightViews'
import { useInsightDetails } from './useInsightDetails'

const ticks = [0, 0.25, 0.5, 0.75, 1]
const compact = new Intl.NumberFormat('en', {
  notation: 'compact',
  maximumFractionDigits: 1,
})
const precise = new Intl.NumberFormat('en', { maximumFractionDigits: 2 })
const width = (fraction) => `${fraction * 100}%`

function Axis({ min = 0, max, currency, share = false }) {
  return (
    <div className="insight-axis" aria-hidden="true">
      <div className="insight-axis-ticks">
        {ticks.map((fraction) => {
          const value = min + (max - min) * fraction
          return (
            <span key={fraction}>
              {(max - min < 1000 ? precise : compact).format(value)}
              {share ? '%' : ''}
            </span>
          )
        })}
      </div>
      {!share && <span className="insight-axis-unit">{currency}</span>}
    </div>
  )
}

function BoxPlot({ row, fraction }) {
  const { p10, p25, p50, p75, p90 } = row.percentiles
  return (
    <>
      <span
        className="insight-whisker"
        style={{
          insetInlineStart: width(fraction(p10)),
          inlineSize: width(fraction(p90) - fraction(p10)),
        }}
      />
      <span
        className="insight-box"
        style={{
          insetInlineStart: width(fraction(p25)),
          inlineSize: width(fraction(p75) - fraction(p25)),
        }}
      />
      <span
        className="insight-median"
        style={{ insetInlineStart: width(fraction(p50)) }}
      />
    </>
  )
}

function Dots({ plot, row, series, fraction }) {
  const [first, second] = series.map(([key]) => row[key])
  return (
    <>
      {first != null && second != null && (
        <span
          className="insight-dot-link"
          style={{
            left: width(Math.min(fraction(first), fraction(second))),
            width: width(Math.abs(fraction(first) - fraction(second))),
          }}
        />
      )}
      {series.map(([key]) =>
        row[key] == null ? null : (
          <span
            className="insight-endpoint"
            data-series={key}
            key={key}
            data-coincident={first != null && first === second}
            style={{ left: width(fraction(row[key])) }}
          />
        ),
      )}
      {plot === 'shares' && second == null && (
        <span className="insight-missing-point">Payroll unavailable</span>
      )}
    </>
  )
}

function HorizontalPlot({
  rows,
  type,
  series,
  currency,
  isActive,
  markProps,
  onPin,
}) {
  const range = type === 'range' || type === 'country'
  const share = type === 'shares'
  const low = range
    ? Math.min(...rows.map((row) => Number(row.percentiles.p10)))
    : 0
  const high = range
    ? Math.max(...rows.map((row) => Number(row.percentiles.p90)))
    : share
      ? 100
      : Math.max(
          ...rows.map((row) =>
            Number(type === 'mix' ? row.amount : row.target_ctc),
          ),
        )
  const min = high === low ? 0 : low
  const max = high || 1
  const fraction = (value) => (Number(value) - min) / (max - min)
  return (
    <div className="insight-horizontal" data-plot={type}>
      <Axis min={min} max={max} currency={currency} share={share} />
      {rows.map((row) => {
        const value = range
          ? row.percentiles.p50
          : share
            ? difference(row.payroll_share, row.headcount_share)
            : type === 'mix'
              ? row.amount
              : difference(row.target_ctc, row.guaranteed_ctc)
        return (
          <button
            type="button"
            className="insight-mark"
            key={row.group_id}
            data-active={isActive(row.group_id)}
            {...markProps(row.group_id)}
            onClick={(event) => onPin(row.group_id, event)}
          >
            <span className="insight-mark-label">{row.group_name}</span>
            <span className="insight-track" aria-hidden="true">
              {range ? (
                <BoxPlot row={row} fraction={fraction} />
              ) : type === 'mix' ? (
                <span className="insight-stack">
                  {series.map(([key]) => {
                    const amount = row.categories.find(
                      (category) => category.category === key,
                    )?.amount
                    return amount == null ? null : (
                      <span
                        key={key}
                        data-series={key}
                        style={{ inlineSize: width(fraction(amount)) }}
                      />
                    )
                  })}
                </span>
              ) : (
                <Dots
                  plot={type}
                  row={row}
                  series={series}
                  fraction={fraction}
                />
              )}
            </span>
            <strong>
              {type === 'paired' && value != null && '+'}
              {formatValue(value, share ? 'points' : 'money', currency)}
            </strong>
          </button>
        )
      })}
    </div>
  )
}

function tiles(rows, box = { x: 0, y: 0, w: 1, h: 1 }) {
  if (rows.length <= 1) return rows.map((row) => ({ ...box, row }))
  const total = rows.reduce((sum, row) => sum + Number(row.amount), 0)
  let cut = 1
  let left = Number(rows[0].amount)
  while (
    cut < rows.length - 1 &&
    left + Number(rows[cut].amount) / 2 < total / 2
  ) {
    left += Number(rows[cut].amount)
    cut += 1
  }
  const ratio = left / total
  const split =
    box.w * 2 >= box.h
      ? [
          { ...box, w: box.w * ratio },
          { ...box, x: box.x + box.w * ratio, w: box.w * (1 - ratio) },
        ]
      : [
          { ...box, h: box.h * ratio },
          { ...box, y: box.y + box.h * ratio, h: box.h * (1 - ratio) },
        ]
  return [
    ...tiles(rows.slice(0, cut), split[0]),
    ...tiles(rows.slice(cut), split[1]),
  ]
}

function Treemap({ rows, isActive, markProps, onPin }) {
  return (
    <div className="insight-treemap" data-single={rows.length === 1}>
      {tiles(rows).map(({ x, y, w, h, row }, index) => (
        <button
          key={row.group_id}
          type="button"
          className="insight-tile"
          data-active={isActive(row.group_id)}
          data-tone={index % 3}
          aria-label={`${row.group_name}, ${row.payroll_share ?? dash}% of payroll`}
          style={{
            insetInlineStart: width(x),
            insetBlockStart: width(y),
            inlineSize: width(w),
            blockSize: width(h),
          }}
          {...markProps(row.group_id)}
          onClick={(event) => onPin(row.group_id, event)}
        >
          <span>{row.group_name}</span>
          <strong>{formatValue(row.payroll_share, 'share')}</strong>
        </button>
      ))}
    </div>
  )
}

function PlotDetails({ selected, columns, currency, onDrill, drillLabel }) {
  return (
    <div className="insight-detail">
      <div className="insight-detail-heading">
        <strong>{selected.group_name ?? selected.year}</strong>
        {onDrill && (
          <button
            type="button"
            className="insight-text-button"
            onClick={() => onDrill(selected)}
          >
            {drillLabel} <ArrowRight size={15} aria-hidden="true" />
          </button>
        )}
      </div>
      {(selected.awards ?? [selected]).map((row) => (
        <div className="insight-detail-series" key={row.kind ?? row.group_id}>
          {row.kind && <strong>{AWARDS[row.kind]}</strong>}
          <dl>
            {columns.map(([label, getValue, mode]) => (
              <div key={label}>
                <dt>{label}</dt>
                <dd>{formatValue(getValue(row), mode, currency)}</dd>
              </div>
            ))}
          </dl>
        </div>
      ))}
      {selected.awards?.length === 0 && (
        <p>No applicable awards in this year.</p>
      )}
    </div>
  )
}

export default function InsightChart({
  type,
  rows,
  currency,
  series,
  columns,
  startYear,
  year,
  onDrill,
  drillLabel,
}) {
  const details = useInsightDetails()
  const plotRows =
    type === 'timeline'
      ? Array.from({ length: year - startYear + 1 }, (_, index) => ({
          year: startYear + index,
          awards: rows.filter((row) => row.year === startYear + index),
        }))
      : rows.filter((row) =>
          type === 'treemap'
            ? Number(row.amount) > 0
            : type === 'shares'
              ? row.population > 0
              : row.eligible > 0,
        )
  const keyOf = (row) => row.group_id ?? row.year
  const selected = plotRows.find((row) => keyOf(row) === details.entry?.key)
  if (!plotRows.length) return null
  const plotProps = {
    rows: plotRows,
    currency,
    series,
    isActive: (key) => details.entry?.key === key,
    markProps: details.trigger,
    onPin: details.pin,
  }
  return (
    <div className="insight-chart" role="group" aria-label="Interactive chart">
      {series.length > 0 && (
        <ul className="insight-legend" aria-label="Chart legend">
          {series.map(([key, label]) => (
            <li key={key}>
              <i data-series={key} aria-hidden="true" />
              {label}
              <InsightHelp label={label}>{helpFor(label)}</InsightHelp>
            </li>
          ))}
        </ul>
      )}
      {type === 'timeline' && (
        <div className="insight-equity-key">
          <span>
            <i data-partial="true" /> Partial total
          </span>
          <span>
            <i data-zero="true" /> Recorded zero
          </span>
          <InsightHelp label="Equity markers">
            A partial point includes recorded allocations only. A square marks a
            reported total of zero. Missing amounts and years with no applicable
            awards leave gaps.
          </InsightHelp>
        </div>
      )}
      {type === 'treemap' ? (
        <Treemap {...plotProps} />
      ) : type === 'timeline' ? (
        <TimelinePlot {...plotProps} />
      ) : (
        <HorizontalPlot type={type} {...plotProps} />
      )}
      {selected && (
        <InsightCard details={details} label="Selected values">
          <PlotDetails
            selected={selected}
            columns={columns}
            currency={currency}
            onDrill={details.entry.pinned ? onDrill : null}
            drillLabel={drillLabel}
          />
        </InsightCard>
      )}
    </div>
  )
}
