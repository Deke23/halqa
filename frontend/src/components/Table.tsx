import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { cx } from "@/lib/cx";

export interface Column<T> {
  key: string;
  header: ReactNode;
  cell: (row: T) => ReactNode;
  className?: string;
  /** Right-align (end-align) numeric columns. */
  numeric?: boolean;
}

export interface TableProps<T> {
  columns: Column<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  caption: string;
  /** Makes each row keyboard reachable and clickable. */
  onRowClick?: (row: T) => void;
  empty?: ReactNode;
  className?: string;
  /** Scroll the body inside this height (for example "28rem") so the header stays visible. */
  maxHeight?: string;
}

export function Table<T>({ columns, rows, rowKey, caption, onRowClick, empty, className, maxHeight }: TableProps<T>) {
  const { t } = useTranslation();
  return (
    <div className={cx("overflow-x-auto rounded-card border border-line bg-surface", maxHeight && "overflow-y-auto", className)} style={maxHeight ? { maxHeight } : undefined}>
      <table className="w-full border-collapse text-start text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="sticky top-0 z-10 bg-surface-2">
          <tr>
            {columns.map((c) => (
              <th
                key={c.key}
                scope="col"
                className={cx("border-b border-line px-4 py-2.5 text-xs font-medium text-muted", c.numeric ? "text-end" : "text-start", c.className)}
              >
                {c.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={columns.length} className="px-4 py-10 text-center text-muted">
                {empty ?? t("table.noRows")}
              </td>
            </tr>
          )}
          {rows.map((row) => (
            <tr
              key={rowKey(row)}
              className={cx("border-t border-line first:border-t-0 hover:bg-surface-2/60", onRowClick && "cursor-pointer focus-within:bg-accent-soft/50")}
              onClick={onRowClick ? () => onRowClick(row) : undefined}
              onKeyDown={
                onRowClick
                  ? (e) => {
                      if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) {
                        e.preventDefault();
                        onRowClick(row);
                      }
                    }
                  : undefined
              }
              tabIndex={onRowClick ? 0 : undefined}
            >
              {columns.map((c) => (
                <td key={c.key} className={cx("px-4 py-3 align-middle", c.numeric ? "text-end" : "text-start", c.className)}>
                  {c.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
