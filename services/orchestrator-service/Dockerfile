FROM node:18-slim

WORKDIR /app

COPY package.json ./

RUN npm i

COPY . .

RUN npm run clean

RUN npm run build

ENV NODE_ENV=production

RUN chown -R node /app

CMD ["npm", "start"]