# Stage 1: Build dependencies
FROM python:3.11-slim

# Set the working directory
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY server_w_time_emotion_detector_V4_with_simplified.py /app
COPY requirements.txt /app

# Installiere systemweite Abhängigkeiten 
RUN apt-get update && apt-get install -y \ 
	libgl1-mesa-glx \ 
	libglib2.0-0 \
  	wget \
  	&& rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y moviepy \
    && pip install --no-cache-dir moviepy==1.0.3

# Make port 51821 available to the world outside this container
EXPOSE 51820

# Define environment variable
ENV key=value

# Run app.py when the container launches
CMD ["python", "server_w_time_emotion_detector_V4_with_simplified.py"]
