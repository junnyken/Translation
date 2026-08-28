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
# Image nginx chính thức tự chạy mọi script trong /docker-entrypoint.d/ trước khi khởi động
# (bao gồm 20-envsubst-on-templates.sh xử lý /etc/nginx/templates/). Dùng đúng cơ chế đó thay
# vì tự đặt ENTRYPOINT — nền tảng hosting có bước "Dockerfile Patching" dễ xung đột.
COPY default.conf.template /etc/nginx/templates/default.conf.template
COPY docker-entrypoint.sh /docker-entrypoint.d/40-sinh-config.sh
RUN chmod +x /docker-entrypoint.d/40-sinh-config.sh

# Mặc định 8000; nền tảng đặt PORT khác thì nginx đi theo (xem default.conf.template).
ENV PORT=8000
EXPOSE 8000
