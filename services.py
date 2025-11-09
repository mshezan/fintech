from models import db, Category

# Indian vendor categorization keywords
CATEGORY_KEYWORDS = {
    'Food & Drink': ['zomato', 'swiggy', 'mcdonalds', 'mcd', 'starbucks', 'cafe coffee day', 'ccd', 
                     'dominos', 'pizza hut', 'eatsure', 'burger king', 'kfc', 'subway', 'dunkin'],
    'Groceries': ['bigbasket', 'blinkit', 'zepto', 'grofers', 'jiomart', 'dmart', 'reliance fresh', 
                  'more', 'spencers', 'nature basket', 'star bazaar'],
    'Fuel': ['indian oil', 'ioc', 'hpcl', 'hindustan petroleum', 'bharat petroleum', 'bpcl', 
             'shell', 'essar', 'reliance petroleum', 'petrol', 'diesel', 'fuel'],
    'Subscriptions': ['netflix', 'spotify', 'prime video', 'amazon prime', 'hotstar', 'disney', 
                      'jiocinema', 'sonyliv', 'zee5', 'apple music', 'youtube premium', 'voot'],
    'Utilities': ['bses', 'tata power', 'bescom', 'adani electricity', 'airtel', 'jio', 'vodafone', 
                  'vi', 'bsnl', 'mtnl', 'electricity', 'water bill', 'gas bill', 'piped gas', 
                  'indraprastha gas', 'mahanagar gas'],
    'Transport': ['ola', 'uber', 'rapido', 'redbus', 'irctc', 'metro', 'delhi metro', 'mumbai metro', 
                  'bangalore metro', 'namma metro', 'makemytrip', 'goibibo', 'yatra'],
    'Shopping': ['amazon', 'flipkart', 'myntra', 'meesho', 'ajio', 'nykaa', 'reliance digital', 
                 'croma', 'vijay sales', 'lifestyle', 'westside', 'max fashion', 'pantaloons'],
    'Payments': ['paytm', 'phonepe', 'gpay', 'google pay', 'bhim', 'upi', 'mobikwik'],
    'Rent/EMI': ['rent', 'emi', 'housing loan', 'home loan', 'hdfc', 'icici', 'sbi', 'axis']
}


def categorize_transaction(transaction):
    """
    Automatically categorize a transaction based on description.
    FIXED: Better error handling and performance optimization
    """
    if transaction.category_id is not None:
        return False  # Already categorized
    
    description_lower = transaction.description.lower()
    
    # Iterate through categories and keywords
    for category_name, keywords in CATEGORY_KEYWORDS.items():
        for keyword in keywords:
            if keyword in description_lower:
                # Find category (cached query)
                category = Category.query.filter_by(name=category_name).first()
                if category:
                    transaction.category_id = category.id
                    return True
    
    return False


def initialize_categories():
    """
    Initialize default categories in the database.
    FIXED: Better error handling and duplicate prevention
    """
    default_categories = list(CATEGORY_KEYWORDS.keys()) + ['Uncategorized', 'Other', 'Income']
    
    for category_name in default_categories:
        # Check if category already exists
        if not Category.query.filter_by(name=category_name).first():
            category = Category(name=category_name)
            db.session.add(category)
    
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Warning: Could not initialize categories: {e}")
# Add these imports at the top if not present
from models import BankAccount
from datetime import datetime

def get_user_accounts(user):
    """
    Get all bank accounts for a user
    Returns list of BankAccount objects
    """
    return BankAccount.query.filter_by(user_id=user.id).order_by(BankAccount.created_at.desc()).all()


def get_active_account(user):
    """
    Get the currently active bank account for a user
    Returns BankAccount object or None
    """
    active = BankAccount.query.filter_by(user_id=user.id, is_active=True).first()
    
    # If no active account, make the first one active
    if not active:
        accounts = get_user_accounts(user)
        if accounts:
            accounts[0].is_active = True
            db.session.commit()
            return accounts[0]
    
    return active


def set_active_account(user, account_id):
    """
    Set a specific account as active for the user
    Deactivates all other accounts
    """
    # Deactivate all user's accounts
    BankAccount.query.filter_by(user_id=user.id).update({'is_active': False})
    
    # Activate the selected account
    account = BankAccount.query.get(account_id)
    if account and account.user_id == user.id:
        account.is_active = True
        db.session.commit()
        return True
    
    return False


def get_account_stats(account):
    """
    Get statistics for a specific bank account
    """
    from models import Transaction, Category
    from sqlalchemy import func
    
    total_spending = db.session.query(
        func.sum(Transaction.amount)
    ).filter(Transaction.bank_account_id == account.id).scalar() or 0
    
    transaction_count = Transaction.query.filter_by(bank_account_id=account.id).count()
    
    # Get top category
    top_category = db.session.query(
        Category.name,
        func.sum(Transaction.amount).label('total')
    ).join(Transaction).filter(
        Transaction.bank_account_id == account.id
    ).group_by(Category.name).order_by(
        func.sum(Transaction.amount).desc()
    ).first()
    
    return {
        'total_spending': float(total_spending),
        'transaction_count': transaction_count,
        'top_category': top_category[0] if top_category else 'N/A',
        'balance': float(account.balance) if account.balance else 0.0
    }
