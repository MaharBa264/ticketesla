const templateSelect = document.querySelector("#template");
const description = document.querySelector("#description");
const structuredPanel = document.querySelector("#structured-panel");
const structuredFields = document.querySelector("#structured-fields");

function safeJson(value, fallback) {
  try { return JSON.parse(value || "{}"); } catch (err) { return fallback; }
}

function setSelectValue(selector, value) {
  const el = document.querySelector(selector);
  if (el && value) el.value = value;
}

function setTicketType(value) {
  if (!value) return;
  const radio = document.querySelector(`input[name="ticket_type"][value="${CSS.escape(value)}"]`);
  if (radio) radio.checked = true;
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>'"]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[ch]));
}

function fieldInput(field) {
  const name = `structured_${field.key}`;
  const required = field.required ? "required" : "";
  const placeholder = field.placeholder ? `placeholder="${escapeHtml(field.placeholder)}"` : "";
  const help = field.help ? `<div class="form-text">${escapeHtml(field.help)}</div>` : "";
  const label = `<label class="form-label">${escapeHtml(field.label)}${field.required ? " *" : ""}</label>`;
  if (field.type === "textarea") return `<div class="col-12">${label}<textarea class="form-control" name="${name}" rows="3" ${required} ${placeholder}></textarea>${help}</div>`;
  if (field.type === "select") {
    const options = (field.options || []).map(o => `<option value="${escapeHtml(o)}">${escapeHtml(o)}</option>`).join("");
    return `<div class="col-md-6">${label}<select class="form-select" name="${name}" ${required}><option value="">Seleccionar...</option>${options}</select>${help}</div>`;
  }
  if (field.type === "checkbox") return `<div class="col-md-6"><div class="form-check structured-check"><input class="form-check-input" type="checkbox" name="${name}" id="${name}"><label class="form-check-label" for="${name}">${escapeHtml(field.label)}</label></div>${help}</div>`;
  const type = ["number", "date", "datetime-local"].includes(field.type) ? field.type : "text";
  return `<div class="col-md-6">${label}<input class="form-control" type="${type}" name="${name}" ${required} ${placeholder}>${help}</div>`;
}

function renderStructuredFields(schema) {
  const fields = schema && Array.isArray(schema.fields) ? schema.fields : [];
  structuredFields.innerHTML = fields.map(fieldInput).join("");
  structuredPanel.classList.toggle("d-none", fields.length === 0);
}

if (templateSelect) {
  templateSelect.addEventListener("change", () => {
    const option = templateSelect.selectedOptions[0];
    if (!option || !option.value) {
      renderStructuredFields({ fields: [] });
      return;
    }
    setSelectValue("#responsible_area_id", option.dataset.area);
    setSelectValue("#subtype", option.dataset.subtype);
    setTicketType(option.dataset.type);
    const schema = safeJson(option.dataset.schema, { fields: [] });
    renderStructuredFields(schema);
    if (description && option.dataset.body && !description.value.trim() && (!schema.fields || schema.fields.length === 0)) description.value = option.dataset.body;
  });
}
