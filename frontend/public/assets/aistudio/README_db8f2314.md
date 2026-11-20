# Trexo (Hackathon Demo)

**Free your cash. Never run out.**

A desktop billing, dead-stock cash rescue, and restock planning demo built for rural Indian kirana owners.

> **Connectivity & Persistence:** Works with unreliable connectivity; all data is saved on this device in `localStorage`. *(This demo has no service worker and does not load offline from a cold browser refresh.)*

## Core Demo Story

1. Inspect **Cash trapped in dead stock** and **Estimated sales lost to stockouts** on the Counter or Inventory hero strip.
2. Open **Rescue Stuck Cash**, apply a counter discount to a slow/dead item (updating Counter pricing immediately), or move items to the supplier return list.
3. Sell the discounted dead-stock item at the Counter (via search + `Enter`, category browse, or the Counter Dead-Stock Bundle suggestion) and watch trapped capital, dead-stock tabs, and alerts update immediately on bill completion.
4. Switch to **Restock** (`/restock`) to review forward demand forecasts (*Demo forecast*) and add out-of-stock fast movers to a Purchase Order.

## Run Steps

```bash
npm install
npm run dev       # Starts Vite dev server on port 3000
npm test          # Runs Vitest unit tests (paise & cart math)
npm run lint      # Runs TypeScript type-checking (tsc --noEmit)
npm run build     # Builds production bundle into dist/
```

## Service Layer Interfaces (For Backend Integration)

UI components read from a single Zustand ledger store backed by typed async service contracts in `src/services/interfaces.ts` and switched via `VITE_USE_MOCK`:

- `IProductService`: `getAll()`, `create(input)`, `update(id, patch)`, `setCounterDiscount(id, pricePaise)`, `setStopReordering(id, stop)`
- `IBillingService`: `getSales()`, `completeSale(input)`
- `IInventoryService`: `adjustStock(id, deltaQty)`, `returnToSupplier({ productId, qty, reason })`
- `ISupplierService`: `getAll()`, `getReturnList()`, `markReturnSlipGenerated(returnIds)`, `clearReturnedItem(returnId)`
- `ICustomerService`: `getAll()`, `create(input)`, `recordPartialPayment(customerId, amountPaise)`
- `IForecastService`: `getForecast(horizon)`, `getPurchaseOrders()`, `createPurchaseOrder(items)`
- `IReportsService`: `getSalesSummary()`, `resetDemoData()`

## What Is Mocked in This Demo

- **Persistence**: All products, sales, customers, suppliers, supplier returns, and purchase orders are stored in `localStorage` (`src/services/mockServices.ts`) and seeded with relative dates around today (`DEADSTOCK_DAYS = 30`, `NEAR_EXPIRY_DAYS = 14` in `src/config.ts`).
- **Demand Forecasts (Restock)**: Forward multipliers (`1W`, `1M`, `6M`, `1Y`) and lost-sales estimates are seeded calculations labeled **Demo forecast** / **Seeded estimate**.
- **WhatsApp & Print**: Low-stock WhatsApp sharing opens `https://wa.me/?text=...` in a new tab; receipts and supplier return slips use `window.print()` with an A5/A4 print stylesheet (`Powered by Trexo`).
