/**
 * Machine-learning API client.
 *
 * These endpoints require the FastAPI backend (`VITE_USE_MOCK=false`); they are
 * read-only apart from model activation, which is admin-gated server-side.
 */
import { api } from './apiClient';

export interface ModelInfo {
  kind: string;
  latest: string | null;
  versions: string[];
  metadata: Record<string, unknown>;
}

export interface MlHealth {
  status: string;
  schema_version?: string;
  dead_stock?: { model_version?: string; model_trained_at_utc?: string; pipeline_version?: string };
  forecasting?: { model_version?: string; pipeline_version?: string };
  [key: string]: unknown;
}

export interface PortfolioItem {
  productId: string;
  name: string;
  status: 'OK' | 'ERROR';
  error?: { code: string; message: string };
  deadStock?: {
    status: string;
    prediction?: string | null;
    dead_stock_risk_score?: number;
    model_version?: string;
    predictor?: string;
    warnings?: string[];
    human_review_required?: boolean;
  };
  forecast?: {
    status: string;
    method?: string;
    forecast_total_units?: number;
    forecast_weekly_units?: number[];
  };
}

export interface PortfolioResponse {
  status: string;
  evaluated: number;
  failures: number;
  syntheticHistoryNote: string;
  results: PortfolioItem[];
}

export interface RetailInsights {
  status: string;
  sources: string[];
  bundlesAndCustomers?: Record<string, unknown> | null;
  pricingElasticity?: Record<string, unknown> | null;
  priceAwareForecast?: Record<string, unknown> | null;
  customerSegments?: Record<string, string>[] | null;
}

export const mlService = {
  health: () => api.get<MlHealth>('/health'),
  models: () => api.get<ModelInfo[]>('/models'),
  portfolio: (horizonWeeks = 4) =>
    api.post<PortfolioResponse>('/ml/portfolio', { horizon_weeks: horizonWeeks }),
  insights: () => api.get<RetailInsights>('/retail/insights'),
};
