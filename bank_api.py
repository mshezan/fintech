import random
from datetime import datetime, timedelta


class SimulatedBankAPI:
    """
    Simulated Bank API for demonstration.
    FIXED: Better random data generation and error handling
    """
    
    def __init__(self):
        self.mock_vendors = [
            # (Description, Category, (Min Amount, Max Amount))
            ('ZOMATO ONLINE ORDER', 'Food & Drink', (200, 800)),
            ('SWIGGY DELIVERY', 'Food & Drink', (150, 600)),
            ('MCDONALDS INDIA', 'Food & Drink', (250, 500)),
            ('STARBUCKS COFFEE', 'Food & Drink', (300, 600)),
            ('DOMINOS PIZZA', 'Food & Drink', (400, 800)),
            ('CAFE COFFEE DAY', 'Food & Drink', (150, 400)),
            
            ('BIGBASKET GROCERY', 'Groceries', (800, 3000)),
            ('BLINKIT DELIVERY', 'Groceries', (500, 2000)),
            ('DMART RETAIL', 'Groceries', (1000, 4000)),
            ('RELIANCE FRESH', 'Groceries', (600, 2500)),
            ('ZEPTO INSTANT', 'Groceries', (400, 1500)),
            
            ('INDIAN OIL PETROL PUMP', 'Fuel', (1000, 3000)),
            ('HPCL FUEL STATION', 'Fuel', (1200, 2800)),
            ('BHARAT PETROLEUM', 'Fuel', (1500, 3500)),
            
            ('NETFLIX SUBSCRIPTION', 'Subscriptions', (199, 649)),
            ('AMAZON PRIME VIDEO', 'Subscriptions', (299, 1499)),
            ('SPOTIFY PREMIUM', 'Subscriptions', (119, 119)),
            ('HOTSTAR DISNEY PLUS', 'Subscriptions', (299, 1499)),
            
            ('TATA POWER ELECTRICITY', 'Utilities', (800, 3000)),
            ('AIRTEL POSTPAID', 'Utilities', (500, 1200)),
            ('JIO FIBER BROADBAND', 'Utilities', (699, 1499)),
            ('BSES ELECTRICITY', 'Utilities', (1000, 4000)),
            
            ('UBER TRIP', 'Transport', (100, 500)),
            ('OLA CAB SERVICE', 'Transport', (80, 450)),
            ('DELHI METRO CARD', 'Transport', (200, 1000)),
            ('IRCTC TRAIN TICKET', 'Transport', (500, 2000)),
            
            ('AMAZON INDIA', 'Shopping', (500, 5000)),
            ('FLIPKART ORDER', 'Shopping', (600, 4500)),
            ('MYNTRA FASHION', 'Shopping', (1000, 3000)),
            ('RELIANCE DIGITAL', 'Shopping', (2000, 10000)),
            
            ('PAYTM WALLET', 'Payments', (100, 2000)),
            ('PHONEPE UPI', 'Payments', (50, 1500)),
            
            ('SALARY CREDIT HDFC', 'Income', (30000, 80000)),
            ('FREELANCE PAYMENT', 'Income', (5000, 25000)),
        ]
    
    def initiate_connection(self, user):
        """Simulate bank account linking"""
        from models import db
        
        try:
            user.aa_token = f"SIMULATED_TOKEN_{user.id}_{int(datetime.now().timestamp())}"
            user.aa_consent_id = f"CONSENT_{user.id}"
            db.session.commit()
            
            return f"/api/bank/callback?code=SIM_{user.id}&state=user_{user.id}"
        except Exception as e:
            db.session.rollback()
            print(f"Error initiating connection: {e}")
            return None
    
    def handle_api_callback(self, request_args, user):
        """Handle simulated OAuth callback"""
        from models import db
        
        auth_code = request_args.get('code')
        
        if not auth_code or not auth_code.startswith('SIM_'):
            return False
        
        try:
            user.aa_token = f"SIMULATED_ACCESS_TOKEN_{auth_code}"
            user.aa_consent_id = f"CONSENT_{user.id}_{int(datetime.now().timestamp())}"
            db.session.commit()
            return True
        except Exception as e:
            db.session.rollback()
            print(f"Error in callback: {e}")
            return False
    
    def fetch_new_transactions(self, user, days_back=30, num_transactions=None):
        """Generate realistic mock transaction data"""
        if not user.aa_token:
            return []
        
        if num_transactions is None:
            num_transactions = random.randint(15, 40)
        
        transactions = []
        
        for _ in range(num_transactions):
            days_ago = random.randint(0, days_back)
            transaction_date = datetime.now() - timedelta(days=days_ago)
            
            vendor, category, amount_range = random.choice(self.mock_vendors)
            amount = random.uniform(amount_range[0], amount_range[1])
            
            # Add variation to descriptions
            if random.random() > 0.7:
                vendor = vendor + f" - {random.choice(['ONLINE', 'POS', 'UPI', 'CARD'])}"
            
            transactions.append({
                'date': transaction_date.strftime('%Y-%m-%d'),
                'description': vendor,
                'amount': round(amount, 2),
                'category_hint': category if category != 'Income' else None
            })
        
        # Sort by date (newest first)
        transactions.sort(key=lambda x: x['date'], reverse=True)
        return transactions
    
    def generate_monthly_statement(self, user, year, month):
        """Generate a full monthly statement for demonstration"""
        import calendar
        
        transactions = []
        num_days = calendar.monthrange(year, month)[1]
        
        for day in range(1, num_days + 1):
            # Random transactions per day (0-3)
            num_daily_txns = random.choices([0, 1, 2, 3], weights=[0.2, 0.4, 0.3, 0.1])[0]
            
            for _ in range(num_daily_txns):
                vendor, category, amount_range = random.choice(self.mock_vendors)
                amount = random.uniform(amount_range[0], amount_range[1])
                
                transactions.append({
                    'date': f'{year}-{month:02d}-{day:02d}',
                    'description': vendor,
                    'amount': round(amount, 2),
                    'category_hint': category if category != 'Income' else None
                })
        
        return transactions


# Global instance
simulated_bank = SimulatedBankAPI()


# Public API functions
def initiate_connection(user):
    """Initiate simulated bank connection"""
    return simulated_bank.initiate_connection(user)


def handle_api_callback(request_args, user):
    """Handle simulated bank callback"""
    return simulated_bank.handle_api_callback(request_args, user)


def fetch_new_transactions(user, days_back=30):
    """Fetch simulated transactions"""
    return simulated_bank.fetch_new_transactions(user, days_back)


def generate_monthly_statement(user, year, month):
    """Generate monthly statement"""
    return simulated_bank.generate_monthly_statement(user, year, month)
