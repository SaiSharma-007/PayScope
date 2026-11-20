import { Plus, Trash2 } from 'lucide-react'
import SelectField from '../../components/SelectField'
import { FormField } from './Fields'
import { errorsFor, newComponent } from './shared'

const options = (values) => values.map(([value, label]) => ({ value, label }))
const categories = options([
  ['earning', 'Earnings'],
  ['employer_cost', 'Employer cost'],
  ['deduction', 'Employee deduction'],
])
const methods = options([
  ['fixed', 'Fixed annual amount'],
  ['percent_of_base', '% of basic pay'],
])
const commitments = options([
  ['guaranteed', 'Guaranteed'],
  ['target', 'Target / variable'],
])

export default function ComponentEditor({
  components,
  onChange,
  error,
  disabled = false,
}) {
  function change(index, patch) {
    onChange(
      components.map((component, position) =>
        position === index ? { ...component, ...patch } : component,
      ),
    )
  }
  return (
    <section className="component-editor" aria-labelledby="components-title">
      <div className="comp-section-heading">
        <div>
          <h2 id="components-title">Custom components</h2>
          <p>Basic pay is included once. Add the rest of the package here.</p>
        </div>
        <span className="demo-label">{components.length} / 32</span>
      </div>
      {!components.length && (
        <div className="comp-empty">
          <p>Start with basic pay, or add allowances, benefits, and bonuses.</p>
        </div>
      )}
      {components.map((component, index) => (
        <fieldset className="component-card" key={index} disabled={disabled}>
          <legend>
            Component {index + 1}
            {component.label ? ` · ${component.label}` : ''}
          </legend>
          {errorsFor(error, `components.${index}`) && (
            <p className="component-error error-message">
              {errorsFor(error, `components.${index}`)}
            </p>
          )}
          <div className="component-fields">
            <FormField
              id={`component-${index}-label`}
              label="Component name"
              value={component.label}
              maxLength={80}
              error={errorsFor(error, `components.${index}.label`)}
              onChange={(event) =>
                change(index, {
                  label: event.target.value,
                })
              }
              placeholder="Custom yearly bonus"
            />
            <FormField
              id={`component-${index}-code`}
              label="Component code"
              value={component.code}
              maxLength={50}
              error={errorsFor(error, `components.${index}.code`)}
              onChange={(event) => change(index, { code: event.target.value })}
              hint="A stable name, e.g. custom_yearly_bonus"
            />
            <SelectField
              id={`component-${index}-category`}
              label="Category"
              value={component.category}
              options={categories}
              onChange={(category) =>
                change(index, {
                  category,
                  ...(category === 'deduction'
                    ? { included_in_cost: false, commitment: 'guaranteed' }
                    : {}),
                })
              }
              disabled={disabled}
            />
            <SelectField
              id={`component-${index}-method`}
              label="Calculation"
              value={component.method}
              options={methods}
              onChange={(method) => change(index, { method })}
              disabled={disabled}
            />
            <FormField
              id={`component-${index}-value`}
              label={
                component.method === 'fixed'
                  ? 'Annual amount'
                  : 'Percentage of basic pay'
              }
              value={component.value}
              inputMode="decimal"
              error={errorsFor(error, `components.${index}.value`)}
              onChange={(event) => change(index, { value: event.target.value })}
              placeholder={component.method === 'fixed' ? '0.00' : '1'}
            />
            <SelectField
              id={`component-${index}-commitment`}
              label="Payment basis"
              value={component.commitment}
              options={commitments}
              onChange={(commitment) => change(index, { commitment })}
              disabled={disabled || component.category === 'deduction'}
            />
          </div>
          <div className="component-footer">
            <label className="comp-checkbox">
              <input
                type="checkbox"
                checked={component.included_in_cost}
                disabled={disabled || component.category === 'deduction'}
                onChange={(event) =>
                  change(index, { included_in_cost: event.target.checked })
                }
              />
              Include in company cost
            </label>
            <button
              type="button"
              className="text-link remove-component"
              disabled={disabled}
              onClick={() =>
                onChange(components.filter((_, position) => position !== index))
              }
            >
              <Trash2 size={15} aria-hidden="true" />
              Remove component {index + 1}
            </button>
          </div>
        </fieldset>
      ))}
      <button
        type="button"
        className="button secondary"
        disabled={disabled || components.length >= 32}
        onClick={() => onChange([...components, newComponent()])}
      >
        <Plus size={17} aria-hidden="true" />
        Add component
      </button>
    </section>
  )
}
