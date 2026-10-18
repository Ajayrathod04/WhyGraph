"""Generates seed/*.json (SYNTHETIC data only: fictional companies and people).

Run:  python scripts/make_seed.py
The JSON files are committed so you can also edit them by hand.
"""
import json
import pathlib

OUT = pathlib.Path(__file__).resolve().parent.parent / "seed"

PLAYBOOKS = [
    {"id": "pb_why", "title": "why", "steps": "trace,stale_check", "uses": 0},
    {"id": "pb_who", "title": "who", "steps": "who_knows", "uses": 0},
    {"id": "pb_impact", "title": "impact", "steps": "impact,pagerank", "uses": 0},
    {"id": "pb_stale", "title": "stale", "steps": "stale_scan", "uses": 0},
    {"id": "pb_plan", "title": "plan", "steps": "impact,pagerank,shortest_path,plan", "uses": 0},
]


def lumen():
    return {
        "tenant": "lumen",
        "name": "Lumen Payments",
        "blurb": "Synthetic fintech: payments, billing and a ledger.",
        "synthetic": True,
        "sample_document": (
            "Title: ADR-031 Queue Capacity Study v2\n"
            "Kind: ADR\n"
            "Replaces: ADR-014 Queue Capacity Study\n"
            "Decision: Pause the billing migration until exactly-once delivery is validated\n"
            "Decided by: Maya Chen\n"
            "Affects: Billing Service, Event Bus\n"
            "Rationale: The first study was measured on retired hardware, so its numbers no longer hold."
        ),
        "examples": [
            "Why did we move billing off the old queue, and what breaks if we undo it?",
            "Who should I ask about the ledger?",
            "Which decisions are stale?",
            "Is the fraud vendor decision still valid?",
            "Draft a reversal plan for the billing queue migration",
        ],
        "nodes": {
            "Team": [
                {"id": "t_platform", "name": "Platform"},
                {"id": "t_billing", "name": "Billing"},
                {"id": "t_payments", "name": "Payments"},
                {"id": "t_security", "name": "Security"},
                {"id": "t_data", "name": "Data & Risk"},
                {"id": "t_mobile", "name": "Mobile"},
            ],
            "Person": [
                {"id": "p_maya", "name": "Maya Chen", "team": "Platform"},
                {"id": "p_rohan", "name": "Rohan Iyer", "team": "Billing"},
                {"id": "p_sofia", "name": "Sofia Alvarez", "team": "Payments"},
                {"id": "p_dev", "name": "Dev Patel", "team": "Security"},
                {"id": "p_liam", "name": "Liam O'Connor", "team": "Data & Risk"},
                {"id": "p_aisha", "name": "Aisha Khan", "team": "Platform"},
                {"id": "p_tomas", "name": "Tomas Weber", "team": "Mobile"},
                {"id": "p_priya", "name": "Priya Nair", "team": "Data & Risk"},
            ],
            "System": [
                {"id": "s_ledger", "name": "Ledger Service", "criticality": 5, "aliases": "ledger, general ledger"},
                {"id": "s_billing", "name": "Billing Service", "criticality": 4, "aliases": "billing, invoicing"},
                {"id": "s_queue", "name": "Legacy Queue", "criticality": 3, "aliases": "old queue, rabbitmq, legacy message queue"},
                {"id": "s_bus", "name": "Event Bus", "criticality": 4, "aliases": "kafka, new queue, event streaming"},
                {"id": "s_pay", "name": "Payments Gateway", "criticality": 5, "aliases": "gateway, payments api"},
                {"id": "s_notify", "name": "Notification Service", "criticality": 2, "aliases": "notifications, emails"},
                {"id": "s_fraud", "name": "Fraud Engine", "criticality": 4, "aliases": "fraud, risk engine"},
                {"id": "s_auth", "name": "Auth Service", "criticality": 5, "aliases": "login, sso, authentication"},
                {"id": "s_report", "name": "Reporting Warehouse", "criticality": 2, "aliases": "warehouse, analytics, bi"},
                {"id": "s_mobile", "name": "Mobile App API", "criticality": 3, "aliases": "mobile api, mobile backend"},
            ],
            "Project": [
                {"id": "pr_migrate", "name": "Queue Migration 2026"},
                {"id": "pr_fraud2", "name": "Fraud Rules v2"},
                {"id": "pr_sso", "name": "SSO Rollout"},
                {"id": "pr_recon", "name": "Ledger Reconciliation"},
                {"id": "pr_mobile3", "name": "Mobile v3"},
            ],
            "Document": [
                {"id": "doc_adr014", "title": "ADR-014 Queue Capacity Study", "kind": "ADR", "date": "2026-01-12", "status": "current",
                 "url": "https://lumen.example/docs/adr-014",
                 "excerpt": "Load tests show the legacy queue saturates at 4,000 msg/s; projected peak is 9,000 msg/s."},
                {"id": "doc_rfc021", "title": "RFC-021 Event Bus Proposal", "kind": "RFC", "date": "2026-02-03", "status": "current",
                 "url": "https://lumen.example/docs/rfc-021",
                 "excerpt": "Proposes a Kafka-compatible event bus with exactly-once delivery for money movement."},
                {"id": "doc_inc301", "title": "INC-301 Postmortem: Duplicate Charges", "kind": "Postmortem", "date": "2026-03-02", "status": "current",
                 "url": "https://lumen.example/docs/inc-301",
                 "excerpt": "Retries on the legacy queue produced duplicate charges for 212 customers."},
                {"id": "doc_adr022", "title": "ADR-022 Ledger Idempotency Keys", "kind": "ADR", "date": "2026-03-10", "status": "current",
                 "url": "https://lumen.example/docs/adr-022",
                 "excerpt": "Every ledger write must carry an idempotency key generated by the caller."},
                {"id": "doc_sec007", "title": "SEC-007 Auth Token Lifetime Review", "kind": "Review", "date": "2026-04-18", "status": "current",
                 "url": "https://lumen.example/docs/sec-007",
                 "excerpt": "Long-lived tokens were the root cause in two near-miss events; 15 minutes is the recommended limit."},
                {"id": "doc_vendor1", "title": "Vendor Review: Fraud Scoring API v1", "kind": "Review", "date": "2025-11-20", "status": "outdated",
                 "url": "https://lumen.example/docs/vendor-fraud-v1",
                 "excerpt": "Fraud Scoring API v1 meets latency targets at 120 ms p95 for card-not-present checks."},
                {"id": "doc_vendor2", "title": "Vendor Review: Fraud Scoring API v2", "kind": "Review", "date": "2026-06-01", "status": "current",
                 "url": "https://lumen.example/docs/vendor-fraud-v2",
                 "excerpt": "v1 is deprecated; v2 adds device signals and cuts false positives by 18 percent."},
                {"id": "doc_ops", "title": "Ops thread: Weekend queue alerts", "kind": "Chat summary", "date": "2026-02-20", "status": "current",
                 "url": "https://lumen.example/docs/ops-thread-0220",
                 "excerpt": "Three weekend pages in a row came from notification polling against the legacy queue."},
                {"id": "doc_policy", "title": "Data Retention Policy 2026", "kind": "Policy", "date": "2026-05-05", "status": "current",
                 "url": "https://lumen.example/docs/retention-2026",
                 "excerpt": "Raw payment events may be kept for at most 13 months."},
                {"id": "doc_okr", "title": "Q3 Platform OKRs", "kind": "Planning", "date": "2026-07-01", "status": "current",
                 "url": "https://lumen.example/docs/okr-q3",
                 "excerpt": "Reduce mobile balance-read latency and keep the reporting load nightly."},
            ],
            "Decision": [
                {"id": "d_queue", "title": "Move billing off the legacy queue onto the event bus", "date": "2026-02-10", "status": "active",
                 "rationale": "The legacy queue saturates under projected peak load and caused duplicate charges.",
                 "aliases": "move billing, billing queue, queue migration, off the old queue, billing migration"},
                {"id": "d_bus", "title": "Adopt an exactly-once event bus for money movement", "date": "2026-02-25", "status": "active",
                 "rationale": "Exactly-once delivery removes a whole class of duplicate-charge bugs.",
                 "aliases": "exactly once, adopt the event bus"},
                {"id": "d_idem", "title": "Require idempotency keys on all ledger writes", "date": "2026-03-12", "status": "active",
                 "rationale": "Idempotency keys make retries safe after the duplicate-charge incident.",
                 "aliases": "idempotency, idempotency keys"},
                {"id": "d_fraudvendor", "title": "Use Fraud Scoring API v1 for card-not-present checks", "date": "2025-11-25", "status": "active",
                 "rationale": "v1 met the 120 ms latency target in the vendor review.",
                 "aliases": "fraud vendor, fraud scoring, scoring api"},
                {"id": "d_tokens", "title": "Shorten auth token lifetime to 15 minutes", "date": "2026-04-20", "status": "active",
                 "rationale": "Long-lived tokens were the root cause in two near-miss events.",
                 "aliases": "token lifetime, auth tokens, shorter tokens"},
                {"id": "d_retention", "title": "Retain raw payment events for 13 months", "date": "2026-05-08", "status": "active",
                 "rationale": "Matches the 2026 retention policy while keeping audit history.",
                 "aliases": "retention, retain raw events, 13 months"},
                {"id": "d_mobilecache", "title": "Cache balance reads for 5 seconds in the Mobile API", "date": "2026-06-14", "status": "active",
                 "rationale": "Cuts ledger read load and meets the mobile latency objective.",
                 "aliases": "balance cache, cache balance, mobile cache"},
                {"id": "d_reports", "title": "Run the reporting warehouse as a nightly batch", "date": "2026-01-30", "status": "active",
                 "rationale": "Nightly loads avoid contention with peak payment traffic.",
                 "aliases": "nightly batch, reporting batch"},
                {"id": "d_pollold", "title": "Poll the legacy queue every 30 seconds for notifications", "date": "2025-08-14", "status": "superseded",
                 "rationale": "Simple polling was good enough at the time.",
                 "aliases": "notification polling, poll the queue"},
                {"id": "d_rabbit", "title": "Adopt the legacy message queue for all async jobs", "date": "2024-03-01", "status": "superseded",
                 "rationale": "It was the fastest option to ship in 2024.",
                 "aliases": "adopt the queue, original queue"},
            ],
            "Playbook": PLAYBOOKS,
        },
        "edges": [
            # membership and ownership
            ["p_maya", "MEMBER_OF", "t_platform"], ["p_aisha", "MEMBER_OF", "t_platform"],
            ["p_rohan", "MEMBER_OF", "t_billing"], ["p_sofia", "MEMBER_OF", "t_payments"],
            ["p_dev", "MEMBER_OF", "t_security"], ["p_liam", "MEMBER_OF", "t_data"],
            ["p_priya", "MEMBER_OF", "t_data"], ["p_tomas", "MEMBER_OF", "t_mobile"],
            ["t_platform", "OWNS", "s_bus"], ["t_platform", "OWNS", "s_queue"],
            ["t_billing", "OWNS", "s_billing"], ["t_billing", "OWNS", "s_notify"],
            ["t_payments", "OWNS", "s_pay"], ["t_payments", "OWNS", "s_ledger"],
            ["t_security", "OWNS", "s_auth"], ["t_data", "OWNS", "s_fraud"],
            ["t_data", "OWNS", "s_report"], ["t_mobile", "OWNS", "s_mobile"],
            # dependencies (A depends on B)
            ["s_billing", "DEPENDS_ON", "s_bus"], ["s_billing", "DEPENDS_ON", "s_ledger"],
            ["s_billing", "DEPENDS_ON", "s_auth"], ["s_notify", "DEPENDS_ON", "s_bus"],
            ["s_notify", "DEPENDS_ON", "s_queue"], ["s_report", "DEPENDS_ON", "s_bus"],
            ["s_report", "DEPENDS_ON", "s_ledger"], ["s_fraud", "DEPENDS_ON", "s_bus"],
            ["s_pay", "DEPENDS_ON", "s_ledger"], ["s_pay", "DEPENDS_ON", "s_auth"],
            ["s_pay", "DEPENDS_ON", "s_fraud"], ["s_mobile", "DEPENDS_ON", "s_pay"],
            ["s_mobile", "DEPENDS_ON", "s_auth"], ["s_mobile", "DEPENDS_ON", "s_notify"],
            # projects
            ["pr_migrate", "USES", "s_queue"], ["pr_migrate", "USES", "s_bus"], ["pr_migrate", "USES", "s_billing"],
            ["pr_fraud2", "USES", "s_fraud"], ["pr_fraud2", "USES", "s_bus"],
            ["pr_sso", "USES", "s_auth"], ["pr_sso", "USES", "s_mobile"],
            ["pr_recon", "USES", "s_ledger"], ["pr_recon", "USES", "s_report"],
            ["pr_mobile3", "USES", "s_mobile"], ["pr_mobile3", "USES", "s_pay"],
            ["p_maya", "WORKED_ON", "pr_migrate"], ["p_rohan", "WORKED_ON", "pr_migrate"], ["p_aisha", "WORKED_ON", "pr_migrate"],
            ["p_priya", "WORKED_ON", "pr_fraud2"], ["p_liam", "WORKED_ON", "pr_fraud2"],
            ["p_dev", "WORKED_ON", "pr_sso"], ["p_tomas", "WORKED_ON", "pr_sso"],
            ["p_sofia", "WORKED_ON", "pr_recon"], ["p_liam", "WORKED_ON", "pr_recon"],
            ["p_tomas", "WORKED_ON", "pr_mobile3"], ["p_sofia", "WORKED_ON", "pr_mobile3"],
            # who knows what
            ["p_maya", "KNOWS", "s_bus"], ["p_maya", "KNOWS", "s_queue"], ["p_maya", "KNOWS", "s_ledger"],
            ["p_rohan", "KNOWS", "s_billing"], ["p_rohan", "KNOWS", "s_queue"], ["p_rohan", "KNOWS", "s_notify"],
            ["p_sofia", "KNOWS", "s_pay"], ["p_sofia", "KNOWS", "s_ledger"], ["p_sofia", "KNOWS", "s_bus"],
            ["p_dev", "KNOWS", "s_auth"], ["p_dev", "KNOWS", "s_report"],
            ["p_liam", "KNOWS", "s_report"], ["p_liam", "KNOWS", "s_bus"],
            ["p_aisha", "KNOWS", "s_queue"], ["p_aisha", "KNOWS", "s_bus"], ["p_aisha", "KNOWS", "s_ledger"], ["p_aisha", "KNOWS", "s_auth"],
            ["p_tomas", "KNOWS", "s_mobile"], ["p_tomas", "KNOWS", "s_pay"], ["p_tomas", "KNOWS", "s_auth"],
            ["p_priya", "KNOWS", "s_fraud"], ["p_priya", "KNOWS", "s_pay"],
            # decisions: who decided
            ["p_maya", "DECIDED", "d_queue"], ["p_rohan", "DECIDED", "d_queue"],
            ["p_maya", "DECIDED", "d_bus"], ["p_sofia", "DECIDED", "d_bus"],
            ["p_sofia", "DECIDED", "d_idem"], ["p_aisha", "DECIDED", "d_idem"],
            ["p_priya", "DECIDED", "d_fraudvendor"], ["p_dev", "DECIDED", "d_tokens"],
            ["p_liam", "DECIDED", "d_retention"], ["p_dev", "DECIDED", "d_retention"],
            ["p_tomas", "DECIDED", "d_mobilecache"], ["p_liam", "DECIDED", "d_reports"],
            ["p_rohan", "DECIDED", "d_pollold"], ["p_maya", "DECIDED", "d_rabbit"],
            # decisions: evidence
            ["d_queue", "BASED_ON", "doc_adr014"], ["d_queue", "BASED_ON", "doc_inc301"], ["d_queue", "BASED_ON", "doc_rfc021"],
            ["d_bus", "BASED_ON", "doc_rfc021"],
            ["d_idem", "BASED_ON", "doc_adr022"], ["d_idem", "BASED_ON", "doc_inc301"],
            ["d_fraudvendor", "BASED_ON", "doc_vendor1"],
            ["d_tokens", "BASED_ON", "doc_sec007"],
            ["d_retention", "BASED_ON", "doc_policy"],
            ["d_mobilecache", "BASED_ON", "doc_okr"],
            ["d_reports", "BASED_ON", "doc_okr"],
            ["d_pollold", "BASED_ON", "doc_ops"],
            # decisions: what they touch
            ["d_queue", "AFFECTS", "s_billing"], ["d_queue", "AFFECTS", "s_queue"], ["d_queue", "AFFECTS", "s_bus"],
            ["d_bus", "AFFECTS", "s_bus"], ["d_bus", "AFFECTS", "s_ledger"], ["d_bus", "AFFECTS", "s_pay"],
            ["d_idem", "AFFECTS", "s_ledger"], ["d_idem", "AFFECTS", "s_billing"], ["d_idem", "AFFECTS", "s_pay"],
            ["d_fraudvendor", "AFFECTS", "s_fraud"], ["d_fraudvendor", "AFFECTS", "s_pay"],
            ["d_tokens", "AFFECTS", "s_auth"], ["d_tokens", "AFFECTS", "s_mobile"],
            ["d_retention", "AFFECTS", "s_report"], ["d_retention", "AFFECTS", "s_bus"],
            ["d_mobilecache", "AFFECTS", "s_mobile"], ["d_mobilecache", "AFFECTS", "s_ledger"],
            ["d_reports", "AFFECTS", "s_report"],
            ["d_pollold", "AFFECTS", "s_notify"], ["d_pollold", "AFFECTS", "s_queue"],
            ["d_rabbit", "AFFECTS", "s_queue"],
            # lineage and document replacement
            ["d_queue", "SUPERSEDES", "d_pollold"], ["d_pollold", "SUPERSEDES", "d_rabbit"],
            ["doc_vendor1", "REPLACED_BY", "doc_vendor2"],
        ],
    }


