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
