# CSW appliance-to-software migration

**Move Cisco Secure Workload off end-of-life M5/M6 hardware — to SaaS or to software on
your own virtualized infrastructure — with proof that nothing was lost in the move.**

## The opportunity

Cisco has announced end-of-life for the Secure Workload M5 and M6 hardware appliances.
The product continues as **SaaS** or as **CSW software** deployed on customer-prepared
virtualized infrastructure (VMware/ESXi). Every M5/M6 deployment therefore has a migration
project ahead of it, with a deadline set by the hardware support calendar — and a real risk:
years of accumulated scopes, policies and agent configuration that must survive the move.

## What's included

1. **Deployment baseline (automated)** — full snapshot of the current cluster: agent fleet
   (count, versions, platforms, enforcement state), scopes, workspaces, policy counts,
   catch-all actions, analysis/enforcement versions. Timestamped evidence export.
2. **Target architecture decision** — SaaS vs. on-prem virtual cluster: sizing against the
   real fleet, licensing implications, connectivity and data-residency considerations.
3. **Infrastructure preparation** (on-prem path) — hardware specification, VMware/ESXi
   design and build, storage/network prerequisites, CSW software cluster installation.
4. **Migration execution** — scope/policy migration, agent re-homing, cutover plan with
   rollback points.
5. **Post-migration assurance (automated)** — re-run the baseline against the new
   deployment and diff: agents that did not report back, policy count divergences,
   workspaces whose enforcement state changed. Signed-off assurance report.

## Deliverables

- Migration readiness report (current-state baseline + risk register)
- Target architecture & sizing document
- Cutover runbook
- **Post-migration assurance report** — the evidence the customer's auditors and
  management actually ask for

## Typical engagement

4–8 weeks depending on fleet size and on-prem vs. SaaS target. The automated baseline
runs in hours on day one.

## How the toolkit accelerates it

The toolkit already extracts every data point the baseline needs (paginated agent fleet,
workspaces with combined policy sets, enforcement state, scope hierarchy) with CSV
evidence export. The dedicated baseline-snapshot + assurance-diff module is the next item
on the product roadmap — built on the same deterministic engine as the PCI assessment.

## Customer prerequisites

- CSW API credentials (read-only is sufficient for assessment phases)
- Access to virtualization team for the on-prem path
- Change-window agreement for cutover
