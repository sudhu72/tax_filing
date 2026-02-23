import { useCallback, useState } from "react";
import { processDocuments, type ClassifiedDoc, type DocumentIntakeResult } from "../services/api";

const ACCEPT = ".pdf,.png,.jpg,.jpeg,.gif,.webp,.xlsx,.xls";
const MAX_SIZE_MB = 20;

type Props = {
  onUseInAGICalculator?: (mergedFields: Record<string, number>) => void;
};

export function DocumentIntake({ onUseInAGICalculator }: Props) {
  const [files, setFiles] = useState<File[]>([]);
  const [result, setResult] = useState<DocumentIntakeResult | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [dragOver, setDragOver] = useState(false);

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
              <DocCard key={i} doc={d} />
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

function DocCard({ doc }: { doc: ClassifiedDoc }) {
  const [expanded, setExpanded] = useState(false);
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
