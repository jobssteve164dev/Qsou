ARG BUILDPLATFORM
FROM --platform=${BUILDPLATFORM} node:20-bookworm-slim AS build

WORKDIR /app
COPY web-frontend/package.json web-frontend/package-lock.json ./
RUN npm ci
COPY web-frontend ./

ARG API_INTERNAL_URL=http://api:8000
ARG NEXT_TELEMETRY_DISABLED=1
ENV API_INTERNAL_URL=${API_INTERNAL_URL} \
    NEXT_TELEMETRY_DISABLED=${NEXT_TELEMETRY_DISABLED}

RUN npm run build

FROM --platform=${BUILDPLATFORM} node:20-bookworm-slim AS runtime-dependencies

WORKDIR /app
COPY web-frontend/package.json web-frontend/package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts --cpu=x64 --os=linux --libc=glibc

FROM node:20-bookworm-slim AS runtime

ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000 \
    API_INTERNAL_URL=http://api:8000
WORKDIR /app
COPY --from=build /app/.next/standalone/server.js ./server.js
COPY --from=build /app/.next/standalone/package.json ./package.json
COPY --from=build /app/.next/standalone/.next ./.next
COPY --from=build /app/.next/standalone/src ./src
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
COPY --from=runtime-dependencies /app/node_modules ./node_modules

EXPOSE 3000
CMD ["node", "server.js"]
