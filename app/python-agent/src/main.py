import os
import pika
import json
import sys
import logging
from langchain import hub
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from models import Job
from tools.git_tool import clone_repo, create_branch, commit, push, create_pull_request
from tools.file_system_tool import read_file, write_file, list_files
from tools.llm_tool import get_instructions
from tools.database_tool import AnalysisUpdater


# --- Configuration ---
RABBITMQ_HOST = os.environ.get("RABBITMQ_HOST", "localhost")
RABBITMQ_QUEUE = os.environ.get("RABBITMQ_QUEUE", "fix_jobs")

# --- Agent Initialization ---
def main():
    """
    Main function to consume jobs from RabbitMQ and process them.
    """
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()
    channel.queue_declare(queue=RABBITMQ_QUEUE, durable=True)

    print(" [*] Waiting for messages. To exit press CTRL+C")

    def callback(ch, method, properties, body):
        """
        Callback function to process a message from the queue.
        """
        print(f" [x] Received {body}")
        try:
            job_data = json.loads(body)
            job = Job(**job_data)
            process_job(job)
            ch.basic_ack(delivery_tag=method.delivery_tag)
            print(f" [x] Done processing job {job.id}")
        except Exception as e:
            logging.error(f" [!] Error processing job", exc_info=True)
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)
    channel.start_consuming()

def process_job(job: Job):
    """
    Processes a single job.
    """
    analysis_updater = AnalysisUpdater(job.log_id)
    analysis_updater.update_analysis_processing()

    tools = [clone_repo, create_branch, commit, push, create_pull_request, read_file, write_file, list_files, get_instructions]
    
    logger = logging.getLogger(__name__)
    print("api key:", os.environ.get("GEMINI_API_KEY"))
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", logger=logger, google_api_key=os.environ.get("GEMINI_API_KEY"))
    
    prompt_template = """
    You are a helpful assistant that fixes errors in code.
    You have access to the following tools:
    {tools}
    Use the following format:
    Question: the input question you must answer
    Thought: you should always think about what to do
    Action: the action to take, should be one of [{tool_names}]
    Action Input: the input to the action
    Observation: the result of the action
    ... (this Thought/Action/Action Input/Observation can repeat N times)
    Thought: I now know the final answer
    Final Answer: the final answer to the original input question
    Begin!
    Question: {input}
    Thought:{agent_scratchpad}
    """
    prompt = ChatPromptTemplate.from_template(prompt_template)
    
    agent = create_react_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.info(f"Processing job {job.id} for app {job.app_name}")

    try:
        result = agent_executor.invoke({
            "input": f"Fix the error in the {job.app_name} application. Here is the error log: {job.error_log}."
        })
        logging.info(f"Agent execution result: {result}")
        
        pull_request_url = result.get("output")

        analysis_updater.set_pull_request_url(pull_request_url)
        analysis_updater.update_analysis_completed()

    except Exception as e:
        logging.error(f"Error during agent execution: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

