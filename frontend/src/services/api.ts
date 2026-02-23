export type FieldEntry = {
  key: string;
  value: string;
  description: string;
  confidence: number;
  source_excerpt: string;
  target_field_name?: string | null;
};

export type TaxResult = {
  total_income?: number;
  agi?: number;
  standard_deduction?: number;
  itemized_deduction?: number;
  deduction_used?: string;
  taxable_income?: number;
  tax_before_credits?: number;
  credits?: {
    total_credits?: number;
    tax_after_credits?: number;
    earned_income_credit?: number;
    child_tax_credit?: { total?: number; nonrefundable?: number; refundable?: number };
    child_dependent_care_credit?: number;
    credit_elderly_disabled?: number;
  };
};

export type Recommendation = {
  type: string;
  title: string;
  detail: string;
};

export type RunState = {
  run_id: string;
  status: string;
  logs: string[];
  errors: string[];
  irs_instructions?: { form_code: string; source_url: string; summary: string }[];
  transformed_fields: FieldEntry[];
  reviewed_fields: FieldEntry[];
  tax_result?: TaxResult | null;
  recommendations?: Recommendation[] | null;
  completed_pdf_path?: string | null;
};

const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api/workflow";
const API_ORIGIN = API_BASE.replace(/\/api\/workflow\/?$/, "");
const IRS_FORMS_BASE = `${API_ORIGIN}/api/irs-forms`;

async function jsonRequest<T>(url: string, options?: RequestInit): Promise<T> {
  const response = await fetch(url, options);
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body?.detail ?? `Request failed with ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export async function createRun(
  identityFile: File,
  formFile: File | null,
  schemaName = "w9.yaml",
  irsFormId?: string
): Promise<{ run_id: string }> {
  const data = new FormData();
  data.append("identity_document", identityFile);
  if (formFile) {
    data.append("tax_form", formFile);
  }
  if (irsFormId) {
    data.append("irs_form_id", irsFormId);
  }
  data.append("schema_name", schemaName);
  return jsonRequest(`${API_BASE}/runs`, { method: "POST", body: data });
}

export async function scanRun(runId: string): Promise<RunState> {
  const result = await jsonRequest<{ run: RunState }>(`${API_BASE}/runs/${runId}/scan`, { method: "POST" });
  return result.run;
}

export async function transformRun(runId: string): Promise<RunState> {
  const result = await jsonRequest<{ run: RunState }>(`${API_BASE}/runs/${runId}/transform`, { method: "POST" });
  return result.run;
}

export async function loadIrsInstructions(runId: string, formCodes: string[]): Promise<RunState> {
  const result = await jsonRequest<{ run: RunState }>(`${API_BASE}/runs/${runId}/instructions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ form_codes: formCodes })
  });
  return result.run;
}

export async function reviewRun(runId: string, fields: FieldEntry[]): Promise<RunState> {
  const result = await jsonRequest<{ run: RunState }>(`${API_BASE}/runs/${runId}/review`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ fields })
  });
  return result.run;
}

export async function fillRun(runId: string): Promise<RunState> {
  const result = await jsonRequest<{ run: RunState }>(`${API_BASE}/runs/${runId}/fill`, { method: "POST" });
  return result.run;
}

export async function submitRun(runId: string, emailTo?: string, webhookUrl?: string): Promise<RunState> {
  const result = await jsonRequest<{ run: RunState }>(`${API_BASE}/runs/${runId}/submit`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email_to: emailTo || null,
      webhook_url: webhookUrl || null
    })
  });
  return result.run;
}

export function downloadUrl(runId: string): string {
  return `${API_BASE}/runs/${runId}/download`;
}

export type IrsForm = { id: string; name: string; url: string };

export async function getIrsFormsList(): Promise<{ forms: IrsForm[] }> {
  return jsonRequest(`${IRS_FORMS_BASE}/list`);
}

export function irsFormDownloadUrl(formId: string): string {
  return `${IRS_FORMS_BASE}/${formId}/download`;
}

export type TaxCalculateParams = {
  num_qualifying_children?: number;
  num_dependents_under_17?: number;
  dependent_care_expenses?: number;
  num_dep_care_individuals?: number;
  elderly_or_disabled?: boolean;
  has_disability_income?: boolean;
};

export async function calculateTax(runId: string, params?: TaxCalculateParams): Promise<RunState> {
  const result = await jsonRequest<{ run: RunState }>(`${API_BASE}/runs/${runId}/tax/calculate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(params ?? {})
  });
  return result.run;
}

export async function getRecommendations(runId: string): Promise<RunState> {
  const result = await jsonRequest<{ run: RunState }>(`${API_BASE}/runs/${runId}/recommendations`, {
    method: "GET"
  });
  return result.run;
}

/* AGI Calculator */
export type AGIInputs = {
  filing_status?: string;
  wages?: number;
  taxable_interest?: number;
  ordinary_dividends?: number;
  taxable_ira?: number;
  taxable_pension?: number;
  taxable_social_security?: number;
  capital_gain_loss?: number;
  sch_c_income?: number;
  other_income?: number;
  educator_expenses?: number;
  ira_deduction?: number;
  student_loan_interest?: number;
  other_adjustments?: number;
  medical_expenses?: number;
  medical_insurance_reimbursement?: number;
};

export type DocumentSource = {
  line: string;
  description: string;
  documents: string[];
  value: number;
};

export type AGICalculatorResult = {
  total_income: number;
  adjustments: number;
  agi: number;
  medical_7p5_threshold: number;
  medical_expenses_net: number;
  medical_deductible: number;
  medical_exceeds_threshold: boolean;
  document_sources: DocumentSource[];
  message: string | null;
};

const AGI_CALCULATOR_BASE = `${API_ORIGIN}/api/agi-calculator`;

export async function calculateAGI(inputs: AGIInputs): Promise<AGICalculatorResult> {
  return jsonRequest(`${AGI_CALCULATOR_BASE}/calculate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(inputs)
  });
}

/* Document Intake */
export type ClassifiedDoc = {
  filename: string;
  doc_type: string;
  confidence: number;
  extracted_fields: Record<string, number | string>;
  message?: string;
};

export type DocumentIntakeResult = {
  documents: ClassifiedDoc[];
  merged_fields: Record<string, number>;
  message: string;
};

const DOCUMENT_INTAKE_BASE = `${API_ORIGIN}/api/document-intake`;

export async function processDocuments(files: File[]): Promise<DocumentIntakeResult> {
  const formData = new FormData();
  files.forEach((f) => formData.append("files", f));
  const response = await fetch(`${DOCUMENT_INTAKE_BASE}/process`, { method: "POST", body: formData });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body?.detail ?? `Request failed with ${response.status}`);
  }
  return response.json() as Promise<DocumentIntakeResult>;
}
