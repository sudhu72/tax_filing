import { useEffect, useState } from "react";
import { calculateAGI, type AGICalculatorResult, type AGIInputs } from "../services/api";

type Props = {
  initialValues?: Record<string, number>;
};

const INCOME_FIELDS: { key: keyof AGIInputs; label: string; docHint: string }[] = [
  { key: "wages", label: "Wages, salaries, tips (W-2 box 1)", docHint: "W-2" },
  { key: "taxable_interest", label: "Taxable interest", docHint: "1099-INT" },
  { key: "ordinary_dividends", label: "Ordinary dividends", docHint: "1099-DIV" },
  { key: "taxable_ira", label: "Taxable IRA distributions", docHint: "1099-R" },
  { key: "taxable_pension", label: "Taxable pensions/annuities", docHint: "1099-R" },
  { key: "taxable_social_security", label: "Taxable Social Security", docHint: "SSA-1099" },
  { key: "capital_gain_loss", label: "Capital gains or losses (net)", docHint: "1099-B, Schedule D" },
  { key: "sch_c_income", label: "Self-employment income (Schedule C)", docHint: "1099-NEC" },
  { key: "other_income", label: "Other income", docHint: "1099-MISC, etc." }
];

const ADJUSTMENT_FIELDS: { key: keyof AGIInputs; label: string; docHint: string }[] = [
  { key: "educator_expenses", label: "Educator expenses", docHint: "School receipts" },
  { key: "ira_deduction", label: "IRA deduction", docHint: "Form 5498" },
  { key: "student_loan_interest", label: "Student loan interest", docHint: "1098-E" },
  { key: "other_adjustments", label: "Other adjustments", docHint: "HSA, etc." }
];

