/**
 * Accounts page: identity-based bank linking + sync (single or all accounts)
 */

var FINTRACK_LINK_PENDING_KEY = 'fintrack_link_pending';
var discoverState = { identityId: '', holderName: '' };

document.addEventListener('DOMContentLoaded', function () {
    setupLinkSuccessPanel();
    setupBankConnectFlow();
    setupSyncButton();
    setupDemoDataButton();
});

/**
 * After successful POST, server redirects with flash. We show an inline success panel
 * and stash the account display name from sessionStorage (set on submit). No backend change.
 */
function setupLinkSuccessPanel() {
    var errorFlash = document.querySelector('[data-flash-category="error"]');
    if (errorFlash) {
        try {
            sessionStorage.removeItem(FINTRACK_LINK_PENDING_KEY);
        } catch (e) {}
        return;
    }

    var successFlash = document.querySelector('[data-flash-category="success"]');
    var panel = document.getElementById('bank-connect-success');
    var nameEl = document.getElementById('bank-connect-success-name');
    var onboarding = document.getElementById('bank-connect-onboarding');

    if (!successFlash || !panel || !nameEl) {
        return;
    }

    var msg = (successFlash.textContent || '').trim();
    if (msg.indexOf('Account connected successfully') === -1) {
        return;
    }

    var pending = null;
    try {
        pending = JSON.parse(sessionStorage.getItem(FINTRACK_LINK_PENDING_KEY) || 'null');
    } catch (e) {
        pending = null;
    }

    var displayName = pending && pending.holderName ? pending.holderName : '';
    if (pending && pending.type) {
        displayName = displayName ? displayName + ' (' + pending.type + ')' : pending.type;
    }
    nameEl.textContent = displayName ? displayName : 'Your account is ready to use.';

    try {
        sessionStorage.removeItem(FINTRACK_LINK_PENDING_KEY);
    } catch (e) {}

    successFlash.closest('.max-w-7xl') && successFlash.closest('.max-w-7xl').classList.add('hidden');
    panel.classList.remove('hidden');
    if (onboarding) {
        onboarding.classList.add('hidden');
    }
}

function formatINR(amount) {
    try {
        return new Intl.NumberFormat('en-IN', {
            style: 'currency',
            currency: 'INR',
            maximumFractionDigits: 0,
        }).format(Number(amount));
    } catch {
        return '₹' + amount;
    }
}

