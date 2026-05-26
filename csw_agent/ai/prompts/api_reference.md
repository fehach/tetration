## Cisco Secure Workload OpenAPI Reference

Authentication uses tetpyclient.RestClient. The `restclient` variable is already initialized.
All API paths should use the short form (e.g., '/sensors' not '/openapi/v1/sensors').

### CRITICAL: Response Format Rules
- api_call() returns (data, error). If error is not None, the call failed.
- DICT responses (use data.get('results', []) to extract items):
  - GET /sensors returns DICT: { "results": [...], "offset": "..." }. Use: `agents = data.get('results', [])`
  - POST /inventory/search returns DICT: { "results": [...], "offset": ... }
  - POST /flowsearch returns DICT: { "results": [...], "offset": ... }
  - POST /inventory/count returns DICT: { "count": N }
- PLAIN LIST responses (data IS the list directly):
  - GET /applications returns PLAIN LIST. Use: `workspaces = data`
  - GET /app_scopes returns PLAIN LIST.
  - GET /filters/inventories returns PLAIN LIST.
  - GET /users returns PLAIN LIST.
  - GET /roles returns PLAIN LIST.
  - GET /alerts returns PLAIN LIST.
- SAFE pattern that works for BOTH formats:
  `items = data.get('results', data) if isinstance(data, dict) else data`
- To paginate /sensors: use limit=500, get offset from response, pass it as next offset until no more offset.

### Software Agents (Sensors)
- GET /sensors — Returns DICT: { "results": [...], "offset": "..." }. Params: limit (int), offset (str).
  To extract agents: `agents = data.get('results', [])`
  To paginate: use limit=500, check for 'offset' key in response, pass it as next offset param until offset is absent.
  Agent attributes: uuid, host_name, platform, current_sw_version, agent_type_str, interfaces (array),
  last_config_fetch_at (epoch), vrf_id, enforcement_enabled, config_intent_id, config_profile_id,
  config_profile_name, os_display_label, client_ip, enable_pid_lookup, enable_forensics,
  data_plane_disabled, created_at, deleted_at, uninstalled_at, bios_uuid, arch, vrf,
  kernel_version, enable_conversation_flows, enable_cache_sidechannel, max_rss_limit
- GET /sensors/{uuid} — Get specific agent by UUID. Returns single agent object.
- DELETE /sensors/{uuid} — Decommission an agent (DANGEROUS).

### Workspaces (Applications)
- GET /applications — Returns PLAIN LIST of workspace objects. Params: app_scope_id (str), exact_name (str).
  Workspace attributes: id, name, description, app_scope_id, author, primary, alternate_query_mode,
  created_at, latest_adm_version, analysis_enabled, analyzed_version, enforcement_enabled, enforced_version
- GET /applications/{id} — Get specific workspace. Returns single workspace object.
- GET /applications/{id}/details — Full export (clusters, policies, inventory_filters). Params: version (str, e.g. 'v10' or 'p10').
  Returns DICT with keys: absolute_policies, default_policies, catch_all_action, clusters, inventory_filters, etc.
- GET /applications/{id}/policies — Get policies. Params: version (str).
  Returns DICT: { absolute_policies: [...], default_policies: [...], catch_all_action: "ALLOW"|"DENY" }
  IMPORTANT: To get ALL policies, combine BOTH lists: `all_policies = data.get('absolute_policies', []) + data.get('default_policies', [])`
  Each policy object keys: id, application_id, version, rank ("DEFAULT" or "ABSOLUTE"), action ("ALLOW"/"DENY"),
  priority (int), consumer_filter_id, provider_filter_id, consumer_filter (dict with name, id, filter_type),
  provider_filter (dict with name, id, filter_type), l4_params (list of L4 rule objects), created_at, updated_at.
  l4_params items: { proto: int (6=TCP, 17=UDP, 1=ICMP, -1=ANY), port: [start, end], id, ... }
  To extract protocol/port from a policy: iterate p.get('l4_params', []), each has 'proto' and 'port' (2-element list [start, end]).
  If l4_params is empty or proto is -1, the policy applies to ALL protocols/ports.
- GET /applications/{id}/default_policies — Get default policies. Params: version, limit, offset.
- GET /applications/{id}/versions — List versions. Params: limit, created_before.
- POST /applications — Create workspace.
- POST /applications/{id}/import — Import new version.
- PUT /applications/{id} — Update workspace (name, description, primary).
- DELETE /applications/{id} — Delete workspace (enforcement must be disabled first).
- POST /applications/{id}/enable_enforce — Enable enforcement.
- POST /applications/{id}/disable_enforce — Disable enforcement.
- POST /applications/{id}/analyze — Analyze latest policies.
- POST /applications/{id}/disable_analysis — Disable analysis.

