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
    """Enhanced accounts page with LinkedAccount management"""
    try:
        legacy_accounts = get_user_accounts(current_user)
        linked_accounts = get_linked_accounts(current_user)
        
        legacy_accounts_data = []
        for account in legacy_accounts:
            stats = get_account_stats(account)
            account_info = account.to_dict()
            account_info.update(stats)
            legacy_accounts_data.append(account_info)
        
        linked_accounts_data = []
        for account in linked_accounts:
            account_info = account.to_dict()
            linked_accounts_data.append(account_info)
        
        return render_template('accounts.html',
                             page_name='accounts',
                             accounts=legacy_accounts_data,
                             linked_accounts=linked_accounts_data,
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
                             user_accounts=[])


# ============================================================================
# API ROUTES - LINKED ACCOUNT MANAGEMENT
# ============================================================================

@app.route('/api/bank/connect', methods=['POST'])
@login_required
def bank_connect_new():
    """Create new LinkedAccount from form data"""
    try:
        bank_name = request.form.get('bank_name', '').strip()
        account_nickname = request.form.get('account_nickname', '').strip()
        
        if not bank_name or not account_nickname:
            flash('Bank name and account nickname are required.', 'error')
            return redirect(url_for('accounts'))
        
        new_account = LinkedAccount(
            user_id=current_user.id,
            bank_name=bank_name,
            account_nickname=account_nickname,
            consent_status='active',
            is_active=True,
            creation_date=datetime.utcnow()
        )
        
        db.session.add(new_account)
        db.session.commit()
        
        flash(f'Successfully linked {account_nickname} ({bank_name})!', 'success')
        return redirect(url_for('accounts'))
    
    except Exception as e:
        db.session.rollback()
        print(f"Error linking account: {e}")
        flash('Failed to link account. Please try again.', 'error')
        return redirect(url_for('accounts'))


@app.route('/api/bank/sync', methods=['POST'])
@login_required
def bank_sync_account():
    """Enhanced sync endpoint - syncs specific LinkedAccount"""
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
        
        current_date = datetime.now()
        total_added = 0
        
        monthly_transactions = bank_api.generate_monthly_statement(
            current_user, current_date.year, current_date.month
        )
        
        for tx_data in monthly_transactions:
            tx_date = datetime.strptime(tx_data['date'], '%Y-%m-%d')
            
            existing = Transaction.query.filter_by(
                account_id=linked_account.id,
                date=tx_date,
                description=tx_data['description'],
                amount=abs(tx_data['amount'])
            ).first()
            
            if not existing:
                new_transaction = Transaction(
                    user_id=current_user.id,
                    account_id=linked_account.id,
                    date=tx_date,
                    description=tx_data['description'],
                    amount=abs(tx_data['amount']),
                    transaction_type='debit'
                )
                
                db.session.add(new_transaction)
                db.session.flush()
                categorize_transaction(new_transaction)
                total_added += 1
        
        linked_account.last_synced = datetime.utcnow()
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
            # All user's transactions
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
            # Legacy BankAccount
            account = BankAccount.query.get(account_id)
            if not account or account.user_id != current_user.id:
                print(f"❌ Legacy account {account_id} not found or unauthorized")
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
            # LinkedAccount
            account = LinkedAccount.query.get(account_id)
            if not account or account.user_id != current_user.id:
                print(f"❌ Linked account {account_id} not found or unauthorized")
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
    """Generate demo data for all user accounts"""
    try:
        legacy_accounts = get_user_accounts(current_user)
        linked_accounts = get_linked_accounts(current_user)
        
        all_accounts = []
        
        for acc in legacy_accounts:
            all_accounts.append(('legacy', acc))
        
        for acc in linked_accounts:
            all_accounts.append(('linked', acc))
        
        if not all_accounts:
            return jsonify({
                'status': 'error',
                'message': 'No bank accounts linked. Please link an account first.'
            }), 400
        
        print(f"📊 Generating demo data for {len(all_accounts)} account(s)")
        
        Transaction.query.filter_by(user_id=current_user.id).delete()
        db.session.commit()
        
        total_count = 0
        current_date = datetime.now()
        
        for account_type, account in all_accounts:
            account_name = account.account_name if account_type == 'legacy' else account.account_nickname
            print(f"  🏦 Generating for: {account_name}")
            
            for month_offset in range(3):
                year = current_date.year
                month = current_date.month - month_offset
                
                if month <= 0:
                    month += 12
                    year -= 1
                
                monthly_transactions = bank_api.generate_monthly_statement(
                    current_user, year, month
                )
                
                print(f"    📅 {year}-{month:02d}: {len(monthly_transactions)} transactions")
                
                for tx_data in monthly_transactions:
                    try:
                        new_transaction = Transaction(
                            user_id=current_user.id,
                            date=datetime.strptime(tx_data['date'], '%Y-%m-%d'),
                            description=tx_data['description'],
                            amount=abs(float(tx_data['amount'])),
                            transaction_type='debit'
                        )
                        
                        if account_type == 'legacy':
                            new_transaction.bank_account_id = account.id
                        else:
                            new_transaction.account_id = account.id
                        
                        db.session.add(new_transaction)
                        db.session.flush()
                        categorize_transaction(new_transaction)
                        total_count += 1
                    except Exception as e:
                        print(f"      ⚠️ Error creating transaction: {e}")
                        continue
        
        db.session.commit()
        
        print(f"✅ Successfully generated {total_count} transactions")
        
        return jsonify({
            'status': 'success',
            'message': f'Generated {total_count} demo transactions',
            'transactions': total_count,
            'accounts': len(all_accounts)
        })
    
    except Exception as e:
        db.session.rollback()
        print(f"❌ Demo data error: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'status': 'error',
            'message': f'Failed to generate demo data: {str(e)}'
        }), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
