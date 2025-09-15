from typing import Optional, List, Dict
from datetime import datetime
import hashlib
import pandas as pd
from pymongo import MongoClient
import logging
import os
import certifi
from pymongo.server_api import ServerApi

from urllib.parse import quote_plus

# --- Optional: example of building a connection string with escaped credentials ---
# username = "doctor-appointment-assistant-server"
# password = "Azentyk@123"   # your real primary password
# username_escaped = quote_plus(username)
# password_escaped = quote_plus(password)
# uri = f"mongodb://{username_escaped}:{password_escaped}@doctor-appointment-assistant-server.mongo.cosmos.azure.com:10255/?ssl=true&replicaSet=globaldb&retrywrites=false&maxIdleTimeMS=120000&appName=@doctor-appointment-assistant-server@"
# client = MongoClient(uri, tls=True, tlsAllowInvalidCertificates=False)

# Initialize MongoDB client with TLS
# client = MongoClient("mongodb://doctor-appointment-assistant-server:r05e2ZWM4DJrMGfEE02D8oJDFdhXp9ZCi57AqAECn4mval7SKosxhqVCVO80dtCu2Tkfr84ML0AyACDbykAtSw==@doctor-appointment-assistant-server.mongo.cosmos.azure.com:10255/?ssl=true&retrywrites=false&replicaSet=globaldb&maxIdleTimeMS=120000&appName=@doctor-appointment-assistant-server@",tls=True, tlsAllowInvalidCertificates=False)
client = MongoClient("mongodb+srv://azentyk:azentyk123@cluster0.b9aaq47.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0",server_api=ServerApi('1'))
db = client["patient_db"]
# Collections
patient_information_details_table_collection = db["patient_information_details_table"]
patient_chat_table_collection = db["patient_chat_table"]
chat_collection = db["patient_each_chat_table"]
patient_credentials_collection = db["patient_credentials"]

logger = logging.getLogger(__name__)


def init_db():
    """Initialize database collections if they don't exist.

    Note: MongoDB creates collections on first insert; this function is a placeholder
    if you want to create indexes or perform initial setup.
    """
    try:
        # Example: ensure an index on email for fast lookups and uniqueness
        patient_credentials_collection.create_index("email", unique=True)
        patient_credentials_collection.create_index("phone", unique=True, sparse=True)
        logger.info("Database indexes ensured (email, phone)")
    except Exception as e:
        logger.exception(f"init_db: failed to ensure indexes: {e}")


def hash_password(password: str) -> str:
    """Hash password using SHA256"""
    return hashlib.sha256(password.encode()).hexdigest()


def load_users_df() -> pd.DataFrame:
    """Load users from MongoDB and return as DataFrame"""
    try:
        cursor = patient_credentials_collection.find({})
        users_data = list(cursor)

        df = pd.DataFrame(users_data)

        if df.empty:
            # Return an empty dataframe with expected columns to keep callers safe
            expected_columns = ["firstname", "email", "phone", "country", "state", "location", "city", "password"]
            logger.info("No users found in patient_credentials_collection")
            return pd.DataFrame(columns=expected_columns)

        if "_id" in df.columns:
            df.drop("_id", axis=1, inplace=True)

        expected_columns = ["firstname", "email", "phone", "country", "state", "location", "city", "password"]
        for col in expected_columns:
            if col not in df.columns:
                df[col] = None

        logger.info(f"Successfully loaded {len(df)} users from MongoDB")
        return df

    except Exception as e:
        logger.exception(f"Error loading users from MongoDB: {str(e)}")
        return pd.DataFrame(columns=["firstname", "email", "phone", "country", "state", "location", "city", "password"])


def authenticate_user(email: str, password: str) -> bool:
    """Return True if email/password match a document in MongoDB."""
    try:
        hashed = hash_password(password)
        user = patient_credentials_collection.find_one({"email": email, "password": hashed})
        logger.info(f"Authentication attempt for {email}: {'success' if user else 'failed'}")
        return user is not None
    except Exception as e:
        logger.exception(f"Authentication error for {email}: {e}")
        return False


def register_user(firstname: str, email: str, phone: str, country: str,
                 state: str, location: str, city: str, password: str) -> Optional[str]:
    """Register a new user in the database"""
    try:
        # Normalize inputs a bit
        email = (email or "").strip().lower()
        phone = (phone or "").strip()

        # Check if email or phone already exists
        if email and patient_credentials_collection.find_one({"email": email}):
            logger.warning(f"Registration failed - email already exists: {email}")
            return "Email already registered."
        if phone and patient_credentials_collection.find_one({"phone": phone}):
            logger.warning(f"Registration failed - phone already exists: {phone}")
            return "Phone number already registered."

        # Hash the password
        hashed = hash_password(password)

        now = datetime.now()
        # Create the user document
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

        # Insert into MongoDB
        insert_result = patient_credentials_collection.insert_one(user_document)
        logger.info(f"New user registered: {email} (id={insert_result.inserted_id})")
        return None  # Success
    except Exception as e:
        logger.exception(f"Registration error for {email}: {e}")
        return "Registration failed. Please try again."


def get_user_contact_info(email: str) -> List[Dict[str, str]]:
    """Get user contact information by email"""
    try:
        df = load_users_df()
        ele_user_id = df[df['email'] == email]
        contact_info = ele_user_id[["firstname", "email", "phone"]]
        logger.info(f"Retrieved contact info for user: {email}")
        return contact_info.to_dict(orient="records")
    except Exception as e:
        logger.exception(f"Error getting contact info for {email}: {e}")
        return []


def push_patient_information_data_to_db(patient_data: dict):
    """Insert patient information into database"""
    try:
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M:%S")

        patient_data['date'] = str(current_date)
        patient_data['time'] = str(current_time)

        insert_result = patient_information_details_table_collection.insert_one(patient_data)
        logger.info(f"Inserted Patient Information Data ID: {insert_result.inserted_id}")
        return insert_result
    except Exception as e:
        logger.exception(f"Error inserting patient information: {e}")
        return None


def push_patient_chat_data_to_db(patient_data: dict):
    """Insert patient chat data into database"""
    try:
        now = datetime.now()
        current_date = now.strftime("%Y-%m-%d")
        current_time = now.strftime("%H:%M:%S")

        patient_data['date'] = str(current_date)
        patient_data['time'] = str(current_time)

        insert_result = patient_chat_table_collection.insert_one(patient_data)
        logger.info(f"Inserted Patient Chat Data ID: {insert_result.inserted_id}")
        return insert_result
    except Exception as e:
        logger.exception(f"Error inserting patient chat data: {e}")
        return None


def push_patient_each_chat_message(message_text: str):
    """Insert individual chat message into database (alias)

    This forwards to patient_each_chat_table_collection to keep backwards compatibility.
    """
    return patient_each_chat_table_collection(message_text)


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
        logger.exception(f"Error inserting chat message: {e}")
        return None
