"""
Bank API Simulator Module
Simulates a bank/Account Aggregator API for FinTrack
This is a MOCK implementation for educational purposes
"""

from datetime import datetime, timedelta
import random


# ============================================================================
# DEMO TRANSACTION GENERATION
# ============================================================================

def generate_monthly_statement(user, year, month):
    """
    Generate demo transactions for a specific month
    
    Args:
        user: User object
        year: Year (e.g., 2025)
        month: Month (1-12)
    
    Returns:
        List of transaction dictionaries
    """
    
    # Sample merchants categorized
    merchants = {
        # Food & Drink
        'Zomato': (450, 'Food & Drink'),
        'Swiggy': (380, 'Food & Drink'),
        'McDonald\'s': (150, 'Food & Drink'),
        'Dominos': (400, 'Food & Drink'),
        'Starbucks': (250, 'Food & Drink'),
        'Cafe Coffee Day': (180, 'Food & Drink'),
        
        # Groceries
        'Blinkit': (250, 'Groceries'),
        'Zepto': (180, 'Groceries'),
        'Big Basket': (1200, 'Groceries'),
        'Dmart': (800, 'Groceries'),
        
        # Shopping
        'Flipkart': (1200, 'Shopping'),
        'Amazon': (2500, 'Shopping'),
        'Myntra': (800, 'Shopping'),
        'Ajio': (600, 'Shopping'),
        
        # Transport
        'Uber': (350, 'Transport'),
        'Ola': (280, 'Transport'),
        'MakeMyTrip': (5000, 'Transport'),
        
        # Utilities
        'Electricity Bill': (1800, 'Utilities'),
        'Water Bill': (400, 'Utilities'),
        'Internet Bill': (799, 'Utilities'),
        'Mobile Recharge': (499, 'Subscriptions'),
        
        # Subscriptions
        'Netflix': (199, 'Subscriptions'),
        'Spotify': (79, 'Subscriptions'),
        'Prime Video': (129, 'Subscriptions'),
        'Gym Membership': (500, 'Subscriptions'),
        
        # Rent/EMI
        'Rent Payment': (12000, 'Rent/EMI'),
        'Home Loan EMI': (25000, 'Rent/EMI'),
        
        # Fuel
        'Petrol Pump': (1500, 'Fuel'),
        'Shell Gas Station': (1200, 'Fuel'),
        
        # Shopping/Entertainment
        'BookMyShow': (400, 'Shopping'),
        'PVR Cinema': (450, 'Shopping'),
        'Airbnb': (2000, 'Shopping'),
        
        # Healthcare
        'PharmEasy': (150, 'Groceries'),
        'Apollo Pharmacy': (200, 'Groceries'),
        
        # Others
        'ATM Withdrawal': (5000, 'Uncategorized'),
        'Transfer to Friend': (1000, 'Uncategorized'),
    }
    
    transactions = []
    
    # Generate 15-25 transactions per month
    num_transactions = random.randint(15, 25)
    
    for _ in range(num_transactions):
        try:
            # Random day in month (1-28 to avoid day 30/31 issues)
            day = random.randint(1, 28)
            
            # Create date
            transaction_date = datetime(year, month, day)
            date_str = transaction_date.strftime('%Y-%m-%d')
            
            # Random merchant
            merchant_name = random.choice(list(merchants.keys()))
            base_amount, category = merchants[merchant_name]
            
            # Add some variance (+/- 10-30%)
            variance = random.randint(-30, 30)
            amount = base_amount + (base_amount * variance // 100)
            amount = max(50, amount)  # Minimum ₹50
            
            transaction = {
                'date': date_str,
                'description': f'Payment to {merchant_name}',
                'amount': amount,
                'category': category
            }
            
            transactions.append(transaction)
            
        except Exception as e:
            print(f"⚠️ Error generating transaction: {e}")
            continue
    
    return transactions


# ============================================================================
# BANK CONNECTION SIMULATION
# ============================================================================

def initiate_connection(user):
    """
    Simulate initiating bank connection
    In a real scenario, this would redirect to bank's authentication page
    
    Args:
        user: User object
    
    Returns:
        URL string or None
    """
    try:
        print(f"🔗 Initiating bank connection for user: {user.email}")
        
        # Simulate generating auth token
        auth_token = generate_mock_token()
        
        # In a real implementation, this would be the bank's auth URL
        # For now, we'll redirect to our callback
        callback_url = f"/api/bank/callback?auth_token={auth_token}&user_id={user.id}"
        
        return callback_url
        
    except Exception as e:
        print(f"❌ Error initiating connection: {e}")
        return None


def handle_api_callback(args, user):
    """
    Handle the callback from bank/Account Aggregator
    
    Args:
        args: Request arguments from callback
        user: User object
    
    Returns:
        Boolean indicating success
    """
    try:
        from models import db, BankAccount
        
        print(f"📞 Handling callback for user: {user.email}")
        
        # Get auth token from callback
        auth_token = args.get('auth_token')
        
        if not auth_token:
            print("❌ No auth token in callback")
            return False
        
        # Check if user already has this account (avoid duplicates)
        existing = BankAccount.query.filter_by(
            user_id=user.id,
            aa_token=auth_token
        ).first()
        
        if existing:
            print(f"⚠️ Account already linked: {existing.account_name}")
            return True
        
        # Create new bank account
        account_count = BankAccount.query.filter_by(user_id=user.id).count()
        
        if account_count == 0:
            account_name = "Primary Account"
        else:
            account_name = f"Account {account_count + 1}"
        
        new_account = BankAccount(
            user_id=user.id,
            account_name=account_name,
            account_type='checking',
            aa_token=auth_token,
            is_active=True,
            last_synced=datetime.utcnow()
        )
        
        db.session.add(new_account)
        db.session.commit()
        
        print(f"✅ Bank account created: {account_name}")
        return True
        
    except Exception as e:
        print(f"❌ Error handling callback: {e}")
        return False


def fetch_new_transactions(user):
    """
    Fetch new transactions from bank
    In a real scenario, this would call the Account Aggregator API
    
    Args:
        user: User object
    
    Returns:
        List of new transactions
    """
    try:
        print(f"🔄 Fetching transactions for user: {user.email}")
        
        # Generate current month transactions
        now = datetime.now()
        new_transactions = generate_monthly_statement(user, now.year, now.month)
        
        print(f"✅ Fetched {len(new_transactions)} transactions")
        return new_transactions
        
    except Exception as e:
        print(f"❌ Error fetching transactions: {e}")
        return []


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def generate_mock_token():
    """
    Generate a mock authentication token
    
    Returns:
        Random token string
    """
    import string
    
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=32))
    return token


