# syntax=docker/dockerfile:1.4
FROM node:20-slim

WORKDIR /app

# Change ownership of /app directory upfront
RUN chown -R node:node /app

# Switch to node user
USER node

ENV YARN_CACHE_FOLDER=/home/node/.cache/yarn

COPY --chown=node:node package.json ./
COPY --chown=node:node yarn.lock ./

RUN yarn install --frozen-lockfile 

COPY --chown=node:node . .

RUN npm run clean

RUN npm run build

ENV NODE_ENV=production

CMD ["npm", "start"]