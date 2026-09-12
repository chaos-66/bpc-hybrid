# Provenance and ambiguity note — Sun et al. (2024) Figure 10 reconstruction

**Artifact:** `formal_experiment/data/development/sim_case_c1/sun_figure10_reconstruction.bpmn`
**Companion note:** this file.
**Status:** project reconstruction of a published figure. **Development artifact, not Gold, not an author file.**

---

## 1. What this file is and is not

* This BPMN 2.0 file is a **reconstruction produced by this project** from the published figure
  (Sun et al., 2024, "Design-time business process compliance assessment based on multi-granularity
  semantic information", Section 5.4, Figure 10, manuscript page 24) plus the paper's narrative text.
* It is **not** the authors' original BPMN file, **not** an exact copy of the authors' model, and
  **not** the Sun benchmark/archive model. It must never be labelled "Sun original", "exact Sun",
  or "the authors' model". It is our reading of a printed diagram.
* The local document used is a **pre-publication manuscript** (every page carries the
  "Springer Nature 2021 LaTeX template" running head). The **version of record could not be
  obtained** in this session (no network access is permitted for this task), so page numbering,
  figure content and the rule/violation mapping below refer to the manuscript copy only.
* The figure is the report of a compliance-checking *result*: the four callout boxes drawn over the
  diagram (V1–V4) are the paper's **findings**, not process content, and are deliberately **not**
  modelled here. Section 8 records them separately.

## 2. Evidence base

| Evidence | Local source | Use |
|---|---|---|
| Figure 10 raster image (1835×964 px) | attachment object `e635ee14ee042215232a5b3a385e5a3a9891bff74e03e462808069c1f924e940` (sha256 = that name), supplied with the task | primary evidence for topology, element types, glyphs, labels, pool/lane names, message-flow directions, geometry |
| Paper narrative §5.4 + Table 13 (R1–R4) + scrambled figure fragments + caption | `references/papers/extracted/sun_2024_full_text.txt` lines 923–1007 | naming, semantics, rule statements, cross-check of labels |
| Structural sanity reference (read-only, **not copied**) | `references/barrientos_2026/artifact_input/process_models/SIM_card_scenario/SIM_card_scenario.bpmn` | naming-convention check only (a different, expanded, Sun-derived model; e.g. pool names "Customer" / "Phone company" / "Another phone company") |

Text fragments recovered from the extraction (line 983–1006) that corroborate the model:
`Activate SIM card`, `Request personal data`, `Ask portability`, `Ask old number`,
`Ask portability third party`, `Assign new number`, `Sign contract`, `Request payment`,
`Send SIM card`, `New client`, `Request`, `Send personal data`, `Not requested`, `Requested`,
`Granted`, `Not granted`, `Personal data received`, `Payment received`, `Store Data`,
`Data Store`, `Personal data`, `Receive SIM card`, and the pool names `Customer`,
`Phone Company`, `Another Phone Company`.

## 3. Method (how the figure was read)

1. The figure was inspected at multiple magnifications (region crops at 2×–8×).
2. Because the rendering is small, the geometry was measured programmatically on the raster:
   long dark horizontal runs were used to locate the pool borders (Customer y 273–357,
   Phone Company y 390–703, Another Phone Company y 734–821) and the activity boxes
   (top row y 428–486, bottom row y 530–586, Customer row y 287–345); column dark-pixel
   histograms located box edges and the vertical message-flow lines.
3. Message-flow **direction** was decided per line by classifying the glyph at the pool border:
   a filled round **dot = source**, a widening **triangle = target (arrowhead)**. This was applied
   to every line that crosses a pool boundary (see §5).
4. The reconstructed model was re-rendered from its own `bpmndi` section with a throw-away
   renderer and compared against the figure; the layout matches pool-for-pool and lane-for-lane.
   The temporary crops and scratch scripts were deleted; no figure derivative is kept in the repo.

## 4. Deliberate design decisions inside the BPMN file

* **One `<process>`, three participants, three lanes.** The frozen Stage 1 parser
  (`bpc_hybrid/stage1_process.py`) accepts **exactly one** `<process>` per file
  ("BPMN input must contain exactly one process"), while Figure 10 is a three-participant
  collaboration. To stay parseable *and* keep actor attribution (essential for the paper's
  "incorrect actor" rule R3), the file uses one process `sun10_process_acquire_new_customer`
  with a lane per participant (`sun10_lane_customer`, `sun10_lane_phone_company`,
  `sun10_lane_another_phone_company`), and all three participants reference that one process.
  This is a schema-valid but unusual construction; a strictly standard model would use three
  processes. The project already owns a transform for the standard case
  (`bpc_hybrid/sim_case_c1_transforms.py::flatten_collaboration`), which is **not needed** here.
  *Consequence:* `parse_bpmn_file` yields 3 pools and 3 lanes, and every activity carries its
  actor lane in `lane_ids`.
* **Node ids** are stable and readable with the `sun10_` prefix as requested (e.g.
  `sun10_request_personal_data`, `sun10_gw_portability_choice`, `sun10_flow_05_not_requested_to_assign_new_number`).
* **Pool/lane names follow the figure spelling** ("Customer", "Phone Company",
  "Another Phone Company"). Note that the project's Barrientos-derived SIM pipeline expects the
  spelling "Phone company" (`sim_case_c1_transforms.py`, repair `r10_activation_owner`); an adapter
  must map names if the two artifacts are ever combined.
* The **"Another Phone Company" pool is empty in the figure** (verified across the whole pool band),
  so its lane has no `flowNodeRef`; the two message flows to/from it attach to the *participant*,
  exactly as the figure draws them (the lines stop at the pool border).
* The **Customer pool has no start event** in the figure (see A6).
* All XML is ASCII-only; no `DOCTYPE`, no entities (the parser forbids both).

## 5. Element inventory and evidence

### 5.1 Participants / lanes

| id | name | evidence |
|---|---|---|
| `sun10_participant_customer` | Customer | left-hand rotated pool label, top pool |
| `sun10_participant_phone_company` | Phone Company | rotated pool label, middle pool |
| `sun10_participant_another_phone_company` | Another Phone Company | rotated pool label, bottom pool (pool empty) |

### 5.2 Events (5)

| id | type | name | evidence |
|---|---|---|---|
| `sun10_new_client_acquired` | `startEvent` + `messageEventDefinition` | New client acquired | circle with open envelope at the left of the Phone Company pool; label below it; a dashed message line with a source-dot on the Customer pool border runs down into it; text line 1003 "New client" |
| `sun10_personal_data_received` | `intermediateCatchEvent` + `messageEventDefinition` | Personal data received | double-ring circle with envelope between "Request personal data" and "Ask portability"; label below it; text line 993 "Personal data received" |
| `sun10_payment_received` | `intermediateCatchEvent` + `messageEventDefinition` | Payment received | double-ring circle with envelope between "Request payment" and "Send SIM card"; label below it; text line 991 "Payment received" |
| `sun10_not_granted_end` | `endEvent` + `terminateEventDefinition` | "" (unlabelled in figure) | solid black disc inside a ring, right of the "Not granted" branch (x≈933–975, y≈540–582) |
| `sun10_customer_end` | `endEvent` | "" (unlabelled in figure) | plain thick ring in the Customer pool right of "Activate SIM card" |

### 5.3 Activities (11)

| id | BPMN type | name | lane | evidence |
|---|---|---|---|---|
| `sun10_request_personal_data` | `task` | Request personal data | Phone Company | first activity after the start event; text line 983/1003 |
| `sun10_ask_portability` | `task` | Ask portability | Phone Company | after the data-received event, before the XOR; text line 984 |
| `sun10_assign_new_number` | `task` | Assign new number | Phone Company | top branch of the first XOR; text line 983 |
| `sun10_sign_contract` | `task` | Sign contract | Phone Company | after the join XOR; text line 983 |
| `sun10_request_payment` | `task` | Request payment | Phone Company | after the parallel gateway; text line 1003 |
| `sun10_send_sim_card` | `task` | Send SIM card | Phone Company | last Phone Company activity; text line 983 |
| `sun10_ask_old_number` | `task` | Ask old number | Phone Company | bottom branch of the first XOR; text line 984 |
| `sun10_ask_portability_third_party` | `task` | Ask portability third party | Phone Company | after "Ask old number"; text line 984 |
| `sun10_store_data` | `subProcess` (collapsed) | Store Data | Phone Company | rounded box below "Send SIM card" with a small square "+" marker at its bottom edge; text line 993 "Store Data" |
| `sun10_receive_sim_card` | `task` | Receive SIM card | Customer | first Customer activity; text line 1001 |
| `sun10_activate_sim_card` | `task` | Activate SIM card | Customer | second Customer activity, enclosed by the yellow V3 box; text line 981 |

### 5.4 Gateways (4)

| id | type | position / role | evidence |
|---|---|---|---|
| `sun10_gw_portability_choice` | `exclusiveGateway` | after "Ask portability"; splits into "Not requested" / "Requested" | diamond with a bold X |
| `sun10_gw_portability_result` | `exclusiveGateway` | after "Ask portability third party"; splits into "Granted" / "Not granted" | diamond with a bold X |
| `sun10_gw_portability_join` | `exclusiveGateway` | merge of "Assign new number" and "Granted" before "Sign contract" | diamond with a bold X |
| `sun10_gw_parallel_payment_store` | `parallelGateway` | after "Sign contract"; splits to "Request payment" and to "Store Data" | diamond with a bold "+" |

### 5.5 Sequence flows (20) — labels exactly as legible in the figure

| id | source → target | label |
|---|---|---|
| `sun10_flow_01_new_client_to_request_data` | start → Request personal data | |
| `sun10_flow_02_request_data_to_data_received` | Request personal data → Personal data received | |
| `sun10_flow_03_data_received_to_ask_portability` | Personal data received → Ask portability | |
| `sun10_flow_04_ask_portability_to_portability_choice` | Ask portability → XOR | |
| `sun10_flow_05_not_requested_to_assign_new_number` | XOR → Assign new number | **Not requested** |
| `sun10_flow_06_requested_to_ask_old_number` | XOR → Ask old number | **Requested** |
| `sun10_flow_07_ask_old_number_to_third_party` | Ask old number → Ask portability third party | |
| `sun10_flow_08_third_party_to_portability_result` | Ask portability third party → XOR | |
| `sun10_flow_09_granted_to_portability_join` | XOR → join XOR | **Granted** |
| `sun10_flow_10_not_granted_to_end` | XOR → terminate end | **Not granted** |
| `sun10_flow_11_assign_new_number_to_join` | Assign new number → join XOR | |
| `sun10_flow_12_join_to_sign_contract` | join XOR → Sign contract | |
| `sun10_flow_13_sign_contract_to_parallel` | Sign contract → parallel gateway | |
| `sun10_flow_14_parallel_to_request_payment` | parallel → Request payment | |
| `sun10_flow_15_parallel_to_store_data` | parallel → Store Data | |
| `sun10_flow_16_request_payment_to_payment_received` | Request payment → Payment received | |
| `sun10_flow_17_payment_received_to_send_sim_card` | Payment received → Send SIM card | |
| `sun10_flow_18_store_data_to_send_sim_card` | Store Data → Send SIM card (elbow up into the box bottom) | |
| `sun10_flow_19_receive_sim_card_to_activate` | Receive SIM card → Activate SIM card | |
| `sun10_flow_20_activate_to_customer_end` | Activate SIM card → end | |

### 5.6 Message flows (14)

Direction was read from the dot/arrowhead glyph at the pool border (dot = source, arrowhead = target).

| id | source → target | label | measured line |
|---|---|---|---|
| `sun10_messageflow_new_client` | Customer → start event | **New client** | x≈230, dot on the Customer border, arrow into the start event |
| `sun10_messageflow_request_personal_data` | Request personal data → Customer | **Request** | x≈321, arrowhead at the Customer border |
| `sun10_messageflow_send_personal_data` | Customer → Personal data received | **Send personal data** | x≈413, dot on the Customer border |
| `sun10_messageflow_ask_portability_request` | Customer → Ask portability | (unlabelled) | x≈529, dot on the Customer border |
| `sun10_messageflow_ask_portability_response` | Ask portability → Customer | (unlabelled) | x≈542, arrowhead at the Customer border |
| `sun10_messageflow_assign_new_number_request` | Customer → Assign new number | (unlabelled) | x≈746, dot |
| `sun10_messageflow_assign_new_number_response` | Assign new number → Customer | (unlabelled) | x≈760, arrowhead |
| `sun10_messageflow_sign_contract_request` | Customer → Sign contract | (unlabelled) | x≈948, dot |
| `sun10_messageflow_sign_contract_response` | Sign contract → Customer | (unlabelled) | x≈962, arrowhead |
| `sun10_messageflow_request_payment` | Request payment → Customer | **Request** | x≈1147, arrowhead |
| `sun10_messageflow_payment` | Customer → Payment received | **Payment** | x≈1243, dot |
| `sun10_messageflow_send_sim_card` | Send SIM card → Receive SIM card | (unlabelled, drawn as a solid line) | x≈1338, arrowhead into the bottom of "Receive SIM card" |
| `sun10_messageflow_ask_third_party` | Ask portability third party → Another Phone Company | (unlabelled) | x≈746, dot below the task, arrowhead at the pool border |
| `sun10_messageflow_third_party_response` | Another Phone Company → Ask portability third party | (unlabelled) | x≈758, dot on the Another Phone Company border, arrowhead below the task |

### 5.7 Data

| id | type | name | evidence |
|---|---|---|---|
| `sun10_personal_data` / `sun10_data_object_personal_data` | `dataObjectReference` / `dataObject` | Personal data | document icon under the "Personal data received" area (x≈395–425, y≈617–657) with the caption "Personal data" |
| `sun10_data_store` / `sun10_datastore_definition` | `dataStoreReference` / `dataStore` | Data Store | cylinder below/right of "Store Data" (x≈1265–1323, y≈615–660), caption "Data Store" |

Associations (drawn as dotted lines in the figure):

| id | source → target | evidence |
|---|---|---|
| `sun10_assoc_data_received_to_personal_data` | Personal data received → Personal data | vertical dotted line at x≈413 from the event down to the icon |
| `sun10_assoc_personal_data_to_sign_contract` | Personal data → Sign contract | dotted rail at y≈645 from the icon, turning up at x≈980 into the bottom of "Sign contract" |
| `sun10_assoc_personal_data_to_store_data` | Personal data → Store Data | dotted rail at y≈655, turning up at x≈1205 with an arrowhead into the bottom of "Store Data" |
| `sun10_assoc_store_data_to_data_store` | Store Data → Data Store | dotted elbow from the "Store Data" bottom (x≈1245) to the cylinder |

## 6. Ambiguities, chosen reading, and the alternative

| # | Ambiguity | Chosen reading | Alternative / impact |
|---|---|---|---|
| A1 | Pool/lane name spelling ("Phone Company" vs "Phone company") | figure spelling, capital C | the project's Barrientos-derived SIM pipeline expects "Phone company"; an adapter must normalise names |
| A2 | Three pools vs. one process | one process + three lanes + three participants sharing it (parser requirement, §4) | strictly standard BPMN would use three processes; the project's `flatten_collaboration` transform exists for that shape. Consequence: two participants share one `processRef` |
| A3 | Direction of the six unlabelled pool-crossing lines (Ask portability ×2, Assign new number ×2, Sign contract ×2) and of the two third-party lines | dot = source, arrowhead = target (pixel classification, §3) | if the dots were merely decorative, the direction of those pairs would be reversed. No sequence-flow semantics depend on this; only the message direction does |
| A4 | Are those pool-crossing lines message flows or data associations? | message flows (they terminate with dot/arrowhead **on the pool border**) | they cannot be data associations to the data object, whose rails are horizontal at y≈645/655 |
| A5 | `Store Data` box has a small square "+" at its bottom edge | modelled as a **collapsed `subProcess`** (`sun10_store_data`) | could be a plain task with a decorative marker; the figure has no legend. Only the activity *type* changes |
| A6 | The Customer pool has **no start event** and no sequence connection to the Phone Company pool | kept faithful to the figure: the three Customer nodes are only "reached" through message flows | adding a message start event ("SIM card received") would repair reachability but invent figure content. **Consequence:** `parse_bpmn_file` reports `control_flow.unreachable_node_ids = [sun10_activate_sim_card, sun10_customer_end, sun10_receive_sim_card]`, because Stage 1 models sequence flows only |
| A7 | Solid black disc inside a ring at the end of the "Not granted" branch | `endEvent` with `terminateEventDefinition` | a plain end event drawn with a filled style. Affects only the event subtype |
| A8 | The two envelope intermediate events: catch or throw? | `intermediateCatchEvent` + `messageEventDefinition` (the company *receives* data / payment) | throw events would reverse the meaning. The envelope icon is not resolvable at this print resolution |
| A9 | "Personal data received" / "Payment received" — event names or floating annotations? | event names (they sit under the circles exactly like "New client acquired") | they could be text annotations; then the two events would be unnamed |
| A10 | Arrow direction on the y≈645 rail into "Sign contract" | association direction "One" toward Sign contract (consistent with the sibling rails) | `associationDirection="None"` if the missing arrowhead is meaningful |
| A11 | "Send SIM card" has two incoming sequence flows and no merge gateway | kept as drawn: the two flows enter the task (implicit XOR merge) | the diagram may intend a parallel join; no "+" gateway is drawn, so no parallel join is modelled |
| A12 | Message flow "Send SIM card" → "Receive SIM card" is drawn **solid**, not dashed | still modelled as a message flow (it crosses pools between two tasks), unlabelled | it could be a drawing style variant; no better reading available |
| A13 | Gateway types | bold X = `exclusiveGateway` (3×), bold + = `parallelGateway` (1×) | an inclusive reading of the merge before "Sign contract" is conceivable but the glyph is a plain X |
| A14 | Whether the long dotted rails at y≈645/655 associate the data object with further activities | only the three visible vertical branches are modelled (event, Sign contract, Store Data) | other tasks might have been intended to share the data object; no vertical dotted stub is visible at any of them |
| A15 | Pool band geometry / lane modelling | each pool = one participant with exactly one lane; the "Another Phone Company" lane is empty, matching the empty pool | the figure does not show lane separators inside pools, so no additional lanes were invented |
| A16 | Exact pixel geometry of data object / data store / terminate end | taken from the raster measurements in §3 | ±5 px placement differences are possible |
| A17 | Names of unlabelled elements (the two end events, the four gateways, most message flows) | left as empty `name` attributes to avoid inventing figure text | descriptive names would render extra text that is not in the figure |
| A18 | The paper's own figure is a *result* figure: the coloured dashed rectangles and callouts are overlays | not modelled (see §8) | if the overlays were modelled as artifacts, they would falsely become process content |

## 7. Cross-check against the narrative text (§5.4, lines 924–973)

* "the phone company requests new data from the customer and verifies that the data is correct" →
  `sun10_request_personal_data` + the received-data event. **The figure contains no verification
  activity**; that absence is exactly the paper's R2 finding (see §8), so no verification task was
  added.
* "If the customer decides to change the phone number, the phone company will communicate with the
  original phone company and sign a contract with the customer" → the `Requested` branch
  (`Ask old number` → `Ask portability third party` → second company) and `sun10_sign_contract`.
* "After completing the above steps and receiving payment, the phone company sends the SIM card to
  the customer and activates it" → `Request payment` → `Payment received` → `Send SIM card` →
  (message) → `Receive SIM card` → `Activate SIM card`.
* "If for any reason the process takes more than 30 days to complete, the process will be
  terminated" → **not represented in the figure** (this is the paper's R1 finding). No timer or
  termination branch was invented.

## 8. The four violation callouts (paper's reported findings — deliberately NOT modelled)

Figure 10 overlays four callout boxes and coloured dashed rectangles on the model. They are the
output of the paper's compliance check, i.e. a *result*, and are excluded from the BPMN file:

| Callout (as printed in Figure 10) | Corresponding rule | Violation type (as printed) | Region outlined in the figure |
|---|---|---|---|
| ID: Violation 1 | R1 | Missing Action | the whole Phone Company execution path (no 30-day termination sub-process) |
| ID: Violation 2 | R2 | Missing Action | dashed blue box around "Request personal data" + the data-received event + "Ask portability" (the verification action is missing / out of order) |
| ID: Violation 3 | R3 | Incorrect Actor | dashed yellow box around "Activate SIM card" in the **Customer** pool |
| ID: Violation 4 | R4 | Out-of-order Execution | dashed orange box around the parallel-gateway → "Store Data" branch (no prior consent activity) |

The page-23 text (lines 957–968) states: "for both rules R1 and R4, we detect missing action
violations … For the rule with R2, we detected the out-of-order execution violation … Finally, we
detect the incorrect actors violation with R3."

## 9. The paper's two conflicting rule ↔ violation mappings (unresolved)

* **Page 23 body text (lines 957–968) — one mapping:**
  * R1 → *missing action* ("a sub-process … which terminates the process when the execution time exceeds 30 days"),
  * R4 → *missing action* ("the activity of asking for consent is added"),
  * R2 → *out-of-order execution* ("check the correctness of personal data should be added **after** the personal data has been obtained"),
  * R3 → *incorrect actor* ("the SIM card should be activated by the phone company, not the customer himself").
* **Figure 10 callouts (lines 998–1006) — a different mapping:**
  * Violation 1 / R1 → Missing Action,
  * Violation 2 / R2 → **Missing Action**,
  * Violation 3 / R3 → Incorrect Actor,
  * Violation 4 / R4 → **Out-of-order Execution**.

The two statements agree on R1 and R3 and **disagree on R2 and R4** (missing action vs out-of-order
execution are swapped). This reconstruction does not adjudicate between them: it preserves the
figure text verbatim in the table in §8 and the body text verbatim in §9.
**The version of record could not be obtained** in this session (the local PDF is a pre-publication
manuscript, and this task forbids network access), so the conflict cannot be resolved from a
publisher copy here. Downstream work must not silently pick one mapping.

## 10. Validation (exact command and output)

Run from the repository root `D:\Paper\experiment\bpc-hybrid`:

```
python -c "import sys; sys.path.insert(0,'formal_experiment/src'); from bpc_hybrid.stage1_process import load_stage1_contract, parse_bpmn_file; c=load_stage1_contract('formal_experiment/configs/stage1_structural_s11_s14.json'); r=parse_bpmn_file('formal_experiment/data/development/sim_case_c1/sun_figure10_reconstruction.bpmn', contract=c); print(r['process_id'], len(r['activities']), len(r['gateways']), len(r['events']))"
```

Output (no exception):

```
sun10_process_acquire_new_customer 11 4 5
```

`load_stage1_contract` takes the contract **path** (`formal_experiment/configs/stage1_structural_s11_s14.json`),
as used above; `parse_bpmn_file` internally calls `validate_process_record`, which returned
`valid=True` (`schema_valid=True`, `cross_field_valid=True`, `errors=[]`).

Additional checks performed on the same file (project code + ElementTree only):

* `sha256 = 773c46914e4d3a9c59737d09c536eaabdfc5b76d347fad391600d060bad3a206`, `byte_size = 26673`,
  `bpmn_namespace = http://www.omg.org/spec/BPMN/20100524/MODEL`
* ASCII-only: `True` (no non-ASCII byte, no `DOCTYPE`, no entity declaration)
* counts: **activities 11, gateways 4, events 5, sequence flows 20**, plus **14 message flows**,
  **4 data associations**, **3 participants**, **3 lanes**, 1 collaboration
* no dangling `sourceRef`/`targetRef` in any sequence/message flow or association
* all 66 `BPMNDiagram` shapes/edges reference existing element ids (the file renders from `bpmndi`)
* `validate_process_record(record) → valid=True`
* `control_flow`: `cycle_detected=False`; `parallel_split_gateway_ids=[sun10_gw_parallel_payment_store]`,
  `parallel_join_gateway_ids=[]` (the parallel split rejoins implicitly at "Send SIM card", as drawn);
  `unreachable_node_ids=[sun10_activate_sim_card, sun10_customer_end, sun10_receive_sim_card]`
  (the Customer-pool nodes; expected, see A6)

## 11. Handoff notes

* Bind downstream code to the `sun10_` ids listed in §5; they are stable for this reconstruction.
* Actor attribution lives in `lanes[*].flow_node_refs` / `activities[*].lane_ids`
  (`sun10_lane_customer` holds exactly the two Customer tasks and the Customer end event) — this is
  what an "incorrect actor" check (R3) would read.
* If a standard three-process collaboration is ever required, re-emit the participants/processes and
  apply the project's existing flattening transform instead of editing this file in place.
* Do not describe this file as the authors' model. Suggested wording: *"our reconstruction of
  Figure 10 of Sun et al. (2024), built from the published figure and the paper's narrative."*