function setupBankConnectFlow() {
    const successPanelGate = document.getElementById('bank-connect-success');
    if (successPanelGate && !successPanelGate.classList.contains('hidden')) {
        return;
    }

    const loadingEl = document.getElementById('bank-connect-loading');
    const unreachableEl = document.getElementById('bank-connect-unreachable');
    const unreachableMsg = document.getElementById('bank-connect-unreachable-msg');
    const fetchErrorEl = document.getElementById('bank-connect-fetch-error');
    const fetchErrorMsg = document.getElementById('bank-connect-fetch-error-msg');
    const allLinkedEl = document.getElementById('bank-connect-all-linked');
    const emptyEl = document.getElementById('bank-connect-empty');
    const formEl = document.getElementById('bank-connect-form');
    const cardsContainer = document.getElementById('account-cards-container');
    const hiddenId = document.getElementById('api_account_id');
    const formIdentityId = document.getElementById('form_identity_id');
    const formBankName = document.getElementById('form_bank_name');
    const formMasked = document.getElementById('form_masked_account_number');
    const identityInput = document.getElementById('identity_id_input');
    const fetchBtn = document.getElementById('fetch-accounts-btn');
    const nicknameInput = document.getElementById('account_nickname');
    const submitBtn = document.getElementById('connect-submit-btn');
    const submitLabel = document.getElementById('connect-submit-label');
    const submitSpinner = document.getElementById('connect-submit-spinner');
    const retryUnreachable = document.getElementById('bank-connect-retry');
    const retryError = document.getElementById('bank-connect-retry-error');
    const cardsHint = document.getElementById('account-cards-hint');
    const selectionConfirmation = document.getElementById('selection-confirmation');
    const stepProgressLabel = document.getElementById('step-progress-label');

    if (!loadingEl || !formEl || !cardsContainer) {
        return;
    }

    function updateStepVisuals() {
        const hasIdentity = !!(discoverState.identityId && discoverState.identityId.length >= 5);
        const hasAccount = !!(hiddenId && hiddenId.value.trim());
        const hasNickname = !!(nicknameInput && nicknameInput.value.trim());
        let current = 1;
        if (hasIdentity) {
            current = 2;
        }
        if (hasAccount) {
            current = 3;
        }
        if (hasAccount && hasNickname) {
            current = 3;
        }
        if (stepProgressLabel) {
            stepProgressLabel.textContent = 'Step ' + current + ' of 3';
        }
        document.querySelectorAll('#bank-link-steps .link-step').forEach(function (li) {
            const idx = parseInt(li.getAttribute('data-step-index'), 10);
            const dot = li.querySelector('.link-step-dot');
            const label = li.querySelector('.link-step-label');
            if (!dot || !label) {
                return;
            }
            dot.classList.remove('bg-indigo-600', 'text-white', 'ring-2', 'ring-indigo-200', 'scale-105', 'shadow-md');
            dot.classList.remove('bg-emerald-500', 'text-white', 'ring-2', 'ring-emerald-200');
            dot.classList.remove('bg-gray-200', 'text-gray-600');
            label.classList.remove('text-gray-900', 'font-semibold', 'text-gray-500');

            if (idx < current) {
                dot.classList.add('bg-emerald-500', 'text-white', 'ring-2', 'ring-emerald-200');
                dot.classList.add('transition-all', 'duration-300');
                label.classList.add('text-gray-600');
            } else if (idx === current) {
                dot.classList.add('bg-indigo-600', 'text-white', 'ring-2', 'ring-indigo-200', 'scale-105', 'shadow-md');
                dot.classList.add('transition-all', 'duration-300');
                label.classList.add('text-gray-900', 'font-semibold');
            } else {
                dot.classList.add('bg-gray-200', 'text-gray-600', 'transition-all', 'duration-300');
                label.classList.add('text-gray-500');
            }
        });
    }

    function hideAllStates() {
        loadingEl.classList.add('hidden');
        unreachableEl.classList.add('hidden');
        fetchErrorEl.classList.add('hidden');
        allLinkedEl.classList.add('hidden');
        emptyEl.classList.add('hidden');
        formEl.classList.add('hidden');
        loadingEl.setAttribute('aria-busy', 'false');
    }

    function showLoading() {
        hideAllStates();
        loadingEl.classList.remove('hidden');
        loadingEl.setAttribute('aria-busy', 'true');
    }

    function updateSubmitEnabled() {
        const idOk = hiddenId && hiddenId.value.trim() !== '';
        const nameOk = nicknameInput && nicknameInput.value.trim().length > 0;
        const ready = idOk && nameOk;
        submitBtn.disabled = !ready;
        submitBtn.classList.toggle('connect-submit-btn--ready', !!ready);
        updateStepVisuals();
    }

    function clearSelection() {
        hiddenId.value = '';
        if (formBankName) formBankName.value = '';
        if (formMasked) formMasked.value = '';
        if (nicknameInput) {
            nicknameInput.value = '';
        }
        if (selectionConfirmation) {
            selectionConfirmation.textContent = '';
            selectionConfirmation.classList.add('hidden');
        }
        cardsContainer.querySelectorAll('.account-select-card').forEach(function (el) {
            el.classList.remove(
                'ring-2',
                'ring-indigo-600',
                'bg-indigo-50',
                'border-indigo-500',
                'shadow-md',
                'account-select-card--selected'
            );
            el.classList.add('border-gray-200', 'bg-white');
            el.setAttribute('aria-checked', 'false');
        });
        updateSubmitEnabled();
    }

    function renderBankGroups(banks) {
        cardsContainer.innerHTML = '';
        (banks || []).forEach(function (bank) {
            const bankName = bank.name || 'Bank';
            const header = document.createElement('h3');
            header.className = 'text-sm font-bold text-gray-800 mt-4 first:mt-0 mb-2';
            header.textContent = bankName;
            cardsContainer.appendChild(header);

            (bank.accounts || []).forEach(function (acc) {
                const id = acc.id;
                const btn = document.createElement('button');
                btn.type = 'button';
                btn.className =
                    'account-select-card w-full text-left rounded-xl border-2 border-gray-200 bg-white p-4 shadow-sm hover:border-indigo-300 hover:shadow-md focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 mb-2';
                btn.setAttribute('role', 'radio');
                btn.setAttribute('aria-checked', 'false');
                btn.dataset.accountId = String(id);
                btn.dataset.accountName = acc.name || '';
                btn.dataset.accountType = acc.type || '';
                btn.dataset.bankName = acc.bank_name || bankName;
                btn.dataset.maskedAccountNumber = acc.account_number_masked || '';

                const name = document.createElement('div');
                name.className = 'font-semibold text-gray-900 text-base';
                name.textContent = (acc.type || 'Account') + (acc.account_number_masked ? ' · ' + acc.account_number_masked : '');

                const meta = document.createElement('div');
                meta.className = 'text-sm text-gray-600 mt-1';
                meta.textContent = acc.name || discoverState.holderName || '';

                const bal = document.createElement('div');
                bal.className = 'text-lg font-semibold text-gray-900 mt-3 tabular-nums';
                bal.textContent = formatINR(acc.balance != null ? acc.balance : 0);

                btn.appendChild(name);
                btn.appendChild(meta);
                btn.appendChild(bal);

                btn.addEventListener('click', function () {
                    clearSelection();
                    hiddenId.value = String(id);
                    if (formIdentityId) formIdentityId.value = discoverState.identityId || '';
                    if (formBankName) formBankName.value = btn.dataset.bankName || '';
                    if (formMasked) formMasked.value = btn.dataset.maskedAccountNumber || '';
                    btn.classList.remove('border-gray-200', 'bg-white');
                    btn.classList.add(
                        'account-select-card--selected',
                        'ring-2',
                        'ring-indigo-600',
                        'bg-indigo-50',
                        'border-indigo-500',
                        'shadow-md'
                    );
                    btn.setAttribute('aria-checked', 'true');
                    if (cardsHint) cardsHint.classList.remove('hidden');

                    var tp = acc.type || '';
                    var masked = acc.account_number_masked || '';
                    if (selectionConfirmation) {
                        selectionConfirmation.textContent =
                            bankName + (tp ? ' — ' + tp : '') + (masked ? ' (' + masked + ')' : '');
                        selectionConfirmation.classList.remove('hidden');
                    }
                    if (nicknameInput) {
                        nicknameInput.value = bankName + (tp ? ' ' + tp : '');
                    }

                    updateSubmitEnabled();
                });

                cardsContainer.appendChild(btn);
            });
        });
    }

    function runDiscover() {
        const raw = identityInput ? identityInput.value.trim() : '';
        if (raw.length < 5) {
            hideAllStates();
            if (fetchErrorMsg) {
                fetchErrorMsg.textContent = 'Enter a valid identity (at least 5 characters).';
            }
            fetchErrorEl.classList.remove('hidden');
            return;
        }

        showLoading();
        if (fetchErrorEl) fetchErrorEl.classList.add('hidden');
        if (unreachableEl) unreachableEl.classList.add('hidden');

        fetch('/api/bank/discover?identity_id=' + encodeURIComponent(raw), {
            method: 'GET',
            headers: { Accept: 'application/json' },
            credentials: 'same-origin',
        })
            .then(function (res) {
                return res
                    .json()
                    .then(function (data) {
                        return { ok: res.ok, status: res.status, data: data };
                    })
                    .catch(function () {
                        return {
                            ok: res.ok,
                            status: res.status,
                            data: { status: 'error', message: 'Invalid response from server' },
                        };
                    });
            })
            .then(function (result) {
                hideAllStates();
                const data = result.data || {};

                if (data.status === 'error' || !result.ok) {
                    if (fetchErrorMsg) {
                        fetchErrorMsg.textContent =
                            data.message || 'We could not load your accounts. Please try again.';
                    }
                    fetchErrorEl.classList.remove('hidden');
                    return;
                }

                discoverState.identityId = data.identity_id || raw.toUpperCase();
                discoverState.holderName = data.holder_name || '';
                if (formIdentityId) formIdentityId.value = discoverState.identityId;

                if (data.scenario === 'all_linked') {
                    allLinkedEl.classList.remove('hidden');
                    updateStepVisuals();
                    return;
                }

                if (data.scenario === 'empty_source') {
                    emptyEl.classList.remove('hidden');
                    updateStepVisuals();
                    return;
                }

                if (data.banks && data.banks.length > 0) {
                    hiddenId.value = '';
                    if (nicknameInput) nicknameInput.value = '';
                    if (formBankName) formBankName.value = '';
                    if (formMasked) formMasked.value = '';
                    if (selectionConfirmation) {
                        selectionConfirmation.textContent = '';
                        selectionConfirmation.classList.add('hidden');
                    }
                    renderBankGroups(data.banks);
                    formEl.classList.remove('hidden');
                    updateSubmitEnabled();
                    updateStepVisuals();
                    return;
                }

                emptyEl.classList.remove('hidden');
                updateStepVisuals();
            })
            .catch(function () {
                hideAllStates();
                if (unreachableMsg) {
                    unreachableMsg.textContent = 'Unable to reach your bank right now.';
                }
                unreachableEl.classList.remove('hidden');
            });
    }

    if (nicknameInput) {
        nicknameInput.addEventListener('input', updateSubmitEnabled);
        nicknameInput.addEventListener('blur', updateStepVisuals);
    }

    if (retryUnreachable) {
        retryUnreachable.addEventListener('click', runDiscover);
    }
    if (retryError) {
        retryError.addEventListener('click', runDiscover);
    }
    if (fetchBtn) {
        fetchBtn.addEventListener('click', runDiscover);
    }

    formEl.addEventListener('submit', function (e) {
        if (!hiddenId.value.trim() || !nicknameInput.value.trim()) {
            e.preventDefault();
            return;
        }
        var selectedBtn = cardsContainer.querySelector('.account-select-card[aria-checked="true"]');
        var holderName = discoverState.holderName || '';
        var accType = '';
        if (selectedBtn) {
            holderName = holderName || selectedBtn.dataset.accountName || '';
            accType = selectedBtn.dataset.accountType || '';
        }
        try {
            sessionStorage.setItem(
                FINTRACK_LINK_PENDING_KEY,
                JSON.stringify({
                    holderName: holderName,
                    type: accType,
                    nickname: nicknameInput.value.trim(),
                })
            );
        } catch (err) {}

        submitBtn.disabled = true;
        if (submitLabel) submitLabel.classList.add('hidden');
        if (submitSpinner) submitSpinner.classList.remove('hidden');
    });

    hideAllStates();
    updateStepVisuals();
}

