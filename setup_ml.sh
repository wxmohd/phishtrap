#!/bin/bash

echo "======================================================================"
echo "🤖 PhishTrap ML Setup"
echo "======================================================================"

# Activate virtual environment
echo ""
echo "📦 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "📥 Installing ML dependencies..."
pip install kagglehub pandas scikit-learn joblib -q

# Train model
echo ""
echo "🚀 Training ML model..."
python -m ai.train_model

echo ""
echo "======================================================================"
echo "✅ ML Setup Complete!"
echo "======================================================================"
echo ""
echo "Next steps:"
echo "  1. Start PhishTrap: python main.py"
echo "  2. Look for: [AI_CLASSIFIER] ✓ ML model loaded successfully"
echo ""
