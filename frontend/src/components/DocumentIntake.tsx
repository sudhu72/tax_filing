import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getDocumentFeedbackStats,
  processDocuments,
  submitDocumentFeedback,
  testDocument,
  type ClassifiedDoc,
  type DocumentFeedbackStats,
  type DocumentIntakeResult,
  type DocumentTestResult,
} from "../services/api";

const ACCEPT = ".pdf,.png,.jpg,.jpeg,.gif,.webp,.xlsx,.xls";
const MAX_SIZE_MB = 20;
const DOC_TYPE_OPTIONS = [
  "W-2",
  "1099-INT",
  "1099-DIV",
  "1099-R",
  "SSA-1099",
  "1099-B",
  "1099-NEC",
  "1098-E",
  "Medical/Receipt",
  "Government ID",
  "Unknown",
];

type Props = {
  onUseInAGICalculator?: (mergedFields: Record<string, number>) => void;
};

export function DocumentIntake({ onUseInAGICalculator }: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const [result, setResult] = useState<DocumentIntakeResult | null>(null);
  const [testFile, setTestFile] = useState<File | null>(null);
  const [testResult, setTestResult] = useState<DocumentTestResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [testBusy, setTestBusy] = useState(false);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [showSnippet, setShowSnippet] = useState(false);
  const [testOverrideType, setTestOverrideType] = useState<string>("Unknown");
  const [feedbackBusy, setFeedbackBusy] = useState(false);
  const [feedbackMessage, setFeedbackMessage] = useState("");
  const [feedbackStats, setFeedbackStats] = useState<DocumentFeedbackStats | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const selected = Array.from(e.target.files ?? []);
    setFiles((prev) => [...prev, ...selected].slice(0, 50));
    setResult(null);
    setError("");
  };

  const removeFile = (index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
    setResult(null);
  };

  const handleTestFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0] ?? null;
    setTestFile(f);
    setTestResult(null);
    setError("");
  };

  const handleProcess = async () => {
    if (files.length === 0) {
      setError("Add at least one file.");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const res = await processDocuments(files);
      setResult(res);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Processing failed");
    } finally {
      setBusy(false);
    }
  };

  const handleTestDocument = async () => {
    if (!testFile) {
      setError("Choose one file to test.");
      return;
    }
    setTestBusy(true);
    setError("");
    try {
      const res = await testDocument(testFile);
      setTestResult(res);
      setTestOverrideType(res.document.doc_type);
      setShowSnippet(false);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test failed");
    } finally {
      setTestBusy(false);
    }
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = Array.from(e.dataTransfer.files).filter((f) => {
      const ext = "." + f.name.split(".").pop()?.toLowerCase();
      return [".pdf", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".xlsx", ".xls"].includes(ext);
    });
    setFiles((prev) => [...prev, ...dropped].slice(0, 50));
    setResult(null);
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  }, []);

  const handleDragLeave = useCallback(() => setDragOver(false), []);

  const useInAGI = () => {
    if (result?.merged_fields && onUseInAGICalculator) {
      onUseInAGICalculator(result.merged_fields);
    }
  };

  const sortedScores = useMemo(() => {
    if (!testResult?.document.score_breakdown) return [];
    return Object.entries(testResult.document.score_breakdown).sort((a, b) => b[1] - a[1]);
  }, [testResult]);

  const loadFeedbackStats = useCallback(async () => {
    try {
      const stats = await getDocumentFeedbackStats();
      setFeedbackStats(stats);
    } catch {
      // Stats are auxiliary; ignore fetch failures.
    }
  }, []);

  useEffect(() => {
    void loadFeedbackStats();
  }, [loadFeedbackStats]);

  const sendFeedback = async (doc: ClassifiedDoc, correctedType: string, accepted: boolean) => {
    setFeedbackBusy(true);
    setFeedbackMessage("");
    try {
      const res = await submitDocumentFeedback({
        filename: doc.filename,
        predicted_doc_type: doc.doc_type,
        corrected_doc_type: correctedType,
        raw_snippet: doc.raw_snippet ?? "",
        accepted,
      });
      setFeedbackMessage(res.message);
      await loadFeedbackStats();
    } catch (err) {
      setFeedbackMessage(err instanceof Error ? err.message : "Failed to save feedback");
    } finally {
      setFeedbackBusy(false);
    }
  };

  return (
    <div className="document-intake">
      <div className="doc-intro">
        <h2>Upload Documents &amp; Receipts</h2>
        <p>
          Upload W-2s, 1099s, medical receipts, and other tax documents. The agent will classify
          each file and extract values for your tax forms. Supports PDF, Excel (.xlsx, .xls), and
          images (PNG, JPG, etc.).
        </p>
      </div>

      <div className="doc-tester card-lite">
        <h3>Document Tester (single file)</h3>
        <p>Upload one document to see classification confidence, tax-relevant fields, and extraction details.</p>
        <label className="doc-test-upload">
          Choose document
          <input type="file" accept={ACCEPT} onChange={handleTestFileChange} />
        </label>
        {testFile && <p className="doc-test-file">Selected: {testFile.name}</p>}
        <button type="button" className="btn-primary" onClick={handleTestDocument} disabled={testBusy}>
          {testBusy ? "Testing..." : "Test document"}
        </button>

        {testResult && (
          <div className="doc-test-results">
            <h4>Classification result</h4>
            <p>
              <strong>Type:</strong> {testResult.document.doc_type}{" "}
              <span className="doc-card-conf">({(testResult.document.confidence * 100).toFixed(0)}%)</span>
            </p>
            {testResult.document.message && <p className="doc-card-msg">{testResult.document.message}</p>}
            <div className="doc-feedback-controls">
              <label>
                Correct type
                <select
                  value={testOverrideType}
                  onChange={(e) => setTestOverrideType(e.target.value)}
                >
                  {DOC_TYPE_OPTIONS.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                className="btn-outline"
                disabled={feedbackBusy}
                onClick={() => sendFeedback(testResult.document, testResult.document.doc_type, true)}
              >
                Approve
              </button>
              <button
                type="button"
                className="btn-primary"
                disabled={feedbackBusy}
                onClick={() => sendFeedback(testResult.document, testOverrideType, false)}
              >
                Save correction
              </button>
            </div>
            {feedbackMessage ? <p className="doc-feedback-msg">{feedbackMessage}</p> : null}

            <h5>Tax-relevant fields</h5>
            {testResult.tax_relevant_fields.length > 0 ? (
              <ul>
                {testResult.tax_relevant_fields.map((k) => {
                  const v = testResult.document.extracted_fields[k];
                  return (
                    <li key={k}>
                      {k.replace(/_/g, " ")}: {typeof v === "number" ? `$${v.toLocaleString()}` : String(v)}
                    </li>
                  );
                })}
              </ul>
            ) : (
              <p>No tax-relevant fields extracted.</p>
            )}

            {sortedScores.length > 0 && (
              <>
                <h5>Model scores</h5>
                <div className="score-grid">
                  {sortedScores.map(([name, score]) => (
                    <div key={name} className="score-item">
                      <span>{name}</span>
                      <span>{Math.round(score * 100)}%</span>
                    </div>
                  ))}
                </div>
              </>
            )}

            {testResult.document.raw_snippet && (
              <>
                <button type="button" className="btn-outline" onClick={() => setShowSnippet((s) => !s)}>
                  {showSnippet ? "Hide" : "Show"} OCR snippet
                </button>
                {showSnippet && <pre className="doc-snippet">{testResult.document.raw_snippet}</pre>}
              </>
            )}
          </div>
        )}
      </div>

      <div className="card-lite doc-feedback-stats">
        <h3>Feedback analytics</h3>
        <p>Classifier learning progress from approve/correct actions.</p>
        <div className="stats-inline">
          <span className="stats-pill">
            Total feedback: <strong>{feedbackStats?.feedback_count ?? 0}</strong>
          </span>
          <button type="button" className="btn-outline" onClick={() => void loadFeedbackStats()}>
            Refresh stats
          </button>
        </div>

        <div className="stats-grid">
          <div>
            <h5>Top confusion corrections</h5>
            {feedbackStats?.top_confusions?.length ? (
              <ul>
                {feedbackStats.top_confusions.map((r, idx) => (
                  <li key={`${r.predicted}-${r.corrected}-${idx}`}>
                    {r.predicted} → {r.corrected} ({r.count})
                  </li>
                ))}
              </ul>
            ) : (
              <p>No confusion data yet.</p>
            )}
          </div>
          <div>
            <h5>Most reinforced classes</h5>
            {feedbackStats?.top_classes?.length ? (
              <ul>
                {feedbackStats.top_classes.map((r) => (
                  <li key={r.doc_type}>
                    {r.doc_type} ({r.count})
                  </li>
                ))}
              </ul>
            ) : (
              <p>No class reinforcement data yet.</p>
            )}
          </div>
        </div>
      </div>

      <div
        className={`doc-dropzone ${dragOver ? "drag-over" : ""}`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        <input
          type="file"
          id="doc-upload"
          accept={ACCEPT}
          multiple
          onChange={handleFileChange}
          className="doc-input-hidden"
        />
        <label htmlFor="doc-upload" className="doc-drop-label">
          <span className="doc-drop-icon">📄</span>
          <span>Drop files here or click to browse</span>
          <span className="doc-drop-hint">PDF, Excel, PNG, JPG (max {MAX_SIZE_MB} MB each)</span>
        </label>
      </div>

      {files.length > 0 && (
        <div className="doc-file-list">
          <h4>Selected files ({files.length})</h4>
          <ul>
            {files.map((f, i) => (
              <li key={`${f.name}-${i}`}>
                <span className="doc-filename">{f.name}</span>
                <button type="button" className="doc-remove" onClick={() => removeFile(i)} aria-label="Remove">
                  ×
                </button>
              </li>
            ))}
          </ul>
          <button
            type="button"
            className="btn-primary"
            onClick={handleProcess}
            disabled={busy}
          >
            {busy ? "Processing..." : "Process Documents"}
          </button>
        </div>
      )}

      {error && <p className="error">{error}</p>}

      {result && (
        <div className="doc-results">
          <h3>Results</h3>
          <p className="doc-message">{result.message}</p>

          <div className="doc-classified">
            <h4>Documents classified</h4>
            {result.documents.map((d, i) => (
              <DocCard
                key={i}
                doc={d}
                onFeedback={(corrected, accepted) => sendFeedback(d, corrected, accepted)}
              />
            ))}
          </div>

          {Object.keys(result.merged_fields).length > 0 && (
            <div className="doc-merged">
              <h4>Extracted values (merged)</h4>
              <div className="doc-merged-grid">
                {Object.entries(result.merged_fields).map(([key, val]) => (
                  <div key={key} className="doc-merged-item">
                    <span className="doc-merged-key">{key.replace(/_/g, " ")}</span>
                    <span className="doc-merged-val">${Number(val).toLocaleString()}</span>
                  </div>
                ))}
              </div>
              {onUseInAGICalculator && (
                <button type="button" className="btn-primary" onClick={useInAGI}>
                  Use in AGI Calculator
                </button>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function DocCard({
  doc,
  onFeedback,
}: {
  doc: ClassifiedDoc;
  onFeedback?: (correctedType: string, accepted: boolean) => Promise<void> | void;
}) {
  const [expanded, setExpanded] = useState(false);
  const [correctedType, setCorrectedType] = useState(doc.doc_type);
  const hasFields = Object.keys(doc.extracted_fields).length > 0;
  const isSkipped = doc.doc_type === "Skipped" || doc.doc_type === "Error";

  return (
    <div className={`doc-card ${isSkipped ? "doc-card-skipped" : ""}`}>
      <div className="doc-card-header" onClick={() => setExpanded(!expanded)}>
        <span className="doc-card-filename">{doc.filename}</span>
        <span className={`doc-card-type doc-type-${doc.doc_type.replace(/[/\s]/g, "-").toLowerCase()}`}>
          {doc.doc_type}
        </span>
        {!isSkipped && (
          <span className="doc-card-conf">{(doc.confidence * 100).toFixed(0)}%</span>
        )}
      </div>
      {doc.message && <p className="doc-card-msg">{doc.message}</p>}
      {!isSkipped && onFeedback ? (
        <div className="doc-card-feedback">
          <select value={correctedType} onChange={(e) => setCorrectedType(e.target.value)}>
            {DOC_TYPE_OPTIONS.map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
          <button type="button" className="btn-outline" onClick={() => onFeedback(doc.doc_type, true)}>
            Approve
          </button>
          <button type="button" className="btn-primary" onClick={() => onFeedback(correctedType, false)}>
            Correct
          </button>
        </div>
      ) : null}
      {hasFields && expanded && (
        <div className="doc-card-fields">
          {Object.entries(doc.extracted_fields).map(([k, v]) => (
            <div key={k}>
              {k.replace(/_/g, " ")}: {typeof v === "number" ? `$${v.toLocaleString()}` : v}
            </div>
          ))}
        </div>
      )}
      {hasFields && !expanded && (
        <button type="button" className="doc-card-toggle" onClick={() => setExpanded(true)}>
          Show extracted values
        </button>
      )}
    </div>
  );
}
