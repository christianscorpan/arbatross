function initVolticEyeWidget(protocol, host) {
    const container = document.getElementById("voltic-eye-widget");
    container.innerHTML = `
        <div class="voltic-eye-display">
            <h3>Top 10 Volatile Assets (Binance)</h3>
            <ul id="voltic-list"><li>Loading...</li></ul>
        </div>
    `;

    const ws = new WebSocket(`${protocol}//${host}/volatility/ws`);
    const list = document.getElementById("voltic-list");

    ws.onmessage = function(event) {
        try {
            const message = JSON.parse(event.data);
            console.log("VolticEye Received:", JSON.stringify(message, null, 2));
            if (message.top_volatile && message.top_volatile.length > 0) {
                const volatileItems = message.top_volatile
                    .filter(item => item.volatility > 0.0001)
                    .map(item => {
                        const volatility = item.volatility;
                        const displayValue = volatility < 0.01 
                            ? volatility.toFixed(4) 
                            : volatility.toFixed(2);
                        // Split pair before last 4 chars
                        const pair = item.pair;
                        const formattedPair = pair.length > 4 
                            ? `${pair.slice(0, -4)}/${pair.slice(-4)}` 
                            : pair; // Fallback if too short
                        return `<li><span class="clickable-pair" data-pair="${formattedPair}">${formattedPair}</span>: ${displayValue}%</li>`;
                    });
                
                if (volatileItems.length > 0) {
                    list.innerHTML = volatileItems.join("");
                    
                    // Add click event listeners to copy pairs to clipboard
                    document.querySelectorAll('.clickable-pair').forEach(element => {
                        element.style.cursor = 'pointer';
                        element.title = 'Click to copy to clipboard';
                        
                        element.addEventListener('click', function() {
                            const pairText = this.getAttribute('data-pair');
                            navigator.clipboard.writeText(pairText).then(() => {
                                // Visual feedback
                                const originalColor = this.style.color;
                                this.style.color = '#741fb5'; // PURPLE
                                this.textContent = `${pairText}`;
                                
                                // Reset after 1 second
                                setTimeout(() => {
                                    this.style.color = originalColor;
                                    this.textContent = pairText;
                                }, 1000);
                            }).catch(err => {
                                console.error('Failed to copy: ', err);
                            });
                        });
                    });
                } else {
                    list.innerHTML = "<li>No significant volatility detected</li>";
                }
            } else {
                list.innerHTML = "<li>Waiting for volatility data...</li>";
            }
        } catch (error) {
            console.error("VolticEye parse error:", error);
            list.innerHTML = "<li>Error processing data</li>";
        }
    };

    ws.onerror = () => list.innerHTML = "<li>VolticEye service error</li>";
    ws.onclose = () => {
        list.innerHTML = "<li>Disconnected - reconnecting...</li>";
        setTimeout(() => initVolticEyeWidget(protocol, host), 1000);
    };
}
