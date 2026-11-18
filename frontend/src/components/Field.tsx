import {
  cloneElement,
  forwardRef,
  isValidElement,
  useId,
  type InputHTMLAttributes,
  type ReactElement,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { useTranslation } from "react-i18next";
import { cx } from "@/lib/cx";

const controlCls =
  "block w-full min-h-11 rounded-lg border border-line bg-surface px-3 py-2 text-base text-ink placeholder:text-muted " +
  "disabled:bg-surface-2 aria-[invalid=true]:border-due";

export interface FieldProps {
  label: ReactNode;
  /** One control (Input, Select, Textarea). The id and aria wiring are injected. */
  children: ReactElement<{ id?: string; "aria-describedby"?: string; "aria-invalid"?: boolean; required?: boolean }>;
  hint?: ReactNode;
  error?: ReactNode;
  required?: boolean;
  optional?: boolean;
  className?: string;
}

/** Label, hint and error message wired to a single control. */
export function Field({ label, children, hint, error, required, optional, className }: FieldProps) {
  const { t } = useTranslation();
  const id = useId();
  const hintId = `${id}-hint`;
  const errId = `${id}-err`;
  const describedBy = [hint ? hintId : null, error ? errId : null].filter(Boolean).join(" ") || undefined;
  const wired = isValidElement(children)
    ? cloneElement(children, { id, "aria-describedby": describedBy, "aria-invalid": error ? true : undefined, required })
    : children;
  return (
    <div className={cx("flex flex-col gap-1.5", className)}>
      <label htmlFor={id} className="text-sm font-medium">
        {label}
        {optional && <span className="ms-1 font-normal text-muted">({t("generic.optional")})</span>}
      </label>
      {wired}
      {hint && (
        <p id={hintId} className="text-sm text-muted">
          {hint}
        </p>
      )}
      {error && (
        <p id={errId} role="alert" className="text-sm font-medium text-due-ink">
          {error}
        </p>
      )}
    </div>
  );
}

export const Input = forwardRef<HTMLInputElement, InputHTMLAttributes<HTMLInputElement>>(function Input(
  { className, ...rest },
  ref,
) {
  return <input ref={ref} className={cx(controlCls, className)} {...rest} />;
});

export const Textarea = forwardRef<HTMLTextAreaElement, TextareaHTMLAttributes<HTMLTextAreaElement>>(function Textarea(
  { className, rows = 3, ...rest },
  ref,
) {
  return <textarea ref={ref} rows={rows} className={cx(controlCls, className)} {...rest} />;
});

export interface SelectOption {
  value: string;
  label: string;
}

export interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> {
  options: SelectOption[];
  placeholder?: string;
}

export const Select = forwardRef<HTMLSelectElement, SelectProps>(function Select(
  { options, placeholder, className, ...rest },
  ref,
) {
  return (
    <select ref={ref} className={cx(controlCls, "pe-8", className)} {...rest}>
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  );
});

export interface RadioOption {
  value: string;
  label: ReactNode;
  description?: ReactNode;
  disabled?: boolean;
}

export interface RadioGroupProps {
  name: string;
  legend: ReactNode;
  options: RadioOption[];
  value: string;
  onChange: (value: string) => void;
  error?: ReactNode;
  /** Lay options out side by side. Default is stacked. */
  inline?: boolean;
  className?: string;
}

export function RadioGroup({ name, legend, options, value, onChange, error, inline, className }: RadioGroupProps) {
  return (
    <fieldset className={cx("min-w-0", className)}>
      <legend className="mb-2 text-sm font-medium">{legend}</legend>
      <div className={cx("flex gap-2", inline ? "flex-row flex-wrap" : "flex-col")}>
        {options.map((o) => {
          const checked = o.value === value;
          return (
            <label
              key={o.value}
              className={cx(
                "flex min-h-11 cursor-pointer items-start gap-3 rounded-lg border px-3 py-2",
                checked ? "border-accent bg-accent-soft" : "border-line bg-surface hover:bg-surface-2",
                o.disabled && "cursor-not-allowed opacity-60",
              )}
            >
              <input
                type="radio"
                name={name}
                value={o.value}
                checked={checked}
                disabled={o.disabled}
                onChange={() => onChange(o.value)}
                className="mt-1 size-4 accent-[var(--color-accent)]"
              />
              <span className="flex flex-col">
                <span className="font-medium">{o.label}</span>
                {o.description && <span className="text-sm text-muted">{o.description}</span>}
              </span>
            </label>
          );
        })}
      </div>
      {error && (
        <p role="alert" className="mt-1 text-sm font-medium text-due-ink">
          {error}
        </p>
      )}
    </fieldset>
  );
}
