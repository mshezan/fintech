from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_required, current_user
from models import db, User, BankAccount, Transaction, Category
from services import (
    categorize_transaction, 
    initialize_categories,
    get_user_accounts,
    get_active_account,
    set_active_account,
    get_account_stats
)
import bank_api
from config import Config
from auth import auth_bp
from datetime import datetime
from sqlalchemy import func, extract

app = Flask(__name__)
app.config.from_object(Config)

# Initialize database
db.init_app(app)

# Initialize Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'


@login_manager.user_loader
def load_user(user_id):
    """Load user by ID"""
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None


# Register authentication blueprint
app.register_blueprint(auth_bp)


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    if current_user.is_authenticated:
        return render_template('404.html', 
                             page_name='error',
                             user_accounts=get_user_accounts(current_user)), 404
    return redirect(url_for('auth.login'))


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    db.session.rollback()
    if current_user.is_authenticated:
        flash('An internal error occurred. Please try again.', 'error')
        return redirect(url_for('dashboard'))
    return jsonify({'error': 'Internal server error'}), 500


# Initialize database and categories
with app.app_context():
    db.create_all()
    initialize_categories()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_selected_account_and_month(user_id):
    """
    Get selected account and month from query parameters
    Returns: (account_id, account_type, selected_month, all_months)
    """
    # Get account selection from query (default: 'all' for combined view)
    account_param = request.args.get('account', 'all')
    
    # Get month from query
    selected_month = request.args.get('month')
    
    # Get user's accounts
    user_accounts = get_user_accounts(current_user)
    
    if not user_accounts:
        return None, 'none', None, []
    
    # Determine account to view
    if account_param == 'all':
        account_id = None  # None means combined view
        account_type = 'combined'
    else:
        try:
            account_id = int(account_param)
            # Verify account belongs to user
            account = BankAccount.query.get(account_id)
            if not account or account.user_id != current_user.id:
                account_id = None
                account_type = 'combined'
            else:
                account_type = 'individual'
        except:
            account_id = None
            account_type = 'combined'
    
    # Default to current month if not specified
    if not selected_month:
        selected_month = datetime.now().strftime('%Y-%m')
    
    # Parse month
    try:
        year, month = map(int, selected_month.split('-'))
    except:
        year = datetime.now().year
        month = datetime.now().month
        selected_month = f"{year:04d}-{month:02d}"
    
    # Get all months with transactions for this account
    if account_type == 'combined':
        all_months_query = db.session.query(
            func.strftime('%Y-%m', Transaction.date).label('month')
        ).filter(
            Transaction.user_id == current_user.id
        ).distinct().order_by(
            func.strftime('%Y-%m', Transaction.date).desc()
        ).all()
    else:
        all_months_query = db.session.query(
            func.strftime('%Y-%m', Transaction.date).label('month')
        ).filter(
            Transaction.bank_account_id == account_id
        ).distinct().order_by(
            func.strftime('%Y-%m', Transaction.date).desc()
        ).all()
    
    all_months = [m[0] for m in all_months_query if m[0]]
    
    if not all_months:
        all_months = [selected_month]
    elif selected_month not in all_months:
        all_months.insert(0, selected_month)
        all_months.sort(reverse=True)
    
    return account_id, account_type, selected_month, all_months


# ============================================================================
# PAGE ROUTES
# ============================================================================

