const elements = {
  form: document.querySelector('#forecast-form'),
  forecastDate: document.querySelector('#forecast-date'),
  forecastStartValue: document.querySelector('#forecast-start-value'),
  forecastDateDisplay: document.querySelector('#forecast-date-display'),
  forecastDateNote: document.querySelector('#forecast-date-note'),
  greeting: document.querySelector('#greeting'),
  healthPill: document.querySelector('#health-pill'),
  healthLabel: document.querySelector('#health-label'),
  manualSource: document.querySelector('#manual-source'),
  weatherSource: document.querySelector('#weather-source'),
  weatherNote: document.querySelector('#weather-note'),
  weatherNoteTitle: document.querySelector('#weather-note-title'),
  weatherNoteCopy: document.querySelector('#weather-note-copy'),
  horizonInputs: document.querySelector('#horizon-inputs'),
  model: document.querySelector('#model'),
  modelNote: document.querySelector('#model-note'),
  submitButton: document.querySelector('#submit-button'),
  buttonLabel: document.querySelector('#button-label'),
  resultCard: document.querySelector('.result-card'),
  emptyState: document.querySelector('#empty-state'),
  resultsState: document.querySelector('#results-state'),
  resultDate: document.querySelector('#result-date'),
  resultLabel: document.querySelector('#result-label'),
  primaryValue: document.querySelector('#primary-value'),
  resultBrief: document.querySelector('#result-brief'),
  rangeLabel: document.querySelector('#range-label'),
  rangeValue: document.querySelector('#range-value'),
  temperatureSummary: document.querySelector('#temperature-summary'),
  modelsSummary: document.querySelector('#models-summary'),
  daySummary: document.querySelector('#day-summary'),
  horizonResults: document.querySelector('#horizon-results'),
  generatedAt: document.querySelector('#generated-at'),
  toast: document.querySelector('#toast'),
  toastMessage: document.querySelector('#toast-message')
};

const state = {
  metadata: null,
  temperatureSource: 'weather',
  rows: [],
  toastTimer: null,
  weatherRequest: 0
};

const demandFormatter = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });

function setGreeting() {
  const hour = Number(new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    hour12: false,
    hourCycle: 'h23',
    timeZone: 'Asia/Dhaka'
  }).format(new Date()));
  const part = hour < 12 ? 'Good morning' : hour < 17 ? 'Good afternoon' : 'Good evening';
  elements.greeting.textContent = `${part}, Dhaka · seven-day planning`;
}

function formatDate(dateString, options = {}) {
  const value = new Date(`${dateString}T12:00:00Z`);
  return new Intl.DateTimeFormat('en-US', {
    weekday: 'long',
    month: 'long',
    day: 'numeric',
    year: 'numeric',
    timeZone: 'UTC',
    ...options
  }).format(value);
}

function addDays(dateString, amount) {
  const value = new Date(`${dateString}T12:00:00Z`);
  value.setUTCDate(value.getUTCDate() + amount);
  return value.toISOString().slice(0, 10);
}

function formatWindow(startDate, endDate) {
  const start = formatDate(startDate, { weekday: undefined, year: undefined });
  const end = formatDate(endDate, { weekday: undefined });
  return `${start} – ${end}`;
}

function showToast(message) {
  window.clearTimeout(state.toastTimer);
  elements.toastMessage.textContent = message;
  elements.toast.dataset.visible = 'true';
  state.toastTimer = window.setTimeout(() => {
    elements.toast.dataset.visible = 'false';
  }, 6500);
}

function errorMessage(body) {
  if (body?.error?.details?.length) {
    return body.error.details.map(item => item.message).join(' ');
  }
  return body?.error?.message || body?.detail || 'The forecast could not be generated.';
}

function createHolidayOptions(select) {
  const empty = document.createElement('option');
  empty.value = '';
  empty.textContent = 'Choose a holiday';
  select.append(empty);
  state.metadata.holiday_names.forEach(name => {
    const option = document.createElement('option');
    option.value = name;
    option.textContent = name;
    select.append(option);
  });
}

