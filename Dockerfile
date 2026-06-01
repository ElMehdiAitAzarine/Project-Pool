FROM python:3.12-slim-bookworm
# Fresh build: 2026-05-17-v1

# Install system dependencies for MySQL and Azure SQL (MSSQL)
RUN apt-get update && apt-get install -y \
    default-libmysqlclient-dev \
    build-essential \
    pkg-config \
    curl \
    gnupg \
    unixodbc-dev \
    libzbar0 \
    && curl -fsSL https://packages.microsoft.com/keys/microsoft.asc | gpg --dearmor -o /usr/share/keyrings/microsoft-prod.gpg \
    && curl -fsSL https://packages.microsoft.com/config/debian/12/prod.list | tee /etc/apt/sources.list.d/mssql-release.list \
    && apt-get update \
    && ACCEPT_EULA=Y apt-get install -y msodbcsql18 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install
COPY requirements.docker.txt .
RUN pip install --no-cache-dir -r requirements.docker.txt

COPY . .

# Ensure uploads directory exists
RUN mkdir -p uploads/user_photos uploads/qrcodes

# Make startup script executable
RUN chmod +x startup.sh

EXPOSE 8000

CMD ["/app/startup.sh"]
