const state = {
  movies: [],
  filtered: [],
  filters: {
    search: "",
    lists: [],
    tags: [],
    genres: [],
    languages: [],
    runtime: "any",
    personal: "active",
    sort: "score",
  },
  personal: {},
  spotlightMovie: null,
  activeMoods: new Set(),
  previousSort: "score",
  recentPicks: [],
};

const els = {
  stats: document.querySelector("#stats"),
  search: document.querySelector("#search"),
  list: document.querySelector("#listFilter"),
  tag: document.querySelector("#tagFilter"),
  genre: document.querySelector("#genreFilter"),
  language: document.querySelector("#languageFilter"),
  runtime: document.querySelector("#runtimeFilter"),
  sort: document.querySelector("#sortFilter"),
  personalFilter: document.querySelector("#personalFilter"),
  pick: document.querySelector("#pickButton"),
  pickMode: document.querySelector("#pickMode"),
  reset: document.querySelector("#resetButton"),
  count: document.querySelector("#countLabel"),
  moodBar: document.querySelector("#moodBar"),
  activeFilters: document.querySelector("#activeFilters"),
  selectionPanel: document.querySelector("#selectionPanel"),
  spotlight: document.querySelector("#spotlight"),
  breakdown: document.querySelector("#breakdown"),
  grid: document.querySelector("#movieGrid"),
  template: document.querySelector("#movieCardTemplate"),
  modal: document.querySelector("#movieModal"),
  modalClose: document.querySelector("#modalClose"),
  modalContent: document.querySelector("#modalContent"),
  undoToast: document.querySelector("#undoToast"),
  syncBanner: document.querySelector("#syncBanner"),
  syncBannerMsg: document.querySelector("#syncBannerMsg"),
  syncBannerClose: document.querySelector("#syncBannerClose"),
  themeToggle: document.querySelector("#themeToggle"),
  dataFreshness: document.querySelector("#dataFreshness"),
  missesPanel: document.querySelector("#missesPanel"),
  missesCount: document.querySelector("#missesCount"),
  missesList: document.querySelector("#missesList"),
  rebuildButton: document.querySelector("#rebuildButton"),
  buzzButton: document.querySelector("#buzzButton"),
};

const themeKey = "sundance-theme-v1";

function isDark() {
  const saved = localStorage.getItem(themeKey);
  if (saved) return saved === "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches;
}

function applyTheme(dark) {
  document.documentElement.dataset.theme = dark ? "dark" : "light";
  els.themeToggle.textContent = dark ? "☀︎" : "☾";
  els.themeToggle.setAttribute("aria-label", dark ? "Mudar para tema claro" : "Mudar para tema escuro");
}

function initTheme() {
  applyTheme(isDark());
  els.themeToggle.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme !== "dark";
    localStorage.setItem(themeKey, next ? "dark" : "light");
    applyTheme(next);
  });
}

const palette = ["#27717a", "#a85240", "#506b4e", "#b1842f", "#684d73", "#395f8f"];
const personalLabels = {
  want: "Quero ver",
  maybe: "Talvez",
  seen: "Já vi",
  ignored: "Ignorar",
};
const storageKey = "sundance-watch-picker-v1";
const filtersKey = "sundance-filters-v1";
let undoTimer = null;
let searchTimer = null;
const moodRecipes = {
  laugh: { tags: ["Comedy"], genres: [], runtime: "any", sort: "score" },
  light: { tags: ["Comedy", "Short-ish"], genres: [], runtime: "medium", sort: "score" },
  doc: { tags: ["Documentary"], genres: [], runtime: "any", sort: "rating" },
  weird: { tags: [], genres: ["science-fiction"], runtime: "any", sort: "score" },
  short: { tags: ["Short-ish"], genres: [], runtime: "short", sort: "runtime" },
  winner: { tags: ["Award Winner"], genres: [], runtime: "any", sort: "score" },
  recent: { tags: ["Recent"], genres: [], runtime: "any", sort: "recent" },
};
const genreNames = {
  action: "Ação",
  adventure: "Aventura",
  animation: "Animação",
  comedy: "Comédia",
  crime: "Crime",
  documentary: "Documentário",
  drama: "Drama",
  family: "Família",
  fantasy: "Fantasia",
  history: "História",
  holiday: "Feriado",
  horror: "Terror",
  music: "Música",
  musical: "Musical",
  mystery: "Mistério",
  romance: "Romance",
  "science-fiction": "Ficção científica",
  thriller: "Suspense",
  war: "Guerra",
  western: "Faroeste",
};

function genreLabel(genre) {
  return genreNames[genre] || genre;
}

const languageNames = {
  ar: "Árabe",
  da: "Dinamarquês",
  de: "Alemão",
  el: "Grego",
  en: "Inglês",
  es: "Espanhol",
  et: "Estoniano",
  fa: "Persa",
  fi: "Finlandês",
  fr: "Francês",
  ga: "Irlandês",
  he: "Hebraico",
  hi: "Hindi",
  id: "Indonésio",
  it: "Italiano",
  ja: "Japonês",
  lt: "Lituano",
  mk: "Macedônio",
  mr: "Marathi",
  my: "Birmanês",
  nl: "Holandês",
  no: "Norueguês",
  pt: "Português",
  ro: "Romeno",
  sq: "Albanês",
  sv: "Sueco",
  sw: "Suaíli",
  tl: "Tagalog",
  tr: "Turco",
  uk: "Ucraniano",
};

function uniq(values) {
  return [...new Set(values.filter(Boolean))].sort((a, b) => a.localeCompare(b));
}

function languageLabel(code) {
  return languageNames[code] || (code ? code.toUpperCase() : "Idioma n/d");
}

