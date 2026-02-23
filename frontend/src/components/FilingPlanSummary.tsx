import type { QuestionnaireResult } from "../lib/questionnaire";

type Props = {
  result: QuestionnaireResult;
  onContinue: () => void;
};

export function FilingPlanSummary({ result, onContinue }: Props) {
  const formLabels: Record<string, string> = {
    f1040: "Form 1040",
    f1040sa: "Schedule A (Itemized Deductions)",
    f1040sc: "Schedule C (Self-Employment)",
    f1040se: "Schedule E (Rental)",
    f1040sd: "Schedule D (Capital Gains)",
  };
  const suggestedLabels = result.suggestedForms.map((id) => formLabels[id] ?? id);

  return (
    <div className="filing-plan">
      <h2>Your Filing Plan</h2>
      <p className="filing-plan-desc">
        Based on your answers, we&apos;ve prepared the right forms and workflow for you.
      </p>
      <div className="filing-plan-grid">
        <div className="plan-card">
          <h3>Primary Form</h3>
          <p className="plan-value">{formLabels[result.irsFormId] ?? result.irsFormId}</p>
        </div>
        <div className="plan-card">
          <h3>Suggested Forms</h3>
          <ul>
            {suggestedLabels.map((l) => (
              <li key={l}>{l}</li>
            ))}
          </ul>
        </div>
        <div className="plan-card">
          <h3>Credits Pre-filled</h3>
          <ul>
            {result.creditDefaults.num_qualifying_children > 0 && (
              <li>Qualifying children: {result.creditDefaults.num_qualifying_children}</li>
            )}
            {result.creditDefaults.num_dependents_under_17 > 0 && (
              <li>Dependents under 17: {result.creditDefaults.num_dependents_under_17}</li>
            )}
            {result.creditDefaults.dependent_care_expenses > 0 && (
              <li>Dependent care: ${result.creditDefaults.dependent_care_expenses.toLocaleString()}</li>
            )}
            {result.creditDefaults.elderly_or_disabled && (
              <li>Elderly or disabled credit</li>
            )}
            {result.creditDefaults.num_qualifying_children === 0 &&
              result.creditDefaults.num_dependents_under_17 === 0 &&
              result.creditDefaults.dependent_care_expenses === 0 &&
              !result.creditDefaults.elderly_or_disabled && <li>None pre-filled (you can add later)</li>}
          </ul>
        </div>
        {result.showInstructionsStep && (
          <div className="plan-card plan-note">
            <h3>Note</h3>
            <p>We&apos;ll load IRS instructions for itemized or complex filing to guide you.</p>
          </div>
        )}
      </div>
      <button type="button" className="btn-primary btn-large" onClick={onContinue}>
        Start Filing
      </button>
    </div>
  );
}
