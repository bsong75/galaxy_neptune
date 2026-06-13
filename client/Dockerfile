FROM node:20-alpine AS build 
# on Debian Linux 350MB / Alpine Linux 130MB
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci 
# Clean install
COPY . .
RUN npm run build

FROM nginx:alpine
# on nginx:latest is 60MB / alpine is 7MB
COPY --from=build /app/dist /usr/share/nginx/html
# from the above image, build, 
# grab static files and placing it where nginx needs to find web content
# entire node.js build stage gets thrown away.
# only the compiled files in dist/ survives into the final image
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
