# Stage 1: Build the React Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app/client
COPY client/package*.json ./
RUN npm ci
COPY client/ ./
RUN npm run build

# Stage 2: Build the FastAPI Backend
FROM python:3.11-slim

# Create user for Hugging Face Spaces (UID 1000)
RUN useradd -m -u 1000 user
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

WORKDIR $HOME/app

# Set environment variables for production
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV DISABLE_RELOAD=true
ENV PORT=7860
ENV HOST=0.0.0.0

# Define data paths to be persisted in production
ENV UPLOADS_PATH=$HOME/app/data/uploads
ENV CHROMA_PATH=$HOME/app/data/chroma_db
ENV DATABASE_PATH=$HOME/app/data/dcpi.db

# Install required system dependencies (if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY server/requirements.txt ./server/
RUN pip install --no-cache-dir -r server/requirements.txt

# Copy server code and set ownership
COPY --chown=user:user server/ ./server/

# Copy built frontend from Stage 1 and set ownership
COPY --chown=user:user --from=frontend-builder /app/client/dist ./client/dist

# Create the data directory and ensure proper permissions
RUN mkdir -p $HOME/app/data && chown -R user:user $HOME/app

# Switch to the non-root user required by Hugging Face Spaces
USER user

# Hugging Face Spaces routes traffic to port 7860
EXPOSE 7860

# Run the FastAPI server
WORKDIR $HOME/app/server
CMD ["python", "main.py"]
