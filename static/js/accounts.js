/**
 * FinTrack Accounts JavaScript - Multi-Account Management
 * Handles account operations, sync, and demo data generation
 */

/**
 * Initialize accounts page on load
 */
document.addEventListener('DOMContentLoaded', function() {
    console.log('✓ Accounts page loaded');
    
    // Setup demo data button
    setupDemoDataButton();
});


/**
 * Setup generate demo data button
 */
function setupDemoDataButton() {
    const btn = document.getElementById('generate-demo-btn');
    const status = document.getElementById('sync-status');
    
    if (!btn) {
        console.warn('Demo data button not found');
        return;
    }
    
    console.log('✓ Demo data button initialized');
    
    btn.addEventListener('click', function() {
        console.log('Demo data button clicked');
        
        // Confirm with user
        if (!confirm('Generate 3 months of demo transaction data? This will replace existing transactions.')) {
            console.log('User cancelled demo data generation');
            return;
        }
        
        // Disable button and show loading state
        btn.disabled = true;
        btn.classList.add('opacity-75');
        status.textContent = 'Generating demo data...';
        status.className = 'text-sm font-medium text-blue-600 mt-4 block';
        
        // Call generate demo data API
        fetch('/api/demo/generate-data', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Generation failed: ' + response.status);
            }
            return response.json();
        })
        .then(data => {
            console.log('✓ Demo data generated:', data);
            
            if (data.status === 'success') {
                status.textContent = '✓ ' + data.message;
                status.className = 'text-sm font-medium text-green-600 mt-4 block';
                
                // Show success alert
                alert('Success! Generated ' + data.transactions + ' demo transactions.\n\nRefreshing page...');
                
                // Reload after 1 second
                setTimeout(() => {
                    window.location.reload();
                }, 1000);
            } else {
                status.textContent = '✗ Failed: ' + data.message;
                status.className = 'text-sm font-medium text-red-600 mt-4 block';
            }
        })
        .catch(error => {
            console.error('✗ Demo data generation error:', error);
            
            status.textContent = '✗ Failed to generate demo data. Please try again.';
            status.className = 'text-sm font-medium text-red-600 mt-4 block';
        })
        .finally(() => {
            // Re-enable button
            btn.disabled = false;
            btn.classList.remove('opacity-75');
        });
    });
}

console.log('✓ Accounts.js loaded successfully');
