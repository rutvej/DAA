# Use an official Python runtime as a parent image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application's code into the container
COPY ./src .

# Make port 80 available to the world outside this container
EXPOSE 80

# Define environment variable
ENV PYTHONPATH "${PYTHONPATH}:/app"
ENV NAME World

# Run uvicorn when the container launches
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "80"]