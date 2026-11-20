import { Brain, Boxes, Database, FlaskConical, RefreshCw, ShieldCheck, TriangleAlert } from 'lucide-react';
import { useCallback, useEffect, useState } from 'react';
import {
  EmptyState,
  KpiCell,
  KpiStrip,
  PageHeader,
  SectionCard,
  SectionHeader,
  StatusText,
} from '../components/ui/DesignSystem';
import { USE_MOCK } from '../config';
import { ApiClientError } from '../services/apiClient';
import { mlService, type ModelInfo, type PortfolioResponse, type RetailInsights } from '../services/mlService';

function metric(value: unknown, digits = 3): string {
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(digits) : '—';
}

function firstNumber(source: unknown, keys: string[]): number | null {
  if (!source || typeof source !== 'object') return null;
  for (const key of keys) {
    const value = (source as Record<string, unknown>)[key];
    if (typeof value === 'number' && Number.isFinite(value)) return value;
  }
  return null;
}

export function MlIntelligencePage() {
  const [models, setModels] = useState<ModelInfo[]>([]);
  const [portfolio, setPortfolio] = useState<PortfolioResponse | null>(null);
  const [insights, setInsights] = useState<RetailInsights | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (USE_MOCK) return;
    setLoading(true);
    setError(null);
    try {
      const [modelList, portfolioResult, retailInsights] = await Promise.all([
        mlService.models(),
        mlService.portfolio(4),
        mlService.insights(),
      ]);
      setModels(modelList);
      setPortfolio(portfolioResult);
      setInsights(retailInsights);
    } catch (err) {
      setError(
        err instanceof ApiClientError
          ? `${err.message} (${err.code})`
          : 'The ML service could not be reached.'
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const okResults = portfolio?.results.filter((r) => r.status === 'OK') ?? [];
  const atRisk = okResults.filter(
    (r) => (r.deadStock?.dead_stock_risk_score ?? 0) >= 0.5 || r.deadStock?.prediction === 'Dead Stock Risk'
  );
  const forecastUnits = okResults.reduce((sum, r) => sum + (r.forecast?.forecast_total_units ?? 0), 0);
  const elasticity = firstNumber(insights?.pricingElasticity, ['pooled_elasticity', 'elasticity']);

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Machine Learning"
        title="ML Intelligence Console"
        description="Audited model outputs, dead-stock risk and demand forecasts. Recommendations are decision support only and require owner approval."
        actions={
          <button
            type="button"
            onClick={() => void load()}
            disabled={loading || USE_MOCK}
            className="min-h-[38px] inline-flex items-center gap-1.5 rounded-lg border border-[#E5EAE5] bg-white px-3 py-2 text-xs font-semibold text-[#172B22] hover:bg-[#FAF7EF] transition-colors disabled:opacity-50"
          >
            <RefreshCw className={`h-3.5 w-3.5 ${loading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        }
      />

      {USE_MOCK ? (
        <SectionCard>
          <EmptyState
            icon={<Brain className="h-5 w-5" />}
            title="ML console needs the backend connection"
            description="Set VITE_USE_MOCK=false and point VITE_API_BASE_URL at the FastAPI server to load live model outputs."
          />
        </SectionCard>
      ) : error ? (
        <SectionCard>
          <EmptyState
            icon={<TriangleAlert className="h-5 w-5" />}
            title="ML service unavailable"
            description={error}
          />
        </SectionCard>
      ) : (
        <>
          <KpiStrip columns={4} ariaLabel="ML summary">
            <KpiCell
              label="Registered models"
              value={String(models.length)}
              caption="Versioned bundles on disk"
              icon={<Boxes className="h-3.5 w-3.5" />}
            />
            <KpiCell
              label="Products evaluated"
              value={String(portfolio?.evaluated ?? 0)}
              caption={`${portfolio?.failures ?? 0} failures`}
              icon={<Database className="h-3.5 w-3.5" />}
              tone={(portfolio?.failures ?? 0) > 0 ? 'amber' : 'emerald'}
            />
            <KpiCell
              label="At-risk lines"
              value={String(atRisk.length)}
              caption="Dead-stock risk ≥ 0.50"
              icon={<TriangleAlert className="h-3.5 w-3.5" />}
              tone={atRisk.length > 0 ? 'crimson' : 'emerald'}
            />
            <KpiCell
              label="4-week demand"
              value={forecastUnits.toLocaleString('en-IN')}
              caption="Forecast units across catalogue"
              icon={<FlaskConical className="h-3.5 w-3.5" />}
            />
          </KpiStrip>

          <SectionCard>
            <SectionHeader
              title="Model registry"
              subtitle="Immutable versions; activation is admin-only and checksum-verified."
              icon={<ShieldCheck className="h-4 w-4" />}
            />
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#FAF7EF] text-[#65766D]">
                  <tr>
                    <th className="px-5 py-2.5 font-medium">Kind</th>
                    <th className="px-5 py-2.5 font-medium">Active version</th>
                    <th className="px-5 py-2.5 font-medium">Versions</th>
                    <th className="px-5 py-2.5 font-medium">Trained at (UTC)</th>
                  </tr>
                </thead>
                <tbody>
                  {models.map((model) => {
                    const trained = model.metadata?.model_trained_at_utc;
                    return (
                      <tr key={model.kind} className="border-t border-[#E5EAE5]">
                        <td className="px-5 py-2.5 font-medium text-[#172B22]">{model.kind}</td>
                        <td className="px-5 py-2.5 font-mono text-[11px] text-[#145C3A]">
                          {model.latest ?? '—'}
                        </td>
                        <td className="px-5 py-2.5 tabular-nums">{model.versions.length}</td>
                        <td className="px-5 py-2.5 text-[#65766D]">
                          {typeof trained === 'string' ? trained.replace('T', ' ').slice(0, 19) : '—'}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </SectionCard>

          <SectionCard>
            <SectionHeader
              title="Portfolio recommendations"
              subtitle="Each product is scored independently; insufficient history returns NO_VALID_SALES rather than a guess."
              icon={<Brain className="h-4 w-4" />}
            />
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead className="bg-[#FAF7EF] text-[#65766D]">
                  <tr>
                    <th className="px-5 py-2.5 font-medium">Product</th>
                    <th className="px-5 py-2.5 font-medium">Dead-stock risk</th>
                    <th className="px-5 py-2.5 font-medium">Status</th>
                    <th className="px-5 py-2.5 font-medium">4-week forecast</th>
                    <th className="px-5 py-2.5 font-medium">Method</th>
                  </tr>
                </thead>
                <tbody>
                  {okResults.map((row) => {
                    const risk = row.deadStock?.dead_stock_risk_score;
                    return (
                      <tr key={row.productId} className="border-t border-[#E5EAE5]">
                        <td className="px-5 py-2.5">
                          <p className="font-medium text-[#172B22]">{row.name}</p>
                          <p className="font-mono text-[10px] text-[#718078]">{row.productId}</p>
                        </td>
                        <td className="px-5 py-2.5 font-mono tabular-nums">
                          {typeof risk === 'number' ? risk.toFixed(3) : '—'}
                        </td>
                        <td className="px-5 py-2.5">
                          {typeof risk === 'number' && risk >= 0.5 ? (
                            <StatusText label="Review" tone="amber" />
                          ) : (
                            <StatusText label={row.deadStock?.prediction ?? row.deadStock?.status ?? 'OK'} tone="emerald" />
                          )}
                        </td>
                        <td className="px-5 py-2.5 tabular-nums">
                          {row.forecast?.forecast_total_units ?? '—'}
                        </td>
                        <td className="px-5 py-2.5 text-[#65766D]">{row.forecast?.method ?? '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
            {portfolio?.syntheticHistoryNote && (
              <p className="border-t border-[#E5EAE5] bg-[#FAF7EF] px-5 py-3 text-[11px] text-[#65766D]">
                {portfolio.syntheticHistoryNote}
              </p>
            )}
          </SectionCard>

          <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
            <SectionCard>
              <SectionHeader
                title="Pricing elasticity"
                subtitle="Published experiment output; not a live pricing decision."
                icon={<FlaskConical className="h-4 w-4" />}
              />
              <div className="px-5 py-4 space-y-2 text-xs text-[#5F7068]">
                <p>
                  Pooled elasticity:{' '}
                  <span className="font-mono font-semibold text-[#172B22]">
                    {typeof elasticity === 'number' ? flexibility(elasticity) : '—'}
                  </span>
                </p>
                <p className="leading-relaxed">
                  All price changes are suggestions. The engine labels every recommendation as requiring
                  owner approval before it reaches the counter.
                </p>
              </div>
            </SectionCard>

            <SectionCard>
              <SectionHeader
                title="Retail experiment sources"
                subtitle="Read-only files under reports/ml/retail."
                icon={<Database className="h-4 w-4" />}
              />
              <div className="px-5 py-4 space-y-1.5 text-xs">
                {insights?.sources?.length ? (
                  insights.sources.map((source) => (
                    <p key={source} className="font-mono text-[11px] text-[#65766D]">
                      {source}
                    </p>
                  ))
                ) : (
                  <p className="text-[#65766D]">No published experiment outputs found.</p>
                )}
                <p className="pt-2 text-[11px] text-[#718078]">
                  Price-aware forecast WAPE:{' '}
                  {metric(firstNumber(insights?.priceAwareForecast, ['wape', 'WAPE']))}
                  {' · '}
                  Customer segments:{' '}
                  {insights?.customerSegments?.length
                    ? `${insights.customerSegments.length} published rows`
                    : '—'}
                </p>
              </div>
            </SectionCard>
          </div>
        </>
      )}
    </div>
  );
}

function flexibility(value: number): string {
  return value.toFixed(4);
}