function buildHorizonInputs() {
  state.rows = [];
  elements.horizonInputs.replaceChildren();
  const constraints = state.metadata.temperature_constraints;

  for (let index = 0; index < state.metadata.forecast_horizon_days; index += 1) {
    const forecastDate = addDays(state.metadata.allowed_forecast_date, index);
    const row = document.createElement('div');
    row.className = 'horizon-input-row';
    row.dataset.date = forecastDate;

    const identity = document.createElement('div');
    identity.className = 'horizon-day';
    const weekday = document.createElement('strong');
    weekday.textContent = formatDate(forecastDate, {
      month: undefined,
      day: undefined,
      year: undefined
    });
    const dateLabel = document.createElement('span');
    dateLabel.textContent = formatDate(forecastDate, {
      weekday: undefined,
      year: undefined
    });
    identity.append(weekday, dateLabel);

    const temperature = document.createElement('input');
    temperature.className = 'day-temperature';
    temperature.type = 'number';
    temperature.min = String(constraints.minimum_c);
    temperature.max = String(constraints.maximum_c);
    temperature.step = String(constraints.step_c);
    temperature.value = '30.0';
    temperature.required = true;
    temperature.inputMode = 'decimal';
    temperature.setAttribute('aria-label', `${forecastDate} mean temperature in degrees Celsius`);

    const holidayLabel = document.createElement('label');
    holidayLabel.className = 'day-holiday-toggle';
    const holiday = document.createElement('input');
    holiday.type = 'checkbox';
    holiday.setAttribute('aria-label', `${forecastDate} is a public holiday`);
    const holidayText = document.createElement('span');
    holidayText.textContent = 'Holiday';
    holidayLabel.append(holiday, holidayText);

    const holidayName = document.createElement('select');
    holidayName.className = 'day-holiday-name';
    holidayName.hidden = true;
    holidayName.disabled = true;
    holidayName.setAttribute('aria-label', `${forecastDate} holiday name`);
    createHolidayOptions(holidayName);
    holiday.addEventListener('change', () => {
      holidayName.hidden = !holiday.checked;
      holidayName.disabled = !holiday.checked;
      holidayName.required = holiday.checked;
      if (!holiday.checked) holidayName.value = '';
    });

    row.append(identity, temperature, holidayLabel, holidayName);
    elements.horizonInputs.append(row);
    state.rows.push({ row, forecastDate, temperature, holiday, holidayName });
  }
}

async function loadWeatherPreview() {
  if (!state.metadata || !state.rows.length) return;
  const requestId = ++state.weatherRequest;
  elements.weatherNote.hidden = false;
  elements.weatherNoteTitle.textContent = 'Fetching Dhaka’s seven-day weather';
  elements.weatherNoteCopy.textContent = 'Contacting Open-Meteo for daily highs and lows…';
  state.rows.forEach(item => {
    item.temperature.disabled = true;
    item.temperature.value = '';
    item.temperature.placeholder = '…';
  });

  try {
    const response = await fetch('/api/v1/weather/7-day');
    const body = await response.json();
    if (!response.ok) throw new Error(errorMessage(body));
    if (requestId !== state.weatherRequest || state.temperatureSource !== 'weather') return;

    const byDate = new Map(body.days.map(item => [item.forecast_date, item.temperature]));
    state.rows.forEach(item => {
      const weather = byDate.get(item.forecastDate);
      if (!weather) throw new Error(`Weather is missing for ${item.forecastDate}.`);
      item.temperature.value = weather.daily_temperature_c.toFixed(1);
      item.temperature.title = `High ${weather.daily_high_c.toFixed(1)}°C · Low ${weather.daily_low_c.toFixed(1)}°C`;
    });
    elements.weatherNoteTitle.textContent = 'Dhaka weather loaded for all 7 days';
    elements.weatherNoteCopy.textContent = 'Daily means are ready. Generate the outlook or switch to manual entry to override them.';
  } catch (error) {
    if (requestId !== state.weatherRequest) return;
    showToast(error.message || 'Dhaka weather could not be loaded.');
    setTemperatureSource('manual');
  }
}

function setTemperatureSource(source) {
  state.temperatureSource = source;
  const manual = source === 'manual';
  elements.manualSource.setAttribute('aria-pressed', String(manual));
  elements.weatherSource.setAttribute('aria-pressed', String(!manual));
  elements.weatherNote.hidden = manual;
  state.rows.forEach(item => {
    item.temperature.disabled = !manual;
    item.temperature.required = manual;
    if (manual && !item.temperature.value) item.temperature.value = '30.0';
  });
  if (!manual) loadWeatherPreview();
}