function movieLanguages(movie) {
  return movie.language ? [movie.language] : [];
}

function optionize(select, values, label) {
  select.innerHTML = `<option value="all">${label}</option>`;
  values.forEach((value) => {
    const option = document.createElement("option");
    option.value = value;
    option.textContent = value;
    select.append(option);
  });
}

function optionizeGenres(select, genres, label) {
  select.innerHTML = `<option value="all">${label}</option>`;
  genres
    .sort((a, b) => genreLabel(a).localeCompare(genreLabel(b)))
    .forEach((genre) => {
      const option = document.createElement("option");
      option.value = genre;
      option.textContent = genreLabel(genre);
      select.append(option);
    });
}

function optionizeLanguages(select, codes, label) {
  select.innerHTML = `<option value="all">${label}</option>`;
  codes
    .sort((a, b) => languageLabel(a).localeCompare(languageLabel(b)))
    .forEach((code) => {
      const option = document.createElement("option");
      option.value = code;
      option.textContent = languageLabel(code);
      select.append(option);
    });
}

function formatRuntime(minutes) {
  if (!minutes) return "duração n/d";
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return h ? `${h}h${String(m).padStart(2, "0")}` : `${m} min`;
}

function buzzArrow(trend) {
  if (trend === "rising") return "↑";
  if (trend === "falling") return "↓";
  if (trend === "new") return "✦";
  return "→";
}

function traktUrl(movie) {
  return movie.slug ? `https://trakt.tv/movies/${movie.slug}` : null;
}

function imdbUrl(movie) {
  return movie.imdb ? `https://www.imdb.com/title/${movie.imdb}/` : null;
}

function movieKey(movie) {
  return String(movie.trakt || movie.imdb || `${movie.title}-${movie.year}`);
}

function getPersonal(movie) {
  return state.personal[movieKey(movie)] || "";
}

function writePersonal(movie, value) {
  const key = movieKey(movie);
  if (!value) {
    delete state.personal[key];
  } else {
    state.personal[key] = value;
  }
  localStorage.setItem(storageKey, JSON.stringify(state.personal));
}

function refreshPersonalUi(movie, next) {
  renderStats();
  // Só limpa o spotlight se o filme vai desaparecer do recorte atual
  const willHide = (next === "seen" || next === "ignored") && state.filters.personal === "active";
  if (willHide) renderSpotlight(null);
  applyFilters();
  if (!els.modal.hidden) openMovieModal(movie);
}

function showUndo(movie, previous, next) {
  if (!next) return; // desmarcado, sem toast necessário
  if (undoTimer) clearTimeout(undoTimer);
  const label = personalLabels[next];
  if (!label) return;
  const canUndo = ["seen", "ignored"].includes(next) && state.filters.personal === "active";
  els.undoToast.hidden = false;
  els.undoToast.innerHTML = canUndo
    ? `<span>${escapeHtml(movie.title)} marcado como <strong>${escapeHtml(label)}</strong>.</span><button type="button">Desfazer</button>`
    : `<span>${escapeHtml(movie.title)} marcado como <strong>${escapeHtml(label)}</strong>.</span>`;
  if (canUndo) {
    els.undoToast.querySelector("button").addEventListener(
      "click",
      () => {
        writePersonal(movie, previous);
        els.undoToast.hidden = true;
        refreshPersonalUi(movie, previous);
      },
      { once: true }
    );
  }
  undoTimer = setTimeout(() => {
    els.undoToast.hidden = true;
    undoTimer = null;
  }, 4000);
}

function showSyncBanner(message) {
  els.syncBannerMsg.textContent = message;
  els.syncBanner.hidden = false;
}

// Sincroniza o estado "Quero ver" com a lista no Trakt.
// O localStorage é a fonte de verdade; erros de rede mostram um aviso.
function syncWant(traktId, action) {
  fetch("/api/want", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ trakt_id: traktId, action }),
  })
    .then((res) => {
      if (res.status === 401 || res.status === 500) {
        showSyncBanner("Token do Trakt expirado ou inválido. Rode setup_trakt.py para renovar.");
      } else if (!res.ok) {
        showSyncBanner(`Falha ao sincronizar com o Trakt (HTTP ${res.status}).`);
      }
    })
    .catch(() => {
      showSyncBanner("Sem conexão com o servidor local. O Circuit está rodando?");
    });
}

function setPersonal(movie, value) {
  const previous = getPersonal(movie);
  const next = previous === value || !value ? "" : value;
  writePersonal(movie, next);
  refreshPersonalUi(movie, next);
  showUndo(movie, previous, next);
  // Trakt sync: only when "Quero ver" (want) is added or removed
  if (movie.trakt) {
    if (next === "want") syncWant(movie.trakt, "add");
    else if (previous === "want") syncWant(movie.trakt, "remove");
  }
}

function loadPersonal() {
  try {
    state.personal = JSON.parse(localStorage.getItem(storageKey) || "{}");
  } catch {
    state.personal = {};
  }
}

function saveFilters() {
  const { lists, tags, genres, languages, runtime, personal, sort } = state.filters;
  localStorage.setItem(filtersKey, JSON.stringify({ lists, tags, genres, languages, runtime, personal, sort }));
}

