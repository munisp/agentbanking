# Use the official Node.js runtime as the base image
FROM node:20 AS build

# Set the working directory in the container
WORKDIR /app

# Copy package.json and package-lock.json to the working directory
COPY package.json ./

# Install dependencies
RUN yarn install

# Copy nginx conf
COPY nginx.conf /app/

# Set build-time variables (before copying full context!)
ARG VITE_VERIFICATION_API_URL
ARG VITE_KYC_FLOW_API_KEY
ENV VITE_VERIFICATION_API_URL=$VITE_VERIFICATION_API_URL
ENV VITE_KYC_FLOW_API_KEY=$VITE_KYC_FLOW_API_KEY

# Copy the entire application code to the container
COPY . .

# Build the React app for production
RUN npm run build

# Use Nginx as the production server
FROM nginx:alpine

# Copy the built React app to Nginx's web server directory
COPY --from=build /app/dist /usr/share/nginx/html

# Copy the custom Nginx configuration
COPY --from=build /app/nginx.conf /etc/nginx/conf.d/default.conf

# Expose port 80 for the Nginx server
EXPOSE 80

# Start Nginx when the container runs
CMD ["nginx", "-g", "daemon off;"]
