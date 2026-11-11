const DATA_FILES = [
  "overview",
  "monthly",
  "yoy",
  "categories",
  "category_freight",
  "delivery_delay",
  "repeat",
  "cohort",
  "states",
  "sellers",
  "payment_mix",
];

const state = {
  data: {},
  charts: {},
  view: "overview",
  year: "all",
  category: "all",
  metadata: null,
  categorySearch: "",
  categoryLimit: "20",
  stateSearch: "",
  stateSort: "late",
  stateLimit: "10",
  sellerSearch: "",
  sellerSort: "late",
  sellerLimit: "10",
};

const currency = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "BRL",
  maximumFractionDigits: 2,
});
const number = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
const oneDecimal = new Intl.NumberFormat("en-US", { maximumFractionDigits: 1 });
const compact = new Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 });

function value(row, key) {
  return Number(row?.[key] ?? 0);
}

function formatCurrency(input) {
  return currency.format(value({ input }, "input"));
}

function filterAndLimit(rows, search, limit, textFields) {
  const normalizedSearch = search.trim().toLowerCase();
  const filtered = normalizedSearch
    ? rows.filter((row) => textFields.some((field) =>
      String(row[field] ?? "").toLowerCase().includes(normalizedSearch)))
    : rows;
  return limit === "all" ? filtered : filtered.slice(0, Number(limit));
}

function sortRows(rows, key, direction = "desc") {
  return [...rows].sort((left, right) => {
    const difference = Number(right[key] ?? 0) - Number(left[key] ?? 0);
    return direction === "asc" ? -difference : difference;
  });
}

function formatPercent(input) {
  return `${oneDecimal.format(value({ input }, "input"))}%`;
}

function formatNumber(input) {
  return number.format(value({ input }, "input"));
}

function displayName(input) {
  return String(input ?? "").replaceAll("_", " ");
}

function setText(id, text) {
  const element = document.getElementById(id);
  if (element) element.textContent = text;
}

async function loadData() {
  const entries = await Promise.all(
    DATA_FILES.map(async (name) => {
      const response = await fetch(`data/${name}.json`);
      if (!response.ok) {
        throw new Error(`Could not load data/${name}.json (${response.status})`);
      }
      return [name, await response.json()];
    }),
  );
  state.data = Object.fromEntries(entries);
  const metadataResponse = await fetch("data/metadata.json");
  if (!metadataResponse.ok) {
    throw new Error(`Could not load data/metadata.json (${metadataResponse.status})`);
  }
  state.metadata = await metadataResponse.json();
  const generated = new Date(state.metadata.generated_at_utc);
  setText(
    "refresh-note",
    `Data refreshed ${Number.isNaN(generated.getTime()) ? "recently" : generated.toLocaleString()}`,
  );
}

function filteredMonthly() {
  return state.data.monthly.filter((row) =>
    state.year === "all" || row.year_month.startsWith(state.year),
  );
}

function filteredCategories() {
  if (state.category === "all") return state.data.categories;
  return state.data.categories.filter((row) => row.category === state.category);
}

function destroyCharts() {
  Object.values(state.charts).forEach((chart) => chart.destroy());
  state.charts = {};
}

function baseChartOptions() {
  return {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 350 },
    plugins: {
      legend: { labels: { usePointStyle: true, boxWidth: 8, color: "#667085" } },
      tooltip: { mode: "index", intersect: false },
    },
    scales: {
      x: { grid: { display: false }, ticks: { color: "#667085" } },
      y: { grid: { color: "#edf0f5" }, ticks: { color: "#667085" } },
    },
  };
}

function createChart(id, config) {
  const canvas = document.getElementById(id);
  if (!canvas) return;
  state.charts[id] = new Chart(canvas, config);
}

