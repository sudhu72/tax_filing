import { useEffect, useState } from "react";
import { getIrsFormsList, irsFormDownloadUrl, type IrsForm } from "../services/api";

export function IrsFormsPanel() {
  const [forms, setForms] = useState<IrsForm[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(false);

  useEffect(() => {
    if (expanded && forms.length === 0 && !loading) {
      setLoading(true);
      setError("");
      getIrsFormsList()
        .then((res) => setForms(res.forms))
        .catch((e) => setError(e instanceof Error ? e.message : "Failed to load forms"))
        .finally(() => setLoading(false));
    }
  }, [expanded, forms.length, loading]);

  return (
    <div className="irs-forms-panel">
      <button
        type="button"
        className="toggle-btn"
        onClick={() => setExpanded(!expanded)}
        aria-expanded={expanded}
      >
        {expanded ? "Hide" : "Get"} latest IRS forms from irs.gov
      </button>
      {expanded && (
        <div className="irs-forms-content">
          <p className="irs-forms-desc">
            Download the latest tax form PDFs directly from the IRS. These are the current-year forms.
          </p>
          {error ? <p className="error">{error}</p> : null}
          {loading ? <p>Loading forms...</p> : null}
          {!loading && forms.length > 0 ? (
            <div className="irs-forms-grid">
              {forms.map((f) => (
                <div key={f.id} className="irs-form-card">
                  <span className="form-name">{f.name}</span>
                  <a
                    href={irsFormDownloadUrl(f.id)}
                    target="_blank"
                    rel="noreferrer"
                    className="download-link"
                  >
                    Download PDF
                  </a>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
