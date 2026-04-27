const el = document.getElementById("calendar");
const filters = document.getElementById("calendarFilters");
if (el && window.FullCalendar) {
  const calendar = new FullCalendar.Calendar(el, {
    initialView: "dayGridMonth",
    locale: "es",
    timeZone: "America/Argentina/San_Luis",
    height: "auto",
    events: (info, success) => {
      const qs = new URLSearchParams(new FormData(filters));
      fetch(`/calendar/events?${qs}`).then(r => r.json()).then(success);
    }
  });
  calendar.render();
  filters.addEventListener("submit", event => {
    event.preventDefault();
    calendar.refetchEvents();
  });
}
