import * as SelectPrimitive from '@radix-ui/react-select'
import { useState } from 'react'
import { Check, ChevronDown, ChevronUp } from 'lucide-react'

const ALL = '__all__'

export default function SelectField({
  id,
  label,
  value,
  onChange,
  options,
  placeholder,
  disabled,
}) {
  const [keyboard, setKeyboard] = useState(false)
  return (
    <div className="filter-field">
      <label id={`${id}-label`} htmlFor={id}>
        {label}
      </label>
      <SelectPrimitive.Root
        value={value || ALL}
        onValueChange={(value) => onChange(value === ALL ? '' : value)}
        disabled={disabled}
      >
        <SelectPrimitive.Trigger
          id={id}
          className="select-trigger"
          onKeyDown={() => setKeyboard(true)}
          onPointerDown={() => setKeyboard(false)}
          aria-labelledby={`${id}-label`}
        >
          <SelectPrimitive.Value />
          <SelectPrimitive.Icon asChild>
            <ChevronDown size={16} aria-hidden="true" />
          </SelectPrimitive.Icon>
        </SelectPrimitive.Trigger>
        <SelectPrimitive.Portal>
          <SelectPrimitive.Content
            className="select-menu"
            data-keyboard={keyboard || undefined}
            position="popper"
            sideOffset={7}
            collisionPadding={16}
          >
            <SelectPrimitive.ScrollUpButton className="select-scroll">
              <ChevronUp size={16} />
            </SelectPrimitive.ScrollUpButton>
            <SelectPrimitive.Viewport className="select-viewport">
              {[
                ...(placeholder ? [{ value: ALL, label: placeholder }] : []),
                ...options,
              ].map((option) => (
                <SelectPrimitive.Item
                  className="select-option"
                  key={option.value}
                  value={option.value}
                >
                  <SelectPrimitive.ItemText>
                    {option.label}
                  </SelectPrimitive.ItemText>
                  <SelectPrimitive.ItemIndicator className="select-check">
                    <Check size={16} aria-hidden="true" />
                  </SelectPrimitive.ItemIndicator>
                </SelectPrimitive.Item>
              ))}
            </SelectPrimitive.Viewport>
            <SelectPrimitive.ScrollDownButton className="select-scroll">
              <ChevronDown size={16} />
            </SelectPrimitive.ScrollDownButton>
          </SelectPrimitive.Content>
        </SelectPrimitive.Portal>
      </SelectPrimitive.Root>
    </div>
  )
}
