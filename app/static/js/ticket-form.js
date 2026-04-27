const templateSelect = document.querySelector("#template");
const description = document.querySelector("#description");
if (templateSelect && description) {
  templateSelect.addEventListener("change", () => {
    const option = templateSelect.selectedOptions[0];
    const body = option ? option.dataset.body : "";
    if (body && !description.value.trim()) description.value = body;
  });
}