function setupSyncButton() {
    const btn = document.getElementById('sync-btn');
    const status = document.getElementById('sync-status');
    const selector = document.getElementById('account-selector');
    const syncAllEl = document.getElementById('sync-all-checkbox');

    if (!btn || !selector) {
        return;
    }

    if (syncAllEl) {
        syncAllEl.addEventListener('change', function () {
            selector.disabled = !!syncAllEl.checked;
        });
    }

        btn.addEventListener('click', function () {
        const syncAll = syncAllEl && syncAllEl.checked;
        const accountId = selector.value;

        if (!syncAll && !accountId) {
            if (status) {
                status.textContent = 'Please select an account to sync';
                status.className = 'text-sm font-medium text-amber-600 mt-4 block';
            }
            return;
        }

        btn.disabled = true;
        btn.classList.add('opacity-75');
        if (status) {
            status.textContent = 'Syncing transactions…';
            status.className = 'text-sm font-medium text-indigo-600 mt-4 block';
        }

        const body = syncAll ? { sync_all: true } : { account_id: parseInt(accountId, 10) };

        fetch('/api/accounts/sync', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        })
            .then(function (response) {
                return response
                    .json()
                    .then(function (data) {
                        return { ok: response.ok, data: data };
                    })
                    .catch(function () {
                        return {
                            ok: false,
                            data: {
                                status: 'error',
                                message: 'Invalid response from server',
                            },
                        };
                    });
            })
            .then(function (result) {
                const data = result.data || {};
                if (data.status === 'success') {
                    if (status) {
                        status.textContent = data.message || 'Synced successfully';
                        status.className = 'text-sm font-medium text-emerald-600 mt-4 block';
                    }
                    setTimeout(function () {
                        window.location.reload();
                    }, 2000);
                } else {
                    if (status) {
                        status.textContent = data.message || 'Sync failed';
                        status.className = 'text-sm font-medium text-red-600 mt-4 block';
                    }
                }
            })
            .catch(function () {
                if (status) {
                    status.textContent = 'Sync failed. Please try again.';
                    status.className = 'text-sm font-medium text-red-600 mt-4 block';
                }
            })
            .finally(function () {
                btn.disabled = false;
                btn.classList.remove('opacity-75');
            });
    });
}

