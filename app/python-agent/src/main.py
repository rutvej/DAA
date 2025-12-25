import os
import pika
import json
import sys
from langchain.agents import create_react_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from models import Job
from tools.git_tool import clone_repo, create_branch, commit, push, create_pull_request
from tools.file_system_tool import read_file, write_file, list_files
from tools.llm_tool import get_instructions
from tools.database_tool import update_status, update_pull_request


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
            print(f" [!] Error processing job: {e}")
            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

    channel.basic_qos(prefetch_count=1)
    channel.basic_consume(queue=RABBITMQ_QUEUE, on_message_callback=callback)
    channel.start_consuming()

def process_job(job: Job):
    """
    Processes a single job.
    """
    update_status(job.log_id, "processing")

    # 1. Initialize the agent
    tools = [clone_repo, create_branch, commit, push, create_pull_request, read_file, write_file, list_files, get_instructions, update_status, update_pull_request]
    llm = ChatGoogleGenerativeAi(model="gemini-pro")
    
    # 2. Create the prompt
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", "You are an AI agent that fixes bugs in code. You have access to a set of tools to help you with this task."),
            ("user", "{input}"),
            ("placeholder", "{agent_scratchpad}"),
        ]
    )

    # 3. Create the agent
    agent = create_tool_calling_agent(llm, tools, prompt)
    agent_executor = AgentExecutor(agent=agent, tools=tools, verbose=True)

    # 4. Run the agent
    agent_executor.invoke({
        "input": f"Fix the error in the {job.app_name} application. Here is the error log: {job.error_log}"
    })

    update_status(job.log_id, "completed")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("Interrupted")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)

