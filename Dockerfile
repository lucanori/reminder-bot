# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Install supervisor and gosu (for su-exec)
RUN apt-get update && apt-get install -y --no-install-recommends supervisor gosu procps && rm -rf /var/lib/apt/lists/*

# Set default UID, GID, UMASK
ENV UID=1000
ENV GID=1000
ENV UMASK=0022

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Ensure correct ownership and permissions for the app directory
RUN chown -R ${UID}:${GID} /app && chmod -R u+rwX,go+rX /app && chmod +x /app/*.py

# Copy supervisor configuration
COPY supervisord.conf /etc/supervisor/conf.d/supervisord.conf

# Copy the entrypoint script and make it executable
COPY entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

# Expose the admin app port
EXPOSE 5011

# Set the entrypoint
ENTRYPOINT ["entrypoint.sh"]

# Default command to run the application
# Default command to run supervisor, which will start the bot and admin app
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]