# Workload Atlas — public demo

`index.html` is a **self-contained, static** demo of the PCI-DSS compliance dashboard,
built with **sample data only**. It runs entirely in the browser — no backend, no CSW
tenant, no credentials — so it is safe to host publicly for partners and recruiters.

Try it: pick a scope (`PCI-CDE`, `PAYMENTS`, `CLOUD:CORE`) and click **Run assessment**;
each scope shows a different posture (partial / compliant / non-compliant). The
**Generate executive summary** button simulates the streamed AI narrative.

## Deploy (Vercel)

The repo's `vercel.json` serves this folder as a static site (`outputDirectory: "demo"`).
No build step. See the repository README / deploy notes for the connect steps.

> Sample data — not a real assessment. Independent project, not affiliated with Cisco.
