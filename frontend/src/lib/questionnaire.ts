/**
 * Tax filing questionnaire: maps user answers to forms, schemas, and workflow.
 */
export type QuestionnaireAnswer = {
  filingStatus: string;
  incomeTypes: string[];
  useItemized: boolean;
  hasMedicalExpenses: boolean;
  hasMortgageInterest: boolean;
  hasCharitableGifts: boolean;
  hasChildren: boolean;
  hasDependentCare: boolean;
  isElderlyOrDisabled: boolean;
  hasSelfEmployment: boolean;
  hasInvestments: boolean;
};

export type QuestionnaireResult = {
  irsFormId: string;
  schemaName: string;
  formCodes: string[];
  showInstructionsStep: boolean;
  creditDefaults: {
    num_qualifying_children: number;
    num_dependents_under_17: number;
    dependent_care_expenses: number;
    num_dep_care_individuals: number;
    elderly_or_disabled: boolean;
    has_disability_income: boolean;
  };
  suggestedForms: string[];
};

export type Question = {
  id: string;
  title: string;
  description?: string;
  type: "single" | "multi" | "yesno";
  options?: { value: string; label: string }[];
};

export const QUESTIONS: Question[] = [
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

export function getRecommendation(answers: Partial<Record<string, unknown>>): QuestionnaireResult {
  const itemized = answers.useItemized === true || answers.useItemized === "yes";
  const hasMedical = answers.hasMedicalExpenses === true || answers.hasMedicalExpenses === "yes";
  const hasMortgage = answers.hasMortgageInterest === true || answers.hasMortgageInterest === "yes";
  const hasCharity = answers.hasCharitableGifts === true || answers.hasCharitableGifts === "yes";
  const hasChildren = answers.hasChildren === true || answers.hasChildren === "yes";
  const hasDepCare = answers.hasDependentCare === true || answers.hasDependentCare === "yes";
  const elderlyDisabled = answers.isElderlyOrDisabled === true || answers.isElderlyOrDisabled === "yes";
  const incomeTypes = (answers.incomeTypes as string[]) || [];
  const hasSelf = incomeTypes.includes("self");
  const hasRental = incomeTypes.includes("rental");
  const hasInvest = incomeTypes.includes("investments");

  const needsScheduleA = itemized && (hasMedical || hasMortgage || hasCharity);
  const irsFormId = needsScheduleA ? "f1040sa" : "f1040";
  const schemaName = needsScheduleA ? "schedule-a.yaml" : "form1040.yaml";
  const formCodes = needsScheduleA ? ["form-1040", "schedule-a-form-1040"] : ["form-1040"];
  const showInstructionsStep = needsScheduleA || hasSelf || hasRental || hasInvest;

  const suggestedForms: string[] = ["f1040"];
  if (needsScheduleA) suggestedForms.push("f1040sa");
  if (hasSelf) suggestedForms.push("f1040sc");
  if (hasRental) suggestedForms.push("f1040se");
  if (hasInvest) suggestedForms.push("f1040sd");

  return {
    irsFormId,
    schemaName,
    formCodes,
    showInstructionsStep,
    creditDefaults: {
      num_qualifying_children: hasChildren ? 1 : 0,
      num_dependents_under_17: hasChildren ? 1 : 0,
      dependent_care_expenses: hasDepCare ? 3000 : 0,
      num_dep_care_individuals: hasDepCare ? 1 : 0,
      elderly_or_disabled: elderlyDisabled,
      has_disability_income: elderlyDisabled,
    },
    suggestedForms,
  };
}
