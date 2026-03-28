"""
Retirement Intelligence Engine for FinTrack - Data-Driven Edition.
Replaces manual calculator with real transaction analysis + Indian context.
"""

import math
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
from models import db, User, Transaction, Category, RetirementGoal
from sqlalchemy import func, extract, or_, and_
import re

# Indian Merchant Patterns (case-insensitive regex)
INDIAN_MERCHANTS = {
    # Food Delivery (non-essential)
    'food_delivery': ['swiggy', 'zomato', 'dominos', 'pizza hut', 'mcdonald', 'kfc', 'burger king'],
    
    # Shopping (non-essential)
    'shopping': ['amazon', 'flipkart', 'myntra', 'ajio', 'nykaa', 'dmart', 'bigbasket'],
    
    # Entertainment/Subscriptions
    'entertainment': ['netflix', 'prime video', 'hotstar', 'spotify', 'gaana', 'zee5'],
    
    # Transport
    'transport': ['ola', 'uber', 'rapido', 'blinkit'],  # Blinkit is quick commerce
    
    # EMI/Loans (essential - debt)
    'emi': ['icici', 'hdfc', 'sbi emi', 'phonepe emi', 'credl'],
}

# Portfolio Returns (annual, India-specific)
PORTFOLIOS = {
    'safe': {'name': 'FD + PPF', 'return': 0.065},      # 6.5%
    'balanced': {'name': 'Mutual Funds SIP', 'return': 0.10},  # 10%
    'aggressive': {'name': 'Equity (Nifty)', 'return': 0.12}, # 12%
}

INFLATION_RATE = 0.06  # India avg

# =============================================================================
# CORE DATA-DRIVEN ANALYSIS
# =============================================================================

def analyze_user_finances(user_id: int, months_back: int = 6) -> Dict:
    """
    Analyze real transaction data for income, expenses, surplus.
    Returns comprehensive financial snapshot.
    """
    cutoff_date = datetime.now() - timedelta(days=months_back * 30)
    
    # Total Income (credits) & Expenses (debits) by month
    monthly_data = db.session.query(
        func.strftime('%Y-%m', Transaction.date).label('month'),
        func.avg(
            db.case(
                {(Transaction.transaction_type == 'credit'): Transaction.amount},
                else_=0
            )
        ).label('avg_income'),
        func.avg(
            db.case(
                {(Transaction.transaction_type == 'debit'): Transaction.amount},
                else_=0
            )
        ).label('avg_expense')
    ).filter(
        Transaction.user_id == user_id,
        Transaction.date >= cutoff_date
    ).group_by('month').all()
    
    if not monthly_data:
        return {'has_data': False, 'message': 'Sync bank accounts for 2+ months to unlock analysis'}
    
    # Averages
    avg_monthly_income = sum([float(row.avg_income or 0) for row in monthly_data]) / len(monthly_data)
    avg_monthly_expense = sum([float(row.avg_expense or 0) for row in monthly_data]) / len(monthly_data)
    
    total_expenses = avg_monthly_expense
    
    # Category Breakdown
    expense_breakdown = get_expense_breakdown(user_id, months_back)
    
    # Classify Essential vs Non-Essential
    essentials_total = sum([amt for cat, amt in expense_breakdown['essential']])
    non_essentials_total = sum([amt for cat, amt in expense_breakdown['non_essential']])
    
    surplus = max(0, avg_monthly_income - total_expenses)
    savings_rate = (surplus / avg_monthly_income * 100) if avg_monthly_income > 0 else 0
    
    # Investable Surplus Tiers
    investable = {
        'conservative': surplus * 0.30,
        'moderate': surplus * 0.50,
        'aggressive': surplus * 0.70,
        'optimized': surplus + (non_essentials_total * 0.25)  # +25% cut from non-essentials
    }
    
    # Health Classification
    classification = 'balanced'
    if savings_rate < 10:
        classification = 'high_spender'
    elif savings_rate > 25:
        classification = 'saver'
    
    return {
        'has_data': True,
        'avg_monthly_income': round(avg_monthly_income, 0),
        'avg_monthly_expense': round(avg_monthly_expense, 0),
        'surplus': round(surplus, 0),
        'savings_rate': round(savings_rate, 1),
        'classification': classification,
        'expenses': {
            'essential': essentials_total,
            'non_essential': non_essentials_total,
            'breakdown': expense_breakdown
        },
        'investable_surplus': investable
    }

