from fastapi import APIRouter, Request, Depends
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from datetime import datetime
import logging

from agent import get_or_create_agent_for_user, remove_agent
from db_utils import (patient_each_chat_table_collection,push_patient_information_data_to_db,push_patient_chat_data_to_db)
from session import update_session_record
from patient_bot_conversational import *
from prompt import doctor_appointment_patient_data_extraction_prompt

router = APIRouter()
templates = Jinja2Templates(directory="templates")
logger = logging.getLogger(__name__)

class ChatRequest(BaseModel):
    user_input: str

@router.get("/chat/{session_id}")
async def chat_page(request: Request, session_id: str):
    if (not request.session.get("user") or 
        not request.session.get("session_id") or 
        request.session.get("session_id") != session_id):
        
        update_session_record(session_id, "unauthorized_access_attempt")
        logger.warning(f"Unauthorized access attempt for session_id={session_id}")
        return RedirectResponse(url="/login", status_code=303)
    
    # Log successful access
    update_session_record(session_id, "chat_page_accessed")
    logger.info(f"Chat page accessed: session_id={session_id}, user={request.session.get('user')}")

    email = request.session.get("user")
    user_details = get_or_create_agent_for_user(email, session_id)
    logger.debug(f"user_details: {user_details}")

    initial_message = f"Hello, User Details are: {user_details['configurable']['patient_data']}"
    last_message = part_1_graph.invoke(
        {"messages": ("user", initial_message)},
        config=user_details
    )

    last_message = last_message['messages'][-1].content
    logger.info(f"Last message generated for session_id={session_id}: {last_message}")

    # Save chat into DB
    patient_each_chat_table_collection(last_message)
    logger.debug("Saved last_message into patient_each_chat_table_collection")

    return templates.TemplateResponse("index.html", {
        "request": request,
        "greeting": last_message,
        "session_id": session_id
    })

@router.post("/chat/{session_id}")
async def chat(request: Request, session_id: str, chat_request: ChatRequest):
    if (not request.session.get("user") or 
        not request.session.get("session_id") or 
        request.session.get("session_id") != session_id):
        
        logger.warning(f"Unauthorized chat attempt | session_id={session_id}")
        update_session_record(session_id, "unauthorized_chat_attempt")
        return JSONResponse(content={"response": "Invalid session. Please log in again."})
    
    user_email = request.session.get("user")
    user_input = chat_request.user_input.strip()

    patient_each_chat_table_collection(user_input)
    
    now = datetime.now()
    # Log the chat message
    logger.info(f"[{session_id}] User ({user_email}) input: {user_input}")
    update_session_record(session_id, "user_message", {
        'message': user_input,
        'timestamp': str(now)
    })
    
    user_details = get_or_create_agent_for_user(user_email, session_id)
    
    try:
        last_message = part_1_graph.invoke(
            {"messages": ("user", user_input)},
            config=user_details
        )
        final_response = last_message['messages'][-1].content
    except Exception as e:
        logger.error(f"Error invoking graph for {session_id} | {e}")
        return JSONResponse(content={"response": "Sorry, something went wrong while processing your request."})
    
    patient_each_chat_table_collection(final_response)

    now = datetime.now()
    # Log bot response
    logger.info(f"[{session_id}] Bot response: {final_response}")
    update_session_record(session_id, "bot_response", {
        'response': final_response,
        'timestamp': str(now)
    })

    # Appointment booking trigger check
    if any(phrase in final_response for phrase in [
        'We are booking an appointment','receive a confirmation shortly.','confirmation shortly',
        'processing your doctor appointment request',
        'will receive a confirmation',
        'processing your request','will proceed to finalize the booking',
        'I will confirm the details as soon as possible',
        'wait for a moment while I process your request','Please hold on for a moment','while I process this request']):
        
        try:
            patient_data = doctor_appointment_patient_data_extraction_prompt(llm).invoke(str(last_message['messages']))
            logger.debug(f"[{session_id}] Extracted patient_data: {patient_data}")
            patient_data['appointment_status'] = 'Pending'
            
            push_patient_information_data_to_db(patient_data)
            chat_df = {'patient_name': patient_data['username'], 'chat_history': str(last_message['messages'])}
            push_patient_chat_data_to_db(chat_df)

            update_session_record(session_id, "appointment_booked", {
                'patient_name': patient_data['username'],
                'timestamp': str(now)
            })
            
            logger.info(f"[{session_id}] Appointment booking initiated for patient={patient_data['username']}")
        except Exception as e:
            logger.error(f"Error while booking appointment for {session_id} | {e}")
            return JSONResponse(content={"response": "We faced an issue while processing your appointment. Please try again."})

        return JSONResponse(content={"response": "Thank you! We are currently processing your doctor appointment request. The scheduling is in progress. You will receive a confirmation shortly."})
    
    return JSONResponse(content={"response": final_response})


@router.get("/check-session")
async def check_session(request: Request):
    session_id = request.session.get("session_id")
    valid = (request.session.get("user") is not None and 
             session_id is not None)
    
    # Log session check
    if session_id:
        logger.info(f"Session check performed | session_id={session_id} | valid={valid}")
    else:
        logger.warning("Session check attempted without session_id")

    return JSONResponse({"valid": valid})