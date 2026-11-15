FROM node:20-alpine AS build
WORKDIR /app
COPY package.json ./
RUN npm install
COPY . .
ARG VITE_BUYER_URL=http://localhost:8001
ARG VITE_MARKET_URL=http://localhost:8002
ARG VITE_S1_URL=http://localhost:8003
ARG VITE_S2_URL=http://localhost:8004
ARG VITE_S3_URL=http://localhost:8005
ARG VITE_PROBE_URL=http://127.0.0.1:8010
ENV VITE_BUYER_URL=$VITE_BUYER_URL \
    VITE_MARKET_URL=$VITE_MARKET_URL \
    VITE_S1_URL=$VITE_S1_URL \
    VITE_S2_URL=$VITE_S2_URL \
    VITE_S3_URL=$VITE_S3_URL \
    VITE_PROBE_URL=$VITE_PROBE_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
