# ai/train_model.py
import os
import pandas as pd
import joblib
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, accuracy_score

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "model.pkl")
VECTORIZER_PATH = os.path.join(BASE_DIR, "vectorizer.pkl")


def load_kaggle_dataset():
    """Load phishing email dataset from Kaggle."""
    print("[AI] Downloading dataset from Kaggle...")
    
    try:
        import kagglehub
        
        # Download dataset
        path = kagglehub.dataset_download("naserabdullahalam/phishing-email-dataset")
        print(f"[AI] Dataset downloaded to: {path}")
        
        # Find CSV file in downloaded path
        csv_files = []
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith('.csv'):
                    csv_files.append(os.path.join(root, file))
        
        if not csv_files:
            raise FileNotFoundError("No CSV file found in dataset")
        
        # Load the first CSV file
        df = pd.read_csv(csv_files[0])
        print(f"[AI] Loaded dataset with {len(df)} rows")
        print(f"[AI] Columns: {df.columns.tolist()}")
        
        return df
        
    except ImportError:
        print("[AI] ERROR: kagglehub not installed. Install with: pip install kagglehub")
        raise
    except Exception as e:
        print(f"[AI] ERROR loading dataset: {e}")
        raise


def prepare_dataset(df):
    """Prepare dataset for training."""
    print("[AI] Preparing dataset...")
    
    # Try to identify text and label columns
    # Common column names for phishing datasets
    text_cols = ['text', 'email', 'message', 'body', 'content', 'Email Text']
    label_cols = ['label', 'class', 'type', 'Email Type']
    
    text_col = None
    label_col = None
    
    # Find text column
    for col in df.columns:
        if col.lower() in [c.lower() for c in text_cols]:
            text_col = col
            break
    
    # Find label column
    for col in df.columns:
        if col.lower() in [c.lower() for c in label_cols]:
            label_col = col
            break
    
    if text_col is None or label_col is None:
        print(f"[AI] Available columns: {df.columns.tolist()}")
        # Use first two columns as fallback
        text_col = df.columns[0]
        label_col = df.columns[1]
        print(f"[AI] Using columns: text='{text_col}', label='{label_col}'")
    
    # Extract text and labels
    texts = df[text_col].astype(str).tolist()
    labels = df[label_col].astype(str).tolist()
    
    # Normalize labels to 'phishing' and 'legit'
    normalized_labels = []
    for label in labels:
        label_lower = str(label).lower()
        if 'phish' in label_lower or 'spam' in label_lower or label_lower in ['1', 'true']:
            normalized_labels.append('phishing')
        else:
            normalized_labels.append('legit')
    
    print(f"[AI] Dataset prepared:")
    print(f"     - Total samples: {len(texts)}")
    print(f"     - Phishing: {normalized_labels.count('phishing')}")
    print(f"     - Legitimate: {normalized_labels.count('legit')}")
    
    return texts, normalized_labels


def main():
    print("="*70)
    print("🤖 PhishTrap ML Model Training")
    print("="*70)
    
    # Load dataset
    df = load_kaggle_dataset()
    
    # Prepare data
    texts, labels = prepare_dataset(df)
    
    # Split data
    print("\n[AI] Splitting dataset (80% train, 20% test)...")
    X_train, X_test, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=42, stratify=labels
    )
    
    print(f"     - Training samples: {len(X_train)}")
    print(f"     - Test samples: {len(X_test)}")
    
    # Build pipeline
    print("\n[AI] Building ML pipeline...")
    print("     - Vectorizer: TF-IDF (1-2 grams)")
    print("     - Classifier: Logistic Regression")
    
    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(
            stop_words="english",
            ngram_range=(1, 2),
            max_features=5000,
            min_df=2
        )),
        ("clf", LogisticRegression(
            max_iter=1000,
            random_state=42,
            class_weight='balanced'
        )),
    ])
    
    # Train model
    print("\n[AI] Training model...")
    pipeline.fit(X_train, y_train)
    
    # Evaluate
    print("\n[AI] Evaluating model...")
    y_pred = pipeline.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    
    print(f"\n✅ Model trained successfully!")
    print(f"   Accuracy: {accuracy*100:.2f}%")
    print("\nClassification Report:")
    print(classification_report(y_test, y_pred))
    
    # Save model
    joblib.dump(pipeline, MODEL_PATH)
    print(f"\n💾 Model saved to: {MODEL_PATH}")
    print(f"   Model size: {os.path.getsize(MODEL_PATH) / 1024:.2f} KB")
    
    print("\n" + "="*70)
    print("✅ Training complete! Model ready for use.")
    print("="*70)


if __name__ == "__main__":
    main()
