/* ═════════════════════════════════════════════════════════════════
   meteora web app — consumes your own API
   ═════════════════════════════════════════════════════════════════ */

/* Point at your local meteora server. Swap to production URL after deploy. */
const API_BASE = (location.hostname === "localhost" || location.hostname === "127.0.0.1")
  ? `http://${location.hostname}:8787`
  : "";  // same-origin if bundled

// ─── DOM refs ───
const form       = document.getElementById("search-form");
const input      = document.getElementById("search-input");
const sugList    = document.getElementById("suggestions");
const currentCard= document.getElementById("current-card");
const forecastCard = document.getElementById("forecast-card");
const forecastRow = document.getElementById("forecast-row");
const statusEl   = document.getElementById("status");
const codeSample = document.getElementById("code-sample");

// current card refs
const currentLoc  = document.getElementById("current-loc");
const currentTime = document.getElementById("current-time");
const currentTempVal = document.getElementById("current-temp-val");
const currentDesc = document.getElementById("current-desc");
const currentFeels = document.getElementById("current-feels");
const statHum = document.getElementById("stat-hum");
const statWind = document.getElementById("stat-wind");
const statCloud = document.getElementById("stat-cloud");
const statPres = document.getElementById("stat-pres");

// ─── helpers ───
async function api(path) {
  const url = API_BASE + path;
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
  return { data: await r.json(), url };
}

function setStatus(msg, isError = false) {
  statusEl.innerHTML = `<p>${msg}</p>`;
  statusEl.classList.toggle("error", isError);
  statusEl.hidden = false;
}
function hideStatus() { statusEl.hidden = true; }

function fmtTemp(t) { return Math.round(t); }
function fmtWind(k) { return Math.round(k) + " km/h"; }
function dayName(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { weekday: "short" });
}
function fmtClock(iso) {
  const d = new Date(iso);
  return d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit" });
}

// ─── geo search (debounced live suggestions) ───
let searchTimer;
input.addEventListener("input", () => {
  clearTimeout(searchTimer);
  const q = input.value.trim();
  if (q.length < 2) {
    sugList.classList.remove("open");
    return;
  }
  searchTimer = setTimeout(async () => {
    try {
      const { data } = await api(`/v1/geo/search?q=${encodeURIComponent(q)}&count=6`);
      sugList.innerHTML = data.results.map((r, i) => `
        <li data-lat="${r.latitude}" data-lon="${r.longitude}" data-name="${r.name}${r.admin1 ? ', ' + r.admin1 : ''}${r.country ? ', ' + r.country : ''}">
          <span class="s-main">${r.name}</span>
          <span class="s-meta">${r.admin1 ? r.admin1 + ' · ' : ''}${r.country}</span>
        </li>
      `).join("");
      sugList.classList.add("open");
    } catch (e) {
      // silent — no suggestion dropdown
    }
  }, 200);
});

// click suggestion → load weather
sugList.addEventListener("click", (e) => {
  const li = e.target.closest("li");
  if (!li) return;
  const lat = parseFloat(li.dataset.lat);
  const lon = parseFloat(li.dataset.lon);
  const name = li.dataset.name;
  input.value = name;
  sugList.classList.remove("open");
  loadWeather(lat, lon, name);
});

// form submit → take the first suggestion or geocode fresh
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const q = input.value.trim();
  if (!q) return;
  setStatus(`Searching <em>${q}</em>…`);
  try {
    const { data } = await api(`/v1/geo/search?q=${encodeURIComponent(q)}&count=1`);
    if (!data.results.length) {
      setStatus(`No location found for <em>${q}</em>.`, true);
      return;
    }
    const r = data.results[0];
    const name = `${r.name}${r.admin1 ? ', ' + r.admin1 : ''}${r.country ? ', ' + r.country : ''}`;
    input.value = name;
    sugList.classList.remove("open");
    await loadWeather(r.latitude, r.longitude, name);
  } catch (e) {
    setStatus(`Error — ${e.message}`, true);
  }
});

// close suggestions on outside click
document.addEventListener("click", (e) => {
  if (!form.contains(e.target) && !sugList.contains(e.target)) {
    sugList.classList.remove("open");
  }
});

// ─── load current + forecast, populate UI ───
async function loadWeather(lat, lon, name) {
  setStatus(`Fetching weather for <em>${name}</em>…`);
  try {
    const [{ data: cur, url: curUrl }, { data: fc, url: fcUrl }] = await Promise.all([
      api(`/v1/weather/current?lat=${lat}&lon=${lon}`),
      api(`/v1/weather/forecast?lat=${lat}&lon=${lon}&days=7`),
    ]);

    // current card
    currentLoc.textContent = name;
    currentTime.textContent = fmtClock(cur.current.time);
    currentTempVal.textContent = fmtTemp(cur.current.temperature_c);
    currentDesc.textContent = cur.current.weather_description;
    currentFeels.textContent = fmtTemp(cur.current.feels_like_c) + "°C";
    statHum.textContent = cur.current.humidity_pct + "%";
    statWind.textContent = fmtWind(cur.current.wind_speed_kmh);
    statCloud.textContent = cur.current.cloud_cover_pct + "%";
    statPres.textContent = Math.round(cur.current.pressure_hpa) + " hPa";
    currentCard.hidden = false;

    // forecast row
    forecastRow.innerHTML = fc.days.map(d => `
      <div class="forecast-day">
        <span class="day-date">${dayName(d.date)}</span>
        <span class="day-desc">${d.weather_description}</span>
        <span class="day-temps">${fmtTemp(d.temp_max_c)}° <span class="low">${fmtTemp(d.temp_min_c)}°</span></span>
        <span class="day-rain">${d.precipitation_chance_pct}%</span>
      </div>
    `).join("");
    forecastCard.hidden = false;

    // code sample drawer
    codeSample.textContent =
`// Two calls to the Meteora API:

fetch("${curUrl}")
  .then(r => r.json())
  .then(data => console.log(data.current.temperature_c));
// → ${fmtTemp(cur.current.temperature_c)}

fetch("${fcUrl}")
  .then(r => r.json())
  .then(data => console.log(data.days[0].temp_max_c));
// → ${fmtTemp(fc.days[0].temp_max_c)} (tomorrow's high)`;

    hideStatus();
  } catch (e) {
    setStatus(`Error — ${e.message}`, true);
  }
}

// ─── seed with Thousand Oaks on first load ───
loadWeather(34.17, -118.87, "Thousand Oaks, California, United States");
