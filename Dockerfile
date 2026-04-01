FROM python:3.11-slim

# Install system dependencies needed to compile TA-Lib
RUN apt-get update && apt-get install -y \
    build-essential \
    wget \
    && rm -rf /var/lib/apt/lists/*

# Download and compile TA-Lib from source
RUN cd /tmp && \
    wget https://prdownloads.sourceforge.net/ta-lib/ta-lib-0.4.0-src.tar.gz && \
    tar -xzf ta-lib-0.4.0-src.tar.gz && \
    cd ta-lib-0.4.0 && \
    ./configure --prefix=/usr && \
    make && \
    make install && \
    ldconfig

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose the port Render expects
EXPOSE 10000

# Start the app with gunicorn
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "main:app"]
