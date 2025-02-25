function initDiffEyeWidget(protocol, host) {
    const container = document.getElementById("diff-eye-widget");
    container.innerHTML = `
        <div class="diff-eye-display">
            <div id="controls">
                <input id="asset-search" placeholder="Search asset (e.g., BTC/USDT, ETH/XBT)">
                <select id="exchange-select"><option value="">Select an exchange</option></select>
            </div>
            <p>Asset: <span id="selected-asset">-</span></p>
            <p>Binance Price (<span id="binance-pair">-</span>): <span id="fast-price" class="price">N/A</span></p>
            <p><span id="slow-exchange">Slow</span> Price (<span id="slow-pair">-</span>): <span id="slow-price" class="price">N/A</span></p>
            <p>Price Difference: <span id="price-diff" class="price">N/A</span>%</p>
            <div id="chart-container"><canvas id="price-diff-chart"></canvas></div>
            <p id="status">Waiting for data...</p>
        </div>
    `;

    const ws = new WebSocket(`${protocol}//${host}/ws`);
    let currentAsset = "", currentExchange = "", debounceTimeout;

    const chart = new Chart(document.getElementById("price-diff-chart").getContext("2d"), {
        type: "line",
        data: {
            labels: [],
            datasets: [
                { label: "fast boi price", data: [], borderColor: "#007bff", backgroundColor: "rgba(0, 123, 255, 0.1)", fill: false, tension: 0.3, pointRadius: 0 },
                { label: "slow boi price", data: [], borderColor: "#dc3545", backgroundColor: "rgba(220, 53, 69, 0.1)", fill: false, tension: 0.3, pointRadius: 0 }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { x: { display: false }, y: { beginAtZero: false, title: { display: true, text: "Price" } } },
            plugins: { legend: { display: true, position: "top", labels: { boxWidth: 20, padding: 10 } } }
        }
    });

    const maxPoints = 60;
    let chartData = { labels: [], fastPrices: [], slowPrices: [] };

    function updateChart(fastPrice, slowPrice) {
        const now = new Date().toLocaleTimeString();
        chartData.labels.push(now);
        chartData.fastPrices.push(fastPrice);
        chartData.slowPrices.push(slowPrice);
        if (chartData.labels.length > maxPoints) {
            chartData.labels.shift();
            chartData.fastPrices.shift();
            chartData.slowPrices.shift();
        }
        chart.data.labels = chartData.labels;
        chart.data.datasets[0].data = chartData.fastPrices;
        chart.data.datasets[1].data = chartData.slowPrices;
        chart.update("none");
    }

    fetch("/exchanges")
        .then(response => response.json())
        .then(exchanges => {
            const select = document.getElementById("exchange-select");
            exchanges.forEach(ex => {
                const option = document.createElement("option");
                option.value = ex;
                option.text = ex.charAt(0).toUpperCase() + ex.slice(1);
                select.appendChild(option);
            });
        })
        .catch(err => console.error("Failed to load exchanges:", err));

    function sendSubscription() {
        clearTimeout(debounceTimeout);
        debounceTimeout = setTimeout(() => {
            const asset = document.getElementById("asset-search").value.toUpperCase().trim();
            const exchange = document.getElementById("exchange-select").value;
            if (asset && exchange && (asset !== currentAsset || exchange !== currentExchange)) {
                currentAsset = asset;
                currentExchange = exchange;
                ws.send(JSON.stringify({ asset, exchange }));
                document.getElementById("status").textContent = `Connecting to ${exchange} for ${asset}...`;
                document.getElementById("selected-asset").textContent = asset;
                document.getElementById("slow-exchange").textContent = exchange.charAt(0).toUpperCase() + exchange.slice(1);
                chartData = { labels: [], fastPrices: [], slowPrices: [] };
                chart.data.labels = [];
                chart.data.datasets[0].data = [];
                chart.data.datasets[1].data = [];
                chart.update();
            }
        }, 300);
    }

    document.getElementById("asset-search").addEventListener("input", sendSubscription);
    document.getElementById("exchange-select").addEventListener("change", sendSubscription);

    ws.onmessage = function(event) {
        const message = JSON.parse(event.data);
        console.log("DiffEye Received:", message);
        if (message.asset_diff) {
            const data = message.asset_diff;
            document.getElementById("selected-asset").textContent = data.asset;
            document.getElementById("binance-pair").textContent = data.fast_pair || "-";
            document.getElementById("slow-pair").textContent = data.slow_pair || "-";
            document.getElementById("status").textContent = "Live updates";
            document.getElementById("fast-price").textContent = data.fast_price != null ? Number(data.fast_price).toFixed(10) : "N/A";
            document.getElementById("slow-price").textContent = data.slow_price != null ? Number(data.slow_price).toFixed(10) : "N/A";
            const diffSpan = document.getElementById("price-diff");
            if (data.diff != null) {
                diffSpan.textContent = Number(data.diff).toFixed(6);
                diffSpan.className = "price " + (data.diff > 0 ? "diff-positive" : "diff-negative");
            } else {
                diffSpan.textContent = "N/A";
                diffSpan.className = "price";
            }
            updateChart(data.fast_price != null ? Number(data.fast_price) : null, data.slow_price != null ? Number(data.slow_price) : null);
        }
    };

    ws.onerror = () => document.getElementById("status").textContent = "Connection error - retrying...";
    ws.onclose = () => {
        document.getElementById("status").textContent = "Disconnected - reconnecting...";
        setTimeout(() => initDiffEyeWidget(protocol, host), 1000); // Re-init to reconnect
    };
}