export function AGICalculator({ initialValues }: Props) {
  const [inputs, setInputs] = useState<AGIInputs>({
    filing_status: "Single",
    wages: 0,
    taxable_interest: 0,
    ordinary_dividends: 0,
    taxable_ira: 0,
    taxable_pension: 0,
    taxable_social_security: 0,
    capital_gain_loss: 0,
    sch_c_income: 0,
    other_income: 0,
    educator_expenses: 0,
    ira_deduction: 0,
    student_loan_interest: 0,
    other_adjustments: 0,
    medical_expenses: 0,
    medical_insurance_reimbursement: 0
  });

  useEffect(() => {
    if (initialValues && Object.keys(initialValues).length > 0) {
      setInputs((prev) => {
        const next = { ...prev };
        for (const [k, v] of Object.entries(initialValues)) {
          if (k in next && typeof v === "number") {
            (next as Record<string, number>)[k] = v;
          }
        }
        return next;
      });
    }
  }, [initialValues]);

  const [result, setResult] = useState<AGICalculatorResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [showDocs, setShowDocs] = useState(false);

  const setVal = (key: keyof AGIInputs, value: number) => {
    setInputs((p) => ({ ...p, [key]: value }));
    setResult(null);
  };

  const handleCalculate = async () => {
    setBusy(true);
    setError("");
    try {
      const res = await calculateAGI(inputs);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Calculation failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="agi-calculator">
      <div className="agi-intro">
        <h2>AGI &amp; Medical Deduction Calculator</h2>
        <p>
          Calculate your Adjusted Gross Income (AGI) and see if your disability-related medical
          expenses exceed 7.5% of AGI. Amounts above 7.5% are deductible on Schedule A if you itemize.
        </p>
        <p className="agi-doc-note">
          <strong>Documents beyond W-2:</strong> Use the checklist below to see which forms you need
          for each income line (1099-INT, 1099-DIV, 1099-R, SSA-1099, etc.).
        </p>
      </div>

      <div className="agi-form">
        <section className="agi-section">
          <h3>Income</h3>
          {INCOME_FIELDS.map(({ key, label, docHint }) => (
            <label key={key}>
              <span className="agi-label">{label} <span className="agi-doc-hint">({docHint})</span></span>
              <input
                type="number"
                value={(inputs[key] as number) || ""}
                onChange={(e) => setVal(key, parseFloat(e.target.value) || 0)}
                placeholder="0"
              />
            </label>
          ))}
        </section>

        <section className="agi-section">
          <h3>Adjustments to income</h3>
          {ADJUSTMENT_FIELDS.map(({ key, label, docHint }) => (
            <label key={key}>
              <span className="agi-label">{label} <span className="agi-doc-hint">({docHint})</span></span>
              <input
                type="number"
                value={(inputs[key] as number) || ""}
                onChange={(e) => setVal(key, parseFloat(e.target.value) || 0)}
                placeholder="0"
              />
            </label>
          ))}
        </section>

        <section className="agi-section agi-medical">
          <h3>Medical &amp; dental expenses</h3>
          <p className="agi-section-desc">
            Disability-related: equipment, home modifications, premiums, prescriptions, etc.
          </p>
          <label>
            <span className="agi-label">Total medical expenses (before reimbursement)</span>
            <input
              type="number"
              value={inputs.medical_expenses || ""}
              onChange={(e) => setVal("medical_expenses", parseFloat(e.target.value) || 0)}
              placeholder="0"
            />
          </label>
          <label>
            <span className="agi-label">Insurance or other reimbursement</span>
            <input
              type="number"
              value={inputs.medical_insurance_reimbursement || ""}
              onChange={(e) => setVal("medical_insurance_reimbursement", parseFloat(e.target.value) || 0)}
              placeholder="0"
            />
          </label>
        </section>

        {error ? <p className="error">{error}</p> : null}
        <button type="button" className="btn-primary" onClick={handleCalculate} disabled={busy}>
          {busy ? "Calculating..." : "Calculate AGI & Medical Deduction"}
        </button>
      </div>

      {result && (
        <div className="agi-results">
          <h3>Results</h3>
          <div className="agi-results-grid">
            <div className="agi-result-card">
              <span className="agi-result-label">Total income</span>
              <span className="agi-result-value">${result.total_income.toLocaleString()}</span>
            </div>
            <div className="agi-result-card">
              <span className="agi-result-label">Adjustments</span>
              <span className="agi-result-value">${result.adjustments.toLocaleString()}</span>
            </div>
            <div className="agi-result-card agi-highlight">
              <span className="agi-result-label">AGI</span>
              <span className="agi-result-value">${result.agi.toLocaleString()}</span>
            </div>
            <div className="agi-result-card">
              <span className="agi-result-label">7.5% of AGI (medical floor)</span>
              <span className="agi-result-value">${result.medical_7p5_threshold.toLocaleString()}</span>
            </div>
            <div className="agi-result-card">
              <span className="agi-result-label">Medical expenses (net)</span>
              <span className="agi-result-value">${result.medical_expenses_net.toLocaleString()}</span>
            </div>
            <div className={`agi-result-card ${result.medical_exceeds_threshold ? "agi-success" : ""}`}>
              <span className="agi-result-label">Deductible medical (above 7.5%)</span>
              <span className="agi-result-value">${result.medical_deductible.toLocaleString()}</span>
            </div>
          </div>
          {result.message && <p className="agi-message">{result.message}</p>}
          <button
            type="button"
            className="btn-outline"
            onClick={() => setShowDocs(!showDocs)}
          >
            {showDocs ? "Hide" : "Show"} documents checklist
          </button>
          {showDocs && (
            <div className="agi-docs">
              <h4>Documents needed for AGI</h4>
              <ul>
                {result.document_sources
                  .filter((d) => d.value > 0 || d.line === "medical_expenses")
                  .map((d) => (
                    <li key={d.line}>
                      <strong>{d.description}</strong>
                      {d.value > 0 && (
                        <span className="agi-doc-value"> — ${d.value.toLocaleString()}</span>
                      )}
                      <ul>
                        {d.documents.map((doc) => (
                          <li key={doc}>{doc}</li>
                        ))}
                      </ul>
                    </li>
                  ))}
              </ul>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
