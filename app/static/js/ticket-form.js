const templateSelect = document.querySelector("#template");
const description = document.querySelector("#description");
const titleInput = document.querySelector("#title");
const areaSelect = document.querySelector("#responsibleArea");
const subtypeSelect = document.querySelector("#subtype");
const applyTemplateButton = document.querySelector("#applyTemplate");
const templateHelp = document.querySelector("#templateHelp");
const typeRadios = Array.from(document.querySelectorAll("input[name='ticket_type']"));

function selectedType() {
  const selected = typeRadios.find((radio) => radio.checked);
  return selected ? selected.value : "";
}

function setSelectedType(value) {
  const radio = typeRadios.find((item) => item.value === value);
  if (radio) radio.checked = true;
}

function fillDescriptionFromTemplate(force = false) {
  if (!templateSelect || !description) return;
  const option = templateSelect.selectedOptions[0];
  if (!option || !option.value) return;

  const body = option.dataset.body || "";
  if (!body) return;

  if (force || !description.value.trim()) {
    description.value = body;
  }

  if (titleInput && !titleInput.value.trim()) {
    titleInput.value = option.textContent.replace(/^.*·\s*/, "").trim();
  }
}

function syncFieldsFromTemplate() {
  if (!templateSelect) return;
  const option = templateSelect.selectedOptions[0];
  if (!option || !option.value) {
    if (applyTemplateButton) applyTemplateButton.disabled = true;
    return;
  }

  if (option.dataset.type) setSelectedType(option.dataset.type);
  if (areaSelect && option.dataset.areaId) areaSelect.value = option.dataset.areaId;
  if (subtypeSelect && option.dataset.subtype) subtypeSelect.value = option.dataset.subtype;
  if (applyTemplateButton) applyTemplateButton.disabled = false;
  fillDescriptionFromTemplate(false);
}

function updateTemplateHelp() {
  if (!templateHelp || !templateSelect) return;
  const optionCount = Array.from(templateSelect.options).filter((option) => option.value).length;
  if (!optionCount) {
    templateHelp.textContent = "No hay plantillas activas cargadas.";
    return;
  }
  templateHelp.textContent = "Al elegir una plantilla se cargan automáticamente el área, tipo, subtipo y texto guía.";
}

if (templateSelect) {
  templateSelect.addEventListener("change", syncFieldsFromTemplate);
  updateTemplateHelp();
}

if (applyTemplateButton) {
  applyTemplateButton.addEventListener("click", () => fillDescriptionFromTemplate(true));
}
