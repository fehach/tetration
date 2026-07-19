# SNA ↔ XDR integration & response playbooks

**Turn Secure Network Analytics detections into documented, repeatable response through
Cisco XDR — with playbooks the customer's SOC actually uses.**

## The opportunity

Secure Network Analytics (SNA/Stealthwatch) generates high-fidelity network detections,
and Cisco XDR is where Cisco customers consolidate response. Many deployments have both
but connect them shallowly: alerts flow, nobody has defined what happens next. The gap
between "detection fired" and "documented response executed" is a services engagement.

## What's included

1. **Integration assessment** — current SNA deployment health (flow sources, host group
   coverage, security event tuning) and the state of the SNA → XDR connection.
2. **Integration implementation** — SNA as telemetry/incident source in XDR, incident
   enrichment, priority mapping aligned to the customer's asset criticality.
3. **Response playbook design** — for the customer's top detection scenarios (e.g. data
   exfiltration, lateral movement, C2 beaconing): trigger, triage steps, containment
   actions, owners, escalation paths.
4. **Playbook automation in XDR** — where the customer's licensing and processes allow,
   codify the response steps as XDR automation workflows.
5. **SOC handoff** — tabletop walkthrough of each playbook with the operations team.

## Deliverables

- Integration architecture document + implemented SNA→XDR connection
- Playbook library (documented, versioned, owned)
- Automation workflows for the agreed scenarios
- Tabletop exercise report

## Typical engagement

3–6 weeks depending on the number of playbook scenarios.

## Toolkit roadmap

The SegmentIQ platform pattern (natural-language agent + deterministic checks + evidence
dashboard) extends to SNA via its REST API: planned modules include integration
validation checks (are events reaching XDR? which host groups are covered?), detection
hygiene queries, and AI-assisted playbook documentation generated from the customer's
actual SNA configuration. Delivery of this service does not depend on the tooling —
the tooling compounds its margin over time.

## Customer prerequisites

- SNA Manager API access
- Cisco XDR tenant with admin access for integration configuration
- SOC availability for playbook workshops and tabletop
