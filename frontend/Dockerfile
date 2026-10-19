# syntax=docker/dockerfile:1.7
# Stages: base -> dev (compose) | build -> prod (static files behind nginx)

FROM node:22-alpine AS base
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM base AS dev
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

FROM base AS build
# Vite bakes VITE_* values into the bundle at build time:
# build one image per environment, or load a runtime config.js instead.
ARG VITE_API_BASE_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
COPY . .
RUN npm run build

FROM nginx:alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
RUN printf 'server {\n  listen 80;\n  root /usr/share/nginx/html;\n  location / { try_files $uri /index.html; }\n}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 80
