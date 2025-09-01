from typing import Optional, List, Dict
from datetime import datetime
import hashlib
import pandas as pd
from pymongo import MongoClient
import logging
import os

from pymongo import MongoClient
from urllib.parse import quote_plus
# Raw credentials
username = "doctor-appointment-assistant-server"
password = "Azentyk@123"   # your real primary password

# Escape special characters in password
username_escaped = quote_plus(username)
password_escaped = quote_plus(password)

# Build URI
uri = f"mongodb://{username_escaped}:{password_escaped}@doctor-appointment-assistant-server.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&retrywrites=false&maxIdleTimeMS=120000&appName=@doctor-appointment-assistant-server@"

# Create client
client = MongoClient(uri)

# Initialize MongoDB client with TLS
# client = MongoClient("mongodb://doctor-appointment-assistant-server:0TliSJPl3CaL1ZFGGWbiJX6P2y0ZdpVDWKnFOTa6GVF5Mqau4MEdlz79gA2Bt95VhUFRcfcUygcgACDbGV9yLA==@doctor-appointment-assistant-server.mongo.cosmos.azure.com:10255/patient_db?ssl=true&replicaSet=globaldb&retrywrites=false&maxIdleTimeMS=120000&appName=@doctor-appointment-assistant-server@",tls=True, tlsAllowInvalidCertificates=False)
db = client["patient_db"]

# Collections
patient_information_details_table_collection = db["patient_information_details_table"]
patient_chat_table_collection = db["patient_chat_table"]
chat_collection = db["patient_each_chat_table"]
patient_credentials_collection = db["patient_credentials"]

logger = logging.getLogger(__name__)

def init_db():
    """Initialize database collections if they don't exist"""
    pass

def hash_password(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()

def load_users_df() -> pd.DataFrame:
    """Load users from MongoDB and return as DataFrame"""
    try:
        cursor = patient_credentials_collection.find({})
        users_data = list(cursor)
        
        df = pd.DataFrame(users_data)
        
        if '_id' in df.columns:
            df.drop('_id', axis=1, inplace=True)
            
        expected_columns = ["firstname", "email", "phone", "country", "state", "location", "city", "password"]
        for col in expected_columns:
            if col not in df.columns:
                df[col] = None
                
        logger.info(f"Successfully loaded {len(df)} users from MongoDB")
        return df
    
    except Exception as e:
        logger.error(f"Error loading users from MongoDB: {str(e)}")
        return pd.DataFrame(columns=["firstname", "email", "phone", "country", "state", "location", "city", "password"])

def authenticate_user(email: str, password: str) -> bool:
    """Return True if email/password match a document in MongoDB."""
    try:
        hashed = hash_password(password)
        user = patient_credentials_collection.find_one({"email": email, "password": hashed})
        logger.info(f"Authentication attempt for {email}: {'success' if user else 'failed'}")
        return user is not None
    except Exception as e:
        logger.error(f"Authentication error for {email}: {e}")
        return False

def register_user(firstname: str, email: str, phone: str, country: str,
                 state: str, location: str, city: str, password: str) -> Optional[str]:
    """Register a new user in the database"""
    try:
        if patient_credentials_collection.find_one({"email": email}):
            return "Email already registered."
        if patient_credentials_collection.find_one({"phone": phone}):
            return "Phone number already registered."

        hashed = hash_password(password)
        now = datetime.now()

        user_document = {
            "firstname": firstname,
            "email": email,
            "phone": phone,
            "country": country,
            "state": state,
            "location": location,
            "city": city,
            "password": hashed,
            "created_at": str(now)
        }

        patient_credentials_collection.insert_one(user_document)
        logger.info(f"New user registered: {email}")
        return None
    except Exception as e:
        logger.error(f"Registration error for {email}: {e}")
        return "Registration failed. Please try again."

def get_user_contact_info(email: str) -> List[Dict[str, str]]:
    """Get user contact information by email"""
    try:
        df = load_users_df()
        ele_user_id = df[df['email'] == email]
        contact_info = ele_user_id[["firstname", "email", "phone"]]
        return contact_info.to_dict(orient="records")
    except Exception as e:
        logger.error(f"Error getting contact info for {email}: {e}")
        return []

def push_patient_information_data_to_db(patient_data: dict):
    """Insert patient information into database"""
    try:
        now = datetime.now()
        patient_data['date'] = now.strftime("%Y-%m-%d")
        patient_data['time'] = now.strftime("%H:%M:%S")

        insert_result = patient_information_details_table_collection.insert_one(patient_data)
        return insert_result
    except Exception as e:
        logger.error(f"Error inserting patient information: {e}")
        return None

def push_patient_chat_data_to_db(patient_data: dict):
    """Insert patient chat data into database"""
    try:
        now = datetime.now()
        patient_data['date'] = now.strftime("%Y-%m-%d")
        patient_data['time'] = now.strftime("%H:%M:%S")

        insert_result = patient_chat_table_collection.insert_one(patient_data)
        return insert_result
    except Exception as e:
        logger.error(f"Error inserting patient chat data: {e}")
        return None

def push_patient_each_chat_message(message_text: str):
    """Insert individual chat message into database"""
    try:
        now = datetime.now()
        patient_data = {
            'date': now.strftime("%Y-%m-%d"),
            'time': now.strftime("%H:%M:%S"),
            'message': message_text.strip()
        }
        insert_result = chat_collection.insert_one(patient_data)
        return insert_result
    except Exception as e:
        logger.error(f"Error inserting chat message: {e}")
        return None


def patient_each_chat_table_collection(message_text: str):
    """Insert individual chat message into database"""
    try:
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M:%S")

        patient_data = {
            'date': current_date,
            'time': current_time,
            'message': message_text.strip()
        }

        insert_result = chat_collection.insert_one(patient_data)
        logger.info(f"Inserted Patient Chat Data ID: {insert_result.inserted_id}")
        return insert_result
    except Exception as e:
        logger.error(f"Error inserting chat message: {e}")
        return None
