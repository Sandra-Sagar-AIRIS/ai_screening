import sys, os
sys.path.insert(0, 'c:/Users/Aravind/Desktop/AIRIS_Project/AIRIS/backend')
os.chdir('c:/Users/Aravind/Desktop/AIRIS_Project/AIRIS/backend')
from dotenv import load_dotenv; load_dotenv()

from sqlalchemy import create_engine, text
engine = create_engine(os.environ['DATABASE_URL'])
with engine.connect() as conn:
    # Check candidate org_id and workspace_id
    result = conn.execute(text("SELECT id, org_id, workspace_id FROM candidates LIMIT 5"))
    for row in result.fetchall():
        print(f"Candidate {row[0]}: org_id={row[1]} workspace_id={row[2]}")
    
    # Check org ids
    r3 = conn.execute(text("SELECT id FROM organizations LIMIT 3"))
    for org in r3.fetchall():
        print("Org:", org[0])

    # Check profiles (users) to see what org_id they belong to
    r4 = conn.execute(text("SELECT id, organization_id FROM profiles LIMIT 5"))
    for p in r4.fetchall():
        print(f"Profile {p[0]}: org_id={p[1]}")
