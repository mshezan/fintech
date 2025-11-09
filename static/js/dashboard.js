/**
 * FinTrack Dashboard JavaScript - Multi-Account Support
 * Handles chart rendering, month selector, and account filtering
 */

let spendingChart = null;

/**
 * Initialize dashboard on page load
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('✓ Dashboard page loaded');
    
    const selectedMonth = document.getElementById('month-selector').value;
    const selectedAccount = getSelectedAccountFromURL();
    
    renderChart(selectedMonth, selectedAccount);
    setupMonthSelector();
});


/**
 * Get selected account from URL parameters
 */
function getSelectedAccountFromURL() {
    const params = new URLSearchParams(window.location.search);
    return params.get('account') || 'all';
}


/**
 * Setup month selector change listener
 */
function setupMonthSelector() {
    const selector = document.getElementById('month-selector');
    if (!selector) return;
    
    selector.addEventListener('change', function() {
        const selectedMonth = this.value;
        const selectedAccount = getSelectedAccountFromURL();
        
        console.log('Month changed to:', selectedMonth);
        
        // Update chart with new month data
        renderChart(selectedMonth, selectedAccount);
        
        // Update URL without page reload
        window.history.pushState({}, '', `/?month=${selectedMonth}&account=${selectedAccount}`);
    });
}


/**
 * Render the spending by category chart
 * @param {string} month - Month in YYYY-MM format
 * @param {string} account - Account ID or 'all' for combined
 */
function renderChart(month, account) {
    console.log('Rendering chart for month:', month, 'account:', account);
    
    // Build fetch URL with account parameter
    const url = `/api/spending-by-category?month=${month}&account=${account}`;
    
    fetch(url)
        .then(response => {
            if (!response.ok) {
                throw new Error('Failed to fetch spending data: ' + response.status);
            }
            return response.json();
        })
        .then(data => {
            console.log('Chart data received:', data);
            
            if (data.labels && data.labels.length > 0) {
                displayChart(data.labels, data.data);
            } else {
                displayEmptyChart();
            }
        })
        .catch(error => {
            console.error('Error fetching chart data:', error);
            displayEmptyChart();
        });
}


/**
 * Display chart with data
 * @param {Array} labels - Category names
 * @param {Array} data - Spending amounts
 */
function displayChart(labels, data) {
    const ctx = document.getElementById('spending-chart');
    if (!ctx) return;
    
    const canvasCtx = ctx.getContext('2d');
    
    // Destroy existing chart if it exists
    if (spendingChart) {
        spendingChart.destroy();
    }
    
    console.log('Creating new chart with labels:', labels, 'and data:', data);
    
    // Create new chart
    spendingChart = new Chart(canvasCtx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                label: 'Spending (₹)',
                data: data,
                backgroundColor: [
                    '#FF6384',
                    '#36A2EB',
                    '#FFCE56',
                    '#4BC0C0',
                    '#9966FF',
                    '#FF9F40',
                    '#C9CBCF',
                    '#8B5CF6',
                    '#10B981',
                    '#F59E0B',
                    '#EC4899',
                    '#6366F1'
                ],
                borderWidth: 3,
                borderColor: '#ffffff',
                hoverOffset: 15
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        font: { size: 13, weight: '600' },
                        usePointStyle: true,
                        pointStyle: 'circle'
                    }
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    titleFont: { size: 14, weight: 'bold' },
                    bodyFont: { size: 13 },
                    cornerRadius: 8,
                    callbacks: {
                        label: function(context) {
                            let label = context.label || '';
                            if (label) label += ': ';
                            label += '₹' + context.parsed.toFixed(2);
                            
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = ((context.parsed / total) * 100).toFixed(1);
                            label += ' (' + percentage + '%)';
                            
                            return label;
                        }
                    }
                }
            }
        }
    });
    
    console.log('✓ Chart rendered successfully');
}


/**
 * Display empty chart state (no data available)
 */
function displayEmptyChart() {
    const ctx = document.getElementById('spending-chart');
    if (!ctx) return;
    
    const canvasCtx = ctx.getContext('2d');
    
    if (spendingChart) {
        spendingChart.destroy();
    }
    
    spendingChart = new Chart(canvasCtx, {
        type: 'doughnut',
        data: {
            labels: ['No Data'],
            datasets: [{
                data: [1],
                backgroundColor: ['#E5E7EB'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            }
        }
    });
    
    console.log('✓ Empty chart displayed');
}

console.log('✓ Dashboard.js loaded successfully');