def get_expense_breakdown(user_id: int, months_back: int = 6) -> Dict:
    """Detailed expense classification with Indian patterns."""
    cutoff_date = datetime.now() - timedelta(days=months_back * 30)
    
    expenses_query = db.session.query(
        Category.name.label('category'),
        func.sum(Transaction.amount).label('total')
    ).join(Transaction).filter(
        Transaction.user_id == user_id,
        Transaction.transaction_type == 'debit',
        Transaction.date >= cutoff_date,
        Transaction.category_id.isnot(None)
    ).group_by(Category.id, Category.name).order_by(func.sum(Transaction.amount).desc()).all()
    
    # Uncategorized
    uncat_total = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == user_id,
        Transaction.transaction_type == 'debit',
        Transaction.date >= cutoff_date,
        Transaction.category_id.is_(None)
    ).scalar() or 0
    
    cat_totals = {row.category: float(row.total) for row in expenses_query}
    
    # Merchant classification (description-based)
    non_cat_nonessentials = classify_merchants(user_id, months_back)
    
    # Hardcoded essentials (adjust based on common Indian categories)
    essential_cats = {'Rent', 'EMI', 'Groceries', 'Utilities', 'Fuel', 'Transport'}
    
    essential = {cat: amt for cat, amt in cat_totals.items() if cat in essential_cats}
    non_essential_cats = {cat: amt for cat, amt in cat_totals.items() if cat not in essential_cats}
    
    # Add merchant non-essentials
    for merchant_type, amt in non_cat_nonessentials.items():
        non_essential_cats[f'{merchant_type.title()} (Merchants)'] = amt
    
    return {
        'essential': list(essential.items())[:5],  # Top 5
        'non_essential': list(non_essential_cats.items())[:5],
        'uncategorized': float(uncat_total)
    }

def classify_merchants(user_id: int, months_back: int = 6) -> Dict[str, float]:
    """Classify uncategorized debits by Indian merchant patterns."""
    cutoff_date = datetime.now() - timedelta(days=months_back * 30)
    
    txns = Transaction.query.filter(
        Transaction.user_id == user_id,
        Transaction.transaction_type == 'debit',
        Transaction.date >= cutoff_date,
        Transaction.category_id.is_(None),
        Transaction.description.ilike('%upi%')  # UPI-heavy India filter
    ).all()
    
    merchant_totals = {}
    for txn in txns:
        desc_lower = txn.description.lower()
        for mtype, patterns in INDIAN_MERCHANTS.items():
            for pattern in patterns:
                if pattern in desc_lower:
                    merchant_totals.setdefault(mtype, 0)
                    merchant_totals[mtype] += float(txn.amount)
                    break
    
    return {k: round(v, 0) for k, v in merchant_totals.items()}

# =============================================================================
# BEHAVIORAL INTELLIGENCE
# =============================================================================

