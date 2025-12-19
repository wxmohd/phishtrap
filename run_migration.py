#!/usr/bin/env python3
"""
Run database migration to add link intelligence columns
"""

import os
from sqlalchemy import text
from database.models import ENGINE

def run_migration():
    """Execute the SQL migration file."""
    migration_file = 'migrations/add_link_intelligence.sql'
    
    if not os.path.exists(migration_file):
        print(f"❌ Migration file not found: {migration_file}")
        return False
    
    print("🔄 Running database migration...")
    print(f"   File: {migration_file}")
    
    try:
        # Read migration SQL
        with open(migration_file, 'r') as f:
            sql = f.read()
        
        # Execute migration
        with ENGINE.connect() as conn:
            # Split by semicolon and execute each statement
            statements = [s.strip() for s in sql.split(';') if s.strip()]
            
            for i, statement in enumerate(statements, 1):
                if statement and not statement.strip().startswith('--'):
                    print(f"   Executing statement {i}/{len(statements)}...")
                    conn.execute(text(statement))
                    conn.commit()
        
        print("✅ Migration completed successfully!")
        print("\n📊 New link intelligence features:")
        print("   • Risk scoring (0-100)")
        print("   • Brand impersonation detection")
        print("   • Sandbox analysis (credential harvest, file downloads)")
        print("   • Geolocation tracking")
        print("   • Campaign correlation")
        print("   • Automated link visiting")
        
        return True
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        return False

if __name__ == "__main__":
    success = run_migration()
    exit(0 if success else 1)