function loadFilters() {
  try {
    const saved = JSON.parse(localStorage.getItem(filtersKey) || "{}");
    if (Array.isArray(saved.lists))     state.filters.lists     = saved.lists;
    if (Array.isArray(saved.tags))      state.filters.tags      = saved.tags;
    if (Array.isArray(saved.genres))    state.filters.genres    = saved.genres;
    if (Array.isArray(saved.languages)) state.filters.languages = saved.languages;
    if (saved.runtime)  state.filters.runtime  = saved.runtime;
    if (saved.personal) state.filters.personal = saved.personal;
    if (saved.sort)     state.filters.sort     = saved.sort;
  } catch {
    // ignora erros de parse
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function searchText(movie) {
  return [
    movie.title,
    movie.year,
    movie.overview,
    movie.genres.join(" "),
    languageLabel(movie.language),
    movie.language,
    movie.tags.join(" "),
    movie.lists.join(" "),
    movie.themes.join(" "),
  ]
    .join(" ")
    .toLowerCase();
}

function matchesRuntime(movie) {
  if (state.filters.runtime === "any") return true;
  if (!movie.runtime) return false;
  if (state.filters.runtime === "short") return movie.runtime <= 90;
  if (state.filters.runtime === "medium") return movie.runtime > 90 && movie.runtime <= 120;
  return movie.runtime > 120;
}

function matchesPersonal(movie) {
  const value = getPersonal(movie);
  if (state.filters.personal === "all") return true;
  if (state.filters.personal === "active") return value !== "seen" && value !== "ignored";
  return value === state.filters.personal;
}

function includesAll(values, activeValues) {
  return activeValues.every((value) => values.includes(value));
}

function includesAny(values, activeValues) {
  if (!activeValues.length) return true;
  return activeValues.some((value) => values.includes(value));
}

function applyFilters() {
  const q = state.filters.search.trim().toLowerCase();
  let movies = state.movies.filter((movie) => {
    if (q && !searchText(movie).includes(q)) return false;
    if (!includesAny(movie.lists, state.filters.lists)) return false;
    if (!includesAll(movie.tags, state.filters.tags)) return false;
    if (!includesAll(movie.genres, state.filters.genres)) return false;
    if (!includesAny(movieLanguages(movie), state.filters.languages)) return false;
    if (!matchesPersonal(movie)) return false;
    return matchesRuntime(movie);
  });

  movies = movies.sort((a, b) => {
    if (state.filters.sort === "rating") return b.rating - a.rating || b.votes - a.votes;
    if (state.filters.sort === "recent") return b.year - a.year || b.watch_score - a.watch_score;
    if (state.filters.sort === "runtime") return (a.runtime || 999) - (b.runtime || 999);
    if (state.filters.sort === "title") return a.title.localeCompare(b.title);
    if (state.filters.sort === "buzz") return (b.buzz_score ?? -1) - (a.buzz_score ?? -1) || b.watch_score - a.watch_score;
    return b.watch_score - a.watch_score || b.rating - a.rating;
  });

  state.filtered = movies;
  saveFilters();
  render();
}

function renderStats() {
  const total = state.movies.length;
  const docs = state.movies.filter((movie) => movie.tags.includes("Documentary")).length;
  const comedy = state.movies.filter((movie) => movie.tags.includes("Comedy") || movie.tags.includes("Dramedy")).length;
  const want = state.movies.filter((movie) => getPersonal(movie) === "want").length;
  els.stats.innerHTML = [
    ["Filmes", total],
    ["Docs", docs],
    ["Comédia/drama", comedy],
    ["Quero ver", want],
  ]
    .map(([label, value]) => `<div class="stat"><strong>${value}</strong><span>${label}</span></div>`)
    .join("");
}

function topCounts(source, limit = 5) {
  const counts = new Map();
  source.forEach((value) => counts.set(value, (counts.get(value) || 0) + 1));
  return [...counts.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).slice(0, limit);
}

function renderBreakdown() {
  const buckets = [
    ["Categorias", topCounts(state.filtered.flatMap((movie) => movie.tags), 6)],
    ["Gêneros", topCounts(state.filtered.flatMap((movie) => movie.genres), 6).map(([g, n]) => [genreLabel(g), n])],
    ["Idiomas", topCounts(state.filtered.map((movie) => languageLabel(movie.language)), 6)],
    ["Listas", topCounts(state.filtered.flatMap((movie) => movie.lists), 4)],
  ];
  els.breakdown.innerHTML = buckets
    .map(([title, rows]) => {
      const max = Math.max(...rows.map(([, count]) => count), 1);
      const bars = rows
        .map(([label, count]) => {
          const width = Math.max(8, Math.round((count / max) * 100));
          return `<div class="bar"><span><i style="width:${width}%"></i>${label}</span><b>${count}</b></div>`;
        })
        .join("");
      return `<div class="bucket"><h3>${title}</h3>${bars}</div>`;
    })
    .join("");
}

function colorFor(movie) {
  const seed = [...movie.title].reduce((sum, char) => sum + char.charCodeAt(0), 0);
  return palette[seed % palette.length];
}

function filterChipType(movie, chip) {
  if (movie.tags.includes(chip)) return "tag";
  if (movie.genres.includes(chip)) return "genre";
  if (movie.lists.includes(chip)) return "list";
  if (chip.startsWith("Idioma: ")) return "language";
  return "search";
}

function activeValuesForType(type) {
  if (type === "tag") return state.filters.tags;
  if (type === "genre") return state.filters.genres;
  if (type === "list") return state.filters.lists;
  if (type === "language") return state.filters.languages.map((code) => `Idioma: ${languageLabel(code)}`);
  return [];
}

function isFilterActive(type, value) {
  return activeValuesForType(type).includes(value);
}

function chipMarkup(movie, chip) {
  const type = filterChipType(movie, chip);
  const active = isFilterActive(type, chip);
  const display = type === "genre" ? genreLabel(chip) : chip;
  return `<button class="chip ${active ? "is-active" : ""}" type="button" data-filter-type="${type}" data-filter-value="${escapeHtml(chip)}" aria-pressed="${active ? "true" : "false"}">${escapeHtml(display)}</button>`;
}

function toggleArrayValue(values, value) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function removeArrayValue(values, value) {
  return values.filter((item) => item !== value);
}

function removeFilter(type, value) {
  if (type === "tag") {
    state.filters.tags = removeArrayValue(state.filters.tags, value);
  } else if (type === "genre") {
    state.filters.genres = removeArrayValue(state.filters.genres, value);
  } else if (type === "list") {
    state.filters.lists = removeArrayValue(state.filters.lists, value);
  } else if (type === "language") {
    state.filters.languages = removeArrayValue(state.filters.languages, value);
  }
  renderSpotlight(null);
  applyFilters();
}

function isMoodActive(mood) {
  return state.activeMoods.has(mood);
}

function renderMoodButtons() {
  els.moodBar.querySelectorAll("[data-mood]").forEach((button) => {
    const active = isMoodActive(button.dataset.mood);
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-pressed", active ? "true" : "false");
  });
}

function toggleFilter(type, value) {
  if (!els.modal.hidden) closeMovieModal();
  if (type === "tag") {
    state.filters.tags = toggleArrayValue(state.filters.tags, value);
  } else if (type === "genre") {
    state.filters.genres = toggleArrayValue(state.filters.genres, value);
  } else if (type === "list") {
    state.filters.lists = toggleArrayValue(state.filters.lists, value);
  } else if (type === "language") {
    const displayLabel = value.startsWith("Idioma: ") ? value.slice("Idioma: ".length) : value;
    const code = Object.entries(languageNames).find(([, name]) => name === displayLabel)?.[0] || displayLabel;
    state.filters.languages = toggleArrayValue(state.filters.languages, code);
  } else {
    state.filters.search = state.filters.search === value ? "" : value;
    els.search.value = state.filters.search;
  }
  els.list.value = "all";
  els.tag.value = "all";
  els.genre.value = "all";
  els.language.value = "all";
  renderSpotlight(null);
  applyFilters();
}

function bindChips(root) {
  root.querySelectorAll(".chip[data-filter-type]").forEach((chip) => {
    chip.addEventListener("click", (event) => {
      event.stopPropagation();
      toggleFilter(chip.dataset.filterType, chip.dataset.filterValue);
    });
  });
}

function renderActiveFilters() {
  const filters = [
    ...state.filters.lists.map((value) => ["list", value, "Lista", value]),
    ...state.filters.tags.map((value) => ["tag", value, "Categoria", value]),
    ...state.filters.genres.map((value) => ["genre", value, "Gênero", genreLabel(value)]),
    ...state.filters.languages.map((value) => ["language", value, "Idioma", languageLabel(value)]),
  ];
  if (!filters.length && !state.filters.search && state.filters.runtime === "any" && state.filters.personal === "active") {
    els.activeFilters.innerHTML = "";
    return;
  }

  const chips = filters
    .map(
      ([type, value, label, display]) =>
        `<button class="active-filter" type="button" data-filter-type="${type}" data-filter-value="${escapeHtml(value)}" aria-label="Remover ${escapeHtml(label.toLowerCase())}: ${escapeHtml(display)}"><span>${label}</span>${escapeHtml(display)} ×</button>`
    )
    .join("");
  const search = state.filters.search
    ? `<button class="active-filter" type="button" data-filter-type="search" data-filter-value="${escapeHtml(state.filters.search)}" aria-label="Remover busca: ${escapeHtml(state.filters.search)}"><span>Busca</span>${escapeHtml(state.filters.search)} ×</button>`
    : "";
  const runtime =
    state.filters.runtime !== "any"
      ? `<button class="active-filter" type="button" data-filter-type="runtime" data-filter-value="${escapeHtml(state.filters.runtime)}" aria-label="Remover duração: ${els.runtime.options[els.runtime.selectedIndex].textContent}"><span>Duração</span>${els.runtime.options[els.runtime.selectedIndex].textContent} ×</button>`
      : "";
  const personal =
    state.filters.personal !== "active"
      ? `<button class="active-filter" type="button" data-filter-type="personal" data-filter-value="${escapeHtml(state.filters.personal)}" aria-label="Remover mostrar: ${els.personalFilter.options[els.personalFilter.selectedIndex].textContent}"><span>Mostrar</span>${els.personalFilter.options[els.personalFilter.selectedIndex].textContent} ×</button>`
      : "";

  els.activeFilters.innerHTML = `<strong>Filtros ativos</strong>${chips}${search}${runtime}${personal}`;
  els.activeFilters.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", () => {
      const type = button.dataset.filterType;
      const value = button.dataset.filterValue;
      if (type === "runtime") {
        state.filters.runtime = "any";
        els.runtime.value = "any";
      } else if (type === "personal") {
        state.filters.personal = "active";
        els.personalFilter.value = "active";
      } else if (type === "search") {
        state.filters.search = "";
        els.search.value = "";
      } else {
        removeFilter(type, value);
        return;
      }
      renderSpotlight(null);
      applyFilters();
    });
  });
}

