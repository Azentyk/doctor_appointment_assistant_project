
from dotenv import load_dotenv
import os
load_dotenv()
# Import Azure OpenAI
from langchain_openai import AzureChatOpenAI


llm_deployment_name = os.environ['llm_deployment_name']
llm_api_version =os.environ['llm_api_version']
llm_azure_endpoint = os.environ['llm_azure_endpoint']
llm_api_key = os.environ['llm_api_key']
llm_model =  os.environ['llm_model']
llm_model_version = os.environ['llm_model_version']

def llm_model():
    llm = AzureChatOpenAI(deployment_name = llm_deployment_name,temperature=0.1,api_version=llm_api_version,azure_endpoint=llm_azure_endpoint,api_key=llm_api_key)
    return llm