import { useEffect, useMemo, useState } from "react";
import { IrsFormsPanel } from "../components/IrsFormsPanel";
import { ReviewEditor } from "../components/ReviewEditor";
import {
  calculateTax,
  createRun,
  downloadUrl,
  fillRun,
  getIrsFormsList,
  getRecommendations,
  loadIrsInstructions,
  reviewRun,
  scanRun,
  submitRun,
  transformRun,
  type FieldEntry,
  type IrsForm,
  type RunState,
  type TaxResult
} from "../services/api";
import type { QuestionnaireResult } from "../lib/questionnaire";

const SCHEMAS = [
  { value: "w9.yaml", label: "W-9 (Identity)" },
  { value: "form1040.yaml", label: "Form 1040" },
  { value: "schedule-a.yaml", label: "Schedule A (Itemized)" }
];

const ALL_STEPS = ["Upload", "Scan", "IRS Instructions", "Transform", "Review", "Tax & Credits", "Fill", "Submit"];

type WizardPageProps = {
  questionnaireResult?: QuestionnaireResult | null;
};

export function WizardPage({ questionnaireResult }: WizardPageProps) {
  const showInstructionsStep = questionnaireResult?.showInstructionsStep ?? true;
  const steps = useMemo(
    () => (showInstructionsStep ? ALL_STEPS : ALL_STEPS.filter((s) => s !== "IRS Instructions")),
    [showInstructionsStep]
  );
  const [stepIndex, setStepIndex] = useState(0);
  const [identityFile, setIdentityFile] = useState<File | null>(null);
  const [formSource, setFormSource] = useState<"irs" | "upload">("irs");
  const [formFile, setFormFile] = useState<File | null>(null);
  const [irsFormId, setIrsFormId] = useState(questionnaireResult?.irsFormId ?? "f1040");
  const [irsForms, setIrsForms] = useState<IrsForm[]>([]);
  const [schemaName, setSchemaName] = useState(questionnaireResult?.schemaName ?? "form1040.yaml");
  const [formCodesInput, setFormCodesInput] = useState(
    questionnaireResult?.formCodes?.join(", ") ?? "form-1040,schedule-a-form-1040"
  );
  const [creditParams, setCreditParams] = useState(() =>
    questionnaireResult?.creditDefaults
      ? { ...questionnaireResult.creditDefaults }
      : {
          num_qualifying_children: 0,
          num_dependents_under_17: 0,
          dependent_care_expenses: 0,
          num_dep_care_individuals: 0,
          elderly_or_disabled: false,
          has_disability_income: false,
        }
  );
  const [runId, setRunId] = useState<string>("");
  const [runState, setRunState] = useState<RunState | null>(null);
  const [reviewFields, setReviewFields] = useState<FieldEntry[]>([]);
  const [emailTo, setEmailTo] = useState("");
  const [webhookUrl, setWebhookUrl] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const logs = useMemo(() => runState?.logs ?? [], [runState]);

  useEffect(() => {
    getIrsFormsList()
      .then((r) => setIrsForms(r.forms.filter((f) => f.id.startsWith("f") && !f.id.startsWith("i"))))
      .catch(() => {});
  }, []);

  async function withBusy(fn: () => Promise<void>) {
    try {
      setBusy(true);
      setError("");
      await fn();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Operation failed");
    } finally {
      setBusy(false);
    }
  }

  const onCreateRun = () =>
    withBusy(async () => {
      if (!identityFile) {
        throw new Error("Please upload your identity document.");
      }
      const useIrs = formSource === "irs";
      if (useIrs && !irsFormId) {
        throw new Error("Please select an IRS form.");
      }
      if (!useIrs && !formFile) {
        throw new Error("Please upload a tax form PDF.");
      }
      const created = await createRun(identityFile, useIrs ? null : formFile, schemaName, useIrs ? irsFormId : undefined);
      setRunId(created.run_id);
      setStepIndex(1);
    });

  const goTo = (stepName: string) => setStepIndex(steps.indexOf(stepName));

  const onScan = () =>
    withBusy(async () => {
      const state = await scanRun(runId);
      setRunState(state);
      if (showInstructionsStep) {
        goTo("IRS Instructions");
      } else {
        const formCodes = formCodesInput.split(",").map((c) => c.trim()).filter(Boolean);
        const codes = formCodes.length > 0 ? formCodes : ["form-1040"];
        const instr = await loadIrsInstructions(runId, codes);
        setRunState(instr);
        goTo("Transform");
      }
    });

  const onLoadInstructions = () =>
    withBusy(async () => {
      const formCodes = formCodesInput
        .split(",")
        .map((code) => code.trim())
        .filter(Boolean);
      const state = await loadIrsInstructions(runId, formCodes);
      setRunState(state);
      goTo("Transform");
    });

  const onTransform = () =>
    withBusy(async () => {
      const state = await transformRun(runId);
      setRunState(state);
      setReviewFields(state.transformed_fields);
      goTo("Review");
    });

  const onReview = () =>
    withBusy(async () => {
      const state = await reviewRun(runId, reviewFields);
      setRunState(state);
      goTo("Tax & Credits");
    });

  const onCalculateTax = () =>
    withBusy(async () => {
      const state = await calculateTax(runId, creditParams);
      setRunState(state);
    });

  const onGetRecommendations = () =>
    withBusy(async () => {
      const state = await getRecommendations(runId);
      setRunState(state);
    });

  const onFill = () =>
    withBusy(async () => {
      const state = await fillRun(runId);
      setRunState(state);
      goTo("Submit");
    });

  const onSubmit = () =>
    withBusy(async () => {
      const state = await submitRun(runId, emailTo || undefined, webhookUrl || undefined);
      setRunState(state);
    });

  const stepNum = (name: string) => steps.indexOf(name) + 1;

  return (
    <main className="page wizard-page">
      <div className="wizard-intro">
        <h2>Tax Filing Workflow</h2>
        <p>Follow the steps below to complete your filing.</p>
      </div>

      <section className="stepper">
        {steps.map((step, idx) => (
          <span key={step} className={idx <= stepIndex ? "active" : ""}>
            {idx + 1}. {step}
          </span>
        ))}
      </section>

      {error ? <p className="error">{error}</p> : null}

      <section className="card">
        <h2>{stepNum("Upload")}) Upload</h2>
        <IrsFormsPanel />
        <label>
          Identity PDF
          <input type="file" accept="application/pdf" onChange={(e) => setIdentityFile(e.target.files?.[0] ?? null)} />
        </label>
        <div className="form-source">
          <label>
            <input type="radio" checked={formSource === "irs"} onChange={() => setFormSource("irs")} />
            Use latest IRS form (no upload)
          </label>
          <label>
            <input type="radio" checked={formSource === "upload"} onChange={() => setFormSource("upload")} />
            Upload my own form PDF
          </label>
        </div>
        {formSource === "irs" ? (
          <label>
            IRS form
            <select value={irsFormId} onChange={(e) => setIrsFormId(e.target.value)}>
              {irsForms.map((f) => (
                <option key={f.id} value={f.id}>{f.name}</option>
              ))}
            </select>
          </label>
        ) : (
          <label>
            Tax Form PDF
            <input type="file" accept="application/pdf" onChange={(e) => setFormFile(e.target.files?.[0] ?? null)} />
          </label>
        )}
        <label>
          Schema
          <select value={schemaName} onChange={(e) => setSchemaName(e.target.value)}>
            {SCHEMAS.map((s) => (
              <option key={s.value} value={s.value}>{s.label}</option>
            ))}
          </select>
        </label>
        <button disabled={busy} onClick={onCreateRun} className="btn-primary">
          Initialize Run
        </button>
        {runId ? <p>Run ID: {runId}</p> : null}
      </section>

      <section className="card">
        <h2>{stepNum("Scan")}) Scan (OCR/Text)</h2>
        <button disabled={busy || !runId} onClick={onScan} className="btn-primary">
          Run Document Scanner Agent
        </button>
      </section>

      {showInstructionsStep && (
        <section className="card">
          <h2>{stepNum("IRS Instructions")}) IRS Instructions (Itemized Filing)</h2>
          <label>
            Form Codes
            <select
              value={formCodesInput}
              onChange={(e) => setFormCodesInput(e.target.value)}
            >
              <option value="form-1040">Form 1040 only</option>
              <option value="form-1040, schedule-a-form-1040">Form 1040 + Schedule A</option>
              <option value="form-1040, schedule-a-form-1040, schedule-c-form-1040">1040 + Schedule A + C</option>
            </select>
          </label>
          <button disabled={busy || !runId} onClick={onLoadInstructions} className="btn-primary">
            Load IRS Form Instructions
          </button>
          {runState?.irs_instructions && runState.irs_instructions.length > 0 ? (
            <ul>
              {runState.irs_instructions.map((item) => (
                <li key={item.form_code}>
                  {item.form_code}: <a href={item.source_url} target="_blank" rel="noreferrer">{item.source_url}</a>
                </li>
              ))}
            </ul>
          ) : null}
        </section>
      )}

      <section className="card">
        <h2>{stepNum("Transform")}) Transform</h2>
        <button disabled={busy || !runId} onClick={onTransform} className="btn-primary">
          Run Data Transformer Agent
        </button>
      </section>

      <section className="card">
        <h2>{stepNum("Review")}) Review & Edit</h2>
        <ReviewEditor fields={reviewFields} onChange={setReviewFields} />
        <button disabled={busy || !runId || reviewFields.length === 0} onClick={onReview} className="btn-primary">
          Approve Reviewed Fields
        </button>
      </section>

      <section className="card">
        <h2>{stepNum("Tax & Credits")}) Tax & Credits</h2>
        <p>Calculate tax, apply credits, and get recommendations.</p>
        <div className="credit-params">
          <label>Qualifying children (EITC)</label>
          <select value={creditParams.num_qualifying_children} onChange={(e) => setCreditParams((p) => ({ ...p, num_qualifying_children: +e.target.value }))}>
            {[0, 1, 2, 3, 4, 5, 6].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
          <label>Dependents under 17 (CTC)</label>
          <select value={creditParams.num_dependents_under_17} onChange={(e) => setCreditParams((p) => ({ ...p, num_dependents_under_17: +e.target.value }))}>
            {[0, 1, 2, 3, 4, 5, 6].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
          <label>Dependent care expenses</label>
          <select value={creditParams.dependent_care_expenses} onChange={(e) => setCreditParams((p) => ({ ...p, dependent_care_expenses: +e.target.value }))}>
            {[0, 1500, 3000, 4500, 6000, 9000, 12000].map((n) => <option key={n} value={n}>${n.toLocaleString()}</option>)}
          </select>
          <label># in care (for dependent care credit)</label>
          <select value={creditParams.num_dep_care_individuals} onChange={(e) => setCreditParams((p) => ({ ...p, num_dep_care_individuals: +e.target.value }))}>
            {[0, 1, 2, 3, 4].map((n) => <option key={n} value={n}>{n}</option>)}
          </select>
          <label>Elderly or disabled</label>
          <select value={creditParams.elderly_or_disabled ? "yes" : "no"} onChange={(e) => {
            const v = e.target.value === "yes";
            setCreditParams((p) => ({ ...p, elderly_or_disabled: v, has_disability_income: v }));
          }}>
            <option value="no">No</option>
            <option value="yes">Yes</option>
          </select>
        </div>
        <button disabled={busy || !runId} onClick={onCalculateTax} className="btn-primary">
          Calculate Tax & Credits
        </button>
        <button disabled={busy || !runId} onClick={onGetRecommendations} className="secondary">
          Get Recommendations
        </button>
        {runState?.tax_result ? (
          <div className="tax-summary">
            <h3>Tax Summary</h3>
            <table>
              <tbody>
                <tr><td>AGI</td><td>${(runState.tax_result as TaxResult).agi?.toLocaleString() ?? "—"}</td></tr>
                <tr><td>Deduction</td><td>{(runState.tax_result as TaxResult).deduction_used ?? "—"}</td></tr>
                <tr><td>Taxable Income</td><td>${(runState.tax_result as TaxResult).taxable_income?.toLocaleString() ?? "—"}</td></tr>
                <tr><td>Tax (before credits)</td><td>${(runState.tax_result as TaxResult).tax_before_credits?.toLocaleString() ?? "—"}</td></tr>
                <tr><td>Total Credits</td><td>${(runState.tax_result as TaxResult).credits?.total_credits?.toLocaleString() ?? "0"}</td></tr>
                <tr><td>Tax After Credits</td><td>${(runState.tax_result as TaxResult).credits?.tax_after_credits?.toLocaleString() ?? "—"}</td></tr>
              </tbody>
            </table>
          </div>
        ) : null}
        {runState?.recommendations && runState.recommendations.length > 0 ? (
          <div className="recommendations">
            <h3>Recommendations</h3>
            <ul>
              {runState.recommendations.map((r, i) => (
                <li key={i} className={`rec-${r.type}`}>
                  <strong>{r.title}</strong>: {r.detail}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </section>

      <section className="card">
        <h2>{stepNum("Fill")}) Fill Form</h2>
        <button disabled={busy || !runId} onClick={onFill} className="btn-primary">
          Run Form Filler Agent
        </button>
        {runId && runState?.completed_pdf_path ? (
          <a href={downloadUrl(runId)} target="_blank" rel="noreferrer">
            Download Completed PDF
          </a>
        ) : null}
      </section>

      <section className="card">
        <h2>{stepNum("Submit")}) Submit</h2>
        <label>
          Email (optional)
          <input value={emailTo} onChange={(e) => setEmailTo(e.target.value)} placeholder="recipient@example.com" />
        </label>
        <label>
          Webhook URL (optional)
          <input value={webhookUrl} onChange={(e) => setWebhookUrl(e.target.value)} placeholder="http://localhost:9000/hook" />
        </label>
        <button disabled={busy || !runId} onClick={onSubmit} className="btn-primary">
          Submit Completed Form
        </button>
      </section>

      <section className="card">
        <h2>Execution Logs</h2>
        <pre>{logs.join("\n")}</pre>
      </section>
    </main>
  );
}
