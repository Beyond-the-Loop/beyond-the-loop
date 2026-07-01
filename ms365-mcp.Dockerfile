FROM node:20-alpine

WORKDIR /app

# Pin the ms-365-mcp-server version to a known good release.
ARG MS365_MCP_VERSION=latest
RUN npm install -g @softeria/ms-365-mcp-server@${MS365_MCP_VERSION}

EXPOSE 3000

# The actual args (port, public URL) are supplied by the K8s Deployment.
ENTRYPOINT ["ms-365-mcp-server"]
