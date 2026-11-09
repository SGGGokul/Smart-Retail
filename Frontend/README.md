# RetailIQ — Frontend Web Application

The RetailIQ frontend is a Next.js 16 web dashboard for store managers, operators, and analysts. It connects to the FastAPI backend to display real-time store traffic, shelf occupancy, queue metrics, image/video computer vision results, and an operations AI copilot.

---

## Tech Stack

- **Framework:** [Next.js 16.4.2](https://nextjs.org/) (App Router, Webpack/Turbopack enabled)
- **UI & State:** React 19.3.0, React DOM 19.3.0
- **Styling:** [Tailwind CSS v4](https://tailwindcss.com/)
- **Charts:** [Recharts 3.10.1](https://recharts.org/)
- **Icons:** [Lucide React](https://lucide.dev/)
- **Testing:** Playwright 1.64.1 (E2E), Node.js native test runner

---

## Directory Overview

```text
Frontend/
├── app/                           # App Router routes and page layouts
│   ├── page.tsx                   # Store Overview Dashboard
│   ├── video-analytics/           # Dedicated Image & Video Upload Analytics
│   ├── shelf-monitoring/          # Shelf Bays, Stock Percentages, Restock Alert
│   ├── customer-analytics/        # Visitor Footfall, Dwell Times, Queue Lengths
│   ├── ai-assistant/              # Copilot Chat with Citations and Chips
│   ├── alerts/                    # Store Incidents & Notifications
│   ├── reports/                   # Daily/Weekly Analytics Reports
│   └── settings/                  # Thresholds, Cameras, and Profile
├── components/                    # Reusable UI widgets, layout, and charts
├── lib/                           # API client (lib/api/client.ts) & endpoints
├── public/                        # Static SVG assets
├── types/                         # TypeScript interfaces conforming to API_CONTRACT.md
├── e2e/                           # Playwright end-to-end test specs
├── package.json                   # Dependencies and scripts
└── tsconfig.json                  # TypeScript compiler settings
```

---

## Getting Started

### 1. Install Dependencies
From within the `Frontend/` folder, run:

```bash
pnpm install --frozen-lockfile
```

### 2. Environment Configuration
By default, the frontend connects to the FastAPI backend at `http://localhost:8000`. To override this, create `.env.local` inside `Frontend/`:

```env
NEXT_PUBLIC_API_BASE_URL="http://localhost:8000"
```

### 3. Start Development Server
```bash
pnpm run dev --port 3000
```
Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Available Scripts

| Command | Description |
| :--- | :--- |
| `pnpm run dev` | Starts the Next.js development server on port 3000. |
| `pnpm run build` | Compiles an optimized production build (`next build --webpack`). |
| `pnpm run start` | Runs the compiled production server. |
| `pnpm exec tsc --noEmit` | Validates TypeScript types across all components. |
| `pnpm run test` | Executes native Node.js unit tests in `test/`. |
| `pnpm run test:e2e` | Runs Playwright end-to-end tests in `e2e/`. |

---

## Key Intelligence Views

### 1. Customer Analytics & Footfall Intelligence (`/customer-analytics`)
- **4-Level Pipeline Visualizer:** Visualizes detections -> camera tracks -> daily visitors -> visit sessions.
- **Store-Day Unique Visitors:** Distinguishes repeated detections from unique individuals based on store-local midnight reset.
- **Returning Visitor Counter:** Tracks customers who exit and re-enter the same day with incremented visit numbers.
- **Multi-Camera Ingress:** Displays real-time footfall breakdown by camera stream.

### 2. Shelf Monitoring & Retail Events Timeline (`/shelf-monitoring`)
- **8 KPI Health Cards:** Overall fill rate, critical restock count (<40%), low stock warning (40-70%), optimal fill (>70%), empty position count, customer interactions, pickup candidates/confirmed, and return candidates/confirmed.
- **Bays vs. Timeline Switcher:** Toggle seamlessly between 3-tier visual shelf bay schematics and the unified chronological retail events timeline.
- **Temporal Event Inspector:** Filter events by type (pickups, returns, interactions) and confirmation status (`confirmed`, `candidate`, `uncertain`), displaying exact timestamps, visitor identifiers (`DVIS-...`), confidence percentages, and vision evidence.

---

## Monorepo Reference

For backend architecture, computer vision models, database setup, and Docker Compose orchestration, refer to the [Root README.md](../README.md).