function renderSelectionPanel() {
  const groups = [
    ["want", "Quero ver"],
    ["maybe", "Talvez"],
    ["seen", "Já vi"],
    ["ignored", "Ignorados"],
  ].map(([key, label]) => {
    const movies = state.movies.filter((movie) => getPersonal(movie) === key);
    return { key, label, movies };
  });

  if (!groups.some((group) => group.movies.length)) {
    els.selectionPanel.innerHTML = "";
    return;
  }

  els.selectionPanel.innerHTML = groups
    .map((group) => {
      const items = group.movies
        .slice(0, 6)
        .map(
          (movie) =>
            `<button type="button" data-movie-key="${escapeHtml(movieKey(movie))}">${escapeHtml(movie.title)} <span>${escapeHtml(movie.year)}</span></button>`
        )
        .join("");
      const more = group.movies.length > 6 ? `<em>+${group.movies.length - 6}</em>` : "";
      const pct = state.movies.length ? Math.min(100, Math.round((group.movies.length / state.movies.length) * 100)) : 0;
      return `
        <div class="selection-bucket is-${group.key}">
          <div><strong>${group.movies.length}</strong><span>${group.label}</span></div>
          <div class="bucket-progress"><i style="width:${pct}%"></i></div>
          <nav>${items || "<small>Nenhum</small>"}${more}</nav>
        </div>
      `;
    })
    .join("");

  els.selectionPanel.querySelectorAll("[data-movie-key]").forEach((button) => {
    button.addEventListener("click", () => {
      const movie = state.movies.find((item) => movieKey(item) === button.dataset.movieKey);
      if (movie) openMovieModal(movie);
    });
  });
}

