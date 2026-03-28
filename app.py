from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_required, current_user
from models import db, User, BankAccount, LinkedAccount, Transaction, Category
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
from dotenv import load_dotenv
from models import RetirementGoal, RetirementPlan, RetirementMilestone
from retirement_service import get_retirement_analysis
# Load environment variables
load_dotenv()

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'


@login_manager.user_loader
def load_user(user_id):
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None


app.register_blueprint(auth_bp)


# ============================================================================
# ERROR HANDLERS
# ============================================================================

@app.errorhandler(404)
def not_found_error(error):
    if current_user.is_authenticated:
        return render_template('404.html', 
                             page_name='error',
                             user_accounts=get_user_accounts(current_user),
                             linked_accounts=get_linked_accounts(current_user)), 404
    return redirect(url_for('auth.login'))


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    if current_user.is_authenticated:
        flash('An internal error occurred. Please try again.', 'error')
        return redirect(url_for('dashboard'))
    return jsonify({'error': 'Internal server error'}), 500


with app.app_context():
    db.create_all()
    initialize_categories()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_linked_accounts(user):
    """Get all linked accounts for a user, ordered by creation date"""
    return LinkedAccount.query.filter_by(user_id=user.id).order_by(LinkedAccount.creation_date.asc()).all()


def parse_account_param(account_param):
    """
    Parse account parameter and return (account_type, account_id)
    Returns: ('all', None) | ('legacy', id) | ('linked', id)
    """
    if account_param == 'all':
        return 'all', None
    
    if str(account_param).startswith('linked_'):
        try:
            linked_id = int(account_param.replace('linked_', ''))
            return 'linked', linked_id
        except:
            return 'all', None
    
    try:
        legacy_id = int(account_param)
        return 'legacy', legacy_id
    except:
        return 'all', None


