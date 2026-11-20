import { money } from './shared'

const categoryNames = {
  earning: 'Earnings',
  employer_cost: 'Employer cost',
  deduction: 'Employee deduction',
}

export default function Breakdown({
  result,
  title = 'Annual calculation',
  children,
}) {
  if (!result) return null
  return (
    <section className="comp-breakdown" aria-label={title}>
      <div className="comp-section-heading">
        <div>
          <h2>{title}</h2>
          <p>All amounts in {result.currency_code} · annual</p>
        </div>
      </div>
      <div className="breakdown-line basic-line">
        <div>
          <strong>Basic pay</strong>
          <small>Entered amount · included in company cost</small>
        </div>
        <strong>{money(result.annual_basic_pay, result.currency_code)}</strong>
      </div>
      {result.components.map((line) => (
        <div className="breakdown-line" key={line.code}>
          <div>
            <strong>{line.label}</strong>
            <small>
              {categoryNames[line.category]} · {line.explanation}
            </small>
            <small>
              {line.commitment === 'target' ? 'Target / variable · ' : ''}
              {line.included_in_cost
                ? 'Included in cost'
                : 'Excluded from cost'}
            </small>
            {line.override_reason && (
              <p className="override-note">
                Overridden from{' '}
                {money(line.calculated_amount, result.currency_code)} ·{' '}
                {line.override_reason}
              </p>
            )}
          </div>
          <strong>{money(line.amount, result.currency_code)}</strong>
        </div>
      ))}
      <dl className="comp-totals">
        <div>
          <dt>Guaranteed cash & benefit cost</dt>
          <dd>{money(result.guaranteed_cost, result.currency_code)}</dd>
        </div>
        <div>
          <dt>Cost including target components</dt>
          <dd>{money(result.target_cost, result.currency_code)}</dd>
        </div>
        <div className="deduction-total">
          <dt>Employee deductions · excluded above</dt>
          <dd>{money(result.employee_deductions, result.currency_code)}</dd>
        </div>
      </dl>
      <p className="comp-footnote">
        Cash and benefit costs exclude equity and employee deductions.
      </p>
      {children}
    </section>
  )
}
