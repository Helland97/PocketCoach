# Stage 1: Build React application
FROM node:20.18-alpine AS builder

WORKDIR /app

# Copy package files
COPY package.json package-lock.json* ./

# Install dependencies
# Use npm install instead of npm ci to handle missing lock file
RUN npm install --production=false

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Stage 2: Serve with nginx
# Pinned to current stable mainline (1.27.x on Alpine) for reproducibility.
FROM nginx:1.27-alpine

# Copy built files from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Copy nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80
EXPOSE 80

# NOTE: The stock nginx:alpine image must launch as root in order to bind to
# port 80 and write to /var/cache/nginx, /var/run, etc. Running this image
# under a non-root USER requires switching to nginxinc/nginx-unprivileged
# (port 8080) or remapping ports — see SECURITY-AUDIT.local.md "Not yet
# addressed". For now nginx drops to its built-in `nginx` worker user
# automatically after binding the port.

# Start nginx
CMD ["nginx", "-g", "daemon off;"]