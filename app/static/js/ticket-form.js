const ticketForm = document.querySelector("#ticket-form");
const templateSelect = document.querySelector("#template");
const description = document.querySelector("#description");
const structuredPanel = document.querySelector("#structured-panel");
const structuredFields = document.querySelector("#structured-fields");
const responsibleAreaWrap = document.querySelector("#responsible-area-wrap");
const responsibleAreaSelect = document.querySelector("#responsible_area_id");
const contextTitle = document.querySelector("#ticket-context-title");
const dueAtWrap = document.querySelector("#due-at-wrap");
const dueAtInput = document.querySelector("#due_at");
const userAreaId = ticketForm ? ticketForm.dataset.userAreaId : "";

function safeJson(value, fallback) {
  try { return JSON.parse(value || "{}"); } catch (err) { return fallback; }
}

function setSelectValue(selector, value) {
  const el = document.querySelector(selector);
  if (el && value) el.value = value;
}

function selectedTicketType() {
  const radio = document.querySelector('input[name="ticket_type"]:checked');
  return radio ? radio.value : "";
}

function setTicketType(value) {
  if (!value) return;
  const radio = document.querySelector(`input[name="ticket_type"][value="${CSS.escape(value)}"]`);
  if (radio) {
    radio.checked = true;
    updateTicketContext();
  }
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

function updateTicketContext() {
  const type = selectedTicketType();
  const isChange = type === "Registro de cambio";
  const isRequest = type === "Solicitud de intervención";

  if (contextTitle) contextTitle.textContent = isRequest ? "Área responsable y plantilla" : "Plantilla del registro";
  if (responsibleAreaWrap) responsibleAreaWrap.classList.toggle("d-none", !isRequest);
  if (responsibleAreaSelect) {
    responsibleAreaSelect.required = isRequest;
    if (isChange && userAreaId) responsibleAreaSelect.value = userAreaId;
  }
  if (dueAtWrap) dueAtWrap.classList.toggle("d-none", !isChange);
  if (dueAtInput && !isChange) dueAtInput.value = "";
}

document.querySelectorAll('input[name="ticket_type"]').forEach(radio => {
  radio.addEventListener("change", updateTicketContext);
});

if (templateSelect) {
  templateSelect.addEventListener("change", () => {
    const option = templateSelect.selectedOptions[0];
    if (!option || !option.value) {
      renderStructuredFields({ fields: [] });
      updateTicketContext();
      return;
    }
    setTicketType(option.dataset.type);
    if (selectedTicketType() === "Solicitud de intervención") setSelectValue("#responsible_area_id", option.dataset.area);
    else if (userAreaId) setSelectValue("#responsible_area_id", userAreaId);
    setSelectValue("#subtype", option.dataset.subtype);
    const schema = safeJson(option.dataset.schema, { fields: [] });
    renderStructuredFields(schema);
    if (description && option.dataset.body && !description.value.trim() && (!schema.fields || schema.fields.length === 0)) description.value = option.dataset.body;
    updateTicketContext();
  });
}

updateTicketContext();