function updateOverview() {
  const overview = state.data.overview[0];
  const rows = filteredMonthly();
  const deliveredRevenue = state.year === "all"
    ? value(overview, "delivered_revenue")
    : rows.reduce((sum, row) => sum + value(row, "delivered_revenue"), 0);
  const deliveredOrders = state.year === "all"
    ? value(overview, "delivered_orders")
    : rows.reduce((sum, row) => sum + value(row, "delivered_orders"), 0);
  const averageOrderValue = state.year === "all"
    ? value(overview, "average_order_value")
    : deliveredOrders ? deliveredRevenue / deliveredOrders : 0;

  setText("revenue-kpi", formatCurrency(deliveredRevenue));
  setText("orders-kpi", formatNumber(deliveredOrders));
  setText("aov-kpi", formatCurrency(averageOrderValue));
  setText("repeat-kpi", formatPercent((value(overview, "repeat_buyers") / value(overview, "buyers")) * 100));
  setText("late-kpi", formatPercent(value(overview, "late_rate_pct")));

  createChart("trend-chart", {
    type: "line",
    data: {
      labels: rows.map((row) => row.year_month),
      datasets: [
        {
          label: "Revenue",
          data: rows.map((row) => value(row, "delivered_revenue")),
          borderColor: "#2864dc",
          backgroundColor: "rgba(40, 100, 220, 0.12)",
          fill: true,
          tension: 0.3,
          yAxisID: "revenue",
        },
        {
          label: "Delivered orders",
          data: rows.map((row) => value(row, "delivered_orders")),
          borderColor: "#159570",
          tension: 0.3,
          yAxisID: "orders",
        },
      ],
    },
    options: {
      ...baseChartOptions(),
      scales: {
        revenue: {
          position: "left",
          grid: { color: "#edf0f5" },
          ticks: { color: "#667085", callback: (input) => formatCurrency(input) },
        },
        orders: {
          position: "right",
          grid: { drawOnChartArea: false },
          ticks: { color: "#667085", callback: (input) => compact.format(input) },
        },
      },
    },
  });

  createChart("yoy-chart", {
    type: "bar",
    data: {
      labels: state.data.yoy.map((row) => row.year),
      datasets: [
        {
          label: "Delivered revenue",
          data: state.data.yoy.map((row) => value(row, "delivered_revenue")),
          backgroundColor: ["#b9cdfd", "#2864dc"],
          borderRadius: 6,
          yAxisID: "revenue",
        },
        {
          label: "Revenue growth",
          type: "line",
          data: state.data.yoy.map((row) => row.revenue_growth_pct),
          borderColor: "#f0a202",
          pointBackgroundColor: "#f0a202",
          tension: 0.25,
          yAxisID: "growth",
        },
      ],
    },
    options: {
      ...baseChartOptions(),
      scales: {
        revenue: {
          position: "left",
          grid: { color: "#edf0f5" },
          ticks: { color: "#667085", callback: (input) => formatCurrency(input) },
        },
        growth: {
          position: "right",
          grid: { drawOnChartArea: false },
          ticks: { color: "#667085", callback: (input) => formatPercent(input) },
        },
      },
    },
  });

  const paymentRows = state.data.payment_mix.filter((row) => row.section_order === 1);
  createChart("payment-chart", {
    type: "doughnut",
    data: {
      labels: paymentRows.map((row) => displayName(row.payment_group)),
      datasets: [{
        data: paymentRows.map((row) => value(row, "payment_value")),
        backgroundColor: ["#2864dc", "#159570", "#f0a202", "#8d5be8", "#98a2b3"],
        borderWidth: 0,
      }],
    },
    options: {
      ...baseChartOptions(),
      scales: {},
      plugins: {
        ...baseChartOptions().plugins,
        tooltip: { callbacks: { label: (context) => `${context.label}: ${formatCurrency(context.raw)}` } },
      },
    },
  });

  const delayRows = state.data.delivery_delay.filter((row) => value(row, "bucket_order") <= 5);
  createChart("delay-chart", {
    type: "bar",
    data: {
      labels: delayRows.map((row) => row.delay_bucket),
      datasets: [{
        label: "Average review score",
        data: delayRows.map((row) => value(row, "avg_review_score")),
        backgroundColor: ["#159570", "#55b99b", "#f0a202", "#e76f51", "#b42318"],
        borderRadius: 6,
      }],
    },
    options: {
      ...baseChartOptions(),
      scales: {
        ...baseChartOptions().scales,
        y: { min: 0, max: 5, ticks: { stepSize: 1, color: "#667085" }, grid: { color: "#edf0f5" } },
      },
    },
  });

  renderCategoryTable("overview-category-table", filteredCategories().slice(0, 10));
  setText(
    "overview-category-summary",
    state.category === "all" ? "Top 10 categories by delivered revenue" : "Selected category",
  );
}

