
# Stage 1: Build stage with full JDK and Maven
FROM maven:3.8.1-openjdk-17-slim AS build

WORKDIR /app
COPY pom.xml .

# Download dependencies (this layer will be cached if pom.xml doesn't change)
RUN mvn dependency:go-offline -B
COPY src ./src
RUN mvn clean package -DskipTests -B

# Stage 2: Runtime stage with minimal JRE
FROM openjdk:17-jdk-slim

WORKDIR /app
COPY --from=build /app/target/ci-test-*.jar app.jar
EXPOSE 8080

# Add health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=30s --retries=3 \
  CMD curl -f http://localhost:8080/actuator/health || exit 1

ENTRYPOINT ["java", "-jar", "app.jar"]