function updateModelNote() {
  if (!state.metadata || elements.model.value === 'all') {
    elements.modelNote.innerHTML = '<strong>Balanced consensus</strong>Each day averages all eleven models, and that consensus becomes recursive history for the next day.';
    return;
  }
  const selected = state.metadata.models.find(model => String(model.id) === elements.model.value);
  if (!selected) return;
  elements.modelNote.replaceChildren();
  const heading = document.createElement('strong');
  heading.textContent = `${selected.name} · ${selected.family}`;
  elements.modelNote.append(
    heading,
    document.createTextNode(`${selected.description} Its prediction becomes the next day’s recursive history.`)
  );
}

function setBusy(busy) {
  elements.submitButton.disabled = busy;
  elements.manualSource.disabled = busy;
  elements.weatherSource.disabled = busy;
  elements.resultCard.setAttribute('aria-busy', String(busy));
  elements.buttonLabel.textContent = busy ? 'Building seven daily forecasts' : 'Predict the next 7 days';
  elements.buttonLabel.classList.toggle('loading-label', busy);
}

function renderHorizon(days) {
  elements.horizonResults.replaceChildren();
  days.forEach(day => {
    const values = day.predictions.map(item => item.forecast_demand_mw);
    const minimum = Math.min(...values);
    const maximum = Math.max(...values);
    const source = day.temperature.collected_from_api ? 'Weather API' : 'Manual input';

    const row = document.createElement('div');
    row.className = 'horizon-result-row';

    const identity = document.createElement('div');
    identity.className = 'horizon-result-date';
    const dateHeading = document.createElement('strong');
    dateHeading.textContent = formatDate(day.forecast_date, { year: undefined });
    const context = document.createElement('span');
    context.textContent = day.is_holiday ? day.holiday_name : 'Regular day';
    identity.append(dateHeading, context);

    const temperature = document.createElement('div');
    temperature.className = 'horizon-result-temperature';
    const temperatureValue = document.createElement('strong');
    temperatureValue.textContent = `${day.temperature.daily_temperature_c.toFixed(1)}°C`;
    const temperatureSource = document.createElement('span');
    temperatureSource.textContent = source;
    temperature.append(temperatureValue, temperatureSource);

    const demand = document.createElement('div');
    demand.className = 'horizon-result-demand';
    demand.textContent = `${demandFormatter.format(day.recursive_history_demand_mw)} MW`;

    const range = document.createElement('div');
    range.className = 'horizon-result-range';
    const rangeValue = document.createElement('strong');
    rangeValue.textContent = values.length > 1
      ? `${demandFormatter.format(minimum)}–${demandFormatter.format(maximum)}`
      : demandFormatter.format(minimum);
    const rangeLabel = document.createElement('span');
    rangeLabel.textContent = values.length > 1 ? 'model range' : 'model estimate';
    range.append(rangeValue, rangeLabel);

    row.append(identity, temperature, demand, range);
    elements.horizonResults.append(row);
  });
}

