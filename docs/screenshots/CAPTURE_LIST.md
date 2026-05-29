# Screenshots to Capture

One image per user-flow step. Save each as a PNG in this folder with the
filename shown below, then reference it from the final report if desired.

Easiest way to get realistic data: start the app with the demo seed —

```
DEMO_MODE=1 python run.py        # macOS / Linux
$env:DEMO_MODE = "1"; python run.py   # Windows PowerShell
```

— then capture each screen. The seeded campaigns are id `1` (single) and
id `2` (A/B).

| # | Filename | What to capture | URL |
|---|----------|-----------------|-----|
| 1 | `01-campaign-list.png` | The campaigns table with the two seeded campaigns | `/admin/campaigns` |
| 2 | `02-campaign-new.png` | The new-campaign authoring form | `/admin/campaigns/new` |
| 3 | `03-message-preview.png` | A simulated message in preview mode (no logging) | `/message/1/preview` |
| 4 | `04-fake-login.png` | The fake login landing page with the educational banner | `/landing/1?subject=subject-01&variant=A` |
| 5 | `05-debrief.png` | The educational debrief page | `/landing/debrief` |
| 6 | `06-dashboard.png` | The dashboard with funnel + A/B charts populated | `/admin/dashboard/2` |

Optional extras: the message variant B (`/message/2/preview?variant=B`) and a
zero-data dashboard for a freshly created campaign.
