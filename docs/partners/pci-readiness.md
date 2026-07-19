# PCI-DSS readiness assessment

**Audit-ready evidence of segmentation posture for the Cardholder Data Environment,
generated from live Cisco Secure Workload data — in hours, not weeks.**

## The opportunity

PCI-DSS v4.0.1 makes network segmentation the practical way to control assessment scope,
and CSW is precisely the tool that implements it. But turning CSW state into evidence an
auditor accepts is manual, slow work: exporting policies, cross-referencing agents,
chasing CVE lists. Customers preparing for their annual assessment need that picture
early enough to fix gaps.

## What's included

1. **CDE scope assessment (automated)** — the customer picks the scope that represents
   their CDE; the toolkit scores it against the PCI-DSS requirements CSW evidence can
   verify: Req 1 (network security controls), Req 6/11.3 (vulnerability management),
   Req 7 (need-to-know), Req 10 (monitoring) and Req 11.4.4 (segmentation verification).
2. **100-point deterministic score** — weighted, reproducible; re-run it after remediation
   and the improvement is measurable.
3. **Evidence package** — combined CSV: workspace segmentation posture, critical CVEs on
   CDE workloads, workloads without agent coverage.
4. **AI executive summary** — posture narrative plus one prioritized recommendation per
   requirement, generated from (and grounded in) the deterministic results.
5. **Remediation workshop** — walk the customer's team through the gaps and the fixes.

## Deliverables

- Interactive dashboard session + exported evidence CSV
- Executive summary and prioritized remediation plan
- Re-assessment after remediation (same score model — progress is provable)

## Typical engagement

3–5 days including the remediation workshop. The assessment itself runs in minutes.

## Important disclaimer

This is a compliance **readiness** view, not an official assessment. Formal PCI-DSS
validation requires a Qualified Security Assessor (QSA). The service prepares the
customer to face that assessment with evidence in hand.

## Customer prerequisites

- CSW API credentials (read-only)
- Identification of the scope(s) that represent the CDE (the toolkit auto-suggests
  scopes named PCI/CDE)
