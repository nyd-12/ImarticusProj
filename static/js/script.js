document.addEventListener('DOMContentLoaded', () => {
    // === ELEMENTS FOR REPORT GENERATION ===
    const portfolioIdInput = document.getElementById('portfolio-id');
    const reportDateInput = document.getElementById('report-date');
    const generateBtn = document.getElementById('generate-btn');
    const reportContainer = document.getElementById('report-container');
    const loadingDiv = document.getElementById('loading');
    const errorDiv = document.getElementById('error');

    // === ELEMENTS FOR MANUAL TRADE ENTRY ===
    const addTradeForm = document.getElementById('add-trade-form');
    const tradeStatusDiv = document.getElementById('trade-status');

    // === INITIAL SETUP ===
    // Set default date for both date inputs
    const today = new Date().toISOString().split('T')[0];
    reportDateInput.value = today;
    document.getElementById('trade-date').value = today;

    // === EVENT LISTENERS ===
    generateBtn.addEventListener('click', generateReport);
    addTradeForm.addEventListener('submit', addTrade);

    // === REPORT GENERATION LOGIC ===
    async function generateReport() {
        const portfolioId = portfolioIdInput.value;
        const reportDate = reportDateInput.value;

        if (!portfolioId) {
            showError('Please enter a Portfolio ID.');
            return;
        }

        loadingDiv.classList.remove('hidden');
        reportContainer.classList.add('hidden');
        errorDiv.classList.add('hidden');

        try {
            const apiUrl = `/portfolio/${portfolioId}/statement?date=${reportDate}`;
            const response = await fetch(apiUrl);

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.error || `Error: ${response.statusText}`);
            }

            const data = await response.json();
            populateReport(data);

        } catch (error) {
            showError(error.message);
        } finally {
            loadingDiv.classList.add('hidden');
        }
    }

    function populateReport(data) {
        document.getElementById('client-name').textContent = data.client_name;
        document.getElementById('portfolio-name').textContent = data.portfolio_name;
        document.getElementById('res-report-date').textContent = data.report_date;
        document.getElementById('total-value').textContent = data.total_portfolio_value.toFixed(2);
        document.getElementById('base-currency').textContent = data.base_currency;

        document.getElementById('delta').textContent = (data.risk_measures.delta !== undefined && data.risk_measures.delta !== null) ? data.risk_measures.delta : 0;
        document.getElementById('beta').textContent = (data.risk_measures.beta !== undefined && data.risk_measures.beta !== null) ? data.risk_measures.beta : 'N/A';
        document.getElementById('sharpe-ratio').textContent = (data.risk_measures.sharpe_ratio !== undefined && data.risk_measures.sharpe_ratio !== null) ? data.risk_measures.sharpe_ratio : 'N/A';

        const holdingsBody = document.getElementById('holdings-body');
        holdingsBody.innerHTML = '';
        data.holdings.forEach(h => {
            const row = holdingsBody.insertRow();
            row.innerHTML = `
                <td>${h.ticker}</td>
                <td>${h.quantity}</td>
                <td>${h.average_buy_price.toFixed(2)}</td>
                <td>${h.current_price.toFixed(2)}</td>
                <td>${h.current_value.toFixed(2)}</td>
                <td>${h.gain_loss.toFixed(2)}</td>
            `;
        });

        const cashBody = document.getElementById('cash-body');
        cashBody.innerHTML = '';
        data.cash_balances.forEach(c => {
            const row = cashBody.insertRow();
            row.innerHTML = `
                <td>${c.currency}</td>
                <td>${c.amount.toFixed(2)}</td>
            `;
        });

        // === BENCHMARK PERFORMANCE ===
        const benchmarkBody = document.getElementById('benchmark-body');
        benchmarkBody.innerHTML = '';
        if (data.performance_benchmarks && Array.isArray(data.performance_benchmarks)) {
            data.performance_benchmarks.forEach(b => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${b.vs_index !== undefined && b.vs_index !== null ? b.vs_index : 'N/A'}</td>
                    <td>${b.period !== undefined && b.period !== null ? b.period : 'N/A'}</td>
                    <td>${b.portfolio_return_pct !== undefined && b.portfolio_return_pct !== null ? b.portfolio_return_pct : 'N/A'}</td>
                    <td>${b.benchmark_return_pct !== undefined && b.benchmark_return_pct !== null ? b.benchmark_return_pct : 'N/A'}</td>
                `;
                benchmarkBody.appendChild(row);
            });
            document.getElementById('benchmark-performance').classList.remove('hidden');
        } else {
            document.getElementById('benchmark-performance').classList.add('hidden');
        }

        reportContainer.classList.remove('hidden');
    }

    function showError(message) {
        errorDiv.textContent = message;
        errorDiv.classList.remove('hidden');
    }

    // === MANUAL TRADE ENTRY LOGIC ===
    async function addTrade(event) {
        event.preventDefault();
        tradeStatusDiv.classList.add('hidden');

        const tradeData = {
            portfolio_id: document.getElementById('trade-portfolio-id').value,
            security_id: document.getElementById('trade-security-id').value,
            trade_date: document.getElementById('trade-date').value,
            trade_type: document.getElementById('trade-type').value,
            quantity: document.getElementById('trade-quantity').value,
            price_per_unit: document.getElementById('trade-price').value
        };

        try {
            const response = await fetch('/trade', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(tradeData),
            });

            const result = await response.json();
            if (!response.ok) {
                throw new Error(result.error || 'Failed to add trade.');
            }

            showTradeStatus(`Success: ${result.message}`, 'success');
            addTradeForm.reset();
            document.getElementById('trade-date').value = new Date().toISOString().split('T')[0];

        } catch (error) {
            showTradeStatus(`Error: ${error.message}`, 'error');
        }
    }

    function showTradeStatus(message, type) {
        tradeStatusDiv.textContent = message;
        tradeStatusDiv.className = 'trade-status'; // Reset classes
        tradeStatusDiv.classList.add(type);
    }
});