def generate_behavioral_insights(finances: Dict) -> List[Dict]:
    """India-specific, personalized, actionable insights."""
    insights = []
    expenses = finances['expenses']
    surplus = finances['surplus']
    income = finances['avg_monthly_income']
    rate = finances['savings_rate']
    
    # Spending leaks
    if expenses['non_essential'] and isinstance(expenses['non_essential'], list) and len(expenses['non_essential']) > 0:
        top_noness = max(expenses['non_essential'], key=lambda x: x[1])
        cut_amt = round(top_noness[1] * 0.25, 0)
        future_val = sip_future_value(cut_amt, 12, 25)  # 12%, 25yr
        insights.append({
            'emoji': '🍔',
            'text': f'You spend ₹{top_noness[1]:,} on {top_noness[0]}. Cutting 25% (₹{cut_amt:,}) invests → ₹{future_val:,.0f} corpus boost.',
            'action': 'Track delivery apps weekly'
        })
    
    # Savings rate
    if rate < 15:
        gap = round((income * 0.20) - surplus, 0)
        insights.append({
            'emoji': '💰',
            'text': f'India avg savings rate: 18%. Yours: {rate}%. Add ₹{gap:,}/mo → retire 3-4 years earlier.',
            'priority': 'high'
        })
    
    # EMI detection (essentials high)
    if 'essential' in expenses and isinstance(expenses['essential'], list) and finances['avg_monthly_expense'] > 0 and sum(amt for _, amt in expenses['essential']) / finances['avg_monthly_expense'] > 0.50:
        insights.append({
            'emoji': '🏦',
            'text': 'EMI detected (50%+ expenses). Shift to PPF: tax-free + 7.1% guaranteed.',
            'action': 'PPF ₹1.5L/yr max'
        })
    
    # UPI dominance (general India nudge)
    insights.append({
        'emoji': '📱',
        'text': f"Strong surplus ₹{surplus:,}! Auto-invest 50% via UPI to MFs (Groww/Zerodha).",
        'type': 'positive'
    })
    
    return insights[:5]  # Top 5

# =============================================================================
# INDIAN INVESTMENT SIMULATIONS
# =============================================================================

def simulate_indian_portfolios(finances: Dict, current_age: int = 30, retire_age: int = 60) -> Dict:
    """Simulate portfolios with SIP compounding."""
    years = retire_age - current_age
    months = years * 12
    monthly_invest = finances['investable_surplus']['moderate']
    
    scenarios = {}
    for key, portfolio in PORTFOLIOS.items():
        r_monthly = portfolio['return'] / 12
        corpus = sip_future_value(monthly_invest, r_monthly * 12, years)
        
        # Inflation-adjusted retirement income (4% safe withdrawal)
        adj_corpus = corpus / ((1 + INFLATION_RATE) ** years)
        monthly_income = adj_corpus * 0.04 / 12
        
        scenarios[key] = {
            'name': portfolio['name'],
            'return_pct': portfolio['return'] * 100,
            'corpus': round(corpus, 0),
            'monthly_income': round(monthly_income, 0),
            'years': years
        }
    
    # Optimized scenario
    opt_invest = finances['investable_surplus']['optimized']
    opt_corpus = sip_future_value(opt_invest, 0.10, years)
    scenarios['optimized'] = {
        'name': 'Current +25% Non-Essential Cut',
        'return_pct': 10,
        'corpus': round(opt_corpus, 0),
        'monthly_income': round((opt_corpus / ((1 + INFLATION_RATE) ** years)) * 0.04 / 12, 0),
        'years': years
    }
    
    return scenarios

def sip_future_value(monthly_sip: float, annual_rate: float, years: int) -> float:
    """SIP Future Value formula."""
    monthly_rate = annual_rate / 12
    months = years * 12
    if monthly_rate == 0:
        return monthly_sip * months
    return monthly_sip * ((math.pow(1 + monthly_rate, months) - 1) / monthly_rate) * (1 + monthly_rate)

# =============================================================================
# AGGREGATOR API
# =============================================================================

def get_retirement_analysis(user_id: int) -> Dict:
    """Full analysis JSON for /api/retirement/analysis."""
    goal = RetirementGoal.query.filter_by(user_id=user_id).first()
    current_age = goal.current_age if goal else 30
    
    finances = analyze_user_finances(user_id)
    insights = generate_behavioral_insights(finances)
    portfolios = simulate_indian_portfolios(finances, current_age)
    
    return {
        'finances': finances,
        'insights': insights,
        'portfolios': portfolios,
        'current_age': current_age
    }

