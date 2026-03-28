"""
LOCAL FRAUD DETECTION - Works on Windows CPU
Uses YOUR fintech transaction data
No GPU, No Cloud, No BS!
"""

import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.metrics import (
    f1_score, precision_score, recall_score, 
    roc_auc_score, confusion_matrix, 
    classification_report
)
from imblearn.over_sampling import SMOTE
import warnings
warnings.filterwarnings('ignore')

# Set random seed
np.random.seed(42)

print("="*80)
print("FRAUD DETECTION - LOCAL VERSION")
print("Using Your Fintech Transaction Data")
print("="*80)

# ============================================================================
# STEP 1: LOAD YOUR DATA
# ============================================================================

def load_transaction_data(csv_file='transactions_dataset.csv'):
    """
    Load transactions from CSV (exported from your fintech DB)
    """
    print(f"\n[STEP 1] LOADING DATA FROM: {csv_file}")
    print("-" * 80)

    try:
        df = pd.read_csv(csv_file)
        print(f"✓ Loaded {len(df)} transactions")
    except FileNotFoundError:
        print(f"❌ File not found: {csv_file}")
        print("\nRun this first: python export_transactions.py")
        return None

    # Check required columns
    required = ['amount', 'is_fraud']
    if not all(col in df.columns for col in required):
        print(f"❌ Missing required columns: {required}")
        return None

    # Show data info
    print(f"\n✓ Dataset info:")
    print(f"  - Columns: {list(df.columns)}")
    print(f"  - Date range: {df['date'].min()} to {df['date'].max()}")
    print(f"  - Legitimate: {(df['is_fraud'] == 0).sum()}")
    print(f"  - Fraudulent: {(df['is_fraud'] == 1).sum()}")
    fraud_pct = (df['is_fraud'] == 1).sum() / len(df) * 100
    print(f"  - Fraud ratio: {fraud_pct:.2f}%")

    return df

# ============================================================================
# STEP 2: FEATURE ENGINEERING
# ============================================================================

def create_features(df):
    """
    Extract features from transaction data
    Your fintech data -> ML features
    """
    print(f"\n[STEP 2] FEATURE ENGINEERING")
    print("-" * 80)

    # Numeric features
    features = pd.DataFrame()
    features['amount'] = df['amount']

    # Encode categorical features
    le_mode = LabelEncoder()
    le_category = LabelEncoder()

    features['mode_encoded'] = le_mode.fit_transform(df['mode'].fillna('Unknown'))
    features['category_encoded'] = le_category.fit_transform(df['category'].fillna('Uncategorized'))

    # Transaction type (debit=0, credit=1)
    features['is_credit'] = (df['type'] == 'credit').astype(int)

    # Amount-based features
    features['amount_log'] = np.log1p(features['amount'])
    features['amount_squared'] = features['amount'] ** 2

    # Time-based features (if date available)
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        features['day_of_week'] = df['date'].dt.dayofweek
        features['hour'] = df['date'].dt.hour if df['date'].dt.hour.notna().any() else 0

    # Target
    y = df['is_fraud'].values

    print(f"✓ Created {features.shape[1]} features:")
    print(f"  {list(features.columns)}")

    return features, y

# ============================================================================
# STEP 3: TRAIN MODELS
# ============================================================================

def train_models(X_train, X_test, y_train, y_test):
    """
    Train baseline models (CPU-friendly, fast)
    """
    print(f"\n[STEP 3] TRAINING MODELS (CPU MODE)")
    print("-" * 80)

    results = {}

    # Model 1: Logistic Regression
    print("\n1. Logistic Regression...")
    lr = LogisticRegression(max_iter=1000, random_state=42)
    lr.fit(X_train, y_train)
    y_pred_lr = lr.predict(X_test)
    y_proba_lr = lr.predict_proba(X_test)[:, 1]

    print(f"   F1-Score: {f1_score(y_test, y_pred_lr):.4f}")
    results['Logistic Regression'] = {
        'model': lr,
        'y_pred': y_pred_lr,
        'y_proba': y_proba_lr
    }

    # Model 2: Random Forest (CPU-friendly with small n_estimators)
    print("\n2. Random Forest...")
    rf = RandomForestClassifier(
        n_estimators=50,  # Smaller for CPU speed
        max_depth=10,
        random_state=42,
        n_jobs=-1  # Use all CPU cores
    )
    rf.fit(X_train, y_train)
    y_pred_rf = rf.predict(X_test)
    y_proba_rf = rf.predict_proba(X_test)[:, 1]

    print(f"   F1-Score: {f1_score(y_test, y_pred_rf):.4f}")
    results['Random Forest'] = {
        'model': rf,
        'y_pred': y_pred_rf,
        'y_proba': y_proba_rf
    }

    # Model 3: Isolation Forest (No balancing needed!)
    print("\n3. Isolation Forest (Anomaly Detection)...")
    iso = IsolationForest(contamination=0.02, random_state=42, n_jobs=-1)
    iso.fit(X_train)
    y_pred_iso_raw = iso.predict(X_test)
    y_pred_iso = np.where(y_pred_iso_raw == -1, 1, 0)  # -1 = anomaly = fraud

    # Score for probability-like values
    y_proba_iso = np.maximum(0, -iso.score_samples(X_test))
    y_proba_iso = (y_proba_iso - y_proba_iso.min()) / (y_proba_iso.max() - y_proba_iso.min())

    print(f"   F1-Score: {f1_score(y_test, y_pred_iso):.4f}")
    results['Isolation Forest'] = {
        'model': iso,
        'y_pred': y_pred_iso,
        'y_proba': y_proba_iso
    }

    return results