function updateProducts() {
  const categories = filteredCategories();
  const allCategories = state.data.categories;
  const topCategory = allCategories[0];
  const topTenShare = allCategories.slice(0, 10).reduce((sum, row) => sum + value(row, "revenue_share_pct"), 0);
  const freightRows = state.data.category_freight.filter((row) => value(row, "meets_min_volume") === 1);
  const highestFreight = [...freightRows].sort((a, b) => value(b, "freight_pct_of_price") - value(a, "freight_pct_of_price"))[0];
  const selected = categories[0] || topCategory;

  setText("top-category-kpi", displayName(topCategory.category));
  setText("top-category-detail", `${formatCurrency(topCategory.revenue)} · ${formatPercent(topCategory.revenue_share_pct)} share`);
  setText("pareto-kpi", formatPercent(topTenShare));
  setText("freight-kpi", displayName(highestFreight.category));
  setText("freight-detail", `${formatPercent(highestFreight.freight_pct_of_price)} of item price`);
  setText("category-count-kpi", formatNumber(allCategories.length));

  const categoryRows = (state.category === "all" ? allCategories.slice(0, 15) : [selected]);
  createChart("category-chart", {
    type: "bar",
    data: {
      labels: categoryRows.map((row) => displayName(row.category)),
      datasets: [
        {
          label: "Revenue",
          data: categoryRows.map((row) => value(row, "revenue")),
          backgroundColor: "#2864dc",
          borderRadius: 5,
          yAxisID: "revenue",
        },
        {
          label: "Cumulative share",
          type: "line",
          data: categoryRows.map((row) => value(row, "cumulative_share_pct")),
          borderColor: "#f0a202",
          pointBackgroundColor: "#f0a202",
          tension: 0.25,
          yAxisID: "share",
        },
      ],
    },
    options: {
      ...baseChartOptions(),
      indexAxis: "y",
      scales: {
        revenue: { position: "bottom", grid: { color: "#edf0f5" }, ticks: { color: "#667085", callback: (input) => formatCurrency(input) } },
        share: { position: "top", grid: { drawOnChartArea: false }, min: 0, max: 100, ticks: { color: "#667085", callback: (input) => formatPercent(input) } },
      },
    },
  });

  const freightChartRows = [...freightRows]
    .sort((a, b) => value(b, "freight_pct_of_price") - value(a, "freight_pct_of_price"))
    .slice(0, 10);
  createChart("freight-chart", {
    type: "bar",
    data: {
      labels: freightChartRows.map((row) => displayName(row.category)),
      datasets: [{
        label: "Freight / price",
        data: freightChartRows.map((row) => value(row, "freight_pct_of_price")),
        backgroundColor: "#e76f51",
        borderRadius: 5,
      }],
    },
    options: {
      ...baseChartOptions(),
      indexAxis: "y",
      scales: {
        ...baseChartOptions().scales,
        x: { min: 0, grid: { color: "#edf0f5" }, ticks: { color: "#667085", callback: (input) => formatPercent(input) } },
      },
    },
  });

  createChart("selected-category-chart", {
    type: "bar",
    data: {
      labels: ["Revenue", "Freight"],
      datasets: [{
        label: displayName(selected.category),
        data: [value(selected, "revenue"), value(selected, "freight")],
        backgroundColor: ["#2864dc", "#e76f51"],
        borderRadius: 6,
      }],
    },
    options: {
      ...baseChartOptions(),
      scales: {
        ...baseChartOptions().scales,
        y: { grid: { color: "#edf0f5" }, ticks: { color: "#667085", callback: (input) => formatCurrency(input) } },
      },
    },
  });

  const searchedCategories = filterAndLimit(
    state.category === "all" ? allCategories : [selected],
    state.categorySearch,
    state.categoryLimit,
    ["category"],
  );
  const tableRows = state.category === "all" ? searchedCategories : [selected];
  renderCategoryTable("products-category-table", tableRows);
  setText(
    "products-category-summary",
    state.category === "all" ? "Top 20 categories · select a category for detail" : `Filtered to ${displayName(state.category)}`,
  );
}

