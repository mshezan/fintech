from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from flask_login import LoginManager, login_required, current_user
from models import db, User, Transaction, Category
from services import categorize_transaction, initialize_categories
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


# Error handlers
@app.errorhandler(404)
def not_found_error(error):
    """Handle 404 errors"""
    if current_user.is_authenticated:
        return render_template('dashboard.html', page_name='dashboard'), 404
    return redirect(url_for('auth.login'))


@app.errorhandler(500)
def internal_error(error):
    """Handle 500 errors"""
    db.session.rollback()
    return jsonify({'error': 'Internal server error'}), 500


# Initialize database and categories
with app.app_context():
    db.create_all()
    initialize_categories()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_selected_month_and_months_list(user_id):
    """
    Helper function to get selected month and list of all available months.
    Returns: (selected_month, all_months_list)
    """
    # Get month from query parameter
    selected_month = request.args.get('month')
    
    # Query for all distinct months with transactions
    all_months_query = db.session.query(
        func.strftime('%Y-%m', Transaction.date).label('month')
    ).filter(
        Transaction.user_id == user_id
    ).distinct().order_by(
        func.strftime('%Y-%m', Transaction.date).desc()
    ).all()
    
    all_months_list = [m[0] for m in all_months_query if m[0]]
    
    # Determine selected month
    if selected_month:
        # Use month from URL if provided
        pass
    elif all_months_list:
        # Use newest month if transactions exist
        selected_month = all_months_list[0]
    else:
        # Default to current month if no transactions
        selected_month = datetime.now().strftime('%Y-%m')
        all_months_list = [selected_month]
    
    # Ensure selected month is in list
    if selected_month and selected_month not in all_months_list:
        all_months_list.insert(0, selected_month)
        all_months_list.sort(reverse=True)
    
    return selected_month, all_months_list


# ============================================================================
# PAGE ROUTES
# ============================================================================

