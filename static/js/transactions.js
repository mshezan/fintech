/**
 * FinTrack Transactions JavaScript - Multi-Account Support
 * Handles transaction filtering and categorization
 */

/**
 * Initialize transactions page on load
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('✓ Transactions page loaded');
    
    // Setup month selector
    setupMonthSelector();
    
    // Setup category dropdowns with event delegation
    setupCategoryDropdowns();
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
        console.warn('Month selector not found');
        return;
    }
    
    console.log('✓ Month selector initialized');
    
    selector.addEventListener('change', function() {
        const selectedMonth = this.value;
        const selectedAccount = getSelectedAccountFromURL();
        
        console.log('Month changed to:', selectedMonth);
        
        // Reload page with new month parameter while keeping account filter
        window.location.href = `/transactions?month=${selectedMonth}&account=${selectedAccount}`;
    });
}


/**
 * Setup category dropdown change handlers using event delegation
 */
function setupCategoryDropdowns() {
    const tableContainer = document.getElementById('transaction-table-container');
    if (!tableContainer) {
        console.warn('Transaction table container not found');
        return;
    }
    
    console.log('✓ Category dropdown listeners initialized');
    
    // Event delegation - listen for changes on all dropdowns
    tableContainer.addEventListener('change', function(event) {
        // Check if the changed element is a select (category dropdown)
        if (event.target.classList.contains('category-select')) {
            const dropdown = event.target;
            const transactionId = dropdown.getAttribute('data-tx-id');
            const categoryId = dropdown.value;
            
            console.log('Category changed for transaction:', transactionId, 'to:', categoryId);
            
            // Store original value in case of error
            const originalValue = dropdown.value;
            
            // Disable dropdown during update
            dropdown.disabled = true;
            dropdown.style.opacity = '0.6';
            
            // Send update to server
            updateTransactionCategory(transactionId, categoryId, dropdown, originalValue);
        }
    });
}


/**
 * Update transaction category via API
 * @param {number} transactionId - Transaction ID
 * @param {number|null} categoryId - Category ID (null for uncategorized)
 * @param {HTMLElement} dropdown - The dropdown element
 * @param {number|null} originalValue - Original category value
 */
function updateTransactionCategory(transactionId, categoryId, dropdown, originalValue) {
    // Prepare data
    const data = {
        category_id: categoryId || null
    };
    
    // Send POST request to API
    fetch('/api/transactions/' + transactionId + '/categorize', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(data)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error('Failed to update category: ' + response.status);
        }
        return response.json();
    })
    .then(data => {
        console.log('✓ Category updated successfully:', data);
        
        // Show success feedback
        dropdown.style.borderColor = '#10B981';
        
        // Reset after 1 second
        setTimeout(() => {
            dropdown.style.borderColor = '';
        }, 1000);
    })
    .catch(error => {
        console.error('✗ Error updating category:', error);
        
        // Revert to original value on error
        dropdown.value = originalValue;
        
        // Show error message
        alert('Failed to update category. Please try again.');
    })
    .finally(() => {
        // Re-enable dropdown
        dropdown.disabled = false;
        dropdown.style.opacity = '1';
    });
}

console.log('✓ Transactions.js loaded successfully');
