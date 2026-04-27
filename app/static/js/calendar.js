const filters = document.getElementById("calendarFilters");
const prevBtn = document.getElementById("calendarPrev");
const nextBtn = document.getElementById("calendarNext");
const titleEl = document.getElementById("calendarRangeTitle");
const monthEls = [
  document.getElementById("calendarPrevMonth"),
  document.getElementById("calendarCurrentMonth"),
  document.getElementById("calendarNextMonth"),
];
let anchorDate = new Date();
let calendars = [];

function startOfMonth(date) {
  return new Date(date.getFullYear(), date.getMonth(), 1);
}

function addMonths(date, months) {
  return new Date(date.getFullYear(), date.getMonth() + months, 1);
}

function monthLabel(date) {
  return new Intl.DateTimeFormat("es-AR", { month: "long", year: "numeric" }).format(date);
}

function eventSource(info, success) {
  const qs = new URLSearchParams(new FormData(filters));
  fetch(`/calendar/events?${qs}`).then(r => r.json()).then(success);
}

function buildCalendar(el, date) {
  return new FullCalendar.Calendar(el, {
    initialView: "dayGridMonth",
    initialDate: date,
    locale: "es",
    timeZone: "America/Argentina/San_Luis",
    height: "auto",
    headerToolbar: { left: "", center: "title", right: "" },
    dayMaxEvents: 2,
    events: eventSource,
  });
}

function renderCalendars() {
  if (!window.FullCalendar || monthEls.some(el => !el)) return;
  calendars.forEach(calendar => calendar.destroy());
  const center = startOfMonth(anchorDate);
  const dates = [addMonths(center, -1), center, addMonths(center, 1)];
  calendars = monthEls.map((el, index) => buildCalendar(el, dates[index]));
  calendars.forEach(calendar => calendar.render());
  if (titleEl) titleEl.textContent = `${monthLabel(dates[0])} — ${monthLabel(dates[2])}`;
}

if (filters) {
  filters.addEventListener("submit", event => {
    event.preventDefault();
    calendars.forEach(calendar => calendar.refetchEvents());
  });
}
if (prevBtn) prevBtn.addEventListener("click", () => { anchorDate = addMonths(anchorDate, -1); renderCalendars(); });
if (nextBtn) nextBtn.addEventListener("click", () => { anchorDate = addMonths(anchorDate, 1); renderCalendars(); });
renderCalendars();