### Policy Statistics
- POST /policies/stats/analyzed — Get policy stats for a SINGLE policy.
  Body: { application_id, t0 (ISO 8601), t1 (ISO 8601), policy_identifier: {
    consumer_consistent_uuid, provider_consistent_uuid, rank, priority, action, protocol, start_port } }
  Response DICT: { conversation_count, packet_count, byte_count, first_seen_at, last_seen_at, agg_start_version }
  NOTE: This is per-policy. To get stats for all policies in a workspace, you must iterate over each policy.

### Scopes
- GET /app_scopes — Returns PLAIN LIST of scope objects. Params: vrf_id, root_app_scope_id, exact_name, exact_short_name.
  Scope attributes: id, short_name, name (fully qualified), description, short_query, query, vrf_id,
  parent_app_scope_id, child_app_scope_ids, policy_priority, dirty
- GET /app_scopes/{id} — Get specific scope.
- POST /app_scopes — Create scope. Body: { short_name, description, short_query, parent_app_scope_id }
- PUT /app_scopes/{id} — Update scope.
- DELETE /app_scopes/{id} — Delete scope.

### Inventory Filters
- GET /filters/inventories — Returns PLAIN LIST of filter objects. Params: vrf_id, root_app_scope_id, name, exact_name.
  Filter attributes: id, name, app_scope_id, short_query, primary, public, query
- GET /filters/inventories/{id} — Get specific filter. Returns single object.
- POST /filters/inventories — Create filter. Body: { name, query, app_scope_id, primary, public }
- PUT /filters/inventories/{id} — Update filter.
- DELETE /filters/inventories/{id} — Delete filter.

### Flow Search
- GET /flowsearch/dimensions — Returns DICT: { dimensions: [...] }
- GET /flowsearch/metrics — Returns DICT: { metrics: [...] }
- POST /flowsearch — Search flows. Returns DICT: { results: [...], offset: ... }
  Body: { t0 (ISO 8601 or epoch), t1 (ISO 8601 or epoch), filter: { type, field, value },
  scopeName (str, optional), dimensions (list, optional), metrics (list, optional),
  limit (int, optional), offset (from prev response, optional), descending (bool, optional) }
  Filter types: eq, ne, lt, lte, gt, gte, in (uses "values" key), regex, subnet, contains, range
  Logical filters: { type: "and"/"or", filters: [...] }, { type: "not", filter: {...} }
  Flow dimensions include: src_address, dst_address, src_port, dst_port, proto, src_hostname, dst_hostname,
  fwd_policy_id, rev_policy_id, vrf_name, etc.
  Flow metrics include: fwd_pkts, rev_pkts, fwd_bytes, rev_bytes, etc.
- POST /flowsearch/topn — TopN query. Body: { t0, t1, filter, scopeName, dimension, metric, limit, threshold }
- POST /flowsearch/count — Flow count. Returns DICT: { count: N }

### Inventory
- GET /inventory/search/dimensions — List inventory dimensions.
- POST /inventory/search — Search inventory. Returns DICT: { results: [...], offset: ... }
  Body: { filter, scopeName, dimensions, limit, offset }
- POST /inventory/count — Count inventory items. Returns DICT: { count: N }
  Body: { filter, scopeName }
- GET /inventory/{ip}-{vrf_id}/stats — Inventory stats. Params: t0, t1, td (epoch times, td=granularity like "day","hour","minute").
- POST /inventory/cves/{rootScopeID} — Get CVEs. Body: { ips: [...] }
- GET /malicious_ips — Get malicious IPs. Params: offset, limit.

