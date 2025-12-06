# Use python slim image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install dependencies (now includes Pillow)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code
COPY costing_app.py .

# Expose Streamlit port
EXPOSE 8501

# Run the app
CMD ["streamlit", "run", "costing_app.py", "--server.port=8501", "--server.address=0.0.0.0"]