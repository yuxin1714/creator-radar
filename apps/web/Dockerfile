# Local scaffold only. Generate and commit a lockfile before reproducible deployment.
FROM node:22-alpine
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build
EXPOSE 3000
CMD ["npm", "run", "start"]
