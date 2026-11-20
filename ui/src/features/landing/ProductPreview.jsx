import { useState } from 'react'
import { CircleCheck, Globe2, Layers3, Users } from 'lucide-react'

const examples = {
  India: {
    currency: 'INR',
    scale: '₹5L',
    end: '₹30L',
    axis: [500000, 3000000],
    medians: [1450000, 1220000, 1780000],
    minimums: [650000, 500000, 800000],
    maximums: [2600000, 2000000, 3000000],
  },
  'United States': {
    currency: 'USD',
    scale: '$40k',
    end: '$180k',
    axis: [40000, 180000],
    medians: [112000, 84000, 128000],
    minimums: [65000, 40000, 78000],
    maximums: [160000, 130000, 180000],
  },
  Germany: {
    currency: 'EUR',
    scale: '€35k',
    end: '€130k',
    axis: [35000, 130000],
    medians: [76000, 62000, 88000],
    minimums: [45000, 35000, 53000],
    maximums: [110000, 95000, 130000],
  },
}
const roles = ['Engineering', 'Operations', 'Finance']

export default function ProductPreview() {
  const [country, setCountry] = useState('India')
  const data = examples[country]
  const position = (value) =>
    ((value - data.axis[0]) / (data.axis[1] - data.axis[0])) * 100
  const format = (value) => value.toLocaleString('en-US')
  return (
    <div className="product-preview" aria-label="Illustrative salary report">
      <div className="liquid-wash" aria-hidden="true">
        <span />
        <span />
      </div>
      <div className="preview-caption">
        <span className="small-label">Inside PayScope</span>
        <span className="demo-label">Fictional example</span>
      </div>
      <div className="preview-report panel">
        <div className="panel-heading">
          <div>
            <span className="small-label">Pay Analytics</span>
            <h2>Salary ranges</h2>
          </div>
          <span className="icon-tile">
            <Layers3 size={20} aria-hidden="true" />
          </span>
        </div>
        <fieldset className="country-tabs">
          <legend className="sr-only">Example country</legend>
          {Object.keys(examples).map((name) => (
            <button
              key={name}
              type="button"
              aria-pressed={country === name}
              onClick={() => setCountry(name)}
            >
              {name}
            </button>
          ))}
        </fieldset>
        <div className="chart-meta">
          <span>Median annual base salary</span>
          <span className="currency-chip">{data.currency}</span>
        </div>
        <div className="preview-ranges" aria-live="polite">
          {roles.map((role, index) => (
            <div
              className="preview-range"
              key={role}
              role="group"
              aria-label={`${role}, minimum ${data.currency} ${format(data.minimums[index])}, median ${format(data.medians[index])}, maximum ${format(data.maximums[index])}`}
            >
              <div className="range-label">
                <span>{role}</span>
                <span>
                  {data.currency} {format(data.medians[index])}
                </span>
              </div>
              <div className="range-track" aria-hidden="true">
                <span
                  className="range-fill"
                  style={{
                    left: `${position(data.minimums[index])}%`,
                    width: `${position(data.maximums[index]) - position(data.minimums[index])}%`,
                  }}
                />
                <i
                  className="median-dot"
                  style={{ left: `${position(data.medians[index])}%` }}
                />
              </div>
            </div>
          ))}
        </div>
        <div className="chart-axis">
          <span>{data.scale}</span>
          <span>{data.end}</span>
        </div>
        <div className="chart-legend">
          <span>
            <i className="legend-range" /> Salary range
          </span>
          <span>
            <i className="legend-median" /> Median
          </span>
        </div>
      </div>
      <div className="preview-bottom">
        <div className="panel workforce-card">
          <span className="icon-tile">
            <Users size={20} aria-hidden="true" />
          </span>
          <div>
            <strong>10,000</strong>
            <span>fictional employees</span>
          </div>
          <div className="mini-avatars" aria-hidden="true">
            <span>AR</span>
            <span>ML</span>
            <span>EC</span>
            <span>+</span>
          </div>
        </div>
        <div className="panel currency-card">
          <Globe2 size={21} aria-hidden="true" />
          <strong>One clear view.</strong>
          <span>Every salary in its own currency.</span>
          <div className="currency-row">
            <span>INR</span>
            <span>USD</span>
            <span>GBP</span>
            <span>EUR</span>
          </div>
        </div>
      </div>
      <div className="preview-confirmation">
        <CircleCheck size={17} aria-hidden="true" /> Your next report reflects
        every saved change.
      </div>
    </div>
  )
}