@app.route('/')
@login_required
def dashboard():
    """
    Dashboard homepage - Overview with chart and summary stats
    """
    try:
        selected_month, all_months = get_selected_month_and_months_list(current_user.id)
        
        # Parse month for queries
        try:
            year, month = map(int, selected_month.split('-'))
        except:
            year = datetime.now().year
            month = datetime.now().month
        
        # Get summary stats for selected month
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
        
        # Get top category
        top_category = db.session.query(
            Category.name,
            func.sum(Transaction.amount).label('total')
        ).join(
            Transaction
        ).filter(
            Transaction.user_id == current_user.id,
            extract('year', Transaction.date) == year,
            extract('month', Transaction.date) == month
        ).group_by(Category.name).order_by(func.sum(Transaction.amount).desc()).first()
        
        top_category_name = top_category[0] if top_category else 'N/A'
        
        bank_linked = current_user.aa_token is not None
        
        return render_template('dashboard.html',
                             page_name='dashboard',
                             all_months=all_months,
                             selected_month=selected_month,
                             total_spending=total_spending,
                             transaction_count=transaction_count,
                             top_category=top_category_name,
                             bank_linked=bank_linked)
    
    except Exception as e:
        print(f"Dashboard error: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading dashboard.', 'error')
        return render_template('dashboard.html',
                             page_name='dashboard',
                             all_months=[datetime.now().strftime('%Y-%m')],
                             selected_month=datetime.now().strftime('%Y-%m'),
                             total_spending=0,
                             transaction_count=0,
                             top_category='N/A',
                             bank_linked=False)


@app.route('/transactions')
@login_required
def transactions():
    """
    Transactions page - Full transaction list with filtering
    """
    try:
        selected_month, all_months = get_selected_month_and_months_list(current_user.id)
        
        # Parse month
        try:
            year, month = map(int, selected_month.split('-'))
        except:
            year = datetime.now().year
            month = datetime.now().month
        
        # Get transactions for selected month
        transactions_list = Transaction.query.filter(
            Transaction.user_id == current_user.id,
            extract('year', Transaction.date) == year,
            extract('month', Transaction.date) == month
        ).order_by(Transaction.date.desc()).all()
        
        # Get all categories
        categories = Category.query.order_by(Category.name).all()
        
        return render_template('transactions.html',
                             page_name='transactions',
                             transactions=transactions_list,
                             categories=categories,
                             all_months=all_months,
                             selected_month=selected_month)
    
    except Exception as e:
        print(f"Transactions error: {e}")
        flash('Error loading transactions.', 'error')
        return render_template('transactions.html',
                             page_name='transactions',
                             transactions=[],
                             categories=Category.query.all(),
                             all_months=[datetime.now().strftime('%Y-%m')],
                             selected_month=datetime.now().strftime('%Y-%m'))


@app.route('/accounts')
@login_required
def accounts():
    """
    Accounts page - Bank management and sync
    """
    bank_linked = current_user.aa_token is not None
    
    return render_template('accounts.html',
                         page_name='accounts',
                         bank_linked=bank_linked)


# ============================================================================
# API ROUTES
# ============================================================================

@app.route('/api/spending-by-category')
@login_required
def spending_by_category():
    """
    Get spending aggregated by category for selected month
    """
    try:
        # Get month from query parameter
        selected_month = request.args.get('month')
        
        if not selected_month:
            selected_month = datetime.now().strftime('%Y-%m')
        
        # Parse month
        try:
            year, month = map(int, selected_month.split('-'))
        except:
            year = datetime.now().year
            month = datetime.now().month
        
        # Query spending by category
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
        
        # Handle uncategorized
        uncategorized = db.session.query(
            func.sum(Transaction.amount).label('total')
        ).filter(
            Transaction.user_id == current_user.id,
            Transaction.category_id == None,
            extract('month', Transaction.date) == month,
            extract('year', Transaction.date) == year
        ).scalar()
        
        # Format data
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
    """Sync transactions from bank"""
    try:
        new_transactions_data = bank_api.fetch_new_transactions(current_user)
        transactions_added = 0
        
        for tx_data in new_transactions_data:
            tx_date = datetime.strptime(tx_data['date'], '%Y-%m-%d')
            
            # Check for duplicates
            existing = Transaction.query.filter_by(
                user_id=current_user.id,
                date=tx_date,
                description=tx_data['description'],
                amount=abs(tx_data['amount'])
            ).first()
            
            if not existing:
                new_transaction = Transaction(
                    user_id=current_user.id,
                    date=tx_date,
                    description=tx_data['description'],
                    amount=abs(tx_data['amount'])
                )
                
                db.session.add(new_transaction)
                db.session.flush()
                categorize_transaction(new_transaction)
                transactions_added += 1
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'new_transactions': transactions_added,
            'message': f'Successfully synced {transactions_added} new transactions'
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
            return jsonify({
                'status': 'error',
                'message': 'Transaction not found'
            }), 404
        
        # Security check
        if transaction.user_id != current_user.id:
            return jsonify({
                'status': 'error',
                'message': 'Unauthorized'
            }), 403
        
        data = request.get_json()
        category_id = data.get('category_id')
        
        if category_id == '' or category_id == 'null':
            category_id = None
        elif category_id:
            try:
                category_id = int(category_id)
                category = Category.query.get(category_id)
                if not category:
                    return jsonify({
                        'status': 'error',
                        'message': 'Invalid category'
                    }), 400
            except ValueError:
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid category ID'
                }), 400
        
        transaction.category_id = category_id
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'transaction': transaction.to_dict()
        })
    
    except Exception as e:
        db.session.rollback()
        print(f"Categorization error: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to update category'
        }), 500


@app.route('/api/demo/generate-data', methods=['POST'])
@login_required
def generate_demo_data():
    """Generate demo transaction data"""
    try:
        Transaction.query.filter_by(user_id=current_user.id).delete()
        
        current_date = datetime.now()
        
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
                new_transaction = Transaction(
                    user_id=current_user.id,
                    date=datetime.strptime(tx_data['date'], '%Y-%m-%d'),
                    description=tx_data['description'],
                    amount=abs(tx_data['amount'])
                )
                
                db.session.add(new_transaction)
                db.session.flush()
                categorize_transaction(new_transaction)
        
        db.session.commit()
        
        total_count = Transaction.query.filter_by(user_id=current_user.id).count()
        
        return jsonify({
            'status': 'success',
            'message': f'Generated {total_count} demo transactions',
            'transactions': total_count
        })
    
    except Exception as e:
        db.session.rollback()
        print(f"Demo data error: {e}")
        return jsonify({
            'status': 'error',
            'message': 'Failed to generate demo data'
        }), 500


@app.route('/api/demo/setup')
def setup_demo():
    """Create demo user"""
    try:
        from werkzeug.security import generate_password_hash
        
        demo_user = User.query.filter_by(email=Config.DEMO_USER_EMAIL).first()
        
        if not demo_user:
            demo_user = User(
                email=Config.DEMO_USER_EMAIL,
                password_hash=generate_password_hash(
                    Config.DEMO_USER_PASSWORD,
                    method='pbkdf2:sha256'
                )
            )
            db.session.add(demo_user)
            db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Demo user created successfully',
            'email': Config.DEMO_USER_EMAIL,
            'password': Config.DEMO_USER_PASSWORD
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
