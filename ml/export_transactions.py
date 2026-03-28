"""
Export transactions from your fintech database to CSV
Run this in your Flask project directory
"""

import sys
sys.path.append('..')  # Add parent directory to import models

from models import db, Transaction, User
from app import app
import pandas as pd
from datetime import datetime, timedelta
import random

def export_transactions_to_csv(output_file='transactions_dataset.csv'):
    """
    Export all transactions from database to CSV for ML analysis
    """
    with app.app_context():
        # Get all transactions
        transactions = Transaction.query.all()

        if len(transactions) == 0:
            print("⚠ No transactions found in database!")
            print("  Run your Flask app and sync some accounts first.")
            return None

        print(f"✓ Found {len(transactions)} transactions in database")

        # Convert to DataFrame
        data = []
        for t in transactions:
            data.append({
                'transaction_id': t.id,
                'date': t.date.strftime('%Y-%m-%d') if t.date else None,
                'amount': float(t.amount) if t.amount else 0.0,
                'merchant': t.description,
                'mode': t.mode or 'Unknown',
                'type': t.transaction_type or 'debit',
                'category': t.category.name if t.category else 'Uncategorized',
                'narration': t.narration or '',
                'user_id': t.user_id,
                'account_id': t.account_id
            })

        df = pd.DataFrame(data)

        # Add fraud labels (we'll create synthetic fraud for now)
        df['is_fraud'] = 0  # All legitimate by default

        # Create synthetic fraud cases (5-10 transactions)
        # Strategy: Flag high-value unusual transactions as fraud
        fraud_candidates = df[df['amount'] > df['amount'].quantile(0.95)].index
        n_fraud = min(10, len(fraud_candidates))
        fraud_indices = random.sample(list(fraud_candidates), n_fraud)
        df.loc[fraud_indices, 'is_fraud'] = 1

        print(f"\n✓ Dataset created:")
        print(f"  - Total transactions: {len(df)}")
        print(f"  - Legitimate: {(df['is_fraud'] == 0).sum()}")
        print(f"  - Fraudulent: {(df['is_fraud'] == 1).sum()}")
        print(f"  - Date range: {df['date'].min()} to {df['date'].max()}")

        # Save to CSV
        df.to_csv(output_file, index=False)
        print(f"\n✅ Saved to: {output_file}")

        return df

def create_synthetic_fraud_dataset(n_samples=5000, fraud_ratio=0.02):
    """
    If you don't have enough real data, create synthetic dataset
    Similar to your real transaction patterns
    """
    print(f"\n[SYNTHETIC MODE] Creating {n_samples} transactions...")

    merchants = [
        'Swiggy', 'Zomato', 'Amazon', 'Flipkart', 'Uber', 'Ola',
        'DMart', 'Big Bazaar', 'PVR Cinemas', 'Starbucks',
        'Rent Payment', 'Electricity Bill', 'Mobile Recharge'
    ]

    modes = ['UPI', 'Card', 'NEFT', 'IMPS']
    categories = ['Food & Drink', 'Shopping', 'Transport', 'Utilities', 'Groceries']

    data = []
    n_fraud = int(n_samples * fraud_ratio)

    for i in range(n_samples):
        is_fraud = 1 if i < n_fraud else 0

        # Normal transactions: ₹100-2000
        # Fraud transactions: ₹5000-50000 (unusual)
        if is_fraud:
            amount = random.uniform(5000, 50000)
            merchant = random.choice(['Unknown Merchant', 'Suspicious Transaction'])
        else:
            amount = random.uniform(100, 2000)
            merchant = random.choice(merchants)

        data.append({
            'transaction_id': i + 1,
            'date': (datetime.now() - timedelta(days=random.randint(0, 90))).strftime('%Y-%m-%d'),
            'amount': round(amount, 2),
            'merchant': merchant,
            'mode': random.choice(modes),
            'type': 'debit',
            'category': random.choice(categories),
            'narration': 'Transaction',
            'user_id': 1,
            'account_id': 1,
            'is_fraud': is_fraud
        })

    df = pd.DataFrame(data)
    df.to_csv('synthetic_transactions.csv', index=False)

    print(f"✓ Created {n_samples} synthetic transactions")
    print(f"  - Legitimate: {n_samples - n_fraud}")
    print(f"  - Fraudulent: {n_fraud}")
    print(f"✅ Saved to: synthetic_transactions.csv")

    return df

if __name__ == '__main__':
    print("="*80)
    print("EXPORT FINTECH TRANSACTIONS FOR ML RESEARCH")
    print("="*80)

    # Try to export real data first
    try:
        df = export_transactions_to_csv('transactions_dataset.csv')

        if df is None or len(df) < 100:
            print("\n⚠ Not enough real transactions for ML training")
            print("  Creating synthetic dataset instead...")
            df = create_synthetic_fraud_dataset(n_samples=5000)

    except Exception as e:
        print(f"\n⚠ Could not access database: {e}")
        print("  Creating synthetic dataset instead...")
        df = create_synthetic_fraud_dataset(n_samples=5000)

    print("\n" + "="*80)
    print("✅ DATASET READY FOR ML TRAINING")
    print("="*80)
