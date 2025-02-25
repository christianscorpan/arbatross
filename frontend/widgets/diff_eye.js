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
            <p>Estimated Delay: <span id="estimated-delay">N/A</span> ms (RMSE: <span id="rmse-value">N/A</span>)</p>
            <div id="chart-container" style="height: 300px;"><canvas id="price-diff-chart"></canvas></div>
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
                { 
                    label: "slow boi price", 
                    data: [], 
                    borderColor: "#dc3545", 
                    backgroundColor: "rgba(220, 53, 69, 0.1)", 
                    fill: { target: 0, above: "rgba(40, 167, 69, 0.2)", below: "rgba(220, 53, 69, 0.2)" }, 
                    tension: 0.3, 
                    pointRadius: 0 
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: { x: { display: true }, y: { beginAtZero: false, title: { display: true, text: "Price" }, grace: "5%" } },
            plugins: { 
                legend: { display: true, position: "top", labels: { boxWidth: 20, padding: 10 } },
                tooltip: {
                    callbacks: {
                        label: context => `${context.dataset.label}: ${context.raw.toFixed(8)}`,
                        footer: tooltipItems => tooltipItems.length >= 2 ? `Difference: ${(tooltipItems[0].raw - tooltipItems[1].raw).toFixed(8)}` : ""
                    }
                }
            }
        }
    });

    const maxVisualPoints = 60; // Visual chart window
    const bufferSize = 500; // Total updates
    const sampleSize = 100; // Downsampled size for delay calc
    const sampleInterval = Math.floor(bufferSize / sampleSize); // Every 5th update
    let chartData = { labels: [], fastPrices: [], slowPrices: [] };
    let delayData = {
        fastPrices: new Array(bufferSize),
        slowPrices: new Array(bufferSize),
        times: new Array(bufferSize),
        index: 0,
        count: 0
    };

    function updateChart(fastPrice, slowPrice) {
        const now = new Date();
        const timestamp = now.getTime();
        const timeLabel = now.toLocaleTimeString([], { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit", fractionalSecondDigits: 3 });

        // Update chart
        chartData.labels.push(timeLabel);
        chartData.fastPrices.push(fastPrice);
        chartData.slowPrices.push(slowPrice);

        if (chartData.labels.length > maxVisualPoints) {
            chartData.labels.shift();
            chartData.fastPrices.shift();
            chartData.slowPrices.shift();
        }

        chart.data.labels = chartData.labels;
        chart.data.datasets[0].data = chartData.fastPrices;
        chart.data.datasets[1].data = chartData.slowPrices;
        chart.update("none");

        // Update delay data (circular buffer)
        delayData.fastPrices[delayData.index] = fastPrice;
        delayData.slowPrices[delayData.index] = slowPrice;
        delayData.times[delayData.index] = timestamp;
        delayData.index = (delayData.index + 1) % bufferSize;
        delayData.count = Math.min(delayData.count + 1, bufferSize);

        // Calculate delay every 50 updates
        if (delayData.count >= 10 && delayData.count % 50 === 0) {
            calculateAndDisplayDelay();
        }
    }

    function calculateAndDisplayDelay() {
        const { shift, rmse } = calculateOptimalDelay();
        document.getElementById("estimated-delay").textContent = shift;
        document.getElementById("rmse-value").textContent = rmse.toFixed(6);
    }

    function calculateOptimalDelay() {
        const maxShift = 1000; // ±1000 ms
        const step = 5; // 5 ms steps for speed
        let bestShift = 0;
        let minRmse = Infinity;

        if (delayData.count < 10) return { shift: 0, rmse: 0 };

        // Downsample to 100 points
        const sampledData = { fastPrices: [], slowPrices: [], times: [] };
        const stepSize = Math.max(1, Math.floor(delayData.count / sampleSize));
        for (let i = 0; i < delayData.count; i += stepSize) {
            const idx = (delayData.index - delayData.count + i + bufferSize) % bufferSize;
            sampledData.fastPrices.push(delayData.fastPrices[idx]);
            sampledData.slowPrices.push(delayData.slowPrices[idx]);
            sampledData.times.push(delayData.times[idx]);
        }

        for (let shift = -maxShift; shift <= maxShift; shift += step) {
            let squaredErrorSum = 0;
            let count = 0;

            for (let i = 0; i < sampledData.times.length; i++) {
                const baseTime = sampledData.times[i];
                const shiftedTime = baseTime + shift;

                // Binary search for nearest fast price (faster than linear scan)
                let fastPriceAtShift = null;
                let left = 0, right = sampledData.times.length - 1;
                let minTimeDiff = Infinity;
                while (left <= right) {
                    const mid = Math.floor((left + right) / 2);
                    const timeDiff = Math.abs(sampledData.times[mid] - shiftedTime);
                    if (timeDiff < minTimeDiff) {
                        minTimeDiff = timeDiff;
                        fastPriceAtShift = sampledData.fastPrices[mid];
                    }
                    if (sampledData.times[mid] < shiftedTime) left = mid + 1;
                    else right = mid - 1;
                }

                if (fastPriceAtShift != null && sampledData.slowPrices[i] != null) {
                    const error = fastPriceAtShift - sampledData.slowPrices[i];
                    squaredErrorSum += error * error;
                    count++;
                }
            }

            if (count > 0) {
                const rmse = Math.sqrt(squaredErrorSum / count);
                if (rmse < minRmse) {
                    minRmse = rmse;
                    bestShift = shift;
                }
            }
        }

        return { shift: bestShift, rmse: minRmse };
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
                delayData = {
                    fastPrices: new Array(bufferSize),
                    slowPrices: new Array(bufferSize),
                    times: new Array(bufferSize),
                    index: 0,
                    count: 0
                };
                chart.data.labels = [];
                chart.data.datasets[0].data = [];
                chart.data.datasets[1].data = [];
                document.getElementById("estimated-delay").textContent = "N/A";
                document.getElementById("rmse-value").textContent = "N/A";
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
            if (data.fast_price != null && data.slow_price != null) {
                updateChart(Number(data.fast_price), Number(data.slow_price));
            }
        }
    };

    ws.onerror = () => document.getElementById("status").textContent = "Connection error - retrying...";
    ws.onclose = () => {
        document.getElementById("status").textContent = "Disconnected - reconnecting...";
        setTimeout(() => initDiffEyeWidget(protocol, host), 1000);
    };
}