import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "./Button";
import { Modal } from "./Modal";

export interface ConfirmDialogProps {
  open: boolean;
  title: ReactNode;
  body: ReactNode;
  onConfirm: () => void;
  onCancel: () => void;
  confirmLabel?: string;
  cancelLabel?: string;
  loading?: boolean;
  /** Red confirm button. Staff screens only. */
  destructive?: boolean;
}

export function ConfirmDialog({ open, title, body, onConfirm, onCancel, confirmLabel, cancelLabel, loading, destructive }: ConfirmDialogProps) {
  const { t } = useTranslation();
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onCancel}>
            {cancelLabel ?? t("generic.cancel")}
          </Button>
          <Button variant={destructive ? "danger" : "primary"} onClick={onConfirm} loading={loading}>
            {confirmLabel ?? t("generic.confirm")}
          </Button>
        </>
      }
    >
      <div className="text-base">{body}</div>
    </Modal>
  );
}
