# ci-test
Spring Boot Web Application with CI/CD Pipeline and Helm Deployment

## Overview
This is a Spring Boot web application with a basic ping endpoint, complete CI/CD pipeline using GitHub Actions, and Helm chart for Kubernetes deployment.

## Features
- ✅ Spring Boot 3.1.5 with Java 17
- ✅ RESTful API with ping endpoint
- ✅ Health check endpoint via Spring Actuator
- ✅ Docker containerization
- ✅ GitHub Actions CI/CD pipeline
- ✅ Automated testing
- ✅ Helm chart for Kubernetes deployment
- ✅ Automatic Helm chart updates with latest Docker images

## API Endpoints

### Ping Endpoint
```
GET /ping
```
Response:
```json
{
  "status": "ok",
  "message": "pong",
  "timestamp": "2025-09-10T10:30:00.123456"
}
```

### Health Check
```
GET /health
```
Response:
```json
{
  "status": "UP"
}
```

### Actuator Health
```
GET /actuator/health
```

## Quick Start

### Prerequisites
- Java 17+
- Maven 3.6+
- Docker (optional)
- Kubernetes cluster (for Helm deployment)
- Helm 3.x (for Helm deployment)

### Local Development
1. Clone the repository:
   ```bash
   git clone <repository-url>
   cd ci-test
   ```

2. Run the application:
   ```bash
   mvn spring-boot:run
   ```

3. Test the endpoints:
   ```bash
   curl http://localhost:8080/ping
   curl http://localhost:8080/health
   ```

### Running Tests
```bash
mvn test
```

### Building the Application
```bash
mvn clean package
```

## Docker

### Build Docker Image
```bash
mvn clean package
docker build -t ci-test:latest .
```

### Run Docker Container
```bash
docker run -p 8080:8080 ci-test:latest
```

## GitHub Actions CI/CD

The project includes two GitHub Actions workflows:

### 1. CI/CD Pipeline (`.github/workflows/ci.yml`)
- Triggers on push to `main` and `develop` branches and PRs to `main`
- Runs tests with Maven
- Builds and pushes Docker images to GitHub Container Registry
- Tags images with branch name, commit SHA, and `latest` for main branch

### 2. Helm Chart Update (`.github/workflows/update-helm.yml`)
- Triggers after successful CI/CD pipeline completion
- Automatically updates Helm chart with the latest Docker image tag
- Commits changes back to the repository

### Setup GitHub Actions
1. **Enable GitHub Container Registry**: The workflows use `ghcr.io` to store Docker images
2. **Repository Secrets**: No additional secrets required - uses `GITHUB_TOKEN` automatically
3. **Update Image Repository**: Modify `helm/ci-test/values.yaml` to use your GitHub username/organization:
   ```yaml
   image:
     repository: ghcr.io/YOUR_USERNAME/ci-test
   ```

## Helm Deployment

### Chart Structure
```
helm/ci-test/
├── Chart.yaml          # Chart metadata
├── values.yaml         # Default configuration values
└── templates/
    ├── _helpers.tpl    # Template helpers
    ├── deployment.yaml # Kubernetes Deployment
    ├── service.yaml    # Kubernetes Service
    └── serviceaccount.yaml # Service Account
```

### Deploy to Kubernetes
1. **Install the chart**:
   ```bash
   helm install ci-test helm/ci-test
   ```

2. **Upgrade the chart**:
   ```bash
   helm upgrade ci-test helm/ci-test
   ```

3. **Uninstall the chart**:
   ```bash
   helm uninstall ci-test
   ```

### Custom Configuration
Create a custom `values.yaml` file:
```yaml
image:
  repository: ghcr.io/your-username/ci-test
  tag: "latest"

replicaCount: 3

resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 250m
    memory: 256Mi

ingress:
  enabled: true
  hosts:
    - host: ci-test.example.com
      paths:
        - path: /
          pathType: Prefix
```

Then deploy with:
```bash
helm install ci-test helm/ci-test -f custom-values.yaml
```

## Configuration

### Application Properties
The application can be configured via `src/main/resources/application.properties`:
- `server.port`: Server port (default: 8080)
- `spring.application.name`: Application name
- Management endpoints for health checks

### Helm Values
Key configuration options in `helm/ci-test/values.yaml`:
- `image.repository`: Docker image repository
- `image.tag`: Docker image tag
- `replicaCount`: Number of replicas
- `service.type`: Kubernetes service type
- `ingress.enabled`: Enable ingress controller
- `resources`: CPU and memory limits

## Development Workflow

1. **Make changes** to the application code
2. **Commit and push** to `main` or `develop` branch
3. **GitHub Actions** automatically:
   - Runs tests
   - Builds Docker image
   - Pushes to container registry
   - Updates Helm chart with new image tag
4. **Deploy** updated Helm chart to Kubernetes

## Monitoring

The application includes Spring Boot Actuator for monitoring:
- Health endpoint: `/actuator/health`
- Application info and metrics available
- Kubernetes readiness and liveness probes configured

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

This project is licensed under the MIT License.