function updateCustomers() {
  const overview = state.data.overview[0];
  const allCohorts = state.data.cohort.find((row) => row.cohort_month === "ALL COHORTS");
  const qualifiedStates = state.data.states.filter((row) => value(row, "meets_min_volume") === 1);
  const worstState = qualifiedStates[0];

  setText("repeat-buyers-kpi", formatNumber(overview.repeat_buyers));
  setText("repeat-buyers-detail", `${formatPercent((value(overview, "repeat_buyers") / value(overview, "buyers")) * 100)} of ${formatNumber(overview.buyers)} buyers`);
  setText("return-30-kpi", formatPercent(value(allCohorts, "return_rate_30d_pct")));
  setText("return-180-kpi", formatPercent(value(allCohorts, "return_rate_180d_pct")));
  setText("worst-state-kpi", worstState.customer_state);
  setText("worst-state-detail", `${formatPercent(worstState.late_rate_pct)} late · ${formatNumber(worstState.delivered_orders)} orders`);

  const repeatRows = state.data.repeat.filter((row) => value(row, "bucket_order") <= 5);
  createChart("repeat-chart", {
    type: "bar",
    data: {
      labels: repeatRows.map((row) => row.orders_per_person),
      datasets: [{
        label: "People",
        data: repeatRows.map((row) => value(row, "people")),
        backgroundColor: "#2864dc",
        borderRadius: 6,
      }],
    },
    options: {
      ...baseChartOptions(),
      scales: {
        ...baseChartOptions().scales,
        y: { grid: { color: "#edf0f5" }, ticks: { color: "#667085", callback: (input) => compact.format(input) } },
      },
    },
  });

  const cohortRows = state.data.cohort.filter((row) => row.cohort_month !== "ALL COHORTS");
  createChart("cohort-chart", {
    type: "line",
    data: {
      labels: cohortRows.map((row) => row.cohort_month),
      datasets: [
        { label: "30 days", data: cohortRows.map((row) => row.return_rate_30d_pct), borderColor: "#2864dc", tension: 0.25 },
        { label: "90 days", data: cohortRows.map((row) => row.return_rate_90d_pct), borderColor: "#159570", tension: 0.25 },
        { label: "180 days", data: cohortRows.map((row) => row.return_rate_180d_pct), borderColor: "#f0a202", tension: 0.25 },
      ],
    },
    options: {
      ...baseChartOptions(),
      scales: {
        ...baseChartOptions().scales,
        y: { min: 0, grid: { color: "#edf0f5" }, ticks: { color: "#667085", callback: (input) => formatPercent(input) } },
      },
    },
  });

  const stateChartRows = qualifiedStates.slice(0, 10);
  createChart("state-chart", {
    type: "bar",
    data: {
      labels: stateChartRows.map((row) => row.customer_state),
      datasets: [{
        label: "Late rate",
        data: stateChartRows.map((row) => value(row, "late_rate_pct")),
        backgroundColor: "#e76f51",
        borderRadius: 5,
      }],
    },
    options: {
      ...baseChartOptions(),
      indexAxis: "y",
      scales: {
        ...baseChartOptions().scales,
        x: { min: 0, grid: { color: "#edf0f5" }, ticks: { color: "#667085", callback: (input) => formatPercent(input) } },
      },
    },
  });

  const delayRows = state.data.delivery_delay.filter((row) => value(row, "bucket_order") <= 5);
  createChart("customer-delay-chart", {
    type: "bar",
    data: {
      labels: delayRows.map((row) => row.delay_bucket),
      datasets: [{
        label: "Average review score",
        data: delayRows.map((row) => value(row, "avg_review_score")),
        backgroundColor: ["#159570", "#55b99b", "#f0a202", "#e76f51", "#b42318"],
        borderRadius: 6,
      }],
    },
    options: {
      ...baseChartOptions(),
      scales: {
        ...baseChartOptions().scales,
        y: { min: 0, max: 5, ticks: { stepSize: 1, color: "#667085" }, grid: { color: "#edf0f5" } },
      },
    },
  });

  const filteredStates = filterAndLimit(
    sortRows(qualifiedStates, state.stateSort === "orders"
      ? "delivered_orders"
      : state.stateSort === "revenue" ? "revenue_share_pct" : "late_rate_pct"),
    state.stateSearch,
    state.stateLimit,
    ["customer_state"],
  );
  const qualifiedSellers = state.data.sellers.filter((row) => value(row, "meets_min_volume") === 1);
  const filteredSellers = filterAndLimit(
    sortRows(qualifiedSellers, state.sellerSort === "orders"
      ? "delivered_orders"
      : state.sellerSort === "review" ? "avg_review_score" : "late_rate_pct"),
    state.sellerSearch,
    state.sellerLimit,
    ["seller_id", "seller_state"],
  );
  renderStateTable(filteredStates);
  renderSellerTable(filteredSellers);
}