function renderMovie(movie) {
  const node = els.template.content.firstElementChild.cloneNode(true);
  const personal = getPersonal(movie);
  if (personal) node.classList.add(`is-${personal}`);
  const poster = node.querySelector(".poster-mark");
  const img = poster.querySelector("img");
  poster.style.background = `linear-gradient(145deg, ${colorFor(movie)}, #1f2523)`;
  if (movie.poster_small || movie.poster) {
    img.src = movie.poster_small || movie.poster;
    img.alt = `Capa de ${movie.title}`;
    img.addEventListener("load", () => poster.classList.add("has-image"), { once: true });
    img.addEventListener("error", () => poster.classList.remove("has-image"), { once: true });
  }
  node.querySelector("h2").textContent = movie.title;
  node.querySelector(".year").textContent = movie.year || "";
  if (movie.buzz_score != null) {
    const badge = document.createElement("span");
    badge.className = `buzz-badge is-${movie.buzz_trend || "new"}`;
    badge.title = `Buzz: ${movie.buzz_score}/100`;
    badge.textContent = `${buzzArrow(movie.buzz_trend)} ${Math.round(movie.buzz_score)}`;
    node.querySelector(".movie-title-row").append(badge);
  }
  node.querySelector(".meta").textContent = [
    `${movie.rating}/10`,
    `${movie.votes.toLocaleString("pt-BR")} votos`,
    formatRuntime(movie.runtime),
    languageLabel(movie.language),
  ].join(" · ");
  node.querySelector(".overview").textContent = movie.overview || "Sem sinopse no Trakt.";

  const chipValues = [
    ...movie.tags,
    ...movie.genres.slice(0, 3),
    `Idioma: ${languageLabel(movie.language)}`,
    ...movie.lists.slice(0, 2),
  ];
  node.querySelector(".chips").innerHTML = uniq(chipValues)
    .slice(0, 9)
    .map((chip) => chipMarkup(movie, chip))
    .join("");

  const links = [];
  if (traktUrl(movie)) links.push(`<a href="${traktUrl(movie)}" target="_blank" rel="noreferrer">Trakt</a>`);
  if (imdbUrl(movie)) links.push(`<a href="${imdbUrl(movie)}" target="_blank" rel="noreferrer">IMDb</a>`);
  node.querySelector(".links").innerHTML = links.join("");
  const personalControls = document.createElement("div");
  personalControls.className = "personal-controls";
  personalControls.innerHTML = Object.entries(personalLabels)
    .map(([value, label]) => `<button class="${personal === value ? "is-selected" : ""}" type="button" data-personal="${value}" aria-pressed="${personal === value ? "true" : "false"}">${label}</button>`)
    .join("");
  node.querySelector(".movie-body").append(personalControls);
  personalControls.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", (event) => {
      event.stopPropagation();
      setPersonal(movie, button.dataset.personal);
    });
  });
  node.addEventListener("click", () => openMovieModal(movie));
  node.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      openMovieModal(movie);
    }
  });
  node.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", (event) => event.stopPropagation());
  });
  bindChips(node);
  return node;
}

function renderSpotlight(movie) {
  state.spotlightMovie = movie;
  if (!movie) {
    els.spotlight.innerHTML = "";
    return;
  }
  els.spotlight.innerHTML = "";
  const mark = document.createElement("div");
  mark.className = "poster-mark";
  mark.style.background = `linear-gradient(145deg, ${colorFor(movie)}, #111615)`;
  mark.innerHTML = movie.poster
    ? `<img src="${movie.poster}" alt="Capa de ${movie.title}"><span></span>`
    : "<span></span>";
  const spotlightImage = mark.querySelector("img");
  if (spotlightImage) {
    spotlightImage.addEventListener("load", () => mark.classList.add("has-image"), { once: true });
    spotlightImage.addEventListener("error", () => mark.classList.remove("has-image"), { once: true });
  }

  const body = document.createElement("div");
  const personal = getPersonal(movie);
  const why = [
    movie.tags.includes("Award Winner") ? "premiado" : null,
    movie.tags.includes("Documentary") ? "documentário" : null,
    movie.tags.includes("Dramedy") ? "dramedy" : null,
    movie.runtime && movie.runtime <= 95 ? "bom para hoje" : null,
  ].filter(Boolean);
  body.innerHTML = `
    <p class="eyebrow">Escolha da vez</p>
    <h2>${movie.title}</h2>
    <p class="muted">${movie.year} · ${formatRuntime(movie.runtime)} · ${languageLabel(movie.language)} · ${movie.rating}/10 no Trakt · ${why.join(" · ") || "boa aposta da curadoria"}</p>
    <p>${movie.overview || "Sem sinopse no Trakt."}</p>
    <div class="chips">${uniq([...movie.tags, ...movie.genres, `Idioma: ${languageLabel(movie.language)}`, ...movie.lists]).slice(0, 10).map((chip) => chipMarkup(movie, chip)).join("")}</div>
    <div class="personal-controls">${Object.entries(personalLabels).map(([value, label]) => `<button class="${personal === value ? "is-selected" : ""}" type="button" data-personal="${value}" aria-pressed="${personal === value ? "true" : "false"}">${label}</button>`).join("")}</div>
    <div class="links">${traktUrl(movie) ? `<a href="${traktUrl(movie)}" target="_blank" rel="noreferrer">Abrir no Trakt</a>` : ""}${imdbUrl(movie) ? `<a href="${imdbUrl(movie)}" target="_blank" rel="noreferrer">IMDb</a>` : ""}</div>
  `;
  els.spotlight.append(mark, body);
  bindChips(els.spotlight);
  els.spotlight.querySelectorAll("[data-personal]").forEach((button) => {
    button.addEventListener("click", () => setPersonal(movie, button.dataset.personal));
  });
}

