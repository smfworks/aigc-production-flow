import type { ReactNode } from "react";

type FieldProps = {
  label: string;
  hint?: string;
  children: ReactNode;
};

export function Field({ label, hint, children }: FieldProps) {
  return (
    <label className="field">
      <span className="editor-label">{label}</span>
      {children}
      {hint ? <span className="field-hint">{hint}</span> : null}
    </label>
  );
}

type TextProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  hint?: string;
  placeholder?: string;
  mono?: boolean;
  title?: string;
};

export function TextField({
  label,
  value,
  onChange,
  hint,
  placeholder,
  mono,
  title,
}: TextProps) {
  return (
    <Field label={label} hint={hint}>
      <input
        className={mono ? "mono" : undefined}
        value={value}
        placeholder={placeholder}
        title={title || value}
        onChange={(event) => onChange(event.target.value)}
      />
    </Field>
  );
}

export function TextArea({
  label,
  value,
  onChange,
  hint,
  placeholder,
}: TextProps) {
  return (
    <Field label={label} hint={hint}>
      <textarea
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </Field>
  );
}

type SelectProps = {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: readonly { value: string; label: string }[];
  hint?: string;
  allowEmpty?: boolean;
  emptyLabel?: string;
};

export function SelectField({
  label,
  value,
  onChange,
  options,
  hint,
  allowEmpty,
  emptyLabel = "—",
}: SelectProps) {
  return (
    <Field label={label} hint={hint}>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {allowEmpty ? <option value="">{emptyLabel}</option> : null}
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </Field>
  );
}
