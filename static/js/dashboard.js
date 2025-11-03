// Dashboard JavaScript - Chart.js and API interactions
console.log('Dashboard.js loaded!');

document.addEventListener('DOMContentLoaded', function() {
    console.log('DOM Content Loaded - Initializing FinTrack');
    
    // Initialize all components
    initializeSpendingChart();
    setupSyncButton();
    setupDemoDataButton();
    setupCategoryDropdowns();
});

// Global chart instance
let spendingChart = null;

/**
 * Initialize the spending chart
 */
function initializeSpendingChart() {
    const ctx = document.getElementById('spending-chart');
    if (!ctx) {
        console.warn('Chart canvas not found');
        return;
    }
    
    console.log('Fetching spending data...');
    
    fetch('/api/spending-by-category')
        .then(response => response.json())
        .then(data => {
            console.log('Spending data:', data);
            if (data.labels && data.labels.length > 0) {
                renderChart(data.labels, data.data);
            } else {
                renderEmptyChart();
            }
        })
        .catch(error => {
            console.error('Error fetching spending data:', error);
            renderEmptyChart();
        });
}

/**
 * Render the doughnut chart
 */
function renderChart(labels, data) {
    const ctx = document.getElementById('spending-chart').getContext('2d');
    
    if (spendingChart) {
        spendingChart.destroy();
    }
    
    spendingChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                label: 'Spending (₹)',
                data: data,
                backgroundColor: [
                    '#FF6384', '#36A2EB', '#FFCE56', '#4BC0C0', '#9966FF', 
                    '#FF9F40', '#FF6384', '#C9CBCF', '#4BC0C0', '#FF9F40',
                    '#8B5CF6', '#10B981'
                ],
                borderWidth: 2,
                borderColor: '#ffffff',
                hoverOffset: 10
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: true,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 15,
                        font: { size: 12 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            let label = context.label || '';
                            if (label) {
                                label += ': ';
                            }
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
    
    console.log('Chart rendered successfully');
}

/**
 * Render empty chart
 */
function renderEmptyChart() {
    const ctx = document.getElementById('spending-chart').getContext('2d');
    
    if (spendingChart) {
        spendingChart.destroy();
    }
    
    spendingChart = new Chart(ctx, {
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
    
    console.log('Empty chart rendered');
}

/**
 * Setup sync button
 */
function setupSyncButton() {
    const syncBtn = document.getElementById('sync-btn');
    const syncStatus = document.getElementById('sync-status');
    
    if (!syncBtn) {
        console.log('Sync button not found (bank not linked yet)');
        return;
    }
    
    console.log('Sync button found and initialized');
    
    syncBtn.addEventListener('click', function() {
        console.log('Sync button clicked');
        
        syncBtn.classList.add('loading');
        syncBtn.disabled = true;
        syncStatus.textContent = 'Syncing transactions...';
        syncStatus.className = 'text-sm font-medium text-blue-600';
        
        fetch('/api/bank/sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(response => response.json())
        .then(data => {
            console.log('Sync response:', data);
            if (data.status === 'success') {
                syncStatus.textContent = '✓ ' + data.message;
                syncStatus.className = 'text-sm font-medium text-green-600';
                setTimeout(() => window.location.reload(), 1500);
            } else {
                syncStatus.textContent = '✗ Error: ' + data.message;
                syncStatus.className = 'text-sm font-medium text-red-600';
            }
        })
        .catch(error => {
            console.error('Sync error:', error);
            syncStatus.textContent = '✗ Sync failed';
            syncStatus.className = 'text-sm font-medium text-red-600';
        })
        .finally(() => {
            syncBtn.classList.remove('loading');
            syncBtn.disabled = false;
        });
    });
}

/**
 * Setup demo data button - CRITICAL FUNCTION
 */
function setupDemoDataButton() {
    const demoBtn = document.getElementById('generate-demo-btn');
    const syncStatus = document.getElementById('sync-status');
    
    if (!demoBtn) {
        console.log('Demo button not found (bank not linked yet)');
        return;
    }
    
    console.log('✓ Demo data button found and initialized!');
    
    demoBtn.addEventListener('click', function() {
        console.log('🎯 Demo data button clicked!');
        
        if (!confirm('This will replace all existing transactions with 3 months of demo data. Continue?')) {
            console.log('User cancelled demo data generation');
            return;
        }
        
        console.log('Starting demo data generation...');
        
        demoBtn.classList.add('loading');
        demoBtn.disabled = true;
        syncStatus.textContent = 'Generating demo data...';
        syncStatus.className = 'text-sm font-medium text-blue-600';
        
        fetch('/api/demo/generate-data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(response => {
            console.log('Response status:', response.status);
            if (!response.ok) {
                throw new Error('Server responded with status: ' + response.status);
            }
            return response.json();
        })
        .then(data => {
            console.log('✓ Demo data response:', data);
            if (data.status === 'success') {
                syncStatus.textContent = '✓ ' + data.message;
                syncStatus.className = 'text-sm font-medium text-green-600';
                alert('Success! Generated ' + data.transactions + ' transactions!\n\nRefreshing page...');
                setTimeout(() => window.location.reload(), 1000);
            } else {
                syncStatus.textContent = '✗ Error: ' + data.message;
                syncStatus.className = 'text-sm font-medium text-red-600';
                alert('Error: ' + data.message);
            }
        })
        .catch(error => {
            console.error('✗ Demo data generation error:', error);
            syncStatus.textContent = '✗ Failed to generate demo data';
            syncStatus.className = 'text-sm font-medium text-red-600';
            alert('Error: ' + error.message + '\n\nCheck the browser console for details.');
        })
        .finally(() => {
            demoBtn.classList.remove('loading');
            demoBtn.disabled = false;
        });
    });
}

/**
 * Setup category dropdowns
 */
function setupCategoryDropdowns() {
    const categorySelects = document.querySelectorAll('.category-select');
    console.log('Found ' + categorySelects.length + ' category dropdowns');
    
    categorySelects.forEach(select => {
        select.setAttribute('data-original-value', select.value);
        
        select.addEventListener('change', function() {
            const transactionId = this.getAttribute('data-transaction-id');
            const categoryId = this.value;
            const originalValue = this.getAttribute('data-original-value');
            
            console.log('Category changed for transaction ' + transactionId);
            updateTransactionCategory(transactionId, categoryId, this, originalValue);
        });
    });
}

/**
 * Update transaction category
 */
function updateTransactionCategory(transactionId, categoryId, selectElement, originalValue) {
    selectElement.disabled = true;
    selectElement.style.opacity = '0.6';
    
    fetch('/api/transactions/' + transactionId + '/categorize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ category_id: categoryId || null })
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to update category');
        }
        return response.json();
    })
    .then(data => {
        if (data.status === 'success') {
            selectElement.setAttribute('data-original-value', categoryId);
            console.log('Category updated successfully');
            
            // Visual feedback
            selectElement.style.borderColor = '#10B981';
            setTimeout(() => {
                selectElement.style.borderColor = '';
            }, 1000);
            
            // Refresh chart
            initializeSpendingChart();
        } else {
            selectElement.value = originalValue;
            alert('Failed to update category: ' + data.message);
        }
    })
    .catch(error => {
        console.error('Category update error:', error);
        selectElement.value = originalValue;
        alert('Failed to update category. Please try again.');
    })
    .finally(() => {
        selectElement.disabled = false;
        selectElement.style.opacity = '1';
    });
}

console.log('✓ Dashboard.js loaded completely');