function detailRow(label, value) {
  if (!value) return "";
  return `<div><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function openMovieModal(movie) {
  const links = [
    traktUrl(movie) ? `<a href="${traktUrl(movie)}" target="_blank" rel="noreferrer">Abrir no Trakt</a>` : "",
    imdbUrl(movie) ? `<a href="${imdbUrl(movie)}" target="_blank" rel="noreferrer">Abrir no IMDb</a>` : "",
  ].filter(Boolean);
  const personal = getPersonal(movie);

  els.modalContent.innerHTML = `
    <div class="modal-poster poster-mark ${movie.poster ? "has-image" : ""}" style="background: linear-gradient(145deg, ${colorFor(movie)}, #111615)">
      ${movie.poster ? `<img src="${movie.poster}" alt="Capa de ${escapeHtml(movie.title)}">` : ""}
      <span></span>
    </div>
    <div class="modal-body">
      <p class="eyebrow">${escapeHtml(movie.tags[0] || movie.themes[0] || "Filme")}</p>
      <h2 id="modalTitle">${escapeHtml(movie.title)}</h2>
      <div class="modal-facts">
        ${detailRow("Ano", movie.year)}
        ${detailRow("Duração", formatRuntime(movie.runtime))}
        ${detailRow("Nota Trakt", `${movie.rating}/10`)}
        ${movie.buzz_score != null ? detailRow("Buzz", `${movie.buzz_score}/100 ${buzzArrow(movie.buzz_trend)}`) : ""}
        ${detailRow("Votos", movie.votes.toLocaleString("pt-BR"))}
        ${detailRow("País", movie.country ? movie.country.toUpperCase() : "")}
        ${detailRow("Idioma", languageLabel(movie.language))}
      </div>
      <p class="modal-overview">${escapeHtml(movie.overview || "Sem sinopse no Trakt.")}</p>
      <div class="chips">${uniq([...movie.tags, ...movie.genres, `Idioma: ${languageLabel(movie.language)}`, ...movie.lists]).map((chip) => chipMarkup(movie, chip)).join("")}</div>
      <div class="personal-controls modal-personal">${Object.entries(personalLabels).map(([value, label]) => `<button class="${personal === value ? "is-selected" : ""}" type="button" data-personal="${value}" aria-pressed="${personal === value ? "true" : "false"}">${label}</button>`).join("")}</div>
      <div class="links modal-links">${links.join("")}</div>
    </div>
  `;
  els.modal.hidden = false;
  document.body.classList.add("modal-open");
  els.modal.addEventListener("keydown", trapFocusHandler);
  els.modalClose.focus();
  bindChips(els.modalContent);
  els.modalContent.querySelectorAll("[data-personal]").forEach((button) => {
    button.addEventListener("click", () => setPersonal(movie, button.dataset.personal));
  });
}

function trapFocusHandler(e) {
  if (e.key !== "Tab") return;
  const focusable = Array.from(
    els.modal.querySelectorAll('button:not([disabled]), [href], input, select, textarea, [tabindex]:not([tabindex="-1"])')
  );
  if (!focusable.length) return;
  const first = focusable[0];
  const last = focusable[focusable.length - 1];
  if (e.shiftKey) {
    if (document.activeElement === first) { e.preventDefault(); last.focus(); }
  } else {
    if (document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
}

function closeMovieModal() {
  els.modal.removeEventListener("keydown", trapFocusHandler);
  els.modal.hidden = true;
  els.modalContent.innerHTML = "";
  document.body.classList.remove("modal-open");
}

function scoreForPick(movie, mode) {
  let score = movie.watch_score || 0;
  const personal = getPersonal(movie);
  if (personal === "want") score += 35;
  if (personal === "maybe") score += 10;
  if (personal === "seen" || personal === "ignored") score -= 200;

  if (mode === "safe") {
    score += Math.min(movie.votes || 0, 20000) / 1000;
    score += (movie.rating || 0) * 2;
    score += movie.lists.length * 4;
  } else if (mode === "surprise") {
    score += movie.votes < 2500 ? 28 : 0;
    score += movie.lists.length <= 1 ? 12 : 0;
    score -= movie.votes > 20000 ? 18 : 0;
  } else if (mode === "short") {
    score += movie.runtime && movie.runtime <= 95 ? 45 : -30;
    score += movie.runtime && movie.runtime <= 85 ? 15 : 0;
  } else if (mode === "want") {
    score += personal === "want" ? 70 : 0;
  }
  return score;
}

function pickMovie() {
  const mode = els.pickMode.value;
  const candidates = state.filtered
    .filter((movie) => mode !== "want" || getPersonal(movie) === "want")
    .filter((movie) => mode !== "short" || !movie.runtime || movie.runtime <= 100)
    .filter((movie) => !["seen", "ignored"].includes(getPersonal(movie)));

  if (!candidates.length) {
    renderSpotlight(null);
    return;
  }
  let pool = candidates
    .map((movie) => ({ movie, score: scoreForPick(movie, mode) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, Math.min(mode === "surprise" ? 80 : 35, candidates.length))
    .map((entry) => entry.movie);

  // Evita repetir os últimos picks; reseta o histórico se o pool ficar vazio
  const recent = new Set(state.recentPicks);
  const fresh = pool.filter((m) => !recent.has(movieKey(m)));
  if (fresh.length) pool = fresh;
  else state.recentPicks = [];

  const pick = pool[Math.floor(Math.random() * pool.length)];
  state.recentPicks = [...state.recentPicks.slice(-4), movieKey(pick)];
  renderSpotlight(pick);
}

function setMood(mood) {
  const recipe = moodRecipes[mood];
  if (!recipe) return;

  if (state.activeMoods.has(mood)) {
    state.activeMoods.delete(mood);
    recipe.tags.forEach((tag) => {
      state.filters.tags = removeArrayValue(state.filters.tags, tag);
    });
    recipe.genres.forEach((genre) => {
      state.filters.genres = removeArrayValue(state.filters.genres, genre);
    });
    if (recipe.runtime !== "any" && state.filters.runtime === recipe.runtime) {
      state.filters.runtime = "any";
    }
    // Restaura o sort que estava ativo antes de este mood ser ativado
    state.filters.sort = state.previousSort || "score";
  } else {
    state.previousSort = state.filters.sort;
    state.activeMoods.add(mood);
    recipe.tags.forEach((tag) => {
      if (!state.filters.tags.includes(tag)) state.filters.tags.push(tag);
    });
    recipe.genres.forEach((genre) => {
      if (!state.filters.genres.includes(genre)) state.filters.genres.push(genre);
    });
    state.filters.runtime = recipe.runtime;
    state.filters.sort = recipe.sort;
  }
  els.runtime.value = state.filters.runtime;
  els.sort.value = state.filters.sort;
  renderSpotlight(null);
  applyFilters();
}

function renderGrid() {
  els.grid.innerHTML = "";
  if (!state.filtered.length) {
    els.grid.innerHTML = `<div class="empty-state"><strong>Nenhum filme nesse recorte.</strong><span>Desative uma tag ou limpe os filtros para abrir o leque de novo.</span></div>`;
    return;
  }
  const fragment = document.createDocumentFragment();
  state.filtered.forEach((movie, i) => {
    const node = renderMovie(movie);
    node.style.setProperty("--card-i", Math.min(i, 20));
    fragment.append(node);
  });
  els.grid.append(fragment);
}

function render() {
  els.count.textContent = `${state.filtered.length} filme(s) no recorte atual`;
  renderMoodButtons();
  renderActiveFilters();
  renderSelectionPanel();
  renderBreakdown();
  renderGrid();
  if (!state.filtered.length) {
    renderSpotlight(null);
    return;
  }
  // Se o filme em destaque não está mais no conjunto filtrado, limpar e repor
  if (state.spotlightMovie && !state.filtered.includes(state.spotlightMovie)) {
    renderSpotlight(null);
  }
  if (!els.spotlight.children.length) renderSpotlight(state.filtered[0]);
}

function bind() {
  els.search.addEventListener("input", () => {
    state.filters.search = els.search.value;
    clearTimeout(searchTimer);
    searchTimer = setTimeout(applyFilters, 180);
  });
  [
    [els.list, "list"],
    [els.tag, "tag"],
    [els.genre, "genre"],
    [els.language, "language"],
    [els.runtime, "runtime"],
    [els.sort, "sort"],
    [els.personalFilter, "personal"],
  ].forEach(([el, key]) => {
    el.addEventListener("change", () => {
      if (key === "list" || key === "tag" || key === "genre" || key === "language") {
        if (el.value !== "all") toggleFilter(key, key === "language" ? `Idioma: ${languageLabel(el.value)}` : el.value);
        el.value = "all";
        return;
      }
      state.filters[key] = el.value;
      renderSpotlight(null);
      applyFilters();
    });
  });
  els.pick.addEventListener("click", pickMovie);
  els.moodBar.querySelectorAll("[data-mood]").forEach((button) => {
    button.addEventListener("click", () => setMood(button.dataset.mood));
  });
  els.modalClose.addEventListener("click", closeMovieModal);
  els.modal.addEventListener("click", (event) => {
    if (event.target === els.modal) closeMovieModal();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && !els.modal.hidden) { closeMovieModal(); return; }

    const tag = document.activeElement?.tagName ?? "";
    const inInput = tag === "INPUT" || tag === "SELECT" || tag === "TEXTAREA";
    if (inInput || !els.modal.hidden) return;

    // Espaço = escolher filme (quando nenhum card está focado)
    if (event.key === " " && !document.activeElement?.closest(".movie-card")) {
      event.preventDefault();
      pickMovie();
      return;
    }

    // Setas = navegar entre cards do grid
    if (event.key === "ArrowRight" || event.key === "ArrowLeft") {
      const cards = [...els.grid.querySelectorAll(".movie-card")];
      const idx = cards.indexOf(document.activeElement);
      if (idx === -1) return;
      event.preventDefault();
      const next = event.key === "ArrowRight" ? idx + 1 : idx - 1;
      if (next >= 0 && next < cards.length) {
        cards[next].focus();
        cards[next].scrollIntoView({ block: "nearest", behavior: "smooth" });
      }
    }
  });
  els.syncBannerClose.addEventListener("click", () => {
    els.syncBanner.hidden = true;
  });

  els.rebuildButton.addEventListener("click", async () => {
    els.rebuildButton.disabled = true;
    els.rebuildButton.textContent = "Atualizando…";
    try {
      const res = await fetch("/api/rebuild", { method: "POST" });
      if (!res.ok) { showSyncBanner("Não foi possível iniciar a atualização."); return; }
      const poll = setInterval(async () => {
        const s = await fetch("/api/rebuild-status").then((r) => r.json());
        if (s.state === "running") return;
        clearInterval(poll);
        els.rebuildButton.disabled = false;
        els.rebuildButton.textContent = "Atualizar dados";
        if (s.state === "done") {
          const response = await fetch("movies.json");
          const payload = await response.json();
          state.movies = payload.movies;
          if (payload.generated_at && els.dataFreshness) {
            els.dataFreshness.textContent = `Dados de ${payload.generated_at.slice(0, 10)}`;
          }
          applyFilters();
          renderStats();
        } else {
          showSyncBanner(`Erro ao atualizar: ${s.message}`);
        }
      }, 3000);
    } catch {
      els.rebuildButton.disabled = false;
      els.rebuildButton.textContent = "Atualizar dados";
      showSyncBanner("Sem conexão com o servidor local.");
    }
  });
  els.buzzButton.addEventListener("click", async () => {
    els.buzzButton.disabled = true;
    els.buzzButton.textContent = "Coletando…";
    try {
      const res = await fetch("/api/buzz", { method: "POST" });
      if (!res.ok) { showSyncBanner("Não foi possível iniciar a coleta de buzz."); return; }
      const poll = setInterval(async () => {
        const s = await fetch("/api/buzz-status").then((r) => r.json());
        if (s.state === "running") return;
        clearInterval(poll);
        els.buzzButton.disabled = false;
        els.buzzButton.textContent = "Atualizar buzz";
        if (s.state === "done") {
          await loadBuzz();
          applyFilters();
        } else {
          showSyncBanner(`Erro ao coletar buzz: ${s.message}`);
        }
      }, 4000);
    } catch {
      els.buzzButton.disabled = false;
      els.buzzButton.textContent = "Atualizar buzz";
      showSyncBanner("Sem conexão com o servidor local.");
    }
  });

  els.reset.addEventListener("click", () => {
    state.filters = { search: "", lists: [], tags: [], genres: [], languages: [], runtime: "any", personal: "active", sort: "score" };
    state.activeMoods.clear();
    state.previousSort = "score";
    localStorage.removeItem(filtersKey);
    els.search.value = "";
    els.list.value = "all";
    els.tag.value = "all";
    els.genre.value = "all";
    els.language.value = "all";
    els.runtime.value = "any";
    els.personalFilter.value = "active";
    els.sort.value = "score";
    renderSpotlight(null);
    applyFilters();
  });
}

async function loadBuzz() {
  try {
    const res = await fetch("buzz.json");
    if (!res.ok) return;
    const data = await res.json();
    const map = {};
    (data.movies || []).forEach((b) => {
      if (b.trakt) map[b.trakt] = b;
    });
    state.movies.forEach((m) => {
      const b = map[m.trakt];
      m.buzz_score = b ? b.buzz_score : null;
      m.buzz_trend = b ? b.trend : null;
    });
  } catch {
    // buzz.json ainda não existe — normal na primeira execução
  }
}

async function syncFromTrakt(movies) {
  try {
    const res = await fetch("/api/want");
    if (!res.ok) return;
    const { trakt_ids } = await res.json();
    if (!Array.isArray(trakt_ids)) return;
    const traktSet = new Set(trakt_ids);
    movies.forEach((movie) => {
      if (!movie.trakt) return;
      const current = getPersonal(movie);
      if (traktSet.has(movie.trakt) && !current) {
        writePersonal(movie, "want");
      } else if (!traktSet.has(movie.trakt) && current === "want") {
        writePersonal(movie, "");
      }
    });
  } catch {
    // servidor não disponível — segue com o localStorage
  }
}

async function boot() {
  initTheme();
  els.grid.innerHTML = `<div class="empty-state loading-state"><strong>Carregando filmes…</strong></div>`;
  const response = await fetch("movies.json");
  const payload = await response.json();
  loadPersonal();
  loadFilters();
  await syncFromTrakt(payload.movies);
  state.movies = payload.movies;
  await loadBuzz();
  if (payload.generated_at && els.dataFreshness) {
    const date = payload.generated_at.slice(0, 10);
    els.dataFreshness.textContent = `Dados de ${date}`;
  }
  if (Array.isArray(payload.misses) && payload.misses.length) {
    els.missesCount.textContent = payload.misses.length;
    els.missesList.innerHTML = payload.misses
      .map((m) => `<li>${escapeHtml(m.input_title || m.title || "?")} (${escapeHtml(String(m.input_year || m.year || ""))})${m.reason ? ` — ${escapeHtml(m.reason)}` : ""}</li>`)
      .join("");
    els.missesPanel.hidden = false;
  }
  optionize(els.list, uniq(state.movies.flatMap((movie) => movie.lists)), "Adicionar lista");
  optionize(els.tag, uniq(state.movies.flatMap((movie) => movie.tags)), "Adicionar categoria");
  optionizeGenres(els.genre, uniq(state.movies.flatMap((movie) => movie.genres)), "Adicionar gênero");
  optionizeLanguages(els.language, uniq(state.movies.map((movie) => movie.language)), "Adicionar idioma");
  // Sincroniza os controles com o estado restaurado
  els.runtime.value      = state.filters.runtime;
  els.sort.value         = state.filters.sort;
  els.personalFilter.value = state.filters.personal;
  renderStats();
  bind();
  applyFilters();
}

boot().catch((error) => {
  els.grid.innerHTML = `<p>Não consegui carregar os dados locais: ${error.message}</p>`;
});
