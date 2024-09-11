import os
import json
from typing import Dict, List, Optional

import requests
from loguru import logger
from pydantic import BaseModel, Field
from swarms import OpenAIChat
from swarms import Agent
from dotenv import load_dotenv

load_dotenv()

# Ensure loguru logs are saved to a file
logger.add("medinsight_pro_logs.log", rotation="500 MB")
openai_api_key = os.getenv("OPENAI_API_KEY")
semantic_scholar_api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
pubmed_api_key = os.getenv("PUBMED_API_KEY")


# Define the Pydantic schema for logging metadata
class MedInsightMetadata(BaseModel):
    query: str = Field(
        ..., description="The task or query sent to the agent"
    )
    pubmed_results: Optional[Dict] = Field(
        None, description="Results fetched from PubMed"
    )
    semantic_scholar_results: Optional[Dict] = Field(
        None, description="Results fetched from Semantic Scholar"
    )
    combined_summary: Optional[str] = Field(
        None, description="Final summarized output from the agent"
    )
    status: str = Field(
        ...,
        description="Status of the agent task, e.g., success or failure",
    )


# Create an instance of the OpenAIChat class with GPT-4
model = OpenAIChat(
    openai_api_key=openai_api_key,
    model_name="gpt-4o-mini",
    temperature=0.1,  # Maintain a lower temperature for more focused summarization
    max_tokens=1000,
)

# Define the system prompt
med_sys_prompt = """
You are a highly knowledgeable Medical Research Summarization Agent. 
Your task is to read large volumes of medical research papers and generate concise summaries. 
Highlight potential treatments, ongoing clinical trials, medical breakthroughs, and important medical insights.
You will focus on clarity, relevance, and precision, ensuring the summaries are actionable for doctors and researchers.
"""


# Initialize the Medical Summarization Agent
agent = Agent(
    agent_name="Medical-Summarization-Agent",  # Custom agent name
    system_prompt=med_sys_prompt,
    llm=model,
    max_loops=1,  # Adjust loop count based on summarization needs
    autosave=True,
    dashboard=False,
    verbose=True,
    dynamic_temperature_enabled=False,  # Disable temperature changes for consistency
    saved_state_path="medical_summarization_agent.json",  # Path to save agent state
    user_name="medical_researcher",  # Can be adjusted per user
    retry_attempts=2,
    context_length=100000,  # Adjust based on summarization needs
    return_step_meta=False,
)


# Define the MedInsightPro class with customizable options and logging
class MedInsightPro:
    def __init__(
        self,
        pubmed_api_key: str = pubmed_api_key,
        semantic_scholar_api_key: str = None,
        system_prompt: str = med_sys_prompt,
        agent: Agent = agent,
    ):
        self.pubmed_api_key = pubmed_api_key
        self.semantic_scholar_api_key = semantic_scholar_api_key
        self.system_prompt = system_prompt
        self.agent = agent

        # Initialize the metadata history log
        self.metadata_log: List[MedInsightMetadata] = []

    # Function to access PubMed data
    def fetch_pubmed_data(self, query, max_results=10):
        logger.info(f"Fetching data from PubMed for query: {query}")
        url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": max_results,
            "api_key": self.pubmed_api_key,
            "retmode": "json",
        }
        response = requests.get(url, params=params)
        data = response.json()
        ids = data.get("esearchresult", {}).get("idlist", [])

        if ids:
            id_str = ",".join(ids)
            fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            fetch_params = {
                "db": "pubmed",
                "id": id_str,
                "retmode": "json",
            }
            fetch_response = requests.get(
                fetch_url, params=fetch_params
            )
            return fetch_response.json()
        return {}

    # Function to access Semantic Scholar data
    def fetch_semantic_scholar_data(self, query, max_results=10):
        logger.info(
            f"Fetching data from Semantic Scholar for query: {query}"
        )
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        headers = {"x-api-key": self.semantic_scholar_api_key}
        params = {"query": query, "limit": max_results}
        response = requests.get(url, headers=headers, params=params)
        return response.json()

    # Method to run the agent with a given task
    def run(self, task: str):
        logger.info(f"Running MedInsightPro agent for task: {task}")
        status = "success"
        pubmed_data, semantic_scholar_data = {}, {}
        combined_summary = ""

        try:
            # Fetch data from PubMed
            if self.pubmed_api_key:
                pubmed_data = self.fetch_pubmed_data(task)
                logger.info(f"PubMed data: {pubmed_data}")

            # Fetch data from Semantic Scholar
            if self.semantic_scholar_api_key:
                semantic_scholar_data = (
                    self.fetch_semantic_scholar_data(task)
                )

            # Summarize data with GPT-4
            combined_summary_input = f"PubMed Data: {pubmed_data}\nSemantic Scholar Data: {semantic_scholar_data}"
            combined_summary = self.agent.run(combined_summary_input)
            logger.info(f"Summarization completed for task: {task}")
        except Exception as e:
            logger.error(
                f"Error during processing task: {task}. Error: {e}"
            )
            status = "failure"

        # Log metadata
        metadata = MedInsightMetadata(
            query=task,
            pubmed_results=pubmed_data,
            semantic_scholar_results=semantic_scholar_data,
            combined_summary=combined_summary,
            status=status,
        )
        self.metadata_log.append(metadata)

        # Save log to a JSON file
        self.save_metadata_log()

        return combined_summary

    # Method to save the metadata log to a JSON file
    def save_metadata_log(self):
        log_file = "medinsight_pro_history.json"
        with open(log_file, "w") as f:
            json.dump(
                [metadata.dict() for metadata in self.metadata_log],
                f,
                indent=4,
            )
        logger.info(f"Metadata log saved to {log_file}")