def orbit():
    return {
        "tenant": "orbit",
        "name": "Orbit Logistics",
        "blurb": "Synthetic logistics company: routing, tracking and carriers.",
        "synthetic": True,
        "sample_document": (
            "Title: Route Optimisation Cost Study v2\n"
            "Kind: Study\n"
            "Replaces: Route Optimisation Cost Study\n"
            "Decision: Run the route optimiser twice each night\n"
            "Decided by: Ingrid Larsen\n"
            "Affects: Route Planner\n"
            "Rationale: The new study shows a second nightly run cuts a further 2 percent of fuel cost."
        ),
        "examples": [
            "Why did we switch to nightly route optimisation?",
            "Who should I ask about the tracking API?",
            "Which decisions are stale?",
            "What breaks if the telemetry feed goes down?",
        ],
        "nodes": {
            "Team": [
                {"id": "t_routing", "name": "Routing"},
                {"id": "t_ops", "name": "Operations"},
                {"id": "t_fleet", "name": "Fleet Tech"},
            ],
            "Person": [
                {"id": "p_ingrid", "name": "Ingrid Larsen", "team": "Routing"},
                {"id": "p_kofi", "name": "Kofi Mensah", "team": "Operations"},
                {"id": "p_yuki", "name": "Yuki Tanaka", "team": "Fleet Tech"},
                {"id": "p_carlos", "name": "Carlos Ruiz", "team": "Operations"},
                {"id": "p_nora", "name": "Nora Haddad", "team": "Routing"},
            ],
            "System": [
                {"id": "s_route", "name": "Route Planner", "criticality": 5, "aliases": "routing, route optimisation, route optimization"},
                {"id": "s_track", "name": "Tracking API", "criticality": 4, "aliases": "tracking, parcel tracking"},
                {"id": "s_telem", "name": "Fleet Telemetry", "criticality": 4, "aliases": "telemetry, telemetry feed, vehicle data"},
                {"id": "s_dispatch", "name": "Dispatch Console", "criticality": 3, "aliases": "dispatch"},
                {"id": "s_scan", "name": "Warehouse Scanner Sync", "criticality": 3, "aliases": "scanners, scanner sync"},
                {"id": "s_carrier", "name": "Carrier Billing", "criticality": 3, "aliases": "carrier rates, billing"},
            ],
            "Project": [
                {"id": "pr_night", "name": "Nightly Optimiser"},
                {"id": "pr_scan2", "name": "Scanner Refresh"},
                {"id": "pr_rates", "name": "Carrier Rate Refresh"},
            ],
            "Document": [
                {"id": "doc_study", "title": "Route Optimisation Cost Study", "kind": "Study", "date": "2026-02-02", "status": "current",
                 "url": "https://orbit.example/docs/route-study",
                 "excerpt": "Re-optimising every night cuts fuel cost by 6 percent versus continuous re-planning."},
                {"id": "doc_telem", "title": "Telemetry Batching Test Results", "kind": "Report", "date": "2026-03-15", "status": "current",
                 "url": "https://orbit.example/docs/telemetry-batching",
                 "excerpt": "Batching positions every 30 seconds keeps cellular cost low with no visible tracking delay."},
                {"id": "doc_rates25", "title": "Carrier Rate Table 2025", "kind": "Rates", "date": "2025-01-10", "status": "outdated",
                 "url": "https://orbit.example/docs/rates-2025",
                 "excerpt": "Standard parcel rate: 4.10 per kg for zone B."},
                {"id": "doc_rates26", "title": "Carrier Rate Table 2026", "kind": "Rates", "date": "2026-01-10", "status": "current",
                 "url": "https://orbit.example/docs/rates-2026",
                 "excerpt": "Standard parcel rate: 4.65 per kg for zone B."},
                {"id": "doc_scan", "title": "Scanner Sync Incident Review", "kind": "Postmortem", "date": "2026-04-04", "status": "current",
                 "url": "https://orbit.example/docs/scanner-incident",
                 "excerpt": "Lost scans were caused by unbounded offline queues on handheld devices."},
                {"id": "doc_dispatch", "title": "Dispatcher Interview Notes", "kind": "Research", "date": "2026-05-12", "status": "current",
                 "url": "https://orbit.example/docs/dispatcher-notes",
                 "excerpt": "Dispatchers want a single map with live exceptions."},
            ],
            "Decision": [
                {"id": "d_nightly", "title": "Switch to nightly route optimisation", "date": "2026-02-12", "status": "active",
                 "rationale": "Saves about 6 percent fuel cost compared with continuous re-planning.",
                 "aliases": "nightly route optimisation, nightly optimisation, nightly optimization"},
                {"id": "d_batch", "title": "Batch vehicle telemetry every 30 seconds", "date": "2026-03-20", "status": "active",
                 "rationale": "Keeps cellular cost low with no visible delay for customers.",
                 "aliases": "telemetry batching, batch telemetry"},
                {"id": "d_rates", "title": "Quote shipments using the 2025 carrier rate table", "date": "2025-01-20", "status": "active",
                 "rationale": "It was the signed rate table at the time.",
                 "aliases": "carrier rates, rate table, quote shipments"},
                {"id": "d_offline", "title": "Cap offline scan queues on handheld devices", "date": "2026-04-10", "status": "active",
                 "rationale": "Unbounded queues caused lost scans in the April incident.",
                 "aliases": "offline queue, scan queue, handheld queue"},
                {"id": "d_map", "title": "Build a single live exceptions map for dispatchers", "date": "2026-05-20", "status": "active",
                 "rationale": "Dispatchers asked for one map instead of three screens.",
                 "aliases": "live map, exceptions map, dispatcher map"},
                {"id": "d_replan", "title": "Re-plan routes continuously during the day", "date": "2024-06-01", "status": "superseded",
                 "rationale": "It reacted quickly to traffic but cost more fuel.",
                 "aliases": "continuous replanning, continuous re-planning"},
            ],
            "Playbook": PLAYBOOKS,
        },
        "edges": [
            ["p_ingrid", "MEMBER_OF", "t_routing"], ["p_nora", "MEMBER_OF", "t_routing"],
            ["p_kofi", "MEMBER_OF", "t_ops"], ["p_carlos", "MEMBER_OF", "t_ops"],
            ["p_yuki", "MEMBER_OF", "t_fleet"],
            ["t_routing", "OWNS", "s_route"], ["t_ops", "OWNS", "s_dispatch"], ["t_ops", "OWNS", "s_carrier"],
            ["t_ops", "OWNS", "s_scan"], ["t_fleet", "OWNS", "s_telem"], ["t_fleet", "OWNS", "s_track"],
            ["s_route", "DEPENDS_ON", "s_telem"], ["s_track", "DEPENDS_ON", "s_telem"],
            ["s_dispatch", "DEPENDS_ON", "s_route"], ["s_dispatch", "DEPENDS_ON", "s_track"],
            ["s_carrier", "DEPENDS_ON", "s_track"], ["s_scan", "DEPENDS_ON", "s_track"],
            ["pr_night", "USES", "s_route"], ["pr_night", "USES", "s_telem"],
            ["pr_scan2", "USES", "s_scan"], ["pr_scan2", "USES", "s_track"],
            ["pr_rates", "USES", "s_carrier"],
            ["p_ingrid", "WORKED_ON", "pr_night"], ["p_nora", "WORKED_ON", "pr_night"], ["p_yuki", "WORKED_ON", "pr_night"],
            ["p_carlos", "WORKED_ON", "pr_scan2"], ["p_yuki", "WORKED_ON", "pr_scan2"],
            ["p_kofi", "WORKED_ON", "pr_rates"],
            ["p_ingrid", "KNOWS", "s_route"], ["p_nora", "KNOWS", "s_route"], ["p_yuki", "KNOWS", "s_telem"],
            ["p_yuki", "KNOWS", "s_track"], ["p_kofi", "KNOWS", "s_carrier"], ["p_kofi", "KNOWS", "s_dispatch"],
            ["p_carlos", "KNOWS", "s_scan"], ["p_carlos", "KNOWS", "s_dispatch"],
            ["p_ingrid", "DECIDED", "d_nightly"], ["p_nora", "DECIDED", "d_nightly"],
            ["p_yuki", "DECIDED", "d_batch"], ["p_kofi", "DECIDED", "d_rates"],
            ["p_carlos", "DECIDED", "d_offline"], ["p_kofi", "DECIDED", "d_map"],
            ["p_ingrid", "DECIDED", "d_replan"],
            ["d_nightly", "BASED_ON", "doc_study"], ["d_batch", "BASED_ON", "doc_telem"],
            ["d_rates", "BASED_ON", "doc_rates25"], ["d_offline", "BASED_ON", "doc_scan"],
            ["d_map", "BASED_ON", "doc_dispatch"], ["d_replan", "BASED_ON", "doc_study"],
            ["d_nightly", "AFFECTS", "s_route"], ["d_batch", "AFFECTS", "s_telem"], ["d_batch", "AFFECTS", "s_track"],
            ["d_rates", "AFFECTS", "s_carrier"], ["d_offline", "AFFECTS", "s_scan"],
            ["d_map", "AFFECTS", "s_dispatch"], ["d_replan", "AFFECTS", "s_route"],
            ["d_nightly", "SUPERSEDES", "d_replan"],
            ["doc_rates25", "REPLACED_BY", "doc_rates26"],
        ],
    }


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for fn, data in (("lumen_payments.json", lumen()), ("orbit_logistics.json", orbit())):
        (OUT / fn).write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        print("wrote", fn)