function appendRow(table, cells) {
  const row = document.createElement("tr");
  cells.forEach((cell) => {
    const tableCell = document.createElement("td");
    tableCell.textContent = String(cell);
    row.appendChild(tableCell);
  });
  table.appendChild(row);
}

function renderCategoryTable(id, rows) {
  const table = document.getElementById(id);
  table.replaceChildren();
  rows.forEach((row) => {
    appendRow(table, [
      row.revenue_rank,
      displayName(row.category),
      formatNumber(row.items_sold),
      formatCurrency(row.revenue),
      formatPercent(row.revenue_share_pct),
      formatPercent(value(row, "revenue") ? (value(row, "freight") / value(row, "revenue")) * 100 : 0),
    ]);
  });
}

function renderStateTable(rows) {
  const table = document.getElementById("state-table");
  table.replaceChildren();
  rows.forEach((row) => {
    appendRow(table, [
      row.late_rate_rank ?? "—",
      row.customer_state,
      formatNumber(row.delivered_orders),
      formatPercent(row.late_rate_pct),
      `${value(row, "avg_delay_days").toFixed(1)} days`,
      value(row, "avg_review_score").toFixed(2),
      formatPercent(row.revenue_share_pct),
    ]);
  });
}

function renderSellerTable(rows) {
  const table = document.getElementById("seller-table");
  table.replaceChildren();
  rows.forEach((row) => {
    appendRow(table, [
      row.late_rate_rank ?? "—",
      `${row.seller_id.slice(0, 8)}…`,
      row.seller_state,
      formatNumber(row.delivered_orders),
      formatPercent(row.late_rate_pct),
      value(row, "avg_review_score").toFixed(2),
    ]);
  });
}

