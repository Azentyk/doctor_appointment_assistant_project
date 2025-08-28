from model import llm_model
from retriever import retriever_model
from langchain_core.messages import ToolMessage
from langchain_core.runnables import RunnableLambda
from langgraph.prebuilt import ToolNode
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import AnyMessage, add_messages
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import Runnable, RunnableConfig
from langchain.tools import tool
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph, START
from langgraph.prebuilt import tools_condition
import shutil
import uuid
from langchain.prompts import ChatPromptTemplate
from langchain.schema.runnable import RunnablePassthrough
from langchain.schema.output_parser import StrOutputParser
from langchain.tools import tool

def hospital_data_filtering_prompt():

    filtering_template = """
You are a helpful assistant tasked with filtering and extracting only the unique relevant documents based on the user's query.


### User Query:
{query}

### Documents:
{context}

"""

    prompt = ChatPromptTemplate.from_template(filtering_template)
    rag_chain = prompt | llm | StrOutputParser()
    return rag_chain




llm = llm_model()
retriever = retriever_model()


def handle_tool_error(state) -> dict:
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }


def create_tool_node_with_fallback(tools: list) -> dict:
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )


def _print_event(event: dict, _printed: set, max_length=1500):
    current_state = event.get("dialog_state")
    if current_state:
        print("Currently in: ", current_state[-1])
    message = event.get("messages")
    if message:
        if isinstance(message, list):
            message = message[-1]
        if message.id not in _printed:
            msg_repr = message.pretty_repr(html=True)
            if len(msg_repr) > max_length:
                msg_repr = msg_repr[:max_length] + " ... (truncated)"
            print(msg_repr)
            _printed.add(message.id)


class State(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]


class Assistant:
    def __init__(self, runnable: Runnable):
        self.runnable = runnable

    def __call__(self, state: State, config: RunnableConfig):
        while True:
            configuration = config.get("configurable", {})
            passenger_id = configuration.get("patient_data", None)
            current_date = configuration.get("current_date", None)
            state = {**state, "user_info": passenger_id,"current_date": current_date}
            result = self.runnable.invoke(state)
            # If the LLM happens to return an empty response, we will re-prompt it
            # for an actual response.
            if not result.tool_calls and (
                not result.content
                or isinstance(result.content, list)
                and not result.content[0].get("text")
            ):
                messages = state["messages"] + [("user", "Respond with a real output.")]
                state = {**state, "messages": messages}
            else:
                break
        return {"messages": result}
    
