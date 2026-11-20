import { useState } from 'react'
import { ArrowRight } from 'lucide-react'
import { AWARDS, dash, formatValue } from './insightViews'

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

function HorizontalPlot({
  rows,
  type,
  series,
  currency,
  isActive,
  markProps,
  onPin,
}) {
  const range = type === 'range'
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
    <div className="insight-horizontal">
      <Axis min={min} max={max} currency={currency} share={share} />
      {rows.map((row) => {
        const value = range
          ? row.percentiles.p50
          : share
            ? row.payroll_share
            : type === 'mix'
              ? row.amount
              : row.target_ctc
        return (
          <button
            type="button"
            className="insight-mark"
            key={row.group_id}
            data-active={isActive(row.group_id)}
            {...markProps(row.group_id)}
            onClick={() => onPin(row.group_id)}
          >
            <span className="insight-mark-label">{row.group_name}</span>
            <span className="insight-track" aria-hidden="true">
              {range ? (
                <BoxPlot row={row} fraction={fraction} />
              ) : (
                <span
                  className={type === 'mix' ? 'insight-stack' : 'insight-pair'}
                >
                  {series.map(([key]) => {
                    const amount =
                      type === 'mix'
                        ? row.categories.find(
                            (category) => category.category === key,
                          )?.amount
                        : row[key]
                    return amount == null ? null : (
                      <span
                        key={key}
                        data-series={key}
                        style={{ inlineSize: width(fraction(amount)) }}
                      />
                    )
                  })}
                </span>
              )}
            </span>
            <strong>
              {formatValue(value, share ? 'share' : 'money', currency)}
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
          onClick={() => onPin(row.group_id)}
        >
          <span>{row.group_name}</span>
          <strong>{formatValue(row.payroll_share, 'share')}</strong>
        </button>
      ))}
    </div>
  )
}

function TimelinePlot({ rows, series, isActive, markProps, onPin }) {
  const max =
    Math.max(
      ...rows.flatMap((row) => row.awards.map((award) => Number(award.amount))),
    ) || 1
  return (
    <div className="insight-timeline-frame">
      <div className="insight-y-axis" aria-hidden="true">
        {[1, 0.5, 0].map((value) => (
          <span key={value}>{compact.format(max * value)}</span>
        ))}
      </div>
      <div
        className="insight-timeline-scroll"
        role="region"
        aria-label="Equity chart calendar"
        tabIndex={0}
      >
        <div className="insight-timeline" style={{ '--years': rows.length }}>
          {rows.map((row) => (
            <button
              type="button"
              className="insight-year"
              key={row.year}
              data-active={isActive(row.year)}
              {...markProps(row.year)}
              onClick={() => onPin(row.year)}
            >
              <span className="insight-year-bars" aria-hidden="true">
                {series.map(([key]) => {
                  const award = row.awards.find((award) => award.kind === key)
                  return (
                    <span
                      key={key}
                      data-series={key}
                      data-recorded={award?.amount != null}
                      style={{
                        blockSize: width(Number(award?.amount) / max || 0),
                      }}
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

function PlotDetails({ selected, columns, currency, onDrill, drillLabel }) {
  return (
    <div className="insight-detail" role="region" aria-label="Selected values">
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
  const [hovered, setHovered] = useState(null)
  const [focused, setFocused] = useState(null)
  const [pinned, setPinned] = useState(null)
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
  const selected =
    plotRows.find((row) => keyOf(row) === (hovered ?? focused ?? pinned)) ??
    plotRows.find((row) => row.awards?.length) ??
    plotRows[0]
  if (!selected) return null
  const isActive = (key) => keyOf(selected) === key
  const markProps = (key) => ({
    'aria-pressed': pinned === key,
    onPointerEnter: (event) => {
      if (event.pointerType === 'mouse') setHovered(key)
    },
    onPointerLeave: () => setHovered(null),
    onFocus: (event) => {
      if (event.currentTarget.matches(':focus-visible')) setFocused(key)
    },
    onBlur: () => setFocused(null),
  })
  const plotProps = {
    rows: plotRows,
    currency,
    series,
    isActive,
    markProps,
    onPin: setPinned,
  }
  return (
    <div className="insight-chart" role="group" aria-label="Interactive chart">
      {type !== 'treemap' && (
        <ul className="insight-legend" aria-label="Chart legend">
          {series.map(([key, label]) => (
            <li key={key}>
              <i data-series={key} aria-hidden="true" />
              {label}
            </li>
          ))}
        </ul>
      )}
      {type === 'treemap' ? (
        <Treemap {...plotProps} />
      ) : type === 'timeline' ? (
        <TimelinePlot {...plotProps} />
      ) : (
        <HorizontalPlot type={type} {...plotProps} />
      )}
      <PlotDetails
        selected={selected}
        columns={columns}
        currency={currency}
        onDrill={onDrill}
        drillLabel={drillLabel}
      />
    </div>
  )
}
