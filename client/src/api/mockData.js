// mockData.js
// This file contains exact JSON structures extracted from the backend 
// to allow the frontend to render correctly without a server.

export const mockDashboardSummary = {
  open_ncr_count: { CRITICAL: 1, MAJOR: 0, MINOR: 0 },
  total_documents: 2,
  compliance_checks_run: 1,
  at_risk_tasks: 1,
  critical_path_tasks: 1,
  open_rfis: 2,
  recent_agent_runs: [
    {
       id: "run-001", agent_name: "spec_compliance", trigger_event: "manual", status: "completed",
       started_ts: "2026-07-20T10:00", completed_ts: "2026-07-20T10:01", records_processed: 1,
       records_created: 1, output_summary: "Found 3 deviations"
    }
  ],
  project_health_score: 85.0,
  purchase_orders: [
    {
      id: "po-ps1500-001",
      po_number: "PO-VERTEX-2025-0047",
      vendor_name: "PowerShield Technologies Pvt. Ltd.",
      compliance_status: "FAILED",
      deviation_count: 3,
      po_date: "2025-03-28"
    }
  ],
  manual_hours_saved_weekly: 12.5,
  compliance_accuracy_pct: 100,
  risks_flagged_avg_days_advance: 14,
  commissioning_pass_rate_pct: 100,
  total_ncrs_raised: 1,
  compliance_checks_total: 1
};

export const mockComplianceResults = {
  po_id: "po-ps1500-001",
  po_number: "PO-VERTEX-2025-0047",
  vendor_name: "PowerShield Technologies Pvt. Ltd.",
  compliance_status: "FAILED",
  checked_ts: "2025-04-01T10:00",
  deviations: [
    {
      attribute_name: "efficiency_pct",
      severity: "CRITICAL",
      specified_value: "96.5",
      submitted_value: "95.8",
      clause_number: "4.2.4",
      clause_title: "Efficiency Requirements",
      ncr_id: "ncr-001",
      ncr_title: "UPS Efficiency Failure",
      ncr_status: "open",
      deviation_type: "VALUE_MISMATCH",
      justification: "Critical energy efficiency drop."
    },
    {
      attribute_name: "battery_autonomy_min",
      severity: "MAJOR",
      specified_value: "10",
      submitted_value: "8",
      clause_number: "4.2.6",
      clause_title: "Battery Autonomy",
      ncr_id: null,
      ncr_title: null,
      ncr_status: null,
      deviation_type: "VALUE_MISMATCH",
      justification: "Battery autonomy is insufficient"
    }
  ],
  summary: { total: 2, critical: 1, major: 1, minor: 0 }
};

export const mockNcrsResponse = {
  ncrs: [
    {
      id: "ncr-001",
      title: "UPS Efficiency Failure",
      severity: "CRITICAL",
      status: "open",
      raised_ts: "2025-04-01T10:00:00",
      equipment_description: "1500 kVA UPS",
      equipment_class: "UPS",
      attribute_name: "efficiency_pct",
      specified_value: "96.5",
      submitted_value: "95.8"
    }
  ],
  total: 1,
  by_severity: { CRITICAL: 1, MAJOR: 0, MINOR: 0 }
};

export const mockNcrDetail = {
  ...mockNcrsResponse.ncrs[0],
  clause_number: "4.2.4",
  clause_title: "Efficiency Requirements",
  clause_raw_text: "The UPS shall achieve a minimum efficiency of 96.5%...",
  clause_pages: "[2]",
  vendor_name: "PowerShield Technologies",
  po_number: "PO-VERTEX-2025-0047",
  deviation_type: "VALUE_MISMATCH",
  justification: "Failed to meet efficiency specs.",
  recommended_action: "Require vendor to submit revised model.",
  schedule_impact: { "task_id": "T-003", "delay_days": 14, "risk_level": "HIGH" },
  actions: []
};

