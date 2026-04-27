const container = document.querySelector("#template-fields");
const addButton = document.querySelector("[data-add-field]");

function parseJsonAttr(name, fallback) {
  if (!container) return fallback;
  try { return JSON.parse(container.dataset[name] || ""); } catch (err) { return fallback; }
}

const fieldTypes = parseJsonAttr("fieldTypes", [["text", "Texto corto"]]);
const existingFields = parseJsonAttr("existing", []);

function escapeHtml(value) {
  return String(value || "").replace(/[&<>'"]/g, ch => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[ch]));
}

function typeOptions(selected) {
  return fieldTypes.map(([value, label]) => `<option value="${escapeHtml(value)}" ${value === selected ? "selected" : ""}>${escapeHtml(label)}</option>`).join("");
}

function addField(field = {}) {
  if (!container) return;
  const index = container.querySelectorAll(".template-field-row").length;
  const row = document.createElement("div");
  row.className = "template-field-row";
  row.innerHTML = `
    <div class="row g-2 align-items-end">
      <div class="col-md-5"><label class="form-label">Etiqueta</label><input class="form-control" name="field_label[]" value="${escapeHtml(field.label || "")}" placeholder="Ej.: IP nueva" required></div>
      <div class="col-md-3"><label class="form-label">Tipo</label><select class="form-select" name="field_type[]">${typeOptions(field.type || "text")}</select></div>
      <div class="col-md-2"><label class="form-label">Clave</label><input class="form-control" name="field_key[]" value="${escapeHtml(field.key || "")}" placeholder="auto"></div>
      <div class="col-md-2"><div class="form-check mb-2"><input class="form-check-input" type="checkbox" name="field_required[]" value="${index}" ${field.required ? "checked" : ""}><label class="form-check-label">Obligatorio</label></div></div>
      <div class="col-md-6"><label class="form-label">Ayuda</label><input class="form-control" name="field_help[]" value="${escapeHtml(field.help || "")}" placeholder="Texto aclaratorio para el usuario"></div>
      <div class="col-md-6"><label class="form-label">Placeholder</label><input class="form-control" name="field_placeholder[]" value="${escapeHtml(field.placeholder || "")}" placeholder="Ej.: 192.168.1.10"></div>
      <div class="col-md-10"><label class="form-label">Opciones si es lista</label><input class="form-control" name="field_options[]" value="${escapeHtml((field.options || []).join(', '))}" placeholder="Una, Dos, Tres"></div>
      <div class="col-md-2 d-grid"><button class="btn btn-outline-danger" type="button" data-remove-field>Quitar</button></div>
    </div>`;
  container.appendChild(row);
}

if (addButton) addButton.addEventListener("click", () => addField());
if (container) {
  container.addEventListener("click", (event) => {
    if (event.target.matches("[data-remove-field]")) event.target.closest(".template-field-row").remove();
  });
  if (existingFields.length) existingFields.forEach(addField);
  else addField({ label: "", type: "text", required: true });
}
