import { useState } from "react";
import { getRecommendation, type Question, type QuestionnaireResult } from "../lib/questionnaire";

type Props = {
  onComplete: (result: QuestionnaireResult) => void;
};

export function QuestionnaireWizard({ onComplete }: Props) {
  const [step, setStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const questions: Question[] = [
    {
      id: "filingStatus",
      title: "What is your filing status?",
      type: "single",
      options: [
        { value: "Single", label: "Single" },
        { value: "Married Filing Jointly", label: "Married filing jointly" },
        { value: "Married Filing Separately", label: "Married filing separately" },
        { value: "Head of Household", label: "Head of household" },
        { value: "Qualifying Surviving Spouse", label: "Qualifying surviving spouse" },
      ],
    },
    {
      id: "incomeTypes",
      title: "What types of income do you have?",
      description: "Select all that apply",
      type: "multi",
      options: [
        { value: "w2", label: "W-2 wages (employer)" },
        { value: "1099", label: "1099 (contractor, interest, dividends)" },
        { value: "self", label: "Self-employment / business" },
        { value: "rental", label: "Rental income" },
        { value: "investments", label: "Investments (stocks, capital gains)" },
        { value: "retirement", label: "Retirement / pension / Social Security" },
      ],
    },
    {
      id: "useItemized",
      title: "Do you want to itemize deductions?",
      description: "Itemizing often benefits those with high medical costs, mortgage interest, or charitable gifts",
      type: "yesno",
    },
    {
      id: "hasMedicalExpenses",
      title: "Do you have significant medical expenses?",
      description: "e.g. home modifications, equipment, premiums over 7.5% of income",
      type: "yesno",
    },
    {
      id: "hasMortgageInterest",
      title: "Do you pay mortgage interest or property taxes?",
      type: "yesno",
    },
    {
      id: "hasCharitableGifts",
      title: "Do you make charitable donations?",
      type: "yesno",
    },
    {
      id: "hasChildren",
      title: "Do you have qualifying children or dependents?",
      description: "For Child Tax Credit or Earned Income Credit",
      type: "yesno",
    },
    {
      id: "hasDependentCare",
      title: "Did you pay for child or dependent care to work?",
      type: "yesno",
    },
    {
      id: "isElderlyOrDisabled",
      title: "Are you 65+ or retired on permanent disability?",
      description: "May qualify for Credit for Elderly or Disabled",
      type: "yesno",
    },
  ];

  const q = questions[step];
  const progress = ((step + 1) / questions.length) * 100;
  const isLast = step === questions.length - 1;

  const setAnswer = (key: string, value: unknown) => {
    setAnswers((a) => ({ ...a, [key]: value }));
  };

  const handleNext = () => {
    if (isLast) {
      const result = getRecommendation(answers);
      onComplete(result);
    } else {
      setStep((s) => s + 1);
    }
  };

  const handleBack = () => setStep((s) => Math.max(0, s - 1));

  const canNext = () => {
    const v = answers[q.id];
    if (q.type === "single" || q.type === "yesno") return v !== undefined && v !== null;
    if (q.type === "multi") return Array.isArray(v) && v.length > 0;
    return false;
  };

  return (
    <div className="questionnaire">
      <div className="progress-bar">
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>
      <p className="progress-text">
        Question {step + 1} of {questions.length}
      </p>
      <div className="question-card">
        <h2 className="question-title">{q.title}</h2>
        {q.description && <p className="question-desc">{q.description}</p>}
        <div className="question-options">
          {q.type === "yesno" && (
            <select
              value={answers[q.id] === true ? "yes" : answers[q.id] === false ? "no" : ""}
              onChange={(e) => setAnswer(q.id, e.target.value === "yes")}
              className="question-select"
            >
              <option value="">Choose...</option>
              <option value="yes">Yes</option>
              <option value="no">No</option>
            </select>
          )}
          {q.type === "single" && (
            <select
              value={String(answers[q.id] ?? "")}
              onChange={(e) => setAnswer(q.id, e.target.value)}
              className="question-select"
            >
              <option value="">Choose...</option>
              {q.options?.map((opt) => (
                <option key={opt.value} value={opt.value}>{opt.label}</option>
              ))}
            </select>
          )}
          {q.type === "multi" &&
            q.options?.map((opt) => {
              const arr = (answers[q.id] as string[]) || [];
              const checked = arr.includes(opt.value);
              return (
                <label key={opt.value} className="option-check">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => {
                      setAnswer(
                        q.id,
                        checked ? arr.filter((x) => x !== opt.value) : [...arr, opt.value]
                      );
                    }}
                  />
                  {opt.label}
                </label>
              );
            })}
        </div>
        <div className="question-actions">
          <button type="button" className="btn-outline" onClick={handleBack} disabled={step === 0}>
            Back
          </button>
          <button type="button" className="btn-primary" onClick={handleNext} disabled={!canNext()}>
            {isLast ? "Get my filing plan" : "Continue"}
          </button>
        </div>
      </div>
    </div>
  );
}