@app.route('/')
@login_required
def dashboard():
    """Dashboard with multi-account support"""
    try:
        # Get user's bank accounts
        user_accounts = get_user_accounts(current_user)
        
        if not user_accounts:
            # No accounts linked yet
            return render_template('dashboard.html',
                                 page_name='dashboard',
                                 user_accounts=user_accounts,
                                 selected_account_id='all',
                                 selected_month=datetime.now().strftime('%Y-%m'),
                                 all_months=[datetime.now().strftime('%Y-%m')],
                                 total_spending=0,
                                 transaction_count=0,
                                 top_category='N/A',
                                 account_type='none',
                                 bank_linked=False)
        
        # Get selected account and month
        account_id, account_type, selected_month, all_months = get_selected_account_and_month(current_user.id)
        
        # Parse month
        try:
            year, month = map(int, selected_month.split('-'))
        except:
            year = datetime.now().year
            month = datetime.now().month
        
        # Get transactions based on account selection
        if account_type == 'combined':
            # All user's accounts
            total_spending = db.session.query(
                func.sum(Transaction.amount)
            ).filter(
                Transaction.user_id == current_user.id,
                extract('year', Transaction.date) == year,
                extract('month', Transaction.date) == month
            ).scalar() or 0
            
            transaction_count = Transaction.query.filter(
                Transaction.user_id == current_user.id,
                extract('year', Transaction.date) == year,
                extract('month', Transaction.date) == month
            ).count()
            
            top_category = db.session.query(
                Category.name,
                func.sum(Transaction.amount).label('total')
            ).join(Transaction).filter(
                Transaction.user_id == current_user.id,
                extract('year', Transaction.date) == year,
                extract('month', Transaction.date) == month
            ).group_by(Category.name).order_by(func.sum(Transaction.amount).desc()).first()
        else:
            # Single account
            total_spending = db.session.query(
                func.sum(Transaction.amount)
            ).filter(
                Transaction.bank_account_id == account_id,
                extract('year', Transaction.date) == year,
                extract('month', Transaction.date) == month
            ).scalar() or 0
            
            transaction_count = Transaction.query.filter(
                Transaction.bank_account_id == account_id,
                extract('year', Transaction.date) == year,
                extract('month', Transaction.date) == month
            ).count()
            
            top_category = db.session.query(
                Category.name,
                func.sum(Transaction.amount).label('total')
            ).join(Transaction).filter(
                Transaction.bank_account_id == account_id,
                extract('year', Transaction.date) == year,
                extract('month', Transaction.date) == month
            ).group_by(Category.name).order_by(func.sum(Transaction.amount).desc()).first()
        
        top_category_name = top_category[0] if top_category else 'N/A'
        
        return render_template('dashboard.html',
                             page_name='dashboard',
                             user_accounts=user_accounts,
                             selected_account_id=account_id or 'all',
                             selected_month=selected_month,
                             all_months=all_months,
                             total_spending=total_spending,
                             transaction_count=transaction_count,
                             top_category=top_category_name,
                             account_type=account_type,
                             bank_linked=True)
    
    except Exception as e:
        print(f"Dashboard error: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading dashboard.', 'error')
        return render_template('dashboard.html',
                             page_name='dashboard',
                             user_accounts=[],
                             selected_account_id='all',
                             selected_month=datetime.now().strftime('%Y-%m'),
                             all_months=[datetime.now().strftime('%Y-%m')],
                             total_spending=0,
                             transaction_count=0,
                             top_category='N/A',
                             account_type='none',
                             bank_linked=False)


@app.route('/transactions')
@login_required
def transactions():
    """Transactions page with multi-account support"""
    try:
        user_accounts = get_user_accounts(current_user)
        
        if not user_accounts:
            return render_template('transactions.html',
                                 page_name='transactions',
                                 transactions=[],
                                 categories=Category.query.all(),
                                 user_accounts=[],
                                 selected_account_id='all',
                                 all_months=[datetime.now().strftime('%Y-%m')],
                                 selected_month=datetime.now().strftime('%Y-%m'))
        
        account_id, account_type, selected_month, all_months = get_selected_account_and_month(current_user.id)
        
        # Parse month
        try:
            year, month = map(int, selected_month.split('-'))
        except:
            year = datetime.now().year
            month = datetime.now().month
        
        # Get transactions
        if account_type == 'combined':
            transactions_list = Transaction.query.filter(
                Transaction.user_id == current_user.id,
                extract('year', Transaction.date) == year,
                extract('month', Transaction.date) == month
            ).order_by(Transaction.date.desc()).all()
        else:
            transactions_list = Transaction.query.filter(
                Transaction.bank_account_id == account_id,
                extract('year', Transaction.date) == year,
                extract('month', Transaction.date) == month
            ).order_by(Transaction.date.desc()).all()
        
        categories = Category.query.order_by(Category.name).all()
        
        return render_template('transactions.html',
                             page_name='transactions',
                             transactions=transactions_list,
                             categories=categories,
                             user_accounts=user_accounts,
                             selected_account_id=account_id or 'all',
                             all_months=all_months,
                             selected_month=selected_month)
    
    except Exception as e:
        print(f"Transactions error: {e}")
        flash('Error loading transactions.', 'error')
        return render_template('transactions.html',
                             page_name='transactions',
                             transactions=[],
                             categories=Category.query.all(),
                             user_accounts=get_user_accounts(current_user),
                             selected_account_id='all',
                             all_months=[datetime.now().strftime('%Y-%m')],
                             selected_month=datetime.now().strftime('%Y-%m'))


@app.route('/accounts')
@login_required
def accounts():
    """
    Enhanced accounts page with account management
    Shows all linked accounts with stats and management options
    """
    try:
        user_accounts = get_user_accounts(current_user)
        
        # Get stats for each account
        accounts_data = []
        for account in user_accounts:
            stats = get_account_stats(account)
            account_info = account.to_dict()
            account_info.update(stats)
            accounts_data.append(account_info)
        
        return render_template('accounts.html',
                             page_name='accounts',
                             accounts=accounts_data,
                             user_accounts=user_accounts)
    
    except Exception as e:
        print(f"Accounts error: {e}")
        flash('Error loading accounts.', 'error')
        return render_template('accounts.html',
                             page_name='accounts',
                             accounts=[],
                             user_accounts=[])


# ============================================================================
# API ROUTES - ACCOUNT MANAGEMENT
# ============================================================================

@app.route('/api/accounts/<int:account_id>/set-active', methods=['POST'])
@login_required
def set_account_active(account_id):
    """Set a specific account as active"""
    try:
        account = BankAccount.query.get(account_id)
        if not account or account.user_id != current_user.id:
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
        
        set_active_account(current_user, account_id)
        
        return jsonify({
            'status': 'success',
            'message': f'Switched to {account.account_name}'
        })
    
    except Exception as e:
        print(f"Set active error: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to set active account'}), 500


@app.route('/api/accounts/<int:account_id>/rename', methods=['POST'])
@login_required
def rename_account(account_id):
    """Rename a bank account"""
    try:
        account = BankAccount.query.get(account_id)
        if not account or account.user_id != current_user.id:
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
        
        data = request.get_json()
        new_name = data.get('account_name', '').strip()
        
        if not new_name:
            return jsonify({'status': 'error', 'message': 'Account name cannot be empty'}), 400
        
        account.account_name = new_name
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Account renamed successfully',
            'account_name': new_name
        })
    
    except Exception as e:
        print(f"Rename error: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to rename account'}), 500


@app.route('/api/accounts/<int:account_id>/toggle', methods=['POST'])
@login_required
def toggle_account_active(account_id):
    """Toggle account active/inactive status"""
    try:
        account = BankAccount.query.get(account_id)
        if not account or account.user_id != current_user.id:
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
        
        account.is_active = not account.is_active
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Account {("activated" if account.is_active else "deactivated")} successfully',
            'is_active': account.is_active
        })
    
    except Exception as e:
        print(f"Toggle error: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to toggle account'}), 500


# ============================================================================
# API ROUTES - DATA ENDPOINTS
# ============================================================================

@app.route('/api/spending-by-category')
@login_required
def spending_by_category():
    """Get spending by category - supports multi-account"""
    try:
        selected_month = request.args.get('month')
        account_param = request.args.get('account', 'all')
        
        if not selected_month:
            selected_month = datetime.now().strftime('%Y-%m')
        
        try:
            year, month = map(int, selected_month.split('-'))
        except:
            year = datetime.now().year
            month = datetime.now().month
        
        # Determine which account(s) to include
        if account_param == 'all':
            # Combined view - all user's accounts
            spending_data = db.session.query(
                Category.name,
                func.sum(Transaction.amount).label('total')
            ).join(
                Transaction, Transaction.category_id == Category.id
            ).filter(
                Transaction.user_id == current_user.id,
                extract('month', Transaction.date) == month,
                extract('year', Transaction.date) == year
            ).group_by(Category.name).all()
            
            uncategorized = db.session.query(
                func.sum(Transaction.amount).label('total')
            ).filter(
                Transaction.user_id == current_user.id,
                Transaction.category_id == None,
                extract('month', Transaction.date) == month,
                extract('year', Transaction.date) == year
            ).scalar()
        else:
            # Single account view
            try:
                account_id = int(account_param)
                account = BankAccount.query.get(account_id)
                if not account or account.user_id != current_user.id:
                    return jsonify({'labels': [], 'data': []}), 200
            except:
                return jsonify({'labels': [], 'data': []}), 200
            
            spending_data = db.session.query(
                Category.name,
                func.sum(Transaction.amount).label('total')
            ).join(
                Transaction
            ).filter(
                Transaction.bank_account_id == account_id,
                extract('month', Transaction.date) == month,
                extract('year', Transaction.date) == year
            ).group_by(Category.name).all()
            
            uncategorized = db.session.query(
                func.sum(Transaction.amount).label('total')
            ).filter(
                Transaction.bank_account_id == account_id,
                Transaction.category_id == None,
                extract('month', Transaction.date) == month,
                extract('year', Transaction.date) == year
            ).scalar()
        
        labels = [item[0] for item in spending_data]
        data = [float(item[1]) for item in spending_data]
        
        if uncategorized and uncategorized > 0:
            labels.append('Uncategorized')
            data.append(float(uncategorized))
        
        return jsonify({'labels': labels, 'data': data})
    
    except Exception as e:
        print(f"API error: {e}")
        return jsonify({'labels': [], 'data': []}), 200


@app.route('/api/bank/connect')
@login_required
def bank_connect():
    """Initiate bank connection"""
    try:
        auth_url = bank_api.initiate_connection(current_user)
        if auth_url:
            return redirect(auth_url)
        else:
            flash('Error connecting to bank.', 'error')
            return redirect(url_for('accounts'))
    except Exception as e:
        print(f"Bank connect error: {e}")
        flash('Error connecting to bank.', 'error')
        return redirect(url_for('accounts'))


@app.route('/api/bank/callback')
def bank_callback():
    """Handle bank connection callback"""
    if not current_user.is_authenticated:
        return redirect(url_for('auth.login'))
    
    try:
        success = bank_api.handle_api_callback(request.args, current_user)
        
        if success:
            flash('Bank account linked successfully!', 'success')
        else:
            flash('Failed to link bank account.', 'error')
    except Exception as e:
        print(f"Callback error: {e}")
        flash('Error during bank linking.', 'error')
    
    return redirect(url_for('accounts'))


@app.route('/api/bank/sync', methods=['POST'])
@login_required
def bank_sync():
    """Sync transactions from all linked accounts"""
    try:
        user_accounts = get_user_accounts(current_user)
        total_added = 0
        
        for account in user_accounts:
            if not account.is_active:
                continue
            
            new_transactions_data = bank_api.fetch_new_transactions(current_user)
            
            for tx_data in new_transactions_data:
                tx_date = datetime.strptime(tx_data['date'], '%Y-%m-%d')
                
                existing = Transaction.query.filter_by(
                    bank_account_id=account.id,
                    date=tx_date,
                    description=tx_data['description'],
                    amount=abs(tx_data['amount'])
                ).first()
                
                if not existing:
                    new_transaction = Transaction(
                        user_id=current_user.id,
                        bank_account_id=account.id,
                        date=tx_date,
                        description=tx_data['description'],
                        amount=abs(tx_data['amount'])
                    )
                    
                    db.session.add(new_transaction)
                    db.session.flush()
                    categorize_transaction(new_transaction)
                    total_added += 1
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'new_transactions': total_added,
            'message': f'Synced {total_added} new transactions across all accounts'
        })
    
    except Exception as e:
        db.session.rollback()
        print(f"Sync error: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to sync transactions'
        }), 500