function renderCurrentView() {
  destroyCharts();
  const controlValues = {
    "category-search": state.categorySearch,
    "category-limit": state.categoryLimit,
    "state-search": state.stateSearch,
    "state-sort": state.stateSort,
    "state-limit": state.stateLimit,
    "seller-search": state.sellerSearch,
    "seller-sort": state.sellerSort,
    "seller-limit": state.sellerLimit,
  };
  Object.entries(controlValues).forEach(([id, valueToSet]) => {
    const control = document.getElementById(id);
    if (control) control.value = valueToSet;
  });
  if (state.view === "overview") updateOverview();
  if (state.view === "products") updateProducts();
  if (state.view === "customers") updateCustomers();
  setText(
    "status",
    `${state.view === "overview" ? "Overview" : state.view === "products" ? "Products & categories" : "Customers & delivery"} · ` +
      `${state.year === "all" ? "all trend years" : state.year}` +
      `${state.category === "all" ? "" : ` · ${displayName(state.category)}`}`,
  );
  setText(
    "scope-note",
    state.view === "overview"
      ? "All delivered orders · trend charts use 2017-01 to 2018-08"
      : "All delivered orders · full analysis window",
  );
}

function selectView(view) {
  state.view = view;
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  document.querySelectorAll(".dashboard-page").forEach((page) => {
    page.hidden = page.id !== `${view}-page`;
  });
  renderCurrentView();
}

function populateCategoryFilter() {
  const select = document.getElementById("category-filter");
  state.data.categories.forEach((row) => {
    const option = document.createElement("option");
    option.value = row.category;
    option.textContent = displayName(row.category);
    select.appendChild(option);
  });
}

function bindEvents() {
  document.querySelectorAll(".nav-button").forEach((button) => {
    button.addEventListener("click", () => selectView(button.dataset.view));
  });
  document.getElementById("year-filter").addEventListener("change", (event) => {
    state.year = event.target.value;
    renderCurrentView();
  });
  document.getElementById("category-filter").addEventListener("change", (event) => {
    state.category = event.target.value;
    renderCurrentView();
  });
  document.getElementById("reset-filters").addEventListener("click", () => {
    state.year = "all";
    state.category = "all";
    state.categorySearch = "";
    state.categoryLimit = "20";
    state.stateSearch = "";
    state.stateSort = "late";
    state.    stateLimit = "10";
    state.sellerSearch = "";
    state.sellerSort = "late";
    state.    sellerLimit = "10";
    document.getElementById("year-filter").value = "all";
    document.getElementById("category-filter").value = "all";
    document.getElementById("category-search").value = "";
    document.getElementById("category-limit").value = "20";
    document.getElementById("state-search").value = "";
    document.getElementById("state-sort").value = "late";
    document.getElementById("state-limit").value = "10";
    document.getElementById("seller-search").value = "";
    document.getElementById("seller-sort").value = "late";
    document.getElementById("seller-limit").value = "10";
    renderCurrentView();
  });
  const rerenderOnInput = (id, property) => {
    document.getElementById(id).addEventListener("input", (event) => {
      state[property] = event.target.value;
      renderCurrentView();
    });
    document.getElementById(id).addEventListener("change", (event) => {
      state[property] = event.target.value;
      renderCurrentView();
    });
  };
  rerenderOnInput("category-search", "categorySearch");
  rerenderOnInput("category-limit", "categoryLimit");
  rerenderOnInput("state-search", "stateSearch");
  rerenderOnInput("state-sort", "stateSort");
  rerenderOnInput("state-limit", "stateLimit");
  rerenderOnInput("seller-search", "sellerSearch");
  rerenderOnInput("seller-sort", "sellerSort");
  rerenderOnInput("seller-limit", "sellerLimit");
}

async function start() {
  try {
    if (typeof Chart === "undefined") {
      throw new Error("Chart library did not load. Check the dashboard network connection.");
    }
    await loadData();
    populateCategoryFilter();
    bindEvents();
    selectView("overview");
  } catch (error) {
    const status = document.getElementById("status");
    status.classList.add("error");
    status.textContent = error.message;
  }
}

start();
