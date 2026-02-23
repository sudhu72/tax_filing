import type { FieldEntry } from "../services/api";

type ReviewEditorProps = {
  fields: FieldEntry[];
  onChange: (fields: FieldEntry[]) => void;
};

export function ReviewEditor({ fields, onChange }: ReviewEditorProps) {
  const updateField = (
    index: number,
    key: "key" | "value" | "description" | "target_field_name",
    value: string
  ) => {
    const next = [...fields];
    next[index] = { ...next[index], [key]: value };
    onChange(next);
  };

  if (fields.length === 0) {
    return <p>No transformed fields yet. Run OCR + transform first.</p>;
  }

  return (
    <div className="review-grid">
      {fields.map((field, idx) => (
        <div className="field-card" key={`${field.key}-${idx}`}>
          <label>
            Key
            <input value={field.key} onChange={(e) => updateField(idx, "key", e.target.value)} />
          </label>
          <label>
            Value
            <input value={field.value} onChange={(e) => updateField(idx, "value", e.target.value)} />
          </label>
          <label>
            Description
            <input value={field.description} onChange={(e) => updateField(idx, "description", e.target.value)} />
          </label>
          <label>
            Target PDF Field (optional)
            <input
              value={field.target_field_name ?? ""}
              onChange={(e) => updateField(idx, "target_field_name", e.target.value)}
            />
          </label>
          <small>Confidence: {field.confidence.toFixed(2)}</small>
          {field.source_excerpt ? <small>Source: {field.source_excerpt}</small> : null}
        </div>
      ))}
    </div>
  );
}