@app.route('/api/transactions/<int:tx_id>/categorize', methods=['POST'])
@login_required
def categorize_manual(tx_id):
    """Manually categorize a transaction"""
    try:
        transaction = Transaction.query.get(tx_id)
        
        if not transaction:
            return jsonify({'status': 'error', 'message': 'Transaction not found'}), 404
        
        if transaction.user_id != current_user.id:
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
        
        data = request.get_json()
        category_id = data.get('category_id')
        
        if category_id == '' or category_id == 'null':
            category_id = None
        elif category_id:
            try:
                category_id = int(category_id)
                category = Category.query.get(category_id)
                if not category:
                    return jsonify({'status': 'error', 'message': 'Invalid category'}), 400
            except ValueError:
                return jsonify({'status': 'error', 'message': 'Invalid category ID'}), 400
        
        transaction.category_id = category_id
        db.session.commit()
        
        return jsonify({'status': 'success', 'transaction': transaction.to_dict()})
    
    except Exception as e:
        db.session.rollback()
        print(f"Categorization error: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to update category'}), 500


@app.route('/api/demo/generate-data', methods=['POST'])
@login_required
def generate_demo_data():
    """Generate demo data for all user accounts"""
    try:
        user_accounts = get_user_accounts(current_user)
        
        if not user_accounts:
            return jsonify({
                'status': 'error',
                'message': 'No bank accounts linked. Please link an account first.'
            }), 400
        
        # Clear existing transactions
        Transaction.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        
        total_count = 0
        current_date = datetime.now()
        
        for account in user_accounts:
            for month_offset in range(3):
                year = current_date.year
                month = current_date.month - month_offset
                
                if month <= 0:
                    month += 12
                    year -= 1
                
                monthly_transactions = bank_api.generate_monthly_statement(
                    current_user, year, month
                )
                
                for tx_data in monthly_transactions:
                    try:
                        new_transaction = Transaction(
                            user_id=current_user.id,
                            bank_account_id=account.id,
                            date=datetime.strptime(tx_data['date'], '%Y-%m-%d'),
                            description=tx_data['description'],
                            amount=abs(float(tx_data['amount']))
                        )
                        
                        db.session.add(new_transaction)
                        db.session.flush()
                        categorize_transaction(new_transaction)
                        total_count += 1
                    except Exception as e:
                        print(f"Error creating transaction: {e}")
                        continue
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Generated {total_count} demo transactions',
            'transactions': total_count,
            'accounts': len(user_accounts)
        })
    
    except Exception as e:
        db.session.rollback()
        print(f"Demo data error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f'Failed to generate demo data: {str(e)}'
        }), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
