import { defineStore } from "pinia";

import { fetchParamsOverview } from "@/api/modules/params";
import { fetchSystemOverview } from "@/api/modules/system";
import type { ParamsOverviewResponse } from "@/types/params";
import type { SystemOverview } from "@/types/system";

interface SystemState {
  overview: SystemOverview | null;
  paramsOverview: ParamsOverviewResponse | null;
  loading: boolean;
  error: string;
}

export const useSystemStore = defineStore("system", {
  state: (): SystemState => ({
    overview: null,
    paramsOverview: null,
    loading: false,
    error: "",
  }),
  actions: {
    async loadOverview() {
      this.loading = true;
      this.error = "";
      try {
        const [overview, paramsOverview] = await Promise.all([
          fetchSystemOverview(),
          fetchParamsOverview().catch(() => null),
        ]);
        this.overview = overview;
        if (paramsOverview) {
          this.paramsOverview = paramsOverview;
        }
      } catch (error) {
        this.error = error instanceof Error ? error.message : "系统概览加载失败";
      } finally {
        this.loading = false;
      }
    },
    setParamsOverview(overview: ParamsOverviewResponse) {
      this.paramsOverview = overview;
    },
  },
});
