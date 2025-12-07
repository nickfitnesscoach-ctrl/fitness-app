# Многоступенчатая сборка для оптимизации размера образа

# Этап 1: Сборка приложения
FROM node:20-alpine AS builder

WORKDIR /app

# Копируем package.json и устанавливаем зависимости
COPY package*.json ./
RUN npm ci

# Копируем исходный код
COPY . .

# Копируем .env.production (игнорируется в .gitignore, но нужен для сборки)
COPY .env.production .

# Debug: проверяем содержимое .env.production и список файлов
RUN ls -la .env* && cat .env.production && echo "==== Checking VITE env ====" && grep VITE .env.production || echo "No VITE vars found"

# Собираем production build (Vite использует .env.production)
# Устанавливаем VITE_WEB_DEBUG_ENABLED явно для гарантии
RUN VITE_WEB_DEBUG_ENABLED=true npm run build

# Этап 2: Production образ с nginx
FROM nginx:alpine

# Копируем собранное React приложение в подпапку /app
COPY --from=builder /app/dist /usr/share/nginx/html/app

# Копируем лендинг (статические HTML страницы)
COPY public/landing /usr/share/nginx/html/landing

# Копируем конфигурацию nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Открываем порт 80
EXPOSE 80

# Запускаем nginx
CMD ["nginx", "-g", "daemon off;"]
