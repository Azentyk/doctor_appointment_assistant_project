from langchain_chroma import Chroma
from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import LLMChainExtractor
from langchain.retrievers import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from model import llm_model
import os

from langchain.retrievers.document_compressors import LLMChainFilter
from langchain.retrievers.multi_query import MultiQueryRetriever
from langchain.retrievers.document_compressors import LLMChainFilter
from langchain_openai import AzureOpenAIEmbeddings


llm = llm_model()

embedding_deployment_name = os.environ['embedding_deployment_name']
embedding_api_version =os.environ['embedding_api_version']
embedding_azure_endpoint = os.environ['embedding_azure_endpoint']
embedding_api_key = os.environ['embedding_api_key']
embedding_model =  os.environ['embedding_model']
embedding_model_version = os.environ['embedding_model_version']

def retriever_model():

    embeddings = AzureOpenAIEmbeddings(model= "text-embedding-3-small",
        azure_deployment = embedding_deployment_name,api_version=embedding_api_version,azure_endpoint=embedding_azure_endpoint,api_key=embedding_api_key
    )

    db = Chroma(persist_directory=r"./doctor_details_db",embedding_function=embeddings)

    retriever = db.as_retriever(search_kwargs={'k':20})


    # compressor = LLMChainExtractor.from_llm(llm)
    # _filter = LLMChainFilter.from_llm(llm)
    # compression_retriever = ContextualCompressionRetriever(base_compressor=_filter, base_retriever=retriever)


    return retriever