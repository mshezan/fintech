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
    
    const selectedAccount = getSelectedAccountFromURL();
    
    renderChart(undefined, selectedAccount); // Month is not required by API
    
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
    if (!selector) {
        console.log('Month selector not found');
        return;
    }
    
    console.log('✓ Month selector initialized');
    
    selector.addEventListener('change', function() {
        const selectedMonth = this.value;
        const selectedAccount = getSelectedAccountFromURL();
        
        console.log('Month changed to:', selectedMonth, 'Account:', selectedAccount);
        
        // Update URL and reload page
        window.location.href = `/?month=${selectedMonth}&account=${selectedAccount}`;
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
    const url = `/api/monthly-activity?account=${account}`;
    
    fetch(url)
        .then(response => {
            return response.json().then(data => ({ ok: response.ok, data }));
        })
        .then(({ ok, data }) => {
            console.log('Chart data received:', data);
            if (!data || (data.status === 'error')) {
                displayEmptyChart();
                return;
            }
            const labels = Array.isArray(data.labels) ? data.labels : [];
            const incomeData = Array.isArray(data.income) ? data.income : [];
            const expenseData = Array.isArray(data.expense) ? data.expense : [];
            
            if (labels.length > 0) {
                displayChart(labels, incomeData, expenseData);
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
 * @param {Array} incomeData - Income amounts
 * @param {Array} expenseData - Expense amounts
 */
function displayChart(labels, incomeData, expenseData) {
    const ctx = document.getElementById('spending-chart');
    if (!ctx) {
        console.error('Chart canvas not found');
        return;
    }
    
    const canvasCtx = ctx.getContext('2d');
    
    // Destroy existing chart if it exists
    if (spendingChart) {
        spendingChart.destroy();
    }
    
    console.log('Creating new chart with labels:', labels);
    
    // Create new chart
    spendingChart = new Chart(canvasCtx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [
                {
                    label: 'Income',
                    data: incomeData,
                    backgroundColor: 'rgba(96, 165, 250, 0.75)',
                    borderColor: 'rgba(96, 165, 250, 0.9)',
                    borderWidth: 1,
                    borderRadius: 5,
                    borderSkipped: false
                },
                {
                    label: 'Expense',
                    data: expenseData,
                    backgroundColor: 'rgba(248, 113, 113, 0.75)',
                    borderColor: 'rgba(248, 113, 113, 0.9)',
                    borderWidth: 1,
                    borderRadius: 5,
                    borderSkipped: false
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    backgroundColor: 'rgba(0, 0, 0, 0.8)',
                    padding: 12,
                    titleFont: { size: 14, weight: 'bold' },
                    bodyFont: { size: 13 },
                    cornerRadius: 8,
                    callbacks: {
                        label: function(context) {
                            let label = context.dataset.label || '';
                            if (label) label += ': ';
                            const v = context.parsed.y;
                            if (v >= 100000)  label += '₹' + (v / 100000).toFixed(2) + 'L';
                            else if (v >= 1000) label += '₹' + (v / 1000).toFixed(1) + 'k';
                            else label += '₹' + v.toFixed(2);
                            return label;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    grid: {
                        color: 'rgba(255, 255, 255, 0.05)'
                    },
                    ticks: {
                        color: '#a1a1aa',
                        font: { size: 11 },
                        maxTicksLimit: 5,
                        callback: function(value) {
                            if (value === 0) return '0';
                            if (value >= 10000000) return '₹' + (value / 10000000).toFixed(1) + 'Cr';
                            if (value >= 100000)   return '₹' + (value / 100000).toFixed(1) + 'L';
                            if (value >= 1000)     return '₹' + (value / 1000).toFixed(0) + 'k';
                            return '₹' + value;
                        }
                    }
                },
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        color: '#a1a1aa'
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
    const legend = document.getElementById('chart-legend');
    if (legend) legend.style.display = 'none';

    const ctx = document.getElementById('spending-chart');
    if (!ctx) return;
    
    const canvasCtx = ctx.getContext('2d');
    
    if (spendingChart) {
        spendingChart.destroy();
    }
    
    spendingChart = new Chart(canvasCtx, {
        type: 'bar',
        data: {
            labels: ['No Data'],
            datasets: [{
                data: [0],
                backgroundColor: ['#3f3f46'],
                borderWidth: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: { enabled: false }
            },
            scales: {
                y: { display: false, max: 1 },
                x: { display: false }
            }
        }
    });
    
    console.log('✓ Empty chart displayed');
}

console.log('✓ Dashboard.js loaded successfully');
