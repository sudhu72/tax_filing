import { useState } from "react";
import { WizardPage } from "./pages/WizardPage";
import { QuestionnaireWizard } from "./components/QuestionnaireWizard";
import { FilingPlanSummary } from "./components/FilingPlanSummary";
import { AGICalculator } from "./components/AGICalculator";
import { DocumentIntake } from "./components/DocumentIntake";
import type { QuestionnaireResult } from "./lib/questionnaire";
import "./styles.css";

type Phase = "questionnaire" | "plan" | "wizard" | "agi" | "docs";

export default function App() {
  const [phase, setPhase] = useState<Phase>("questionnaire");
  const [questionnaireResult, setQuestionnaireResult] = useState<QuestionnaireResult | null>(null);
  const [agiPrefill, setAgiPrefill] = useState<Record<string, number> | null>(null);

  const onQuestionnaireComplete = (result: QuestionnaireResult) => {
    setQuestionnaireResult(result);
    setPhase("plan");
  };

  const onPlanContinue = () => {
    setPhase("wizard");
  };

  return (
    <div className="app">
      <header className="app-header">
        <div className="header-inner">
          <h1 className="logo">TaxPro</h1>
          <span className="tagline">Smart Tax Filing Assistant</span>
          <nav className="header-nav">
            <button
              type="button"
              className={`nav-link ${phase === "docs" ? "active" : ""}`}
              onClick={() => setPhase("docs")}
            >
              Upload Docs
            </button>
            <button
              type="button"
              className={`nav-link ${phase === "agi" ? "active" : ""}`}
              onClick={() => { setAgiPrefill(null); setPhase("agi"); }}
            >
              AGI Calculator
            </button>
            <button
              type="button"
              className={`nav-link ${phase !== "agi" && phase !== "docs" ? "active" : ""}`}
              onClick={() => setPhase(questionnaireResult ? "wizard" : "questionnaire")}
            >
              File Taxes
            </button>
          </nav>
        </div>
      </header>
      <div className="app-body">
        {phase === "docs" && (
          <div className="phase-container phase-container-wide">
            <DocumentIntake
              onUseInAGICalculator={(fields) => {
                setAgiPrefill(fields);
                setPhase("agi");
              }}
            />
          </div>
        )}
        {phase === "agi" && (
          <div className="phase-container phase-container-wide">
            <AGICalculator initialValues={agiPrefill ?? undefined} />
          </div>
        )}
        {phase === "questionnaire" && (
          <div className="phase-container">
            <div className="phase-intro">
              <h2>Let&apos;s find the right forms for you</h2>
              <p>Answer a few questions and we&apos;ll recommend the right forms and credits.</p>
            </div>
            <QuestionnaireWizard onComplete={onQuestionnaireComplete} />
          </div>
        )}
        {phase === "plan" && questionnaireResult && (
          <div className="phase-container">
            <FilingPlanSummary result={questionnaireResult} onContinue={onPlanContinue} />
          </div>
        )}
        {phase === "wizard" && questionnaireResult && (
          <WizardPage questionnaireResult={questionnaireResult} />
        )}
      </div>
    </div>
  );
}
