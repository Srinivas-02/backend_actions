FROM python:3.12-slim

# Create a non-root user
RUN useradd -m appuser

# Create and set working directory
WORKDIR /app

# Install system packages including postgresql-client
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    sudo \
    postgresql-client \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the entire project (including server_entrypoint.sh)
COPY . .

# Make the script executable
RUN chmod +x /app/server_entrypoint.sh

# Copy project files
COPY . /app/

# Fix permissions
RUN chown -R appuser:appuser /app
USER appuser

# Expose ports
EXPOSE 8000
EXPOSE 5173

# Run Django server
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
