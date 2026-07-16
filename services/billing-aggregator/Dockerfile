FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json* ./

RUN npm ci

COPY . .

RUN npm run clean

RUN npm run build

ENV NODE_ENV=production

RUN chown -R node /app

CMD ["npm", "start"]
