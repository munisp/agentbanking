FROM node:20-slim

WORKDIR /app

COPY package.json ./
RUN npm install --legacy-peer-deps

COPY . .
RUN npx esbuild server/_core/index.ts --platform=node --packages=external --bundle --format=esm --outdir=dist

ENV NODE_ENV=production

RUN chown -R node /app
USER node

EXPOSE 9531
CMD ["node", "dist/index.js"]
