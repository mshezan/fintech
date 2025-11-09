from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """User model with authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # DEPRECATED: Will be migrated to BankAccount model
    aa_token = db.Column(db.String(500), nullable=True)
    
    # Relationships
    bank_accounts = db.relationship('BankAccount', backref='user', lazy=True, cascade='all, delete-orphan')
    transactions = db.relationship('Transaction', backref='user', lazy=True, cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.email}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'email': self.email,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class BankAccount(db.Model):
    """Bank Account model - supports multiple accounts per user"""
    __tablename__ = 'bank_accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    
    # Account details
    account_name = db.Column(db.String(255), nullable=False, default='Primary Account')
    account_type = db.Column(db.String(50), nullable=True)  # savings, checking, credit, etc.
    aa_token = db.Column(db.String(500), nullable=False)
    
    # Status and metadata
    is_active = db.Column(db.Boolean, default=True)
    balance = db.Column(db.Numeric(12, 2), default=0.0)  # Cached balance
    last_synced = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='bank_account', lazy=True)
    
    def __repr__(self):
        return f'<BankAccount {self.account_name} (User: {self.user_id})>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'account_name': self.account_name,
            'account_type': self.account_type,
            'is_active': self.is_active,
            'balance': float(self.balance) if self.balance else 0.0,
            'last_synced': self.last_synced.isoformat() if self.last_synced else None,
            'transaction_count': len(self.transactions),
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def update_balance(self):
        """Calculate and update cached balance from transactions"""
        total = sum(tx.amount for tx in self.transactions)
        self.balance = total
        db.session.commit()


class Category(db.Model):
    """Transaction category model"""
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    
    # Relationships
    transactions = db.relationship('Transaction', backref='category', lazy=True)
    
    def __repr__(self):
        return f'<Category {self.name}>'


class Transaction(db.Model):
    """Transaction model - linked to both user and bank account"""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    bank_account_id = db.Column(db.Integer, db.ForeignKey('bank_accounts.id'), nullable=True)  # Nullable for backward compatibility
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    
    # Transaction details
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    description = db.Column(db.String(500), nullable=False)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Transaction {self.description} - ₹{self.amount}>'
    
    def to_dict(self):
        return {
            'id': self.id,
            'date': self.date.strftime('%Y-%m-%d'),
            'description': self.description,
            'amount': float(self.amount),
            'category': self.category.name if self.category else 'Uncategorized',
            'bank_account': self.bank_account.account_name if self.bank_account else 'Unknown',
            'bank_account_id': self.bank_account_id
        }