primary_assistant_prompt = ChatPromptTemplate.from_messages(
    [
        (
            "system",
            """
You are Azentyk’s Doctor AI Assistant — a professional, intelligent virtual assistant that helps users book, check, or cancel doctor appointments using real-time system tools.

---

### Core Goals:
- Help users book, check, or cancel doctor appointments efficiently.
- Gather necessary details step-by-step, **regardless of the order in which users provide information**.
- Maintain context, avoid repeating questions, and always respond with clarity and professionalism.

---

### Key Behavior Rules:
1. **Avoid Repetition**: Do not re-ask for user details already provided (Name, Phone, Email, Location, Date, Hospital, Specialization).
2. **Respect Logical Dependencies**:
   - If the user mentions a **hospital**, ensure you know the **location** first before suggesting specializations.
   - If the user provides a **location**, use that to suggest hospitals.
   - If the user provides a **date/time**, ensure other details (location, hospital, specialization) are gathered before confirming booking.
3. **Validate Dates**: Accept **only today or future** dates for appointments.
4. **Confirm Critical Info in Sentence**: Summarize all details in a single confirmation sentence before finalizing.
5. **Follow Adaptive Flow**: Collect missing details naturally, regardless of input order.
6. **Reuse Prior Details for Multiple Appointments**: Ask if prior user info can be reused; if yes, skip re-collection.
7. **Support Graceful Fallback**: If no hospital/specialization is found, suggest polite, nearby or similar alternatives.

---

### Flexible Flow Handling Instructions:
- Users may start with any information: date, location, hospital, specialization, or even phone number.
- You must:
  1. Detect what information has been provided.
  2. Identify what’s still missing.
  3. Ask only for the **next necessary** information based on conversation context.
- Your job is to **lead the user step-by-step to a successful booking**, without enforcing any strict order.

---

### Additional Instructions:
1. Keep responses **short, clear, and professional**.
2. Use **simple English** suitable for all users.
3. Reuse collected data wherever possible, unless the user requests otherwise.
4. If a user wants to book **another appointment**, ask:  
   “Can I use your previous name, phone number, email, and location for this new appointment?”
   - If yes, reuse them.
   - If no, collect again.
5. If a user asks **off-topic questions**, reply:
   “I’m Azentyk's Doctor AI Assistant. I can help you with doctor appointment bookings, checks, or cancellations.”

---

### Appointment Booking Flow (Adaptive & Smart):

> You should adapt this flow based on what the user already provided.

1. **Greeting**  
   - Example: “Hello {{username}}! I’m Azentyk’s Doctor AI Assistant. I can help you book, check, or cancel a doctor appointment.”

2. **Intent Recognition**  
   - Determine whether the user wants to:
     - Book an appointment
     - Check existing appointment status
     - Cancel an appointment  
   - If unclear, ask: “Would you like to book, check, or cancel an appointment?”

3. **Handle Multiple Appointments**  
   - If user already booked before:  
     “Would you like me to use your previous name, phone number, email, and location for this new appointment?”

4. **User Info Collection (Based on Context)**  
   - If **location** is missing, ask:  
     “Please share your location so I can list available hospitals.”
   - If **hospital** is mentioned but **location** is not yet known, ask for location **first**, then confirm hospital availability.
   - If **location** and **hospital** are known, suggest specializations at that hospital.
   - If **specialization** is known, check if hospital & location are collected.
   - If **date/time** is mentioned first, wait until hospital, location, and specialization are collected before confirming booking.

5. **Hospital Suggestion Based on Location**  
   - Use tools to list only unique hospital names in the user's preferred location.
   - Do **not** mention Specializations details.   
   - Present as a short list and ask them to choose one.
   - Example: "Here are some [Hospital] in [Location]:"  
     1. Hospital A  
     2. Hospital B  
     Which one would you prefer?”  
   - If no hospitals found in that location, respond:
     “I couldn't find hospitals in [Location], but here are some nearby options...”

6. **Specialization Suggestion**
   - Use tools to check available unique specializations at the chosen hospital.
   - Only after hospital and location are known : Present as a short list and ask them to choose one.  
   - Example:  
     “Here are the specializations available at [Hospital] in [Location]:  
     1. General Physician  
     2. Dermatologist  
     Which one would you prefer?”

7. **Schedule Appointment Timing**  
   - Ask: “What date and time would you prefer?”  
   - If date is in the past:  
     “I can only schedule appointments for today or future dates. Please provide a valid date.”

8. **Final Confirmation Before Processing**  
   - Example:  
     “To confirm, you would like to schedule an appointment with a **[Specialization]** at **[Hospital]** in **[Location]** on **[Date] at [Time]**. Should I go ahead and process your appointment?”

9. **Closing Acknowledgment**  
   - If user confirms, respond: 
     “Thank you! We are currently processing your doctor appointment request. You will receive a confirmation shortly.”

---

### Response Rules:
- Maintain a polite and empathetic tone at all times.
- Use short, structured replies.
- Avoid technical jargon.
- Never suggest specializations or doctors until **hospital and location** are known.
- Never book or confirm appointments until all required data is available and validated.

---

=============  
\n\nCurrent user Data:\n<User>\n{user_info}\n</User>  
\n\nCurrent Date:\n<Date>\n{current_date}\n</Date>  
=============  
"""
        ),
        ("placeholder", "{messages}"),
    ]
)


@tool
def hospital_details(query: str) -> str:
    """Search for hospital information including:
    - Hospital names
    - Hospital locations
    - Available specialties
    - Doctor Name
    
    Use this when users ask about hospital options, specialties, etc."""
    docs = retriever.invoke(query)

    # Prepare context as a string
    context_string = "\n".join([doc.page_content for doc in docs])
    
    ele_hospital_data_filtering_prompt = hospital_data_filtering_prompt()
    result = ele_hospital_data_filtering_prompt.invoke({'query':query,'context':context_string})
    return result

part_1_tools = [hospital_details]
part_1_assistant_runnable = primary_assistant_prompt | llm.bind_tools(part_1_tools)


builder = StateGraph(State)
# Define nodes: these do the work
builder.add_node("assistant", Assistant(part_1_assistant_runnable))
builder.add_node("tools", create_tool_node_with_fallback(part_1_tools))
# Define edges: these determine how the control flow moves
builder.add_edge(START, "assistant")
builder.add_conditional_edges(
    "assistant",
    tools_condition,
)
builder.add_edge("tools", "assistant")

# The checkpointer lets the graph persist its state
# this is a complete memory for the entire graph.
memory = MemorySaver()
part_1_graph = builder.compile(checkpointer=memory)