function renderForecast(data) {
  const dailyValues = data.days.map(day => day.recursive_history_demand_mw);
  const peakValue = Math.max(...dailyValues);
  const peakIndex = dailyValues.indexOf(peakValue);
  const peakDay = data.days[peakIndex];
  const minimum = Math.min(...dailyValues);
  const maximum = Math.max(...dailyValues);
  const averageTemperature = data.days.reduce(
    (sum, day) => sum + day.temperature.daily_temperature_c,
    0
  ) / data.days.length;

  elements.emptyState.hidden = true;
  elements.resultsState.hidden = false;
  elements.resultDate.textContent = formatWindow(data.start_date, data.end_date);
  elements.resultLabel.textContent = data.model_count > 1
    ? 'Seven-day peak consensus'
    : 'Seven-day peak estimate';
  elements.primaryValue.textContent = demandFormatter.format(peakValue);
  elements.rangeLabel.textContent = 'Daily demand span';
  elements.rangeValue.textContent = `${demandFormatter.format(minimum)}–${demandFormatter.format(maximum)} MW`;
  elements.resultBrief.textContent = `Peak demand is expected on ${formatDate(peakDay.forecast_date, {
    year: undefined
  })}. Each day is predicted sequentially and becomes demand history for the next day.`;
  elements.temperatureSummary.textContent = `${averageTemperature.toFixed(1)}°C · 7-day mean`;
  elements.modelsSummary.textContent = data.model_count > 1
    ? `${data.model_count} model consensus`
    : data.days[0].predictions[0].model_name;
  elements.daySummary.textContent = formatDate(peakDay.forecast_date, {
    weekday: undefined,
    year: undefined
  });

  renderHorizon(data.days);
  const generated = new Date(data.generated_at);
  elements.generatedAt.textContent = `Generated ${new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    timeZone: 'Asia/Dhaka',
    timeZoneName: 'short'
  }).format(generated)}`;

  if (window.matchMedia('(max-width: 820px)').matches) {
    elements.resultCard.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
}

async function loadApp() {
  try {
    const [metadataResponse, healthResponse] = await Promise.all([
      fetch('/api/v1/metadata'),
      fetch('/health')
    ]);
    if (!metadataResponse.ok) throw new Error('Forecast settings are unavailable right now.');

    state.metadata = await metadataResponse.json();
    elements.forecastDate.value = state.metadata.allowed_forecast_date;
    elements.forecastStartValue.dateTime = state.metadata.allowed_forecast_date;
    elements.forecastStartValue.textContent = formatDate(
      state.metadata.allowed_forecast_date,
      { weekday: undefined }
    );
    elements.forecastDateDisplay.textContent = formatWindow(
      state.metadata.allowed_forecast_date,
      state.metadata.forecast_horizon_end_date
    );
    elements.forecastDateNote.textContent = `Backend silently fills missing history after ${formatDate(
      state.metadata.latest_recursive_history_date,
      { weekday: undefined, year: undefined }
    )}; only these 7 days are shown`;
    buildHorizonInputs();

    const groups = new Map();
    state.metadata.models.forEach(model => {
      if (!groups.has(model.family)) {
        const group = document.createElement('optgroup');
        group.label = model.family;
        groups.set(model.family, group);
        elements.model.append(group);
      }
      const option = document.createElement('option');
      option.value = String(model.id);
      option.textContent = `${model.id} · ${model.name}`;
      groups.get(model.family).append(option);
    });

    if (!state.metadata.dhaka_weather_available) {
      elements.weatherSource.disabled = true;
      setTemperatureSource('manual');
    } else {
      setTemperatureSource('weather');
    }

    if (healthResponse.ok) {
      const health = await healthResponse.json();
      elements.healthPill.dataset.status = health.status;
      elements.healthLabel.textContent = `${health.artifacts_available}/${health.models_configured} retrained models ready`;
    } else {
      elements.healthPill.dataset.status = 'error';
      elements.healthLabel.textContent = 'Service needs attention';
    }
  } catch (error) {
    elements.healthPill.dataset.status = 'error';
    elements.healthLabel.textContent = 'Service unavailable';
    elements.forecastDateDisplay.textContent = 'Unable to load';
    elements.forecastStartValue.textContent = 'Date unavailable';
    showToast(error.message || 'The forecasting workspace could not load.');
  }
}

elements.manualSource.addEventListener('click', () => setTemperatureSource('manual'));
elements.weatherSource.addEventListener('click', () => setTemperatureSource('weather'));
elements.model.addEventListener('change', updateModelNote);

elements.form.addEventListener('submit', async event => {
  event.preventDefault();
  if (!state.metadata || state.rows.length !== 7) {
    showToast('The seven-day forecast settings are still loading.');
    return;
  }

  const manual = state.temperatureSource === 'manual';
  const days = state.rows.map(item => {
    const day = {
      forecast_date: item.forecastDate,
      is_holiday: item.holiday.checked,
      holiday_name: item.holiday.checked ? item.holidayName.value : null
    };
    if (manual) day.daily_temperature_c = Number(item.temperature.value);
    return day;
  });

  if (manual && days.some(day => !Number.isFinite(day.daily_temperature_c))) {
    showToast('Enter a valid temperature for every forecast day.');
    return;
  }
  if (days.some(day => day.is_holiday && !day.holiday_name)) {
    showToast('Choose a holiday name for every marked holiday.');
    return;
  }

  const payload = {
    days,
    model: elements.model.value === 'all' ? 'all' : Number(elements.model.value),
    collect_temperature_from_api: !manual
  };

  setBusy(true);
  try {
    const response = await fetch('/api/v1/forecast/7-day', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const body = await response.json();
    if (!response.ok) throw new Error(errorMessage(body));
    renderForecast(body);
  } catch (error) {
    showToast(error.message || 'The seven-day forecast could not be generated.');
  } finally {
    setBusy(false);
  }
});

setGreeting();
loadApp();
