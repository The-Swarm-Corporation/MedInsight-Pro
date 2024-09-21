import json
import os
import time
from typing import Dict, List, Optional, Any

import requests
from dotenv import load_dotenv
from loguru import logger
from pydantic import BaseModel, Field
from swarm_models import OpenAIFunctionCaller
from swarms import Agent, OpenAIChat

from medinsight.pub_med import query_pubmed_with_abstract

load_dotenv()

# Ensure loguru logs are saved to a file
logger.add("medinsight_pro_logs.log", rotation="500 MB")
openai_api_key = os.getenv("OPENAI_API_KEY")
semantic_scholar_api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
time_stamp = time.strftime("%Y-%m-%d_%H-%M-%S")


# Define the Pydantic schema for logging metadata
class MedInsightMetadata(BaseModel):
    task: str = Field(
        ..., description="The task or query sent to the agent"
    )
    query_agent_analysis: Dict[str, Any]
    pubmed_results: Optional[List[Dict]] = Field(
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
    time_stamp: str = Field(
        time_stamp, description="Timestamp of the agent task"
    )


class MedInsightMetadataOutput(BaseModel):
    task: str = Field(..., description=None)
    logs: List[MedInsightMetadata] = Field(None, description=None)
    time_stamp: str = Field(time_stamp, description=None)


class PubMedQuery(BaseModel):
    analysis_of_request: str = Field(
        ...,
        description="Analyze the nature of the request, identifying the specific disease, virus, or condition. Consider the context of the inquiry, including symptoms, demographics, and relevant medical history to provide a comprehensive understanding.",
    )
    pubmed_query: str = Field(
        ...,
        description="Formulate a precise PubMed query based on the analysis of the request. Ensure the query includes the disease or condition name, relevant keywords, and MeSH terms. Incorporate Boolean operators to enhance search accuracy and retrieve the most pertinent research articles, reviews, and clinical trials.",
    )
    max_articles: int = Field(..., description=None)


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
    """
    This class is used to initialize and run the MedInsight Pro agent.
    It allows for customization of various options and provides logging functionality.
    """

    def __init__(
        self,
        semantic_scholar_api_key: str = None,
        system_prompt: str = med_sys_prompt,
        agent: Agent = agent,
        max_articles: int = 10,
        max_loops: int = None,
        return_json: bool = False,
    ):
        """
        Initialize the MedInsight Pro agent with the provided parameters.
        """
        self.semantic_scholar_api_key = semantic_scholar_api_key
        self.system_prompt = system_prompt
        self.agent = agent
        self.max_articles = max_articles
        self.max_loops = max_loops
        self.return_json = return_json

        # Function caller
        self.precise_query_agent = OpenAIFunctionCaller(
            system_prompt="Your task is to meticulously analyze a given disease, virus, condition, or medical data, and craft an extremely precise and accurate PubMed query. This query should be designed to yield the most relevant and up-to-date research articles, reviews, and clinical trials related to the specified topic. Ensure the query incorporates specific keywords to maximize the precision and recall of the search results.",
            base_model=PubMedQuery,
            openai_api_key=openai_api_key,
        )

        # Initialize the metadata history log
        # self.metadata_log: List[MedInsightMetadata] = []
        self.metadata_log = MedInsightMetadataOutput(
            max_loops=max_loops, logs=[], task=""
        )

    # Function to access Semantic Scholar data
    def fetch_semantic_scholar_data(
        self, query: str, max_results: int = 10
    ):
        """
        Fetch data from Semantic Scholar for the provided query.
        """
        logger.info(
            f"Fetching data from Semantic Scholar for query: {query}"
        )
        url = "https://api.semanticscholar.org/graph/v1/paper/search"
        headers = {"x-api-key": self.semantic_scholar_api_key}
        params = {"query": query, "limit": max_results}
        response = requests.get(url, headers=headers, params=params)
        return response.json()

        # Method to run the agent with a given task

    def run(self, task: str, *args, **kwargs):
        logger.info(f"Running MedInsightPro agent for task: {task}")
        combined_summary = ""

        analysis = self.precise_query_agent.run(task)
        logger.info(f"Pubmed query: {analysis}")

        query = analysis["pubmed_query"]

        try:
            # Fetch data from PubMed
            pubmed_data, pubmed_dict = query_pubmed_with_abstract(
                query=query,
                max_articles=self.max_articles,
                *args,
                **kwargs,
            )
            print(pubmed_dict)
            logger.info(f"PubMed data: {pubmed_data}")

            # Fetch data from Semantic Scholar
            if self.semantic_scholar_api_key:
                semantic_scholar_data = (
                    self.fetch_semantic_scholar_data(task)
                )

            # Summarize data with GPT-4
            # combined_summary_input = f"PubMed Data: {pubmed_data}\nSemantic Scholar Data: {semantic_scholar_data}"
            if pubmed_data:
                combined_summary_input = pubmed_data
            else:
                combined_summary_input = semantic_scholar_data

            combined_summary = self.agent.run(combined_summary_input)
            logger.info(f"Summarization completed for task: {task}")
        except Exception as e:
            logger.error(
                f"Error during processing task: {task}. Error: {e}"
            )
            status = "failure"
            raise e

        # Log metadata
        metadata = MedInsightMetadata(
            task=task,
            query_agent_analysis=analysis,
            pubmed_results=pubmed_dict,
            combined_summary=combined_summary,
            status="success",
            time_stamp=time_stamp,
        )
        self.metadata_log.logs.append(metadata)

        # Save log to a JSON file
        self.save_metadata_log()

        # return combined_summary

        if self.return_json:
            return self.metadata_log.model_dump_json()

        else:
            return combined_summary

    # Method to save the metadata log to a JSON file
    def save_metadata_log(self):
        """
        Save the metadata log to a JSON file.
        """
        import time

        time_stamp = time.strftime("%Y-%m-%d_%H-%M-%S")
        log_file = f"medinsight_pro_history_time:{time_stamp}.json"

        with open(log_file, "w") as file:
            json.dump(self.metadata_log.model_dump(), file)

        logger.info(f"Metadata log saved to {log_file}")
