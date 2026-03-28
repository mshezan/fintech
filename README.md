# FinTrack - Personal Finance Manager

A web-based personal finance application designed specifically for users in India, featuring simulated bank integration, automatic transaction categorization, and spending insights.

## 🚀 Features

- **User Authentication** - Secure registration and login system
- **Simulated Bank Integration** - Demo banking environment (no real bank data)
- **Transaction Management** - View and organize all your transactions
- **Automatic Categorization** - AI-powered categorization for Indian vendors
- **Spending Insights** - Visual charts showing monthly spending by category
- **Manual Categorization** - Easily change transaction categories
- **Demo Data Generation** - Generate 3 months of realistic transaction data

## 📋 Prerequisites
- Python 3.8 or higher
- pip (Python package manager)
- Web browser (Chrome, Firefox, Safari, or Edge)

## 🛠️ Installation & Setup

### Step 1: Install Dependencies
```
pip install -r requirements.txt
```

### Step 2: Run Flask App
```
python run.py
```
Open http://localhost:5000

### Step 3: Run Bank API Server (in new terminal)
```
python bank_server.py
```

## 🎯 ML Fraud Detection (Standalone)

ML scripts organized in `ml/` folder:

```
cd ml
python fraud_detection_local.py
```

**Note**: Install ML deps separately:
```
cd ml
pip install pandas scikit-learn imbalanced-learn matplotlib seaborn
```

Generates visualizations + model_comparison.csv in `ml/data/`.

## Project Structure (Organized)
```
fintech/
├── app.py (Flask web app)
├── ml/              ← Fraud detection scripts + data
│   ├── fraud_detection_local.py
│   ├── data/
│   │   ├── transactions_dataset.csv
│   │   └── *.png
├── templates/
├── static/
└── requirements.txt
```

Enjoy tracking your finances + fraud detection!

