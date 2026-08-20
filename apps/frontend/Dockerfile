FROM node:22-alpine

WORKDIR /app

# Copy package files
COPY package.json ./

# We use npm inside Docker to avoid pnpm hard-link issues across Docker volumes
RUN npm install

# Copy application code
COPY . .

# Start development server
CMD ["npm", "run", "dev"]
