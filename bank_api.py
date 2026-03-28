"""
Bank API Integration Module
Connects Flask app to FastAPI mock bank server
All placeholder logic replaced with real HTTP requests
"""

import os
import requests
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Configuration
API_BASE_URL = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
REQUEST_TIMEOUT = 10  # seconds


# ============================================================================
# API HEALTH CHECK
# ============================================================================

def check_api_server() -> bool:
    """
    Check if FastAPI server is running
    
    Returns:
        True if server is online, False otherwise
    """
    try:
        response = requests.get(f"{API_BASE_URL}/", timeout=REQUEST_TIMEOUT)
        if response.status_code == 200:
            data = response.json()
            print(f"✓ API Server Status: {data.get('status')}")
            return True
        return False
    except requests.exceptions.ConnectionError:
        print(f"❌ Cannot connect to API server at {API_BASE_URL}")
        print("   Make sure the FastAPI server is running:")
        print("   python bank_server.py")
        return False
    except Exception as e:
        print(f"❌ API health check error: {e}")
        return False


# ============================================================================
# ACCOUNT MANAGEMENT
# ============================================================================

def fetch_all_api_accounts() -> List[Dict]:
    """
    Fetch all available accounts from FastAPI server
    
    Returns:
        List of account dictionaries, empty list on error
        
    Example response:
        [
            {
                "id": 1,
                "name": "Rohan Gupta",
                "type": "Savings",
                "balance": 45000.00
            }
        ]
    """
    try:
        print(f"📡 Fetching accounts from {API_BASE_URL}/accounts")
        
        response = requests.get(
            f"{API_BASE_URL}/accounts",
            timeout=REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            accounts = response.json()
            print(f"✓ Fetched {len(accounts)} accounts from API")
            return accounts
        else:
            print(f"❌ API returned status {response.status_code}")
            return []
    
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection failed: API server not reachable at {API_BASE_URL}")
        return []
    
    except requests.exceptions.Timeout:
        print(f"❌ Request timeout: API server took too long to respond")
        return []
    
    except Exception as e:
        print(f"❌ Error fetching accounts: {e}")
        return []


def fetch_account_details(api_account_id: int) -> Optional[Dict]:
    """
    Fetch specific account details from API
    
    Args:
        api_account_id: Account ID from FastAPI server
    
    Returns:
        Account dictionary or None on error
    """
    try:
        print(f"📡 Fetching account {api_account_id} details")
        
        response = requests.get(
            f"{API_BASE_URL}/accounts/{api_account_id}",
            timeout=REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            account = response.json()
            print(f"✓ Fetched account: {account.get('name')}")
            return account
        elif response.status_code == 404:
            print(f"❌ Account {api_account_id} not found")
            return None
        else:
            print(f"❌ API returned status {response.status_code}")
            return None
    
    except Exception as e:
        print(f"❌ Error fetching account details: {e}")
        return None


# ============================================================================
# TRANSACTION FETCHING
# ============================================================================

def fetch_transactions_for_account(linked_account) -> List[Dict]:
    """
    Fetch transactions for a specific LinkedAccount from FastAPI
    Implements duplicate prevention by only fetching new transactions
    
    Args:
        linked_account: LinkedAccount object from Flask database
    
    Returns:
        List of transaction dictionaries (only NEW transactions)
        
    Example transaction format:
        {
            "date": "2024-11-01",
            "mode": "UPI",
            "merchant": "Swiggy",
            "amount": 450.00,
            "type": "debit",
            "narration": "Food delivery"
        }
    """
    from models import Transaction  # Import here to avoid circular dependency
    from sqlalchemy import func
    
    try:
        api_account_id = linked_account.api_account_id
        flask_account_id = linked_account.id
        
        print(f"📡 Fetching transactions for account {api_account_id}")
        
        # DUPLICATE PREVENTION: Find latest transaction date
        latest_transaction = Transaction.query.filter_by(
            account_id=flask_account_id
        ).order_by(Transaction.date.desc()).first()
        
        params = {}
        
        if latest_transaction:
            # Add 1 day to latest date to avoid duplicates
            next_date = latest_transaction.date + timedelta(days=1)
            start_date_str = next_date.strftime('%Y-%m-%d')
            params['start_date'] = start_date_str
            print(f"  📅 Fetching transactions after: {start_date_str}")
        else:
            print(f"  📅 No existing transactions, fetching all")
        
        # Make API request
        response = requests.get(
            f"{API_BASE_URL}/accounts/{api_account_id}/transactions",
            params=params,
            timeout=REQUEST_TIMEOUT
        )
        
        if response.status_code == 200:
            transactions = response.json()
            print(f"✓ Fetched {len(transactions)} new transactions")
            return transactions
        elif response.status_code == 404:
            print(f"❌ Account {api_account_id} not found on API")
            return []
        else:
            print(f"❌ API returned status {response.status_code}")
            return []
    
    except requests.exceptions.ConnectionError:
        print(f"❌ Connection failed: API server not reachable")
        return []
    
    except requests.exceptions.Timeout:
        print(f"❌ Request timeout")
        return []
    
    except Exception as e:
        print(f"❌ Error fetching transactions: {e}")
        import traceback
        traceback.print_exc()
        return []


# ============================================================================
# LEGACY FUNCTIONS (Kept for backward compatibility)
# ============================================================================

def initiate_connection(user):
    """Legacy function - kept for backward compatibility"""
    print("⚠️  Using legacy connection method - consider updating to FastAPI")
    return "/accounts"


def handle_api_callback(args, user):
    """Legacy function - kept for backward compatibility"""
    print("⚠️  Using legacy callback method - consider updating to FastAPI")
    return True


def generate_monthly_statement(user, year, month):
    """
    DEPRECATED: This is mock data generation
    Use fetch_transactions_for_account() for real API data
    """
    print("⚠️  WARNING: Using deprecated mock data generation")
    print("   Use FastAPI server for real transaction data")
    return []


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def test_api_connection():
    """Test function to verify API connectivity"""
    print("\n" + "="*60)
    print("🧪 Testing FastAPI Server Connection")
    print("="*60)
    
    if check_api_server():
        print("\n✅ API Server is online and reachable")
        
        # Test fetching accounts
        accounts = fetch_all_api_accounts()
        if accounts:
            print(f"\n✅ Successfully fetched {len(accounts)} accounts:")
            for acc in accounts:
                print(f"   - {acc['name']} ({acc['type']}) - ₹{acc['balance']}")
        
        return True
    else:
        print("\n❌ API Server connection failed")
        print("\n📝 To start the API server, run:")
        print("   python bank_server.py")
        return False


if __name__ == "__main__":
    # Run connection test
    test_api_connection()