function setupDemoDataButton() {
    const btn = document.getElementById('generate-demo-btn');
    const status = document.getElementById('sync-status');

    if (!btn) {
        return;
    }

    btn.addEventListener('click', function () {
        if (!confirm('Generate 3 months of demo transaction data? This will replace existing transactions.')) {
            return;
        }

        btn.disabled = true;
        btn.classList.add('opacity-75');

        if (status) {
            status.textContent = 'Generating demo data…';
            status.className = 'text-sm font-medium text-indigo-600 mt-4 block';
        }

        fetch('/api/demo/generate-data', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
        })
            .then(function (response) {
                if (!response.ok) {
                    throw new Error('Generation failed');
                }
                return response.json();
            })
            .then(function (data) {
                if (data.status === 'success') {
                    if (status) {
                        status.textContent = data.message || 'Done';
                        status.className = 'text-sm font-medium text-emerald-600 mt-4 block';
                    }
                    alert(
                        'Success! Generated ' +
                            data.transactions +
                            ' demo transactions.\n\nRedirecting to dashboard…'
                    );
                    setTimeout(function () {
                        window.location.href = '/';
                    }, 1000);
                } else {
                    if (status) {
                        status.textContent = data.message || 'Failed';
                        status.className = 'text-sm font-medium text-red-600 mt-4 block';
                    }
                }
            })
            .catch(function () {
                if (status) {
                    status.textContent = 'Failed to generate demo data.';
                    status.className = 'text-sm font-medium text-red-600 mt-4 block';
                }
            })
            .finally(function () {
                btn.disabled = false;
                btn.classList.remove('opacity-75');
            });
    });
}