export const mockScheduleTasksResponse = {
  tasks: [
    { 
      id: "T-001", task_code: "T-001", description: "Site preparation", 
      planned_start: "2026-07-01", planned_finish: "2026-07-14", 
      total_float_days: 10, original_float_days: 10,
      risk_score: 0.1, delay_probability: 0.1,
      equipment_description: null, equipment_class: null, predecessor_ids_json: "[]"
    },
    { 
      id: "T-003", task_code: "T-003", description: "UPS equipment delivery", 
      planned_start: "2026-07-22", planned_finish: "2026-07-22", 
      total_float_days: 0, original_float_days: 0,
      risk_score: 0.9, delay_probability: 0.85,
      equipment_description: "1500 kVA UPS", equipment_class: "UPS", predecessor_ids_json: "[\"T-001\"]"
    },
    { 
      id: "T-007", task_code: "T-007", description: "UPS pre-commissioning checks", 
      planned_start: "2026-08-09", planned_finish: "2026-08-12", 
      total_float_days: 0, original_float_days: 0,
      risk_score: 0.2, delay_probability: 0.1,
      equipment_description: "1500 kVA UPS", equipment_class: "UPS", predecessor_ids_json: "[\"T-003\"]"
    }
  ],
  total: 3
};

export const mockScheduleRisksResponse = {
  at_risk_tasks: [ mockScheduleTasksResponse.tasks[1] ],
  total: 1,
  critical_path_count: 1
};

export const mockDelayComparison = {
  tasks: [
    {
       ...mockScheduleTasksResponse.tasks[1],
       predicted_delay_days: 14,
       historical_avg_delay: 5,
       actual_delay_days: 0,
       float_consumed_days: 0,
       delay_gap: 9,
       verdict: "Exceeds Historical Average"
    }
  ],
  total: 1,
  avg_predicted_delay_days: 14,
  avg_historical_delay_days: 5,
  tasks_exceeding_historical: 1,
  avg_lead_time_flagged_days: 10
};

export const mockProjects = [
  {
    id: "proj-001",
    name: "Project VERTEX Tier IV Data Centre",
    status: "active",
    budget: 120000000,
    completion: 15,
    location: "Dubai",
    created_ts: "2025-01-01T10:00"
  }
];

export const mockDocumentsResponse = {
  documents: [
    {
      id: "doc-spec-ups-001",
      filename: "VERTEX-ELEC-SPEC-UPS-001-Rev2.pdf",
      doc_type: "specification",
      upload_ts: "2025-03-15T09:00:00",
      status: "ready",
      page_count: 4
    },
    {
      id: "doc-sub-ps1500-001",
      filename: "PowerShield_PS1500_Technical_Submittal_Rev1.pdf",
      doc_type: "submittal",
      upload_ts: "2025-03-28T14:30:00",
      status: "ready",
      page_count: 3
    }
  ]
};

export const mockEquipment = [
  {
    id: "eq-ups-moda-001",
    item_code: "EQ-UPS-MODA-001",
    description: "1500 kVA Online Double Conversion UPS — Primary Power Path A",
    equipment_class: "UPS",
    design_zone: "UPS Room A1",
    compliance_score: 1.0,
    criticality: "CRITICAL"
  }
];

export const mockRFIs = [
  {
    id: "rfi-001",
    rfi_code: "RFI-2025-0089",
    title: "UPS efficiency specification",
    status: "resolved",
    raised_by: "Site QA Engineer",
    description: "Request clarification on efficiency requirements.",
    resolution_text: "Vendor must supply PE-Series or equivalent.",
    raised_ts: "2025-04-05T09:00:00"
  },
  {
    id: "rfi-002",
    rfi_code: "RFI-2025-0091",
    title: "Battery autonomy adequacy",
    status: "resolved",
    raised_by: "Procurement Manager",
    description: "Vendor proposes 8 minutes autonomy.",
    resolution_text: "Concession NOT granted. 10 minutes minimum.",
    raised_ts: "2025-04-08T11:00:00"
  }
];

export const mockSupplyChainShipments = [
  { id: "shp-001", status: "IN TRANSIT", origin: "Shenzhen", destination: "Dubai", eta: "2026-07-15", equipment: "EQ-UPS-MODA-001", current_location: "Indian Ocean" }
];

export const mockSupplyChainAlerts = [
  { id: "alt-001", severity: "HIGH", message: "Port congestion in origin port delaying UPS delivery by 5 days.", timestamp: "2026-07-01T10:00" }
];

export const mockCommissioningTasks = [
  { id: "chk-ups-fat-001", title: "UPS Factory Acceptance Test", status: "PENDING", equipment: "UPS", steps: [{step_number: 1, description: "Check alignment"}] }
];

export const mockCommissioningRecords = [
  { id: "rec-001", task_id: "chk-ups-fat-001", step: 1, actual_value: "Pass", checked_by: "QA Engineer", timestamp: "2026-07-10T10:00:00" }
];

export const mockBids = [
  { id: "bid-001", vendor: "PowerShield", price: 150000, score: 85, status: "submitted" }
];