# ============================================================================
# STEP 4: EVALUATION
# ============================================================================

def evaluate_models(results, y_test):
    """
    Compare all models
    """
    print(f"\n[STEP 4] EVALUATION RESULTS")
    print("=" * 80)

    comparison = []

    for model_name, result in results.items():
        y_pred = result['y_pred']
        y_proba = result['y_proba']

        metrics = {
            'Model': model_name,
            'Precision': precision_score(y_test, y_pred, zero_division=0),
            'Recall': recall_score(y_test, y_pred, zero_division=0),
            'F1-Score': f1_score(y_test, y_pred, zero_division=0),
            'AUC-ROC': roc_auc_score(y_test, y_proba)
        }

        comparison.append(metrics)

    comparison_df = pd.DataFrame(comparison)
    print(comparison_df.to_string(index=False))

    return comparison_df

# ============================================================================
# STEP 5: VISUALIZE
# ============================================================================

def plot_confusion_matrices(results, y_test):
    """
    Show confusion matrices
    """
    fig, axes = plt.subplots(1, 3, figsize=(15, 4))
    fig.suptitle('Confusion Matrices', fontsize=14, fontweight='bold')

    for idx, (model_name, result) in enumerate(results.items()):
        y_pred = result['y_pred']
        cm = confusion_matrix(y_test, y_pred)

        sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', ax=axes[idx],
                   xticklabels=['Legitimate', 'Fraud'],
                   yticklabels=['Legitimate', 'Fraud'])
        axes[idx].set_title(model_name)
        axes[idx].set_ylabel('True')
        axes[idx].set_xlabel('Predicted')

    plt.tight_layout()
    plt.savefig('confusion_matrices.png', dpi=150, bbox_inches='tight')
    print(f"\n✓ Saved: confusion_matrices.png")
    plt.show()

def plot_feature_importance(rf_model, feature_names):
    """
    Show which features matter most
    """
    importances = rf_model.feature_importances_
    indices = np.argsort(importances)[::-1]

    plt.figure(figsize=(10, 6))
    plt.title('Feature Importance (Random Forest)', fontsize=14, fontweight='bold')
    plt.bar(range(len(importances)), importances[indices])
    plt.xticks(range(len(importances)), [feature_names[i] for i in indices], rotation=45, ha='right')
    plt.xlabel('Features')
    plt.ylabel('Importance')
    plt.tight_layout()
    plt.savefig('feature_importance.png', dpi=150, bbox_inches='tight')
    print(f"✓ Saved: feature_importance.png")
    plt.show()

# ============================================================================
# MAIN EXECUTION
# ============================================================================

if __name__ == '__main__':

    # Step 1: Load data
    df = load_transaction_data('transactions_dataset.csv')
    if df is None:
        print("\n⚠ Trying synthetic dataset...")
        df = load_transaction_data('synthetic_transactions.csv')
        if df is None:
            print("\n❌ No data found. Run: python export_transactions.py")
            exit(1)

    # Step 2: Feature engineering
    X, y = create_features(df)

    # Step 3: Split data (80-20, stratified)
    print(f"\n[SPLITTING DATA] 80% train, 20% test")
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    print(f"✓ Train: {X_train_scaled.shape[0]} samples")
    print(f"✓ Test: {X_test_scaled.shape[0]} samples")

    # Step 4: Train models
    results = train_models(X_train_scaled, X_test_scaled, y_train, y_test)

    # Step 5: Evaluate
    comparison_df = evaluate_models(results, y_test)

    # Save results
    comparison_df.to_csv('model_comparison.csv', index=False)
    print(f"\n✓ Saved: model_comparison.csv")

    # Step 6: Visualize
    print(f"\n[STEP 5] CREATING VISUALIZATIONS")
    print("-" * 80)
    plot_confusion_matrices(results, y_test)

    # Feature importance
    rf_model = results['Random Forest']['model']
    plot_feature_importance(rf_model, X.columns)

    print("\n" + "="*80)
    print("✅ COMPLETE! Check the PNG files for visualizations")
    print("="*80)

    # Next steps
    print("\nNEXT STEPS:")
    print("1. Check confusion_matrices.png - Shows model performance")
    print("2. Check feature_importance.png - Shows what matters")
    print("3. Check model_comparison.csv - Numerical results")
    print("\nFor better results, try SMOTE balancing:")
    print("  - Run: python fraud_detection_smote.py")
