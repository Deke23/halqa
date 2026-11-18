import { useDashboardLive, useDashboardSimulation } from "@/api/hooks";
import type { LiveResponse, SimResponse } from "./types";

/** Measures from the cases in this demo database. */
export function useLive(split: string, region: string) {
  return useDashboardLive<LiveResponse>(split, region);
}

/** The precomputed simulation file. The server ignores the split, so the page picks the split itself. */
export function useSimulation() {
  return useDashboardSimulation<SimResponse>("none");
}
