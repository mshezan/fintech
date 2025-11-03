from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()


class User(UserMixin, db.Model):
    """User model with proper indexing"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    aa_token = db.Column(db.String(500), nullable=True)
    aa_consent_id = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # FIXED: Use lazy='dynamic' to avoid N+1 query problem
    transactions = db.relationship('Transaction', backref='user', lazy='dynamic', 
                                   cascade='all, delete-orphan')
    
    def __repr__(self):
        return f'<User {self.email}>'


class Category(db.Model):
    """Category model for transaction classification"""
    __tablename__ = 'categories'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    transactions = db.relationship('Transaction', backref='category', lazy='dynamic')
    
    def __repr__(self):
        return f'<Category {self.name}>'


class Transaction(db.Model):
    """Transaction model with proper foreign keys and indexing"""
    __tablename__ = 'transactions'
    
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, nullable=False, index=True)
    description = db.Column(db.String(500), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert transaction to dictionary for JSON responses"""
        return {
            'id': self.id,
            'date': self.date.strftime('%Y-%m-%d'),
            'description': self.description,
            'amount': round(self.amount, 2),
            'category_id': self.category_id,
            'category_name': self.category.name if self.category else 'Uncategorized'
        }
    
    def __repr__(self):
        return f'<Transaction {self.id}: {self.description} - ₹{self.amount}>'
