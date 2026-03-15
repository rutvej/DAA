# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Install uv
RUN pip install uv

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN uv pip install --system --no-cache-dir -r requirements.txt

# Copy the application code into the container as a package
COPY ./src ./src
COPY ./tests ./tests

# Make port 80 available to the world outside this container
EXPOSE 80

# Define environment variable
ENV PYTHONPATH "${PYTHONPATH}:/app"
ENV NAME World

# Run uvicorn when the container launches
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "80"]