def get_selected_account_and_month(user_id):
    """Get selected account and month from query parameters"""
    account_param = request.args.get('account', 'all')
    selected_month = request.args.get('month')
    
    user_accounts = get_user_accounts(current_user)
    linked_accounts = get_linked_accounts(current_user)
    
    if not user_accounts and not linked_accounts:
        return None, 'none', None, []
    
    account_type, account_id = parse_account_param(account_param)
    
    if not selected_month:
        selected_month = datetime.now().strftime('%Y-%m')
    
    try:
        year, month = map(int, selected_month.split('-'))
    except:
        year = datetime.now().year
        month = datetime.now().month
        selected_month = f"{year:04d}-{month:02d}"
    
    # Get all months with transactions
    if account_type == 'all':
        all_months_query = db.session.query(
            func.strftime('%Y-%m', Transaction.date).label('month')
        ).filter(
            Transaction.user_id == current_user.id
        ).distinct().order_by(
            func.strftime('%Y-%m', Transaction.date).desc()
        ).all()
    elif account_type == 'legacy':
        all_months_query = db.session.query(
            func.strftime('%Y-%m', Transaction.date).label('month')
        ).filter(
            Transaction.bank_account_id == account_id
        ).distinct().order_by(
            func.strftime('%Y-%m', Transaction.date).desc()
        ).all()
    else:  # linked
        all_months_query = db.session.query(
            func.strftime('%Y-%m', Transaction.date).label('month')
        ).filter(
            Transaction.account_id == account_id
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
        user_accounts = get_user_accounts(current_user)
        linked_accounts = get_linked_accounts(current_user)
        
        if not user_accounts and not linked_accounts:
            return render_template('dashboard.html',
                                 page_name='dashboard',
                                 user_accounts=[],
                                 linked_accounts=[],
                                 selected_account_id='all',
                                 selected_month=datetime.now().strftime('%Y-%m'),
                                 all_months=[datetime.now().strftime('%Y-%m')],
                                 total_spending=0,
                                 transaction_count=0,
                                 top_category='N/A',
                                 account_type='none',
                                 bank_linked=False)
        
        account_id, account_type, selected_month, all_months = get_selected_account_and_month(current_user.id)
        
        try:
            year, month = map(int, selected_month.split('-'))
        except:
            year = datetime.now().year
            month = datetime.now().month
        
        # Calculate stats based on account type
        if account_type == 'all':
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
        
        elif account_type == 'legacy':
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
        
        else:  # linked
            total_spending = db.session.query(
                func.sum(Transaction.amount)
            ).filter(
                Transaction.account_id == account_id,
                extract('year', Transaction.date) == year,
                extract('month', Transaction.date) == month
            ).scalar() or 0
            
            transaction_count = Transaction.query.filter(
                Transaction.account_id == account_id,
                extract('year', Transaction.date) == year,
                extract('month', Transaction.date) == month
            ).count()
            
            top_category = db.session.query(
                Category.name,
                func.sum(Transaction.amount).label('total')
            ).join(Transaction).filter(
                Transaction.account_id == account_id,
                extract('year', Transaction.date) == year,
                extract('month', Transaction.date) == month
            ).group_by(Category.name).order_by(func.sum(Transaction.amount).desc()).first()
        
        top_category_name = top_category[0] if top_category else 'N/A'
        
        # Format selected_account_id for template
        if account_type == 'linked':
            display_account_id = f'linked_{account_id}'
        elif account_type == 'legacy':
            display_account_id = account_id
        else:
            display_account_id = 'all'
        
        return render_template('dashboard.html',
                             page_name='dashboard',
                             user_accounts=user_accounts,
                             linked_accounts=linked_accounts,
                             selected_account_id=display_account_id,
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
                             linked_accounts=[],
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
        linked_accounts = get_linked_accounts(current_user)
        
        if not user_accounts and not linked_accounts:
            return render_template('transactions.html',
                                 page_name='transactions',
                                 transactions=[],
                                 categories=Category.query.all(),
                                 user_accounts=[],
                                 linked_accounts=[],
                                 selected_account_id='all',
                                 all_months=[datetime.now().strftime('%Y-%m')],
                                 selected_month=datetime.now().strftime('%Y-%m'))
        
        account_id, account_type, selected_month, all_months = get_selected_account_and_month(current_user.id)
        
        try:
            year, month = map(int, selected_month.split('-'))
        except:
            year = datetime.now().year
            month = datetime.now().month
        
        # Get transactions based on account type
        if account_type == 'all':
            transactions_list = Transaction.query.filter(
                Transaction.user_id == current_user.id,
                extract('year', Transaction.date) == year,
                extract('month', Transaction.date) == month
            ).order_by(Transaction.date.desc()).all()
        elif account_type == 'legacy':
            transactions_list = Transaction.query.filter(
                Transaction.bank_account_id == account_id,
                extract('year', Transaction.date) == year,
                extract('month', Transaction.date) == month
            ).order_by(Transaction.date.desc()).all()
        else:  # linked
            transactions_list = Transaction.query.filter(
                Transaction.account_id == account_id,
                extract('year', Transaction.date) == year,
                extract('month', Transaction.date) == month
            ).order_by(Transaction.date.desc()).all()
        
        categories = Category.query.order_by(Category.name).all()
        
        # Format selected_account_id for template
        if account_type == 'linked':
            display_account_id = f'linked_{account_id}'
        elif account_type == 'legacy':
            display_account_id = account_id
        else:
            display_account_id = 'all'
        
        return render_template('transactions.html',
                             page_name='transactions',
                             transactions=transactions_list,
                             categories=categories,
                             user_accounts=user_accounts,
                             linked_accounts=linked_accounts,
                             selected_account_id=display_account_id,
                             all_months=all_months,
                             selected_month=selected_month)
    
    except Exception as e:
        print(f"Transactions error: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading transactions.', 'error')
        return render_template('transactions.html',
                             page_name='transactions',
                             transactions=[],
                             categories=Category.query.all(),
                             user_accounts=get_user_accounts(current_user),
                             linked_accounts=get_linked_accounts(current_user),
                             selected_account_id='all',
                             all_months=[datetime.now().strftime('%Y-%m')],
                             selected_month=datetime.now().strftime('%Y-%m'))


@app.route('/accounts')
@login_required
def accounts():
    """Enhanced accounts page with FastAPI integration"""
    try:
        # Get user's existing linked accounts
        linked_accounts = get_linked_accounts(current_user)
        legacy_accounts = get_user_accounts(current_user)
        
        # Fetch ALL available accounts from FastAPI
        all_api_accounts = bank_api.fetch_all_api_accounts()
        
        # Filter: Remove already-linked accounts
        linked_api_ids = [acc.api_account_id for acc in linked_accounts]
        available_api_accounts = [
            acc for acc in all_api_accounts 
            if acc['id'] not in linked_api_ids
        ]
        
        print(f"📊 Available API accounts: {len(available_api_accounts)}")
        print(f"📊 Linked accounts: {len(linked_accounts)}")
        
        # Prepare legacy accounts data
        legacy_accounts_data = []
        for account in legacy_accounts:
            stats = get_account_stats(account)
            account_info = account.to_dict()
            account_info.update(stats)
            legacy_accounts_data.append(account_info)
        
        # Prepare linked accounts data
        linked_accounts_data = []
        for account in linked_accounts:
            account_info = account.to_dict()
            linked_accounts_data.append(account_info)
        
        return render_template('accounts.html',
                             page_name='accounts',
                             accounts=legacy_accounts_data,
                             linked_accounts=linked_accounts_data,
                             available_api_accounts=available_api_accounts,
                             user_accounts=legacy_accounts)
    
    except Exception as e:
        print(f"Accounts error: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading accounts.', 'error')
        return render_template('accounts.html',
                             page_name='accounts',
                             accounts=[],
                             linked_accounts=[],
                             available_api_accounts=[],
                             user_accounts=[])


# ============================================================================
# API ROUTES - LINKED ACCOUNT MANAGEMENT (FastAPI Integration)
# ============================================================================

@app.route('/api/bank/connect', methods=['POST'])
@login_required
def bank_connect_new():
    """Link a new account from FastAPI server"""
    try:
        api_account_id = request.form.get('api_account_id')
        account_nickname = request.form.get('account_nickname', '').strip()
        
        if not api_account_id or not account_nickname:
            flash('Account and nickname are required.', 'error')
            return redirect(url_for('accounts'))
        
        try:
            api_account_id = int(api_account_id)
        except ValueError:
            flash('Invalid account selected.', 'error')
            return redirect(url_for('accounts'))
        
        # Check if already linked
        existing = LinkedAccount.query.filter_by(
            user_id=current_user.id,
            api_account_id=api_account_id
        ).first()
        
        if existing:
            flash(f'Account is already linked as "{existing.account_nickname}".', 'warning')
            return redirect(url_for('accounts'))
        
        # Fetch account details from FastAPI
        account_details = bank_api.fetch_account_details(api_account_id)
        
        if not account_details:
            flash('Failed to fetch account details from API.', 'error')
            return redirect(url_for('accounts'))
        
        # Create new linked account
        new_account = LinkedAccount(
            user_id=current_user.id,
            api_account_id=api_account_id,
            account_nickname=account_nickname,
            api_account_name=account_details.get('name'),
            api_account_type=account_details.get('type'),
            api_balance=account_details.get('balance'),
            consent_status='active',
            is_active=True,
            creation_date=datetime.utcnow()
        )
        
        db.session.add(new_account)
        db.session.commit()
        
        flash(f'Successfully linked {account_nickname}!', 'success')
        return redirect(url_for('accounts'))
    
    except Exception as e:
        db.session.rollback()
        print(f"Error linking account: {e}")
        import traceback
        traceback.print_exc()
        flash('Failed to link account. Please try again.', 'error')
        return redirect(url_for('accounts'))


@app.route('/api/bank/sync', methods=['POST'])
@login_required
def bank_sync_account():
    """Sync transactions from FastAPI for specific LinkedAccount"""
    try:
        data = request.get_json()
        account_id = data.get('account_id')
        
        if not account_id:
            return jsonify({
                'status': 'error',
                'message': 'Account ID is required'
            }), 400
        
        linked_account = LinkedAccount.query.get(account_id)
        
        if not linked_account or linked_account.user_id != current_user.id:
            return jsonify({
                'status': 'error',
                'message': 'Account not found or unauthorized'
            }), 403
        
        print(f"🔄 Syncing account: {linked_account.account_nickname}")
        
        # Fetch transactions from FastAPI
        api_transactions = bank_api.fetch_transactions_for_account(linked_account)
        
        if not api_transactions:
            return jsonify({
                'status': 'success',
                'new_transactions': 0,
                'message': 'No new transactions found'
            })
        
        total_added = 0
        
        # Process each transaction
        for tx_data in api_transactions:
            try:
                # Parse date
                tx_date = datetime.strptime(tx_data['date'], '%Y-%m-%d')
                
                # Create new transaction with API fields
                new_transaction = Transaction(
                    user_id=current_user.id,
                    account_id=linked_account.id,
                    date=tx_date,
                    description=tx_data['merchant'],  # API merchant -> Flask description
                    amount=abs(float(tx_data['amount'])),
                    mode=tx_data.get('mode'),
                    transaction_type=tx_data.get('type', 'debit'),
                    narration=tx_data.get('narration')
                )
                
                db.session.add(new_transaction)
                db.session.flush()
                
                # Auto-categorize
                categorize_transaction(new_transaction)
                total_added += 1
                
            except Exception as e:
                print(f"⚠️  Error processing transaction: {e}")
                continue
        
        # Update last synced time
        linked_account.last_synced = datetime.utcnow()
        
        # Update cached balance from API
        account_details = bank_api.fetch_account_details(linked_account.api_account_id)
        if account_details:
            linked_account.api_balance = account_details.get('balance')
        
        db.session.commit()
        
        print(f"✅ Synced {total_added} transactions")
        
        return jsonify({
            'status': 'success',
            'new_transactions': total_added,
            'message': f'Synced {total_added} new transactions for {linked_account.account_nickname}'
        })
    
    except Exception as e:
        db.session.rollback()
        print(f"Sync error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f'Failed to sync transactions: {str(e)}'
        }), 500


@app.route('/api/linked-accounts/<int:account_id>/delete', methods=['POST'])
@login_required
def delete_linked_account(account_id):
    """Delete a linked account"""
    try:
        account = LinkedAccount.query.get(account_id)
        
        if not account or account.user_id != current_user.id:
            return jsonify({'status': 'error', 'message': 'Unauthorized'}), 403
        
        account_name = account.account_nickname
        
        Transaction.query.filter_by(account_id=account_id).delete()
        db.session.delete(account)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Deleted {account_name} and associated transactions'
        })
    
    except Exception as e:
        db.session.rollback()
        print(f"Delete error: {e}")
        return jsonify({'status': 'error', 'message': 'Failed to delete account'}), 500


# ============================================================================
# API ROUTES - LEGACY ACCOUNT MANAGEMENT
# ============================================================================

@app.route('/api/accounts/<int:account_id>/set-active', methods=['POST'])
@login_required
def set_account_active(account_id):
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
    """Get spending by category - supports LinkedAccounts"""
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
        
        print(f"📊 Chart API: month={selected_month}, account={account_param}")
        
        # Parse account parameter
        account_type, account_id = parse_account_param(account_param)
        
        if account_type == 'all':
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
        
        elif account_type == 'legacy':
            account = BankAccount.query.get(account_id)
            if not account or account.user_id != current_user.id:
                print(f"❌ Legacy account {account_id} not found")
                return jsonify({'labels': [], 'data': []}), 200
            
            spending_data = db.session.query(
                Category.name,
                func.sum(Transaction.amount).label('total')
            ).join(Transaction).filter(
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
        
        else:  # linked
            account = LinkedAccount.query.get(account_id)
            if not account or account.user_id != current_user.id:
                print(f"❌ Linked account {account_id} not found")
                return jsonify({'labels': [], 'data': []}), 200
            
            print(f"✓ Querying LinkedAccount: {account.account_nickname}")
            
            spending_data = db.session.query(
                Category.name,
                func.sum(Transaction.amount).label('total')
            ).join(Transaction).filter(
                Transaction.account_id == account_id,
                extract('month', Transaction.date) == month,
                extract('year', Transaction.date) == year
            ).group_by(Category.name).all()
            
            uncategorized = db.session.query(
                func.sum(Transaction.amount).label('total')
            ).filter(
                Transaction.account_id == account_id,
                Transaction.category_id == None,
                extract('month', Transaction.date) == month,
                extract('year', Transaction.date) == year
            ).scalar()
        
        labels = [item[0] for item in spending_data]
        data = [float(item[1]) for item in spending_data]
        
        if uncategorized and uncategorized > 0:
            labels.append('Uncategorized')
            data.append(float(uncategorized))
        
        print(f"✓ Chart data: {len(labels)} categories, total: {sum(data)}")
        
        return jsonify({'labels': labels, 'data': data})
    
    except Exception as e:
        print(f"❌ Chart API error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'labels': [], 'data': []}), 200


@app.route('/api/transactions/<int:tx_id>/categorize', methods=['POST'])
@login_required
def categorize_manual(tx_id):
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
    """DEPRECATED: Use FastAPI sync instead"""
    return jsonify({
        'status': 'error',
        'message': 'Demo data generation disabled. Use FastAPI sync to get real transactions.'
    }), 400

@app.route('/retirement', methods=['GET'])
@login_required
def retirement():
    """Main retirement planning page."""
    try:
        goal = RetirementGoal.query.filter_by(user_id=current_user.id).first()
        plan = RetirementPlan.query.filter_by(user_id=current_user.id).first()
        milestones = RetirementMilestone.query.filter_by(user_id=current_user.id).all()
        insights = []
 
        return render_template(

            'retirement.html',
            page_name='retirement',
            user_accounts=get_user_accounts(current_user),
            linked_accounts=get_linked_accounts(current_user),
            goal=goal,
            plan=plan,
            milestones=milestones,
            insights=insights,
        )
    except Exception as e:
        print(f"Retirement page error: {e}")
        import traceback; traceback.print_exc()
        flash('Error loading retirement page.', 'error')
        return redirect(url_for('dashboard'))
 
 
@app.route('/retirement/setup', methods=['POST'])
@login_required
def retirement_setup():
    """Create or update a RetirementGoal."""
    try:
        current_age           = int(request.form.get('current_age', 25))
        retirement_age        = int(request.form.get('retirement_age', 60))
        target_monthly_income = float(request.form.get('target_monthly_income', 50000))
        current_monthly_contribution = float(request.form.get('current_monthly_contribution', 0))
        expected_return       = float(request.form.get('expected_return', 12.0))
        inflation_rate        = float(request.form.get('inflation_rate', 6.0))
        life_expectancy       = int(request.form.get('life_expectancy', 85))
 
        # Basic validation
        if retirement_age <= current_age:
            flash('Retirement age must be greater than your current age.', 'error')
            return redirect(url_for('retirement'))
        if life_expectancy <= retirement_age:
            flash('Life expectancy must be greater than retirement age.', 'error')
            return redirect(url_for('retirement'))
 
        # Upsert goal
        goal = RetirementGoal.query.filter_by(user_id=current_user.id).first()
        if not goal:
            goal = RetirementGoal(user_id=current_user.id)
            db.session.add(goal)
 
        goal.current_age                  = current_age
        goal.retirement_age               = retirement_age
        goal.target_monthly_income        = target_monthly_income
        goal.current_monthly_contribution = current_monthly_contribution
        goal.expected_return              = expected_return
        goal.inflation_rate               = inflation_rate
        goal.life_expectancy              = life_expectancy
        goal.updated_at                   = datetime.utcnow()
        db.session.commit()
 
        # Calculate + save plan
        calc = calculate_retirement_plan(goal)
        plan = save_retirement_plan(current_user.id, goal, calc)
 
        # Check milestones
        check_and_award_milestones(current_user.id, goal, plan)
 
        flash('Retirement goal updated! Here\'s your personalised plan. 🎯', 'success')
        return redirect(url_for('retirement'))
 
    except Exception as e:
        db.session.rollback()
        print(f"Retirement setup error: {e}")
        import traceback; traceback.print_exc()
        flash('Failed to save retirement goal. Please try again.', 'error')
        return redirect(url_for('retirement'))
 
 
@app.route('/api/retirement/simulate', methods=['POST'])
@login_required
def retirement_simulate():
    """
    API: run a what-if simulation without saving.
    Body: { monthly_investment: float, retire_age: int }
    """
    try:
        goal = RetirementGoal.query.filter_by(user_id=current_user.id).first()
        if not goal:
            return jsonify({'error': 'No retirement goal set'}), 404
 
        data = request.get_json()
        monthly_investment = float(data.get('monthly_investment', goal.current_monthly_contribution))
        retire_age = int(data.get('retire_age', goal.retirement_age))
 
        if retire_age <= goal.current_age:
            return jsonify({'error': 'Retirement age must be greater than current age'}), 400
 
        result = simulate_scenario(goal, monthly_investment, retire_age)
        return jsonify(result)
 
    except Exception as e:
        print(f"Simulation error: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/retirement/analysis', methods=['GET'])
@login_required
def retirement_analysis():
    """
    NEW: Data-driven retirement intelligence API.
    Returns full JSON: finances, insights, portfolios.
    """
    try:
        analysis = get_retirement_analysis(current_user.id)
        return jsonify(analysis)
    except Exception as e:
        print(f"Retirement analysis error: {e}")
        import traceback; traceback.print_exc()
        return jsonify({'error': 'Analysis failed - sync transactions first'}), 500

@login_required
def generate_demo_data():
    """DEPRECATED: Use FastAPI sync instead"""
    return jsonify({
        'status': 'error',
        'message': 'Demo data generation disabled. Use FastAPI sync to get real transactions.'
    }), 400


if __name__ == '__main__':
    # Check API server on startup
    print("\n" + "="*60)
    print("🚀 Starting FinTrack Flask Application")
    print("="*60)
    bank_api.check_api_server()
    print("="*60 + "\n")
    
    app.run(debug=True, host='0.0.0.0', port=5000)
@app.route('/retirement', methods=['GET'])
@login_required
def retirement():
    """Main retirement planning page."""
    try:
        goal = RetirementGoal.query.filter_by(user_id=current_user.id).first()
        plan = RetirementPlan.query.filter_by(user_id=current_user.id).first()
        milestones = RetirementMilestone.query.filter_by(user_id=current_user.id).all()
        insights = []
 
        if goal and plan:
            insights = get_spending_insights(current_user.id, goal)
 
        return render_template(
            'retirement.html',
            page_name='retirement',
            user_accounts=get_user_accounts(current_user),
            linked_accounts=get_linked_accounts(current_user),
            goal=goal,
            plan=plan,
            milestones=milestones,
            insights=insights,
        )
    except Exception as e:
        print(f"Retirement page error: {e}")
        import traceback; traceback.print_exc()
        flash('Error loading retirement page.', 'error')
        return redirect(url_for('dashboard'))
 
 
@app.route('/retirement/setup', methods=['POST'])
@login_required
def retirement_setup():
    """Create or update a RetirementGoal."""
    try:
        current_age           = int(request.form.get('current_age', 25))
        retirement_age        = int(request.form.get('retirement_age', 60))
        target_monthly_income = float(request.form.get('target_monthly_income', 50000))
        current_monthly_contribution = float(request.form.get('current_monthly_contribution', 0))
        expected_return       = float(request.form.get('expected_return', 12.0))
        inflation_rate        = float(request.form.get('inflation_rate', 6.0))
        life_expectancy       = int(request.form.get('life_expectancy', 85))
 
        # Basic validation
        if retirement_age <= current_age:
            flash('Retirement age must be greater than your current age.', 'error')
            return redirect(url_for('retirement'))
        if life_expectancy <= retirement_age:
            flash('Life expectancy must be greater than retirement age.', 'error')
            return redirect(url_for('retirement'))
 
        # Upsert goal
        goal = RetirementGoal.query.filter_by(user_id=current_user.id).first()
        if not goal:
            goal = RetirementGoal(user_id=current_user.id)
            db.session.add(goal)
 
        goal.current_age                  = current_age
        goal.retirement_age               = retirement_age
        goal.target_monthly_income        = target_monthly_income
        goal.current_monthly_contribution = current_monthly_contribution
        goal.expected_return              = expected_return
        goal.inflation_rate               = inflation_rate
        goal.life_expectancy              = life_expectancy
        goal.updated_at                   = datetime.utcnow()
        db.session.commit()
 
        # Calculate + save plan
        calc = calculate_retirement_plan(goal)
        plan = save_retirement_plan(current_user.id, goal, calc)
 
        # Check milestones
        check_and_award_milestones(current_user.id, goal, plan)
 
        flash('Retirement goal updated! Here\'s your personalised plan. 🎯', 'success')
        return redirect(url_for('retirement'))
 
    except Exception as e:
        db.session.rollback()
        print(f"Retirement setup error: {e}")
        import traceback; traceback.print_exc()
        flash('Failed to save retirement goal. Please try again.', 'error')
        return redirect(url_for('retirement'))
 
 
@app.route('/api/retirement/simulate', methods=['POST'])
@login_required
def retirement_simulate():
    """
    API: run a what-if simulation without saving.
    Body: { monthly_investment: float, retire_age: int }
    """
    try:
        goal = RetirementGoal.query.filter_by(user_id=current_user.id).first()
        if not goal:
            return jsonify({'error': 'No retirement goal set'}), 404
 
        data = request.get_json()
        monthly_investment = float(data.get('monthly_investment', goal.current_monthly_contribution))
        retire_age = int(data.get('retire_age', goal.retirement_age))
 
        if retire_age <= goal.current_age:
            return jsonify({'error': 'Retirement age must be greater than current age'}), 400
 
        result = simulate_scenario(goal, monthly_investment, retire_age)
        return jsonify(result)
 
    except Exception as e:
        print(f"Simulation error: {e}")
        return jsonify({'error': str(e)}), 500