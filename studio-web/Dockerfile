FROM node:22-alpine AS build
WORKDIR /web
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.sh /studio-entrypoint.sh
COPY --from=build /web/dist /usr/share/nginx/html
RUN chmod +x /studio-entrypoint.sh
EXPOSE 80
ENTRYPOINT ["/studio-entrypoint.sh"]
