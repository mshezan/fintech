"""
FastAPI Mock Bank Server
Simulates a bank's Account Aggregator API
Runs on: http://127.0.0.1:8000
"""

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime, timedelta
import random

app = FastAPI(title="Mock Bank API", version="1.0.0")


# ============================================================================
# DATA MODELS
# ============================================================================

class Account(BaseModel):
    """Bank account model"""
    id: int
    name: str
    type: str
    balance: float
    
    class Config:
        schema_extra = {
            "example": {
                "id": 1,
                "name": "Rohan Gupta",
                "type": "Savings",
                "balance": 45000.00
            }
        }


class Transaction(BaseModel):
    """Transaction model matching API format"""
    date: str = Field(..., description="Transaction date in YYYY-MM-DD format")
    mode: str = Field(..., description="Payment mode (UPI, Card, NEFT, etc.)")
    merchant: str = Field(..., description="Merchant/recipient name")
    amount: float = Field(..., description="Transaction amount")
    type: str = Field(..., description="Transaction type (debit/credit)")
    narration: Optional[str] = Field(None, description="Additional description")
    
    class Config:
        schema_extra = {
            "example": {
                "date": "2024-11-01",
                "mode": "UPI",
                "merchant": "Swiggy",
                "amount": 450.00,
                "type": "debit",
                "narration": "Food delivery"
            }
        }


# ============================================================================
# MOCK DATA STORAGE
# ============================================================================

# Mock accounts database
MOCK_ACCOUNTS = [
    {
        "id": 1,
        "name": "Rohan Gupta",
        "type": "Savings",
        "balance": 45000.00
    },
    {
        "id": 2,
        "name": "Priya Sharma",
        "type": "Current",
        "balance": 120000.00
    },
    {
        "id": 3,
        "name": "Amit Patel",
        "type": "Savings",
        "balance": 78000.00
    }
]


# Merchant categories for generating realistic transactions
MERCHANTS = {
    'UPI': [
        ('Swiggy', 250, 600, 'Food delivery'),
        ('Zomato', 300, 700, 'Food delivery'),
        ('Amazon Pay', 100, 2000, 'Online shopping'),
        ('Flipkart', 500, 3000, 'Online shopping'),
        ('Uber', 150, 500, 'Ride sharing'),
        ('Ola', 120, 450, 'Ride sharing'),
    ],
    'Card': [
        ('Big Bazaar', 800, 2500, 'Grocery shopping'),
        ('DMart', 600, 2000, 'Grocery shopping'),
        ('PVR Cinemas', 300, 800, 'Entertainment'),
        ('Starbucks', 150, 400, 'Cafe'),
        ('McDonald\'s', 200, 500, 'Fast food'),
    ],
    'NEFT': [
        ('Rent Payment', 10000, 25000, 'Monthly rent'),
        ('Electricity Bill', 1000, 3000, 'Utility bill'),
        ('Internet Bill', 500, 1500, 'Utility bill'),
        ('Insurance Premium', 2000, 5000, 'Insurance'),
    ],
    'IMPS': [
        ('Mobile Recharge', 200, 600, 'Mobile recharge'),
        ('DTH Recharge', 300, 800, 'TV subscription'),
    ]
}


# ============================================================================
# API ENDPOINTS
# ============================================================================

@app.get("/", tags=["Health"])
def root():
    """API health check"""
    return {
        "status": "online",
        "service": "Mock Bank API",
        "version": "1.0.0",
        "endpoints": {
            "accounts": "/accounts",
            "transactions": "/accounts/{account_id}/transactions"
        }
    }


@app.get("/accounts", response_model=List[Account], tags=["Accounts"])
def get_all_accounts():
    """
    Get all available bank accounts
    
    Returns list of all mock accounts in the system
    """
    return MOCK_ACCOUNTS


@app.get("/accounts/{account_id}", response_model=Account, tags=["Accounts"])
def get_account(account_id: int):
    """
    Get specific account details
    
    Args:
        account_id: Unique account identifier
    
    Returns:
        Account details
    
    Raises:
        HTTPException: If account not found
    """
    for account in MOCK_ACCOUNTS:
        if account["id"] == account_id:
            return account
    
    raise HTTPException(status_code=404, detail=f"Account {account_id} not found")


@app.get("/accounts/{account_id}/transactions", response_model=List[Transaction], tags=["Transactions"])
def get_account_transactions(
    account_id: int,
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)")
):
    """
    Get transactions for a specific account
    
    Args:
        account_id: Unique account identifier
        start_date: Optional start date filter (YYYY-MM-DD format)
    
    Returns:
        List of transactions
    
    Raises:
        HTTPException: If account not found or date format invalid
    """
    # Verify account exists
    account = None
    for acc in MOCK_ACCOUNTS:
        if acc["id"] == account_id:
            account = acc
            break
    
    if not account:
        raise HTTPException(status_code=404, detail=f"Account {account_id} not found")
    
    # Parse start_date
    if start_date:
        try:
            filter_date = datetime.strptime(start_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        # Default: transactions from 3 months ago
        filter_date = datetime.now() - timedelta(days=90)
    
    # Generate transactions
    transactions = generate_transactions_for_account(account_id, filter_date)
    
    return transactions


# ============================================================================
# TRANSACTION GENERATION LOGIC
# ============================================================================

def generate_transactions_for_account(account_id: int, start_date: datetime) -> List[dict]:
    """
    Generate realistic transaction data for an account
    
    Args:
        account_id: Account ID
        start_date: Generate transactions from this date onwards
    
    Returns:
        List of transaction dictionaries
    """
    transactions = []
    current_date = datetime.now()
    
    # Ensure consistent data per account (seed with account_id)
    random.seed(account_id * 1000)
    
    # Generate transactions from start_date to now
    date_cursor = start_date
    
    while date_cursor <= current_date:
        # Generate 0-3 transactions per day
        num_transactions = random.randint(0, 3)
        
        for _ in range(num_transactions):
            # Choose random payment mode
            mode = random.choice(list(MERCHANTS.keys()))
            merchant_data = random.choice(MERCHANTS[mode])
            
            merchant_name, min_amount, max_amount, narration = merchant_data
            
            # Generate amount with some randomness
            amount = round(random.uniform(min_amount, max_amount), 2)
            
            # 90% debit, 10% credit
            tx_type = 'debit' if random.random() < 0.9 else 'credit'
            
            transaction = {
                'date': date_cursor.strftime('%Y-%m-%d'),
                'mode': mode,
                'merchant': merchant_name,
                'amount': amount,
                'type': tx_type,
                'narration': narration
            }
            
            transactions.append(transaction)
        
        # Move to next day
        date_cursor += timedelta(days=1)
    
    # Sort by date (newest first)
    transactions.sort(key=lambda x: x['date'], reverse=True)
    
    return transactions


# ============================================================================
# RUN SERVER
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Mock Bank API Server...")
    print("📍 Server URL: http://127.0.0.1:8000")
    print("📖 API Docs: http://127.0.0.1:8000/docs")
    uvicorn.run(app, host="127.0.0.1", port=8000)
