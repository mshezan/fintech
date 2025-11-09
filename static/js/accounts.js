/**
 * FinTrack Accounts JavaScript - Enhanced LinkedAccount Support
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('✓ Accounts page loaded');
    setupSyncButton();
    setupDemoDataButton();
});

function setupSyncButton() {
    const btn = document.getElementById('sync-btn');
    const status = document.getElementById('sync-status');
    const selector = document.getElementById('account-selector');
    
    if (!btn || !selector) {
        console.log('Sync button or account selector not found');
        return;
    }
    
    console.log('✓ Sync button initialized');
    
    btn.addEventListener('click', function() {
        const accountId = selector.value;
        
        if (!accountId) {
            alert('Please select an account to sync');
            return;
        }
        
        console.log('Syncing account:', accountId);
        
        btn.disabled = true;
        btn.classList.add('opacity-75');
        status.textContent = 'Syncing transactions...';
        status.className = 'text-sm font-medium text-blue-600 mt-4 block';
        
        fetch('/api/bank/sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ account_id: parseInt(accountId) })
        })
        .then(response => {
            if (!response.ok) throw new Error('Sync failed: ' + response.status);
            return response.json();
        })
        .then(data => {
            console.log('✓ Sync successful:', data);
            
            if (data.status === 'success') {
                status.textContent = '✓ ' + data.message;
                status.className = 'text-sm font-medium text-green-600 mt-4 block';
                setTimeout(() => window.location.reload(), 2000);
            } else {
                status.textContent = '✗ Sync failed: ' + data.message;
                status.className = 'text-sm font-medium text-red-600 mt-4 block';
            }
        })
        .catch(error => {
            console.error('✗ Sync error:', error);
            status.textContent = '✗ Sync failed. Please try again.';
            status.className = 'text-sm font-medium text-red-600 mt-4 block';
        })
        .finally(() => {
            btn.disabled = false;
            btn.classList.remove('opacity-75');
        });
    });
}

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
        
        if (!confirm('Generate 3 months of demo transaction data? This will replace existing transactions.')) {
            console.log('User cancelled demo data generation');
            return;
        }
        
        btn.disabled = true;
        btn.classList.add('opacity-75');
        
        if (status) {
            status.textContent = 'Generating demo data...';
            status.className = 'text-sm font-medium text-blue-600 mt-4 block';
        }
        
        fetch('/api/demo/generate-data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        })
        .then(response => {
            if (!response.ok) throw new Error('Generation failed: ' + response.status);
            return response.json();
        })
        .then(data => {
            console.log('✓ Demo data generated:', data);
            
            if (data.status === 'success') {
                if (status) {
                    status.textContent = '✓ ' + data.message;
                    status.className = 'text-sm font-medium text-green-600 mt-4 block';
                }
                
                alert('Success! Generated ' + data.transactions + ' demo transactions.\n\nRedirecting to dashboard...');
                
                // Redirect to dashboard instead of reload
                setTimeout(() => {
                    window.location.href = '/';
                }, 1000);
            } else {
                if (status) {
                    status.textContent = '✗ Failed: ' + data.message;
                    status.className = 'text-sm font-medium text-red-600 mt-4 block';
                }
            }
        })
        .catch(error => {
            console.error('✗ Demo data generation error:', error);
            
            if (status) {
                status.textContent = '✗ Failed to generate demo data. Please try again.';
                status.className = 'text-sm font-medium text-red-600 mt-4 block';
            }
        })
        .finally(() => {
            btn.disabled = false;
            btn.classList.remove('opacity-75');
        });
    });
}

console.log('✓ Accounts.js loaded successfully');