def get_account_balance(user):
    """
    Get account balance for a user
    
    Args:
        user: User object
    
    Returns:
        Dictionary with balance info
    """
    try:
        from models import BankAccount, Transaction, db
        from sqlalchemy import func
        
        accounts_data = []
        
        for account in user.bank_accounts:
            # Calculate balance from transactions
            total = db.session.query(
                func.sum(Transaction.amount)
            ).filter(
                Transaction.bank_account_id == account.id
            ).scalar() or 0
            
            accounts_data.append({
                'account_id': account.id,
                'account_name': account.account_name,
                'balance': float(total)
            })
        
        return {
            'status': 'success',
            'total_balance': sum(a['balance'] for a in accounts_data),
            'accounts': accounts_data
        }
        
    except Exception as e:
        print(f"❌ Error getting balance: {e}")
        return {
            'status': 'error',
            'message': str(e)
        }


def sync_all_accounts(user):
    """
    Sync transactions from all user accounts
    
    Args:
        user: User object
    
    Returns:
        Dictionary with sync results
    """
    try:
        from models import BankAccount, Transaction, db
        from services import categorize_transaction
        
        print(f"🔄 Syncing all accounts for user: {user.email}")
        
        total_synced = 0
        
        for account in user.bank_accounts:
            if not account.is_active:
                print(f"⏭️ Skipping inactive account: {account.account_name}")
                continue
            
            print(f"🔄 Syncing account: {account.account_name}")
            
            # Fetch transactions
            transactions = generate_monthly_statement(user, datetime.now().year, datetime.now().month)
            
            for tx_data in transactions:
                # Check if transaction already exists
                existing = Transaction.query.filter_by(
                    bank_account_id=account.id,
                    description=tx_data['description'],
                    amount=tx_data['amount']
                ).first()
                
                if not existing:
                    new_tx = Transaction(
                        user_id=user.id,
                        bank_account_id=account.id,
                        date=datetime.strptime(tx_data['date'], '%Y-%m-%d'),
                        description=tx_data['description'],
                        amount=tx_data['amount']
                    )
                    
                    db.session.add(new_tx)
                    db.session.flush()
                    categorize_transaction(new_tx)
                    total_synced += 1
            
            # Update last synced time
            account.last_synced = datetime.utcnow()
        
        db.session.commit()
        
        print(f"✅ Synced {total_synced} transactions")
        return {
            'status': 'success',
            'transactions_synced': total_synced
        }
        
    except Exception as e:
        print(f"❌ Error syncing accounts: {e}")
        from models import db
        db.session.rollback()
        return {
            'status': 'error',
            'message': str(e)
        }


# ============================================================================
# TESTING FUNCTIONS
# ============================================================================

def test_generate_transactions():
    """Test transaction generation"""
    print("\n🧪 Testing transaction generation...")
    
    transactions = generate_monthly_statement(None, 2025, 11)
    
    print(f"Generated {len(transactions)} transactions")
    for tx in transactions[:3]:
        print(f"  {tx['date']}: {tx['description']} - ₹{tx['amount']}")
    
    print("✅ Test passed!\n")


if __name__ == '__main__':
    # Run tests
    test_generate_transactions()