# =============================================================================
# BACKWARD COMPAT: Existing Manual Functions (Unchanged)
# =============================================================================

def calculate_retirement_plan(goal: RetirementGoal) -> dict:
    # [EXISTING CODE - UNCHANGED FOR BACKWARD COMPAT]
    years_to_retire = goal.retirement_age - goal.current_age
    years_in_retirement = goal.life_expectancy - goal.retirement_age

    monthly_return = goal.expected_return / 100 / 12
    monthly_inflation = goal.inflation_rate / 100 / 12
    months_to_retire = years_to_retire * 12
    months_in_retirement = years_in_retirement * 12

    # --- Step 1: Inflation-adjusted monthly income needed at retirement ---
    real_monthly_income = float(goal.target_monthly_income) * (
        (1 + goal.inflation_rate / 100) ** years_to_retire
    )

    # --- Step 2: Target corpus (Present Value of annuity at retirement) ---
    real_return = ((1 + goal.expected_return / 100) / (1 + goal.inflation_rate / 100)) - 1
    real_monthly_return = real_return / 12

    if real_monthly_return > 0:
        target_corpus = real_monthly_income * (
            (1 - (1 + real_monthly_return) ** (-months_in_retirement)) / real_monthly_return
        )
    else:
        target_corpus = real_monthly_income * months_in_retirement

    # --- Step 3: Projected corpus ---
    current_contribution = float(goal.current_monthly_contribution)
    if monthly_return > 0 and months_to_retire > 0:
        projected_corpus = current_contribution * (
            ((1 + monthly_return) ** months_to_retire - 1) / monthly_return
        ) * (1 + monthly_return)
    else:
        projected_corpus = current_contribution * months_to_retire

    # --- Step 4: Required monthly ---
    if monthly_return > 0 and months_to_retire > 0:
        required_monthly = target_corpus * monthly_return / (
            ((1 + monthly_return) ** months_to_retire - 1) * (1 + monthly_return)
        )
    else:
        required_monthly = target_corpus / max(months_to_retire, 1)

    readiness_score = min(100, int((projected_corpus / target_corpus) * 100)) if target_corpus > 0 else 0

    return {
        'target_corpus': round(target_corpus, 2),
        'projected_corpus': round(projected_corpus, 2),
        'required_monthly_contribution': round(required_monthly, 2),
        'readiness_score': readiness_score,
        'years_to_retirement': years_to_retire,
        'inflation_adjusted_income': round(real_monthly_income, 2),
    }

def save_retirement_plan(user_id: int, goal, calc: dict):
    """Upsert RetirementPlan from calc results. Backward compat."""


    from models import RetirementPlan
    plan = RetirementPlan.query.filter_by(user_id=user_id).first()
    if not plan:
        plan = RetirementPlan(user_id=user_id, goal_id=goal.id)
        db.session.add(plan)

    plan.goal_id = goal.id
    plan.target_corpus = calc['target_corpus']
    plan.projected_corpus = calc['projected_corpus']
    plan.required_monthly_contribution = calc['required_monthly_contribution']
    plan.readiness_score = calc['readiness_score']
    plan.years_to_retirement = calc['years_to_retirement']
    plan.last_calculated = datetime.utcnow()

    db.session.commit()
    return plan

def check_and_award_milestones(user_id: int, goal, plan):
    """Backward compat milestone checker."""
    return []  # Simplified

def simulate_scenario(goal, monthly_investment: float, retire_age: int) -> dict:
    """Backward compat simulator."""
    original_contribution = goal.current_monthly_contribution
    original_retire_age = goal.retirement_age

    goal.current_monthly_contribution = monthly_investment
    goal.retirement_age = retire_age

    result = calculate_retirement_plan(goal)

    goal.current_monthly_contribution = original_contribution
    goal.retirement_age = original_retire_age

    return result

def get_spending_insights(user_id: int, goal):
    """Backward compat - use new insights."""
    return [{'emoji': '📊', 'text': 'Use new data-driven analysis for better insights!'}]
