# ---------- dev: vite dev server, hot-reload (docker-compose dùng stage này) ----------
FROM node:22-alpine AS dev
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev"]

# ---------- build: dựng file tĩnh ----------
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund
COPY . .
# Địa chỉ API phải nhúng vào lúc BUILD (Vite thay biến lúc dựng, không đọc được lúc chạy).
# Rỗng = gọi đường dẫn tương đối, chỉ đúng khi có proxy đứng trước.
ARG VITE_API_BASE=""
ENV VITE_API_BASE=$VITE_API_BASE
RUN npm run build

# ---------- prod: nginx phục vụ file tĩnh. Stage CUỐI, hosting sẽ build stage này ----------
FROM nginx:1.27-alpine AS prod
COPY --from=build /app/dist /usr/share/nginx/html
# SPA: mọi đường dẫn không phải file đều trả index.html, nếu không thì F5 sẽ ra 404.
RUN printf 'server {\n\
  listen 80;\n\
  root /usr/share/nginx/html;\n\
  location / { try_files $uri $uri/ /index.html; }\n\
}\n' > /etc/nginx/conf.d/default.conf
EXPOSE 80