### Workload
  Two identifier formats are supported: by agent UUID or by IP-VRF.
  PREFERRED: GET /workload/{uuid}/... (use the sensor's 'uuid' field from GET /sensors)
  ALTERNATE: GET /workload/{ip}-{vrf_id}/... (use client_ip and current_sw_id/vrf_id)
- GET /workload/{uuid} — Workload details.
- GET /workload/{uuid}/stats — Workload stats. Params: t0, t1, td.
- GET /workload/{uuid}/packages — Installed packages. Returns 404 if package visibility is not enabled.
- GET /workload/{uuid}/vulnerabilities — Workload vulnerabilities. Returns PLAIN LIST. Returns 404 if not enabled.
  Vulnerability object fields: cve_id, cve_url, cvm_score (int), cvm_severity ("LOW"/"MEDIUM"/"HIGH"/"CRITICAL"),
  cvm_easily_exploitable, cvm_malware_exploitable, cvm_active_internet_breach, cvm_popular_target,
  cvm_predicted_exploitable, cvm_fix_available, v2_score, v2_severity, v3_score, v3_base_severity,
  package_infos (list). Use 'cvm_severity' for Cisco security risk severity, 'v3_base_severity' for CVSS v3.
- GET /workload/{uuid}/process_snapshot — Process snapshot. Returns 404 if not enabled.
  NOTE: /packages, /vulnerabilities, /process_snapshot return HTTP 404 when the feature is not enabled
  for that agent. Always handle 404 gracefully: print "Not available for this agent" instead of showing raw errors.
  NOTE: When searching agents by hostname, use case-insensitive partial match:
  `if search_term.lower() in agent.get('host_name', '').lower()`
  Agent host_name values are often UPPERCASE (e.g., 'DCCIWA01', 'ReingBPIDev').

### Enforcement
- GET /enforcement/agents/{aid}/network_policy_config — Agent network policy. Params: include_filter_names, inject_versions.
- GET /enforcement/agents/{aid}/concrete_policies/{cid}/stats — Concrete policy stats. Params: t0, t1, td.

### Agent Config Intents & Profiles
- GET /inventory_config/intents — Returns PLAIN LIST of config intents.
- GET /inventory_config/intents/{id} — Get specific intent.
- GET /inventory_config/profiles — Returns PLAIN LIST of config profiles.
- GET /inventory_config/profiles/{id} — Get specific profile.

### Users & Roles
- GET /users — Returns PLAIN LIST of user objects.
- GET /users/{id} — Get specific user.
- GET /roles — Returns PLAIN LIST of role objects.
- GET /roles/{id} — Get specific role.

### Alerts
- GET /alerts — Returns PLAIN LIST of alert objects.
- GET /alerts/{id} — Get specific alert.

### VRFs
- GET /vrfs — Returns DICT or LIST (check type). Extract with safe pattern: `vrfs = data if isinstance(data, list) else data.get('results', [])`
- GET /vrfs/{id} — Get specific VRF.

### Labels
- GET /assets/cmdb/download/{rootScopeID} — Download labels.
- POST /assets/cmdb/upload/{rootScopeID} — Upload labels.

### Service Health
- GET /service_status — Get service health status.

### Change Logs
- GET /change_logs — List change logs. Returns DICT: { items: [...], total_count: N }
  Params: limit (int), offset (int, 0-based pagination).
  Item keys: id, scope, action, details, created_at (epoch), updated_at, modified (dict), original (dict), version, association_chain (list).
  Scope values include: data_set, user_session, enforcement_profile, analysis_profile, h4_user,
  inventory_config_intent, inventory_config_profile, inventory_filter.
  NOTE: This is GET, NOT POST. Use params for pagination: offset=0, limit=100, then offset=100, etc.

### Important Notes for Code Generation
- GET requests use: restclient.get('/path', params={...})
- POST requests use: restclient.post('/path', json_body=json.dumps(body))
- PUT requests use: restclient.put('/path', json_body=json.dumps(body))
- DELETE requests use: restclient.delete('/path')
- All responses have .status_code and .json() or .content
- Timestamps are Unix epoch (integers) or ISO 8601 strings (e.g., "2026-01-01T00:00:00Z")
- GET /applications, /app_scopes, /filters/inventories, /users, /roles, /alerts return PLAIN LISTS.
- GET /sensors, POST /flowsearch, POST /inventory/search return DICTS with 'results' key.
- For sensors: use `agents = data.get('results', [])`. Paginate with limit=500 and offset from response.
- There are ~1764 agents and ~1764 workspaces in this deployment.
- When iterating over many items (1000+), show progress with print statements every 50-100 items.
- For flow search with escaped/rejected: use the fwd_policy_id or rev_policy_id fields, or filter by specific scope.
- IMPORTANT: Many API fields may have a None value even when the key exists. obj.get('field', default) returns None
  (not default) if the key exists with value None. Always use the `or` pattern:
  - For lists:   `(obj.get('interfaces') or [])`
  - For strings: `(obj.get('host_name') or '')`
  Example: `hn = (item.get('host_name') or '').lower()` — safe even if host_name is None.
