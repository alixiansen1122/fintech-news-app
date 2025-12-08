import streamlit as st
from supabase import create_client

try:
    SUPABASE_URL = st.secrets["SUPABASE_URL"]
    SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
    supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    response = supabase.table("news").select("title, category").order("created_at", desc=True).limit(10).execute()
    print("Latest News Categories:")
    for n in response.data:
        print(f"- {n['category']}: {n['title'][:30]}...")
        
except Exception as e:
    print(f"Error: {e}")
