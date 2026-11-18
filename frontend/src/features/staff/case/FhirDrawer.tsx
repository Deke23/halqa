import { useTranslation } from "react-i18next";
import { Drawer, ErrorState, JsonViewer, Loading, SimulatedTag } from "@/components";
import { useFhirBundle } from "../api";

export function FhirDrawer({ caseId, open, onClose }: { caseId: string; open: boolean; onClose: () => void }) {
  const { t } = useTranslation("staff");
  const q = useFhirBundle(caseId, open);
  return (
    <Drawer open={open} onClose={onClose} title={t("fhir.title")} width="xl">
      <div className="mb-3 flex flex-col gap-2">
        <p className="text-sm">{t("fhir.explain")}</p>
        <div>
          <SimulatedTag />
        </div>
      </div>
      {q.isLoading && <Loading />}
      {q.error && <ErrorState error={q.error} onRetry={() => void q.refetch()} />}
      {q.data && <JsonViewer data={q.data} defaultDepth={2} />}
    </Drawer>
  );
}
